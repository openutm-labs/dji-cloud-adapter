"""Built adapter + real broker + real HTTP declaration/telemetry contract receiver."""

import json
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from conftest import CODE
from test_declarations import declarations as declarations
from test_mqtt_integration import broker as broker
from test_mqtt_integration import pilot, wait_for

from dji_cloud_adaptor.cli import private_write, secret_json

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_STACK_INTEGRATION") != "1", reason="Build image and set RUN_STACK_INTEGRATION=1"
)

MOCK = r"""
import json, pathlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from uuid import uuid4
root = pathlib.Path('/fixture')
records = {}
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def reply(self, code, body):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())
    def handle_request(self):
        assert self.headers['Authorization'] == 'Bearer test-blender-token'
        path = self.path.split('?')[0]
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
        if path.endswith('/set_flight_declaration'):
            key = str(uuid4())
            record = {**body, 'id': key, 'state': 1, 'is_approved': True,
                      'flight_declaration_raw_geojson': body['flight_declaration_geo_json']}
            records[key] = record
            with (root/'creates.jsonl').open('a') as f: f.write(json.dumps(record)+'\n')
            # Persisted upstream, response lost: only reconciliation may recover it.
            self.close_connection = True
            return
        if path.endswith('/flight_declaration'):
            return self.reply(200, {'count':len(records), 'results':list(records.values())})
        if '/flight_declaration_state/' in path:
            record = records[path.rsplit('/',1)[1]]
            record['state'] = body['state']
            return self.reply(200, body)
        if '/flight_declaration/' in path:
            return self.reply(200, records[path.rsplit('/',1)[1]])
        if path.endswith('/set_telemetry'):
            assert self.command == 'PUT'
            obs = body['observations'][0]
            record = records[obs['flight_details']['id']]
            assert record['state'] in (2,3,4)
            assert obs['current_states'][0]['position']['alt'] == 123.4
            with (root/'telemetry.jsonl').open('a') as f: f.write(json.dumps(body)+'\n')
            return self.reply(201 if (root/'allow').exists() else 503, {})
        if '/set_air_traffic/' in path:
            return self.reply(201, {})
        self.reply(404, {})
    do_POST = do_GET = do_PUT = handle_request
HTTPServer(('0.0.0.0',8080),Handler).serve_forever()
"""


def test_declarations_with_restart_and_lost_response(declarations, osd, broker):
    root = Path(__file__).parents[1]
    work = root / ".integration-runtime" / ("declaration-" + uuid4().hex)
    work.mkdir(parents=True, mode=0o700)
    (work / "data").mkdir(mode=0o700)
    prefix = "dji-declaration-test-" + uuid4().hex[:10]
    network, app, mock = prefix + "-net", prefix + "-app", prefix + "-mock"
    image = os.environ.get("ADAPTOR_TEST_IMAGE", "dji-cloud-adaptor-app")
    declarations.mqtt.host, declarations.mqtt.port = "mqtt", 1883
    declarations.blender.base_url = "http://blender-mock:8080"
    private_write(work / "config.json", json.dumps(declarations.model_dump(), default=secret_json))
    private_write(work / "mock.py", MOCK)

    def docker(*args):
        return subprocess.run(["docker", *args], check=True, capture_output=True, text=True).stdout.strip()

    sender = None
    try:
        docker("network", "create", network)
        docker("network", "connect", "--alias", "mqtt", network, broker[2])
        docker(
            "run",
            "-d",
            "--name",
            mock,
            "--network",
            network,
            "--network-alias",
            "blender-mock",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-v",
            f"{work}:/fixture",
            "--entrypoint",
            "python",
            image,
            "/fixture/mock.py",
        )
        docker(
            "run",
            "-d",
            "--name",
            app,
            "--network",
            network,
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-p",
            "127.0.0.1::8080",
            "-e",
            "ADAPTOR_CONFIG=/config/config.json",
            "-e",
            "ADAPTOR_DATABASE=/data/queue.sqlite3",
            "-v",
            f"{work}/config.json:/config/config.json:ro",
            "-v",
            f"{work}/data:/data",
            image,
        )
        port = docker("port", app, "8080/tcp").rsplit(":", 1)[1]
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=15) as web:

            def ready():
                try:
                    return web.get("/readyz").status_code == 200
                except httpx.HTTPError:
                    return False

            wait_for(ready, timeout=20)
            token = web.post("/api/pilot/login", json={"code": CODE}).json()["token"]
            web.headers["Authorization"] = f"Bearer {token}"
            assert web.post("/api/pilot/activate", json={"gateway_sn": "EXAMPLE-RC-001"}).status_code == 200
            sender, reason = pilot(declarations, broker[0])
            assert not reason.is_failure

            def publish():
                osd["timestamp"] = int(time.time() * 1000)
                osd["data"]["elevation"] = 0
                sender.publish("thing/product/EXAMPLE-M3E-001/osd", json.dumps(osd), qos=1).wait_for_publish(
                    5
                )

            publish()
            wait_for(lambda: web.get("/api/pilot/status").json()["counts"].get("accepted") == 1)
            start = time.time() + 20
            body = {
                "request_id": str(uuid4()),
                "aircraft_sn": "EXAMPLE-M3E-001",
                "pilot_id": "pilot1",
                "radius_m": 100,
                "height_m": 50,
                "start": datetime.fromtimestamp(start, UTC).isoformat(),
                "duration_minutes": 5,
                "on_ground": True,
            }
            response = web.post("/api/pilot/declarations", json=body)
            assert response.status_code == 200, response.text
            op = response.json()
            path = "/api/pilot/declarations/" + op["id"]
            assert web.post(path, json={"action": "submit"}).json()["stage"] == "uncertain"
            op = web.post(path, json={"action": "refresh"}).json()
            assert op["state"] == "accepted" and op["declaration_id"]
            assert web.post(path, json={"action": "submit"}).status_code == 200
            assert len((work / "creates.jsonl").read_text().splitlines()) == 1
            wait_for(lambda: time.time() >= start, timeout=22)
            assert web.post(path, json={"action": "activate"}).json()["state"] == "activated"
            # Source timestamps have millisecond resolution. Publish the next
            # reporting cycle after activation, rather than within its boundary millisecond.
            next_report = time.time() + 2
            wait_for(lambda: time.time() >= next_report)
            publish()
            sample_timestamp = osd["timestamp"]
            wait_for(lambda: (work / "telemetry.jsonl").exists())
            assert (
                web.get("/api/pilot/declarations").json()["operations"][0]["telemetry_counts"].get("pending")
                == 1
            )
            docker("restart", app)
            port = docker("port", app, "8080/tcp").rsplit(":", 1)[1]
            web.base_url = f"http://127.0.0.1:{port}"
            wait_for(ready, timeout=20)
            private_write(work / "allow", "yes")

            def accepted():
                result = web.get("/api/pilot/declarations").json()["operations"][0]
                return result["telemetry_counts"].get("accepted") == 1

            wait_for(accepted, timeout=20)
            op = web.post(path, json={"action": "finish"}).json()
            assert op["state"] == "ended" and op["telemetry_counts"] == {"accepted": 1}
            requests = [json.loads(line) for line in (work / "telemetry.jsonl").read_text().splitlines()]
            assert len(requests) >= 2 and requests[0] == requests[-1]
            obs = requests[-1]["observations"][0]
            assert obs["flight_details"]["id"] == op["declaration_id"]
            sent_at = datetime.fromisoformat(obs["current_states"][0]["timestamp"]["value"]).timestamp()
            assert round(sent_at * 1000) == sample_timestamp
            assert len((work / "creates.jsonl").read_text().splitlines()) == 1
    except Exception:
        if (work / "data" / "queue.sqlite3").exists():
            import sqlite3

            with sqlite3.connect(work / "data" / "queue.sqlite3") as db:
                print(
                    "Sample state:",
                    db.execute("SELECT observed_at,operation_id,state,error FROM samples").fetchall(),
                )
                print(
                    "Operation state:",
                    db.execute(
                        "SELECT stage,remote_state,checked_at,bind_from,error FROM operations"
                    ).fetchall(),
                )
        for name in (app, mock):
            print(subprocess.run(["docker", "logs", name], capture_output=True, text=True).stderr)
        raise
    finally:
        if sender:
            sender.disconnect()
            sender.loop_stop()
        for name in (app, mock):
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        subprocess.run(["docker", "network", "disconnect", network, broker[2]], capture_output=True)
        subprocess.run(["docker", "network", "rm", network], capture_output=True)
        shutil.rmtree(work)
