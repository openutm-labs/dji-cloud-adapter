"""Bounded, authenticated telemetry acceptance harness; never started by the service.

Original implementation based on DJI's documented envelopes, not third-party code.
No native bridge, licensing, aircraft commands or production authentication bypass.
"""

import argparse
import asyncio
import copy
import hashlib
import json
import os
import secrets
import ssl
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4, uuid5

import httpx
import paho.mqtt.client as mqtt

from .blender import BlenderClient, DeliveryError
from .cli import private_write, render_broker, secret_json
from .config import Settings, load_settings


def require_isolation(source: Settings, traffic_source: int, isolation: dict | None):
    local = urlsplit(source.blender.base_url).hostname in {"localhost", "127.0.0.1", "blender-mock"}
    if not local and not (
        isolation
        and isolation.get("base_url") == source.blender.base_url
        and isolation.get("traffic_source") == traffic_source
        and isolation.get("operational_consumers_exclude") is True
        and isinstance(isolation.get("allocation_reference"), str)
        and isolation["allocation_reference"].strip()
    ):
        raise ValueError("An agreed reserved classification and consumer isolation are required")


def prepare(source: Settings, output: Path, traffic_source: int, isolation: dict | None = None) -> Settings:
    """Create an independent runtime; never modify the source fleet or database."""
    if output.exists():
        raise ValueError("Output already exists")
    require_isolation(source, traffic_source, isolation)
    raw = source.model_dump()
    run = uuid4()
    suffix = run.hex[:12].upper()
    raw.update(
        workspace_id=uuid4(),
        workspace_name="SIMULATION acceptance",
        admin_token=secrets.token_urlsafe(32),
        enrollment={"enabled": False},
        devices=[
            {
                "id": "sim-" + suffix.lower(),
                "name": "SIMULATION controller",
                "gateway_sn": "SIM-RC-" + suffix,
                "connection_code_sha256": secrets.token_hex(32),
                "mqtt_password": secrets.token_urlsafe(32),
                "aircraft": [
                    {
                        "serial": "SIM-M3E-" + suffix,
                        "name": "SIMULATION " + suffix,
                        "model": "Mavic 3 Enterprise (simulated properties)",
                        "session_id": uuid5(run, "traffic"),
                        "simulation": {"run_id": run, "traffic_source": traffic_source},
                    }
                ],
            }
        ],
    )
    raw["mqtt"].update(
        worker_password=secrets.token_urlsafe(32),
        client_id="sim-worker-" + suffix.lower(),
        provisioner_password="",
    )
    settings = Settings.model_validate(raw)
    output.mkdir(parents=True, mode=0o700)
    (output / "data").mkdir(mode=0o700)
    private_write(output / "config.json", json.dumps(settings.model_dump(), default=secret_json, indent=2))
    private_write(
        output / "compose.env",
        f"ADAPTOR_RUNTIME={output.resolve()}\nCOMPOSE_PROJECT_NAME=dji-sim-{suffix.lower()}\n"
        f"ADAPTOR_UID={os.getuid()}\nADAPTOR_GID={os.getgid()}\n"
        f"ADAPTOR_DOMAIN={urlsplit(settings.public_url).hostname}\n",
    )
    if isolation:
        private_write(output / "isolation.json", json.dumps(isolation, indent=2))
    render_broker(settings, output / "broker")
    return settings


def equipment(settings: Settings):
    if len(settings.devices) != 1 or len(settings.devices[0].aircraft) != 1:
        raise ValueError("Use a dedicated, single-aircraft simulation configuration")
    device = settings.devices[0]
    aircraft = device.aircraft[0]
    if not aircraft.simulation:
        raise ValueError("Simulation identity required")
    return device, aircraft


def topology(settings: Settings) -> dict:
    device, aircraft = equipment(settings)
    return {
        "tid": str(uuid4()),
        "bid": str(aircraft.simulation.run_id),
        "timestamp": int(time.time() * 1000),
        "method": "update_topo",
        "gateway": device.gateway_sn,
        # These are contract fixtures, not model/firmware compatibility evidence.
        # Do not invent DJI model codes: identity is checked against the private assignment.
        "data": {"sub_devices": [{"sn": aircraft.serial}]},
    }


def position(settings: Settings, index: int) -> dict:
    device, aircraft = equipment(settings)
    return {
        "tid": str(uuid4()),
        "bid": str(aircraft.simulation.run_id),
        "timestamp": int(time.time() * 1000),
        "gateway": device.gateway_sn,
        "data": {
            "latitude": 1.25 + index * 0.00001,
            "longitude": -139.75 + index * 0.00001,
            # Deliberately distinct ellipsoid height and take-off-relative elevation.
            "height": 123.456 + index,
            "elevation": 23.456 + index,
            "horizontal_speed": 2.5,
            "vertical_speed": 0,
            "mode_code": 0,
        },
    }


class Simulator:
    def __init__(self, settings: Settings, endpoint: str, ca_file: str | None = None):
        self.settings = settings
        self.device, self.aircraft = equipment(settings)
        uri = urlsplit(endpoint)
        local = uri.hostname in {"localhost", "127.0.0.1", "mqtt", "::1"}
        if (
            uri.scheme not in {"mqtt", "ws", "mqtts", "wss"}
            or not uri.hostname
            or uri.username
            or uri.password
            or uri.query
            or uri.fragment
            or (uri.scheme in {"mqtt", "ws"} and not local)
        ):
            raise ValueError("Use encrypted MQTT/WSS; plaintext is loopback/development only")
        self.host = uri.hostname
        self.port = uri.port or {"mqtt": 1883, "mqtts": 8883, "ws": 80, "wss": 443}[uri.scheme]
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="sim-" + uuid4().hex[:16],
            protocol=mqtt.MQTTv5,
            transport="websockets" if uri.scheme in {"ws", "wss"} else "tcp",
        )
        self.client.username_pw_set(self.device.mqtt_username, self.device.mqtt_password.get_secret_value())
        if uri.scheme in {"ws", "wss"}:
            self.client.ws_set_options(path=uri.path or "/mqtt")
        if uri.scheme in {"mqtts", "wss"}:
            self.client.tls_set_context(ssl.create_default_context(cafile=ca_file))
        self.connected = threading.Event()
        self.subscribed = threading.Event()
        self.reply = threading.Event()
        self.failure = False
        self.expected = None
        self.client.on_connect = self.on_connect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish

    def on_connect(self, client, userdata, flags, reason_code, properties):
        self.failure = reason_code.is_failure
        self.connected.set()
        if not self.failure:
            client.subscribe(f"sys/product/{self.device.gateway_sn}/status_reply", qos=1)

    def on_subscribe(self, client, userdata, mid, reason_codes, properties):
        self.failure = self.failure or any(r.is_failure for r in reason_codes)
        self.subscribed.set()

    def on_publish(self, client, userdata, mid, reason_code, properties):
        self.failure = self.failure or reason_code.is_failure

    def on_message(self, client, userdata, message):
        try:
            body = json.loads(message.payload)
            if (
                not message.retain
                and self.expected
                and all(body.get(k) == self.expected[k] for k in ("tid", "bid", "method"))
                and body.get("data") == {"result": 0}
            ):
                self.reply.set()
        except (ValueError, TypeError, AttributeError):
            pass

    def __enter__(self):
        try:
            self.client.connect(self.host, self.port, keepalive=15)
            self.client.loop_start()
            if not self.connected.wait(5) or not self.subscribed.wait(5) or self.failure:
                raise ValueError("Broker authentication/subscription failed")
            self.expected = topology(self.settings)
            self.publish(f"sys/product/{self.device.gateway_sn}/status", self.expected)
            if not self.reply.wait(5):
                raise ValueError("Correlated topology acknowledgement missing")
            return self
        except BaseException:
            self.close()
            raise

    def publish(self, topic: str, body: dict):
        result = self.client.publish(topic, json.dumps(body, allow_nan=False), qos=1, retain=False)
        result.wait_for_publish(5)
        if not result.is_published() or self.failure:
            raise ValueError("Publication was not acknowledged")

    def close(self):
        self.client.disconnect()
        self.client.loop_stop()

    def __exit__(self, *args):
        self.close()


def matches(settings: Settings, packet: dict, observation: dict) -> bool:
    """Readback must correlate actual fields and source identity, not just a 201."""
    _, aircraft = equipment(settings)
    if not isinstance(observation, dict) or not isinstance(observation.get("metadata"), dict):
        return False
    m = observation["metadata"]
    data = packet["data"]
    return (
        observation.get("session_id") == str(aircraft.session_id)
        and observation.get("icao_address") == aircraft.address
        and observation.get("traffic_source") == aircraft.simulation.traffic_source
        and observation.get("source_type") == settings.blender.source_type
        and observation.get("lat_dd") == data["latitude"]
        and observation.get("lon_dd") == data["longitude"]
        and observation.get("altitude_mm") == data["height"] * 1000
        and m.get("source") == "dji_cloud_api_simulation"
        and m.get("simulation") is True
        and m.get("simulation_run_id") == str(aircraft.simulation.run_id)
        and m.get("source_timestamp_ms") == packet["timestamp"]
        and m.get("elevation") == data["elevation"]
        and m.get("rid_compliance_asserted") is False
        and m.get("altitude_reference") == "WGS84_ellipsoid"
        and isinstance(m.get("source_event_id"), str)
        and len(m["source_event_id"]) == 64
    )


async def exercise(
    settings: Settings, endpoint: str, report: dict, ca_file=None, count=3, verify=True, isolation=None
):
    if not 1 <= count <= 3:
        raise ValueError("A run is limited to three samples")
    device, aircraft = equipment(settings)
    require_isolation(settings, aircraft.simulation.traffic_source, isolation)
    report.update(
        run_id=str(aircraft.simulation.run_id),
        session_id=str(aircraft.session_id),
        aircraft_id=aircraft.address,
        simulation=True,
        traffic_source=aircraft.simulation.traffic_source,
        observations=[],
        downstream_verified=False,
        target_kind=(
            "local_contract_receiver"
            if urlsplit(settings.blender.base_url).hostname in {"localhost", "127.0.0.1", "blender-mock"}
            else "configured_hosted_blender"
        ),
        mqtt_transport=urlsplit(endpoint).scheme,
    )
    async with httpx.AsyncClient(timeout=10, follow_redirects=False) as http:
        blender = BlenderClient(settings, http)
        if verify:
            await blender.check_access()
        with Simulator(settings, endpoint, ca_file) as simulator:
            report["topology_acknowledged"] = True
            for i in range(count):
                if i:
                    await asyncio.sleep(2)
                packet = position(settings, i)
                item = {"timestamp": packet["timestamp"], **copy.deepcopy(packet["data"]), "verified": False}
                report["observations"].append(item)
                simulator.publish(f"thing/product/{aircraft.serial}/osd", packet)
                if not verify:
                    continue
                deadline = time.monotonic() + 15
                # This API uses the URL session as a reader cursor, NOT a query filter.
                # A new reader avoids missing a row due to another reader's cursor.
                while time.monotonic() < deadline:
                    reader = uuid4()
                    token = await blender.token()
                    response = await http.get(
                        settings.blender.base_url.rstrip("/") + f"/flight_stream/get_air_traffic/{reader}",
                        params={"view": "1.24,-139.76,1.26,-139.74"},
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if response.status_code != 200:
                        raise DeliveryError(f"readback_http_{response.status_code}")
                    for observation in response.json().get("observations", []):
                        if matches(settings, packet, observation):
                            item.update(
                                verified=True, source_event_id=observation["metadata"]["source_event_id"]
                            )
                            break
                    if item["verified"]:
                        break
                    await asyncio.sleep(1)
                if not item["verified"]:
                    raise ValueError("Downstream observation missing or fields differ")
    report["downstream_verified"] = verify and all(item["verified"] for item in report["observations"])


async def inspect_blender(settings: Settings) -> dict:
    """Read-only deployed-contract evidence; no hostnames, credentials or API bodies."""
    report = {"telemetry_submitted": False, "tls_verification": True}
    async with httpx.AsyncClient(timeout=15, follow_redirects=False) as http:
        response = await http.get(settings.blender.base_url.rstrip("/") + "/openapi.json")
        if response.status_code != 200:
            raise DeliveryError(f"openapi_http_{response.status_code}")
        spec = response.json()
        report["openapi_sha256"] = hashlib.sha256(response.content).hexdigest()
        paths = spec["paths"]
        report["write_route_documented"] = "post" in paths.get(
            "/flight_stream/set_air_traffic/{session_id}", {}
        )
        report["read_route_documented"] = "get" in paths.get(
            "/flight_stream/get_air_traffic/{session_id}", {}
        )
        report["isolation"] = (
            "Requires service-owner allocation and consumer exclusion; not inferred from a UUID"
        )
        blender = BlenderClient(settings, http)
        anonymous = await http.get(
            settings.blender.base_url.rstrip("/") + "/surveillance_monitoring_ops/health/"
        )
        report["anonymous_protected_health_status"] = anonymous.status_code
        if anonymous.status_code not in {401, 403}:
            raise DeliveryError("protected_health_allows_anonymous")
        await blender.check_access()
        report["oauth_and_protected_health"] = "passed"
        token = await blender.token()
        response = await http.get(
            settings.blender.base_url.rstrip("/") + f"/flight_stream/get_air_traffic/{uuid4()}",
            params={"view": "1.24,-139.76,1.26,-139.74"},
            headers={"Authorization": f"Bearer {token}"},
        )
        report["protected_traffic_query_status"] = response.status_code
        report["observation_list_returned"] = response.status_code == 200 and isinstance(
            response.json().get("observations"), list
        )
        if not report["observation_list_returned"]:
            raise DeliveryError("protected_traffic_query_failed")
        # Never save observations from other aircraft, tokens, headers or error bodies.
        report["dashboard_routes_documented"] = [p for p in paths if "dashboard" in p or "homebase" in p]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Create a separate private simulation runtime")
    prep.add_argument("--config", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--traffic-source", type=int, required=True)
    prep.add_argument("--isolation-file", type=Path)
    inspect = sub.add_parser(
        "inspect-blender", help="Read deployed contract and verify auth; submits no traffic"
    )
    inspect.add_argument("--config", type=Path, required=True)
    inspect.add_argument("--report", type=Path, required=True)
    run = sub.add_parser("run", help="Publish up to three samples and verify downstream observations")
    run.add_argument("--config", type=Path, required=True)
    run.add_argument("--mqtt-url", help="Credential-free endpoint; defaults to configured public URL")
    run.add_argument("--ca-file", help="Optional trusted CA for a local TLS acceptance proxy")
    run.add_argument("--report", type=Path, required=True)
    run.add_argument("--count", type=int, choices=range(1, 4), default=3)
    run.add_argument("--isolation-file", type=Path, help="Required for non-local Blender targets")
    run.add_argument("--publish-only", action="store_true", help="Skip downstream queries; not acceptance")
    args = parser.parse_args()
    report = {"completed": False}
    try:
        settings = load_settings(args.config)
        if args.command == "prepare":
            isolation = json.loads(args.isolation_file.read_text()) if args.isolation_file else None
            prepare(settings, args.output, args.traffic_source, isolation)
            print("Independent private simulation runtime prepared. No telemetry published.")
        elif args.command == "inspect-blender":
            if args.report.exists():
                raise ValueError("Refusing to replace an existing report")
            private_write(args.report, json.dumps(asyncio.run(inspect_blender(settings)), indent=2) + "\n")
            print("Sanitised deployed-contract and protected-read evidence saved. No traffic submitted.")
        else:
            if args.report.exists():
                raise ValueError("Refusing to replace an existing report")
            try:
                asyncio.run(
                    exercise(
                        settings,
                        args.mqtt_url or settings.mqtt.public_url,
                        report,
                        args.ca_file,
                        args.count,
                        not args.publish_only,
                        json.loads(args.isolation_file.read_text()) if args.isolation_file else None,
                    )
                )
                report["completed"] = True
            finally:
                private_write(args.report, json.dumps(report, indent=2) + "\n")
            print("Bounded run finished; inspect the report for downstream verification. Publisher stopped.")
    except (ValueError, OSError, RuntimeError, httpx.HTTPError, DeliveryError):
        parser.exit(
            1, "Simulation incomplete. Check private configuration, isolation, broker and readback.\n"
        )


if __name__ == "__main__":
    main()
