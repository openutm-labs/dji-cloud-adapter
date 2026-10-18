import json
import time

import pytest

from dji_cloud_adaptor.store import QueueFull, Store
from dji_cloud_adaptor.telemetry import Ingestor, InvalidMessage

TOPIC = "thing/product/EXAMPLE-M3E-001/osd"


def test_aircraft_position_is_durable_and_converted_without_changing_time(settings, store, osd):
    Ingestor(settings, store).process(TOPIC, json.dumps(osd).encode())
    reopened = Store(store.path)
    sample = reopened.next_sample(time.time())
    result = json.loads(sample["payload"])
    assert result["lat_dd"] == 8.5 and result["lon_dd"] == -80.5
    assert result["altitude_mm"] == 123400
    assert result["timestamp"] == osd["timestamp"]
    assert result["metadata"]["altitude_reference"] == "WGS84_ellipsoid"
    assert result["metadata"]["elevation"] == 23.4
    assert result["metadata"]["rid_compliance_asserted"] is False
    assert len(result["icao_address"]) == 24
    assert "EXAMPLE-M3E-001" not in sample["payload"]
    assert sample["session_id"] == str(settings.devices[0].aircraft[0].session_id)


def test_retransmitted_sample_does_not_duplicate_after_restart(settings, store, osd):
    Ingestor(settings, store).process(TOPIC, json.dumps(osd).encode())
    osd["tid"] = "different-delivery-id"
    Ingestor(settings, Store(store.path)).process(TOPIC, json.dumps(osd).encode())
    assert store.status()["counts"] == {"pending": 1}


@pytest.mark.parametrize(
    "topic,change,retained",
    [
        ("thing/product/EXAMPLE-RC-001/osd", {}, False),
        ("thing/product/OTHER-AIRCRAFT/osd", {}, False),
        (TOPIC, {"gateway": "OTHER-RC"}, False),
        (TOPIC, {"timestamp": 1_000_000_000_000}, False),
        (TOPIC, {"timestamp": int((time.time() + 3600) * 1000)}, False),
        (TOPIC, {}, True),
    ],
)
def test_untrusted_stale_or_controller_position_is_not_forwarded(
    settings, store, osd, topic, change, retained
):
    osd.update(change)
    with pytest.raises(InvalidMessage):
        Ingestor(settings, store).process(topic, json.dumps(osd).encode(), retained=retained)
    assert not store.status()["counts"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("latitude", 91),
        ("longitude", -181),
        ("height", float("nan")),
        ("height", float("inf")),
        ("latitude", True),
        ("height", "123"),
    ],
)
def test_invalid_position_never_enters_queue(settings, store, osd, field, value):
    osd["data"][field] = value
    with pytest.raises(InvalidMessage):
        Ingestor(settings, store).process(TOPIC, json.dumps(osd).encode())
    assert not store.status()["counts"]


def test_partial_osd_does_not_reuse_old_coordinates(settings, store, osd):
    receiver = Ingestor(settings, store)
    receiver.process(TOPIC, json.dumps(osd).encode())
    osd["timestamp"] += 2000
    osd["data"] = {"battery": {"capacity_percent": 90}}
    receiver.process(TOPIC, json.dumps(osd).encode())
    assert store.status()["counts"] == {"pending": 1}


def test_topology_acknowledges_correlation_without_retaining_device_secrets(settings, store):
    body = {
        "tid": "transaction",
        "bid": "business",
        "timestamp": int(time.time() * 1000),
        "method": "update_topo",
        "data": {
            "device_secret": "DO-NOT-STORE-THIS",
            "sub_devices": [{"sn": "EXAMPLE-M3E-001", "device_secret": "CHILD-SECRET"}],
        },
    }
    topic, reply = Ingestor(settings, store).process(
        "sys/product/EXAMPLE-RC-001/status", json.dumps(body).encode()
    )
    assert topic == "sys/product/EXAMPLE-RC-001/status_reply"
    assert reply["tid"] == "transaction" and reply["bid"] == "business"
    assert reply["data"] == {"result": 0}
    with store.connection() as db:
        contents = "\n".join(db.iterdump())
    assert "SECRET" not in contents and "DO-NOT-STORE" not in contents


def test_unregistered_topology_is_not_accepted(settings, store):
    body = {
        "tid": "t",
        "bid": "b",
        "timestamp": int(time.time() * 1000),
        "method": "update_topo",
        "data": {"sub_devices": [{"sn": "OTHER-AIRCRAFT"}]},
    }
    with pytest.raises(InvalidMessage, match="unregistered_sub_device"):
        Ingestor(settings, store).process("sys/product/EXAMPLE-RC-001/status", json.dumps(body).encode())


def test_queue_does_not_silently_overwrite_pending_samples(store):
    for i in range(2):
        store.enqueue("c", "a", "s", 1, 1, {"sample": i}, capacity=2)
    with pytest.raises(QueueFull):
        store.enqueue("c", "a", "s", 1, 1, {"sample": 3}, capacity=2)
    assert store.status()["counts"] == {"pending": 2}
