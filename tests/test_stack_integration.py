"""Exercise the built application, real MQTT and a real HTTP contract receiver."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from conftest import CODE
from test_mqtt_integration import pilot, wait_for

from dji_cloud_adaptor.cli import private_write, secret_json

pytest_plugins = ["test_mqtt_integration"]

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_STACK_INTEGRATION") != "1", reason="Build image and set RUN_STACK_INTEGRATION=1"
)

MOCK = """import json, pathlib
from http.server import BaseHTTPRequestHandler, HTTPServer
root=pathlib.Path('/fixture')
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        assert self.headers['Authorization']=='Bearer test-blender-token'
        assert self.path=='/flight_stream/set_air_traffic/00000000-0000-0000-0000-000000000002'
        obs=body['observations'][0]
        assert obs['altitude_mm']==123400 and obs['timestamp']>1000000000000
        assert obs['metadata']['altitude_reference']=='WGS84_ellipsoid'
        with (root/'requests.jsonl').open('a') as f: f.write(json.dumps(body)+'\\n')
        self.send_response(201 if (root/'allow').exists() else 503)
        self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(b'{"message":"OK","status":201}')
HTTPServer(('0.0.0.0',8080),Handler).serve_forever()
"""


def test_built_stack_recovers_outbox_after_restart(settings, osd, broker):
    root = Path(__file__).parents[1]
    work = root / ".integration-runtime" / ("stack-" + uuid4().hex)
    work.mkdir(parents=True, mode=0o700)
    data = work / "data"
    data.mkdir(mode=0o700)
    prefix = "dji-stack-test-" + uuid4().hex[:10]
    network, app, mock = prefix + "-net", prefix + "-app", prefix + "-mock"
    image = os.environ.get("ADAPTOR_TEST_IMAGE", "dji-cloud-adaptor-app")
    settings.mqtt.host, settings.mqtt.port = "mqtt", 1883
    settings.blender.base_url = "http://blender-mock:8080"
    private_write(work / "config.json", json.dumps(settings.model_dump(), default=secret_json))
    private_write(work / "mock.py", MOCK)

    def docker(*args):
        return subprocess.run(["docker", *args], check=True, capture_output=True, text=True).stdout.strip()

    sender = None
    last_ready = {}
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
            f"{data}:/data",
            image,
        )
        port = docker("port", app, "8080/tcp").rsplit(":", 1)[1]
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=3) as http:

            def ready():
                try:
                    response = http.get("/readyz")
                    last_ready["status"] = response.json()
                    return response.status_code == 200
                except httpx.HTTPError as exc:
                    last_ready["status"] = type(exc).__name__
                    return False

            wait_for(ready, timeout=20)
            assert http.get("/api/pilot/config").status_code == 401
            assert http.get("/static/portal.js").status_code == 200
            response = http.post("/api/pilot/login", json={"code": CODE})
            headers = {"Authorization": f"Bearer {response.json()['token']}"}
            assert (
                http.post(
                    "/api/pilot/activate", headers=headers, json={"gateway_sn": "EXAMPLE-RC-001"}
                ).status_code
                == 200
            )
            sender, reason = pilot(settings, broker[0])
            assert not reason.is_failure
            osd["timestamp"] = int(time.time() * 1000)
            sender.publish("thing/product/EXAMPLE-M3E-001/osd", json.dumps(osd), qos=1).wait_for_publish(5)

            def pending():
                return (
                    http.get("/api/pilot/status", headers=headers).json().get("last_error")
                    == "blender_http_503"
                )

            wait_for(pending)
            docker("restart", app)
            new_port = docker("port", app, "8080/tcp").rsplit(":", 1)[1]
            http.base_url = f"http://127.0.0.1:{new_port}"
            wait_for(ready, timeout=20)
            private_write(work / "allow", "yes")

            def accepted():
                status = http.get("/api/pilot/status", headers=headers).json()
                return status.get("counts", {}).get("accepted") == 1

            wait_for(accepted, timeout=20)
            requests = [json.loads(line) for line in (work / "requests.jsonl").read_text().splitlines()]
            assert len(requests) >= 2 and requests[0] == requests[-1]
            assert requests[-1]["observations"][0]["timestamp"] == osd["timestamp"]
            assert requests[-1]["observations"][0]["metadata"]["source_event_id"]
    except Exception:
        print("Readiness:", last_ready)
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
