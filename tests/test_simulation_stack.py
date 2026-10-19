"""TLS/WSS -> authenticated broker -> built adaptor -> queryable local receiver.

The receiver proves the harness, not real Flight Blender persistence. CA trust is
explicit and hostname verification stays enabled. No public service is contacted.
"""

import asyncio
import json
import os
import shutil
import sqlite3
import ssl
import subprocess
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from test_mqtt_integration import wait_for

from dji_cloud_adaptor.cli import private_write, render_broker, secret_json
from dji_cloud_adaptor.config import OAuth
from dji_cloud_adaptor.simulator import exercise, prepare

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_STACK_INTEGRATION") != "1", reason="Build image and set RUN_STACK_INTEGRATION=1"
)

# Test-only receiver returns stored POSTs from a separate GET. Never imported by app.
RECEIVER = """import json, pathlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
root = pathlib.Path('/fixture')
rows = []
token_requests = 0
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def authorized(self):
        if self.headers.get('Authorization') != 'Bearer test-blender-token':
            self.send_response(401); self.end_headers(); return False
        return True
    def reply(self, body, status=200):
        self.send_response(status); self.send_header('Content-Type','application/json'); self.end_headers()
        self.wfile.write(json.dumps(body).encode())
    def do_POST(self):
        global token_requests
        if self.path == '/token':
            form = parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode())
            assert form['grant_type'] == ['client_credentials']
            assert form['client_id'] == ['test-sim-client']
            assert form['client_secret'] == ['test-sim-secret']
            assert form['scope'] == ['flightblender.read flightblender.write']
            token_requests += 1
            self.reply({'access_token':'test-blender-token','expires_in':300}); return
        if not self.authorized(): return
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        for row in body['observations']:
            row['session_id'] = self.path.rsplit('/',1)[1]
            rows.append(row)
        self.reply({'message':'OK'}, 201)
    def do_GET(self):
        if not self.authorized(): return
        result = {'token_requests':token_requests}
        if '/get_air_traffic/' in self.path: result = {'observations': rows}
        self.reply(result)
HTTPServer(('0.0.0.0',8080),Handler).serve_forever()
"""


def test_built_stack_through_verified_https_wss(settings):
    root = Path(__file__).parents[1]
    work = root / ".integration-runtime" / ("tls-" + uuid4().hex)
    settings = prepare(settings, work, 255)
    settings.mqtt.host, settings.mqtt.port = "mqtt", 1883
    settings.blender.base_url = "http://blender-mock:8080"
    settings.blender.bearer_token = SecretStr("")
    settings.blender.oauth = OAuth(
        token_url="http://blender-mock:8080/token",
        client_id="test-sim-client",
        client_secret="test-sim-secret",
    )
    settings.public_url = "https://localhost"
    settings.mqtt.public_url = "wss://localhost/mqtt"
    private_write(work / "config.json", json.dumps(settings.model_dump(), default=secret_json))
    render_broker(settings, work / "broker")
    private_write(work / "receiver.py", RECEIVER)
    # Exercise the exact shipped routing configuration with an internal test CA.
    caddy = (
        (root / "deploy/Caddyfile")
        .read_text()
        .replace("{$ADAPTOR_DOMAIN} {", "https://localhost {\n    tls internal")
    )
    private_write(work / "Caddyfile", caddy)
    prefix = "dji-tls-test-" + uuid4().hex[:10]
    network = prefix + "-net"
    app, broker, proxy, mock = [prefix + "-" + k for k in ("app", "broker", "proxy", "mock")]
    image = os.environ.get("ADAPTOR_TEST_IMAGE", "dji-cloud-adaptor-app")

    def docker(*args):
        return subprocess.run(["docker", *args], check=True, capture_output=True, text=True).stdout.strip()

    try:
        docker("network", "create", network)
        docker(
            "run",
            "-d",
            "--name",
            broker,
            "--network",
            network,
            "--network-alias",
            "mqtt",
            "-v",
            f"{work / 'broker'}:/bootstrap/config:ro",
            "-v",
            f"{root / 'deploy/mosquitto-entrypoint.sh'}:/bootstrap/entrypoint.sh:ro",
            "--entrypoint",
            "/bin/sh",
            "eclipse-mosquitto:2.1.2-alpine",
            "/bootstrap/entrypoint.sh",
        )
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
            "-p",
            "127.0.0.1::8080",
            "-v",
            f"{work}:/fixture:ro",
            "--entrypoint",
            "python",
            image,
            "/fixture/receiver.py",
        )
        docker(
            "run",
            "-d",
            "--name",
            app,
            "--network",
            network,
            "--network-alias",
            "app",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--read-only",
            "--tmpfs",
            "/tmp",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "-e",
            "ADAPTOR_CONFIG=/config/config.json",
            "-e",
            "ADAPTOR_DATABASE=/data/queue.sqlite3",
            "-v",
            f"{work / 'config.json'}:/config/config.json:ro",
            "-v",
            f"{work / 'data'}:/data",
            image,
        )
        docker(
            "run",
            "-d",
            "--name",
            proxy,
            "--network",
            network,
            "-p",
            "127.0.0.1::443",
            "-v",
            f"{work / 'Caddyfile'}:/etc/caddy/Caddyfile:ro",
            "caddy:2-alpine",
        )
        ca = work / "root.crt"

        def copy_ca():
            result = subprocess.run(
                ["docker", "cp", f"{proxy}:/data/caddy/pki/authorities/local/root.crt", str(ca)],
                capture_output=True,
            )
            return result.returncode == 0

        wait_for(copy_ca, timeout=20)
        port = docker("port", proxy, "443/tcp").rsplit(":", 1)[1]
        base = f"https://localhost:{port}"
        with pytest.raises(httpx.ConnectError):
            httpx.get(base + "/healthz", timeout=3)
        trust = ssl.create_default_context(cafile=str(ca))
        with httpx.Client(base_url=base, verify=trust, timeout=3) as web:

            def ready():
                try:
                    return web.get("/readyz").status_code == 200
                except httpx.HTTPError:
                    return False

            wait_for(ready, timeout=20)
            assert web.get("/").status_code == 200
            assert web.get("/api/admin/status").status_code == 401
            # From the workstation, use the receiver's loopback mapping for independent readback.
            mock_port = docker("port", mock, "8080/tcp").rsplit(":", 1)[1]
            settings.blender.base_url = f"http://localhost:{mock_port}"
            settings.blender.oauth.token_url = f"http://localhost:{mock_port}/token"
            report = {}
            asyncio.run(exercise(settings, f"wss://localhost:{port}/mqtt", report, str(ca), count=3))
            assert report["downstream_verified"] is True
            assert len(report["observations"]) == 3
            token_stats = httpx.get(
                settings.blender.base_url + "/stats", headers={"Authorization": "Bearer test-blender-token"}
            ).json()
            assert token_stats["token_requests"] >= 2
            report["local_oauth_token_exchange"] = "passed"
            admin = {"Authorization": "Bearer " + settings.admin_token.get_secret_value()}
            status = web.get("/api/admin/status", headers=admin).json()
            assert status["queue"]["counts"] == {"accepted": 3}
            for service in (broker, app):
                docker("restart", service)
                wait_for(ready, timeout=20)
                status = web.get("/api/admin/status", headers=admin).json()
                assert status["queue"]["counts"] == {"accepted": 3}
            report["broker_and_app_restart"] = "passed"
            with sqlite3.connect(work / "data/queue.sqlite3") as db:
                rows = db.execute("SELECT id,payload,state FROM samples").fetchall()
            assert {row[0] for row in rows} == {o["source_event_id"] for o in report["observations"]}
            assert all(row[2] == "accepted" for row in rows)
            assert {json.loads(row[1])["timestamp"] for row in rows} == {
                o["timestamp"] for o in report["observations"]
            }
            report["outbox_event_ids_and_timestamps_match_readback"] = True
            private_write(
                root / ".integration-runtime/last-tls-acceptance.json", json.dumps(report, indent=2)
            )
    finally:
        for name in (proxy, app, mock, broker):
            subprocess.run(["docker", "rm", "-fv", name], capture_output=True)
        subprocess.run(["docker", "network", "rm", network], capture_output=True)
        shutil.rmtree(work)
