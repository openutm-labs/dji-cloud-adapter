"""Real broker authentication, ACLs and MQTT-to-outbox-to-HTTP tests. Docker required."""

import json
import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from uuid import uuid4

import httpx
import paho.mqtt.client as mqtt
import pytest

from dji_cloud_adaptor.blender import BlenderClient, Forwarder
from dji_cloud_adaptor.cli import render_broker
from dji_cloud_adaptor.mqtt import MqttReceiver

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_MQTT_INTEGRATION") != "1", reason="Set RUN_MQTT_INTEGRATION=1"
)


def wait_for(predicate, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("Timed out waiting for the integration condition")


@pytest.fixture
def broker(settings):
    root = Path(__file__).parents[1]
    tmp_path = root / ".integration-runtime" / uuid4().hex
    render_broker(settings, tmp_path)
    name = "dji-adaptor-test-" + uuid4().hex[:12]
    subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "-p",
            "127.0.0.1::1883",
            "-p",
            "127.0.0.1::9001",
            "-v",
            f"{tmp_path}:/bootstrap/config:ro",
            "-v",
            f"{root / 'deploy/mosquitto-entrypoint.sh'}:/bootstrap/entrypoint.sh:ro",
            "--entrypoint",
            "/bin/sh",
            "eclipse-mosquitto:2.1.2-alpine",
            "/bootstrap/entrypoint.sh",
        ],
        check=True,
        capture_output=True,
    )
    try:

        def port(number):
            output = subprocess.check_output(["docker", "port", name, f"{number}/tcp"], text=True)
            return int(output.strip().rsplit(":", 1)[1])

        tcp, ws = port(1883), port(9001)

        def listening():
            try:
                with socket.create_connection(("127.0.0.1", tcp), timeout=0.1):
                    return True
            except OSError:
                return False

        wait_for(listening)
        yield tcp, ws, name
    except Exception:
        print(subprocess.run(["docker", "logs", name], capture_output=True, text=True).stderr)
        raise
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        shutil.rmtree(tmp_path)


def pilot(settings, port, *, websocket=False, password=None, worker=False):
    device = settings.devices[0]
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="test-pilot-" + uuid4().hex[:8],
        protocol=mqtt.MQTTv5,
        transport="websockets" if websocket else "tcp",
    )
    if websocket:
        client.ws_set_options(path="/mqtt")
    client.username_pw_set(
        settings.mqtt.worker_username if worker else device.mqtt_username,
        password
        or (
            settings.mqtt.worker_password.get_secret_value()
            if worker
            else device.mqtt_password.get_secret_value()
        ),
    )
    event = threading.Event()
    results = []

    def connected(client, userdata, flags, reason_code, properties):
        results.append(reason_code)
        event.set()

    client.on_connect = connected
    client.connect("127.0.0.1", port)
    client.loop_start()
    assert event.wait(5)
    return client, results[0]


async def test_real_broker_to_blender_contract_with_duplicate_and_topology(settings, store, osd, broker):
    settings.mqtt.port = broker[0]
    receiver = MqttReceiver(settings, store)
    receiver.start()
    sender = None
    try:
        wait_for(lambda: receiver.connected)
        sender, reason = pilot(settings, broker[0])
        assert not reason.is_failure
        replies = []
        sender.on_message = lambda c, u, m: replies.append(json.loads(m.payload))
        subscribed = threading.Event()
        sender.on_subscribe = lambda *args: subscribed.set()
        sender.subscribe("sys/product/EXAMPLE-RC-001/status_reply", qos=1)
        assert subscribed.wait(5)
        topology = {
            "tid": "t",
            "bid": "b",
            "method": "update_topo",
            "timestamp": int(time.time() * 1000),
            "data": {"sub_devices": [{"sn": "EXAMPLE-M3E-001"}]},
        }
        sender.publish("sys/product/EXAMPLE-RC-001/status", json.dumps(topology), qos=1).wait_for_publish(5)
        wait_for(lambda: replies)
        assert replies[0]["data"] == {"result": 0}
        osd["timestamp"] = int(time.time() * 1000)
        for _ in range(2):
            sender.publish("thing/product/EXAMPLE-M3E-001/osd", json.dumps(osd), qos=1).wait_for_publish(5)
        wait_for(lambda: store.status().get("counters", {}).get("duplicate_osd") == 1)
        assert store.status()["counts"] == {"pending": 1}
        received = []

        def blender(request):
            received.append(json.loads(request.content))
            return httpx.Response(201, json={"message": "OK", "status": 201})

        async with httpx.AsyncClient(transport=httpx.MockTransport(blender)) as client:
            await Forwarder(settings, store, BlenderClient(settings, client)).once()
        assert received[0]["observations"][0]["altitude_mm"] == 123400
        assert store.status()["counts"] == {"accepted": 1}
    finally:
        if sender:
            sender.disconnect()
            sender.loop_stop()
        receiver.stop()


def test_wrong_password_cannot_connect(settings, broker):
    client, reason = pilot(settings, broker[0], password="wrong-password")
    try:
        assert reason.is_failure
    finally:
        client.disconnect()
        client.loop_stop()


@pytest.mark.parametrize("worker", [False, True])
def test_flight_commands_and_other_aircraft_are_denied(settings, broker, worker):
    for topic in ("thing/product/EXAMPLE-RC-001/services", "thing/product/OTHER-AIRCRAFT/osd"):
        client, reason = pilot(settings, broker[0], worker=worker)
        try:
            assert not reason.is_failure
            published = threading.Event()
            reasons = []

            def ack(client, userdata, mid, reason_code, properties, _reasons=reasons, _published=published):
                _reasons.append(reason_code)
                _published.set()

            client.on_publish = ack
            client.publish(topic, "{}", qos=1)
            assert published.wait(5)
            assert reasons[0].is_failure
        finally:
            client.disconnect()
            client.loop_stop()


def test_controller_can_connect_over_mqtt_websocket(settings, broker):
    client, reason = pilot(settings, broker[1], websocket=True)
    try:
        assert not reason.is_failure
    finally:
        client.disconnect()
        client.loop_stop()
