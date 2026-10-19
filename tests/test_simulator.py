import copy
import json
import os
import subprocess
import time

import httpx
import pytest
from pydantic import ValidationError
from test_mqtt_integration import pilot, wait_for

from dji_cloud_adaptor.config import Settings
from dji_cloud_adaptor.mqtt import MqttReceiver
from dji_cloud_adaptor.simulator import (
    Simulator,
    exercise,
    inspect_blender,
    matches,
    position,
    prepare,
    require_isolation,
)
from dji_cloud_adaptor.telemetry import Ingestor

pytest_plugins = ["test_mqtt_integration"]


@pytest.fixture
def settings(settings, tmp_path):
    return prepare(settings, tmp_path / "simulation", 255)


def test_prepare_preserves_source_and_creates_independent_secrets(settings, tmp_path):
    before = settings.model_dump()
    other = prepare(settings, tmp_path / "second", 255)
    assert settings.model_dump() == before
    assert other.admin_token != settings.admin_token
    assert other.devices[0].mqtt_password != settings.devices[0].mqtt_password
    assert other.devices[0].aircraft[0].session_id != settings.devices[0].aircraft[0].session_id
    assert (tmp_path / "second/config.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError):
        prepare(settings, tmp_path / "second", 255)


def test_nonlocal_target_requires_matching_isolation(settings, tmp_path):
    settings.blender.base_url = "https://blender.example.org"
    for note in (None, {}, {"operational_consumers_exclude": True}):
        with pytest.raises(ValueError, match="isolation"):
            prepare(settings, tmp_path / "forbidden", 255, note)
    note = {
        "base_url": settings.blender.base_url,
        "traffic_source": 255,
        "operational_consumers_exclude": True,
        "allocation_reference": "Local unit fixture, not an allocation for any real service",
    }
    require_isolation(settings, 255, note)
    with pytest.raises(ValueError):
        require_isolation(settings, 254, note)


@pytest.mark.parametrize("code", [0, 9, 11, 256])
def test_simulation_cannot_claim_existing_real_surveillance_categories(settings, code):
    raw = settings.model_dump()
    raw["devices"][0]["aircraft"][0]["simulation"]["traffic_source"] = code
    with pytest.raises(ValidationError):
        Settings.model_validate(raw)


@pytest.mark.parametrize("field", ["serial", "name", "gateway_sn"])
def test_fictional_identity_is_mandatory(settings, field):
    raw = settings.model_dump()
    if field == "gateway_sn":
        raw["devices"][0][field] = "REAL-RC"
    else:
        raw["devices"][0]["aircraft"][0][field] = "REAL"
    with pytest.raises(ValidationError):
        Settings.model_validate(raw)


def test_simulation_metadata_is_owned_by_configuration_and_readback_is_exact(settings, store):
    device = settings.devices[0]
    aircraft = device.aircraft[0]
    packet = position(settings, 0)
    packet["data"]["simulation_run_id"] = "untrusted"
    Ingestor(settings, store).process(f"thing/product/{aircraft.serial}/osd", json.dumps(packet).encode())
    sample = store.next_sample(time.time())
    observation = json.loads(sample["payload"])
    observation["metadata"]["source_event_id"] = sample["id"]
    observation["session_id"] = sample["session_id"]
    assert observation["icao_address"].startswith("sim-dji-") and len(observation["icao_address"]) == 24
    assert observation["altitude_mm"] == 123456
    assert observation["metadata"]["elevation"] == 23.456
    assert matches(settings, packet, observation)
    for field, value in [
        ("lat_dd", 1.0),
        ("lon_dd", -139.0),
        ("altitude_mm", 23456),
        ("traffic_source", 11),
        ("source_type", 1),
        ("session_id", "wrong"),
    ]:
        changed = copy.deepcopy(observation)
        changed[field] = value
        assert not matches(settings, packet, changed)
    for field, value in [("simulation", False), ("source_timestamp_ms", 1), ("source_event_id", "")]:
        changed = copy.deepcopy(observation)
        changed["metadata"][field] = value
        assert not matches(settings, packet, changed)


@pytest.mark.parametrize("url", ["mqtt://example.org", "ws://example.org/mqtt", "wss://u:p@host/mqtt"])
def test_simulator_refuses_plaintext_remote_and_credentials_in_url(settings, url):
    with pytest.raises(ValueError):
        Simulator(settings, url)


async def test_preflight_is_read_only_and_does_not_save_other_traffic(settings, monkeypatch):
    requests = []

    def target(request):
        requests.append(request)
        assert request.method == "GET"
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json={"paths": {}})
        if not request.headers.get("authorization"):
            return httpx.Response(401)
        return httpx.Response(200, json={"observations": [{"private": "unrelated-equipment"}]})

    client_class = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: client_class(transport=httpx.MockTransport(target), **kw)
    )
    report = await inspect_blender(settings)
    assert report["telemetry_submitted"] is False
    assert report["anonymous_protected_health_status"] == 401
    assert report["protected_traffic_query_status"] == 200
    assert "unrelated-equipment" not in json.dumps(report)
    assert len(requests) == 4


async def test_remote_run_is_blocked_before_auth_or_publish_without_isolation(settings):
    settings.blender.base_url = "https://blender.example.org"
    with pytest.raises(ValueError, match="isolation"):
        await exercise(settings, "wss://cloud.example.org/mqtt", {})


async def test_run_bounds_checked_before_any_network(settings):
    for count in (0, 4, 999):
        with pytest.raises(ValueError, match="three"):
            await exercise(settings, "mqtt://localhost:1883", {}, count=count)


@pytest.mark.skipif(os.environ.get("RUN_MQTT_INTEGRATION") != "1", reason="Real broker opt-in")
def test_bounded_simulator_validation_retained_replay_and_broker_reconnect(settings, store, broker):
    settings.mqtt.port = broker[0]
    aircraft = settings.devices[0].aircraft[0]
    topic = f"thing/product/{aircraft.serial}/osd"
    receiver = MqttReceiver(settings, store)
    sender = None
    try:
        # A retained packet delivered on subscription must not enter the outbox.
        sender, reason = pilot(settings, broker[0])
        assert not reason.is_failure
        retained = position(settings, 0)
        sender.publish(topic, json.dumps(retained), qos=1, retain=True).wait_for_publish(5)
        receiver.start()
        wait_for(lambda: store.status()["counters"].get("rejected_retained_message") == 1)
        sender.publish(topic, b"", qos=1, retain=True).wait_for_publish(5)
        sender.disconnect()
        sender.loop_stop()
        sender = None
        with Simulator(settings, f"mqtt://localhost:{broker[0]}") as sim:
            packet = position(settings, 0)
            sim.publish(topic, packet)
            sim.publish(topic, packet)
            wait_for(lambda: store.status()["counters"].get("duplicate_osd") == 1)
            invalid = position(settings, 1)
            invalid["data"]["latitude"] = 91
            sim.publish(topic, invalid)
            partial = position(settings, 1)
            partial["data"] = {"height": 123}
            sim.publish(topic, partial)
            stale = position(settings, 1)
            stale["timestamp"] -= 301000
            sim.publish(topic, stale)
            sim.publish(topic, {"latitude": 1.25, "height": 123})
            wait_for(lambda: store.status()["counters"].get("rejected_invalid_envelope") == 1)
        assert store.status()["counts"] == {"pending": 1}
        counters = store.status()["counters"]
        assert counters["rejected_number_out_of_range"] == 1
        assert counters["rejected_stale_message"] == 1
        assert counters["non_position_osd"] == 1
        # Preserve the receiver session and broker data across a real broker restart.
        subprocess.run(["docker", "restart", broker[2]], check=True, capture_output=True)
        port = int(
            subprocess.check_output(["docker", "port", broker[2], "1883/tcp"], text=True).rsplit(":", 1)[1]
        )
        # Docker can change the host mapping; reconnect the same persistent worker session.
        receiver.stop()
        settings.mqtt.port = port
        receiver = MqttReceiver(settings, store)
        receiver.start()
        wait_for(lambda: receiver.connected)
        with Simulator(settings, f"mqtt://localhost:{port}") as sim:
            sim.publish(topic, packet)
            sim.publish(topic, position(settings, 2))
            wait_for(lambda: store.status()["counts"].get("pending") == 2)
        assert store.status()["counters"]["duplicate_osd"] == 2
    finally:
        if sender:
            sender.disconnect()
            sender.loop_stop()
        receiver.stop()
