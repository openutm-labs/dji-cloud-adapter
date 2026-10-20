import copy
import json
import time
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from conftest import CODE
from fastapi.testclient import TestClient
from pydantic import ValidationError

from dji_cloud_adaptor.api import create_app
from dji_cloud_adaptor.config import Declarations
from dji_cloud_adaptor.declarations import Operations
from dji_cloud_adaptor.telemetry import Ingestor


class Blender:
    """Local contract receiver. Never contacts a deployed service."""

    def __init__(self):
        self.records = {}
        self.posts = []
        self.states = []
        self.telemetry = []
        self.traffic = []
        self.fail_after_create = False
        self.fail_before_create = False
        self.fail_after_state = False
        self.fail_telemetry = False
        self.approved = True
        self.malformed = False
        self.page_calls = []

    def __call__(self, request):
        assert request.headers["authorization"] == "Bearer test-blender-token"
        path = request.url.path
        if path.endswith("/set_flight_declaration"):
            payload = json.loads(request.content)
            self.posts.append(payload)
            if self.fail_before_create:
                raise httpx.ReadTimeout("synthetic failure")
            key = str(uuid4())
            record = {
                **payload,
                "id": key,
                "state": 1,
                "is_approved": self.approved,
                "flight_declaration_raw_geojson": payload["flight_declaration_geo_json"],
            }
            self.records[key] = record
            if self.fail_after_create:
                raise httpx.ReadTimeout("synthetic lost response")
            if self.malformed:
                return httpx.Response(200, json={"id": self.malformed})
            return httpx.Response(200, json={k: record[k] for k in ("id", "state", "is_approved")})
        if path.endswith("/flight_declaration"):
            self.page_calls.append(request.url)
            return httpx.Response(
                200, json={"count": len(self.records), "results": list(self.records.values())}
            )
        if "/flight_declaration_state/" in path:
            key = path.rsplit("/", 1)[1]
            body = json.loads(request.content)
            self.states.append(body)
            self.records[key]["state"] = body["state"]
            if self.fail_after_state:
                self.fail_after_state = False
                raise httpx.ReadTimeout("synthetic lost state response")
            return httpx.Response(200, json=body)
        if "/flight_declaration/" in path:
            return httpx.Response(200, json=self.records[path.rsplit("/", 1)[1]])
        if path.endswith("/set_telemetry"):
            assert request.method == "PUT"
            body = json.loads(request.content)
            self.telemetry.append(body)
            return httpx.Response(503 if self.fail_telemetry else 201, json={})
        if "/set_air_traffic/" in path:
            self.traffic.append(json.loads(request.content))
            return httpx.Response(201, json={})
        raise AssertionError(path)


@pytest.fixture
def declarations(settings):
    settings.declarations = Declarations(
        enabled=True,
        operator_id="test-operator",
        originating_party="Test organisation",
        pilots=[
            {"id": "pilot1", "name": "Test pilot", "device_ids": ["controller1"]},
            {"id": "other-pilot", "name": "Other pilot", "device_ids": ["controller2"]},
        ],
        max_radius_m=500,
        max_height_m=100,
        max_duration_minutes=60,
        altitude_margin_m=5,
        timestamp_accuracy_s=1,
    )
    return settings


@pytest.fixture
def upstream():
    return Blender()


@pytest.fixture
def pilot(declarations, store, upstream):
    app = create_app(declarations, store, background=False, transport=httpx.MockTransport(upstream))
    with TestClient(app) as client:
        token = client.post("/api/pilot/login", json={"code": CODE}).json()["token"]
        client.headers["Authorization"] = f"Bearer {token}"
        assert client.post("/api/pilot/activate", json={"gateway_sn": "EXAMPLE-RC-001"}).status_code == 200
        yield client


def ground(settings, store, osd):
    value = copy.deepcopy(osd)
    value["timestamp"] = int(time.time() * 1000)
    value["data"]["elevation"] = 0
    Ingestor(settings, store).process("thing/product/EXAMPLE-M3E-001/osd", json.dumps(value).encode())


def plan():
    return {
        "request_id": str(uuid4()),
        "aircraft_sn": "EXAMPLE-M3E-001",
        "pilot_id": "pilot1",
        "radius_m": 100,
        "height_m": 50,
        "start": datetime.fromtimestamp(time.time() + 120, UTC).isoformat(),
        "duration_minutes": 30,
        "on_ground": True,
    }


def prepare(pilot, settings, store, osd):
    ground(settings, store, osd)
    response = pilot.post("/api/pilot/declarations", json=plan())
    assert response.status_code == 200, response.text
    return response.json()


def action(pilot, op, name):
    return pilot.post("/api/pilot/declarations/" + op["id"], json={"action": name})


def start_now(store, upstream, op):
    """Advance the saved window and receiver together without sleeping in tests."""
    with store.connection() as db:
        row = db.execute("SELECT payload FROM operations WHERE id=?", (op["id"],)).fetchone()
        payload = json.loads(row[0])
        start = datetime.fromtimestamp(time.time() - 5, UTC).isoformat()
        payload["start_datetime"] = start
        db.execute(
            "UPDATE operations SET start_at=?,payload=? WHERE id=?",
            (datetime.fromisoformat(start).timestamp(), json.dumps(payload), op["id"]),
        )
    upstream.records[op["declaration_id"]]["start_datetime"] = start


def test_optional_and_device_verification(client):
    assert client.get("/api/pilot/declarations").status_code == 401
    token = client.post("/api/pilot/login", json={"code": CODE}).json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/api/pilot/declarations").status_code == 403
    client.post("/api/pilot/activate", json={"gateway_sn": "EXAMPLE-RC-001"})
    assert client.get("/api/pilot/declarations").status_code == 404


def test_config_requires_explicit_limits_and_scoped_roster():
    with pytest.raises(ValidationError):
        Declarations(enabled=True)
    with pytest.raises(ValidationError):
        Declarations(pilots=[{"id": "pilot", "name": "Pilot", "device_ids": []}])


def test_prepare_review_and_idempotent_submission(pilot, declarations, store, osd, upstream):
    options = pilot.get("/api/pilot/declarations").json()
    assert [p["id"] for p in options["pilots"]] == ["pilot1"]
    ground(declarations, store, osd)
    body = plan()
    op = pilot.post("/api/pilot/declarations", json=body).json()
    assert op["stage"] == "prepared"
    assert not upstream.posts
    assert pilot.post("/api/pilot/declarations", json=body).json()["id"] == op["id"]
    body["height_m"] += 1
    assert pilot.post("/api/pilot/declarations", json=body).status_code == 409
    submitted = action(pilot, op, "submit").json()
    assert submitted["declaration_id"] and submitted["state"] == "accepted"
    assert len(upstream.posts) == 1
    assert action(pilot, op, "submit").status_code == 200
    assert len(upstream.posts) == 1
    payload = upstream.posts[0]
    assert "flight_state" not in payload and "is_approved" not in payload
    assert payload["submitted_by"] == "pilot1" and payload["operator_id"] == "test-operator"
    props = payload["flight_declaration_geo_json"]["features"][0]["properties"]
    assert props["min_altitude"] == {"meters": 118.4, "datum": "W84"}
    assert props["max_altitude"] == {"meters": 178.4, "datum": "W84"}
    ring = payload["flight_declaration_geo_json"]["features"][0]["geometry"]["coordinates"][0]
    assert len(ring) == 33 and ring[0] == ring[-1]
    assert action(pilot, op, "activate").status_code == 409  # too early
    assert action(pilot, op, "cancel").json()["state"] == "cancelled"
    assert len(upstream.states) == 1


@pytest.mark.parametrize(
    "field,value,status",
    [
        ("pilot_id", "other-pilot", 403),
        ("aircraft_sn", "not-this-controller", 403),
        ("radius_m", 501, 422),
        ("height_m", 101, 422),
        ("duration_minutes", 61, 422),
        ("on_ground", False, 422),
        ("start", "2020-01-01T00:00:00Z", 422),
        ("start", "2030-01-01T00:00:00", 422),
    ],
)
def test_invalid_plans(pilot, declarations, store, osd, field, value, status, upstream):
    ground(declarations, store, osd)
    body = plan()
    body[field] = value
    assert pilot.post("/api/pilot/declarations", json=body).status_code == status
    assert not upstream.posts


def test_ground_reference_required(pilot, declarations, store, osd):
    assert pilot.post("/api/pilot/declarations", json=plan()).status_code == 409
    Ingestor(declarations, store).process("thing/product/EXAMPLE-M3E-001/osd", json.dumps(osd).encode())
    assert pilot.post("/api/pilot/declarations", json=plan()).status_code == 409
    with store.connection() as db:
        db.execute("UPDATE samples SET observed_at=?", (time.time() - 11,))
    assert pilot.post("/api/pilot/declarations", json=plan()).status_code == 409


@pytest.mark.parametrize("mode", ["lost_response", "malformed_response", "numeric_id", "not_sent"])
def test_uncertain_creation_never_reposts(pilot, declarations, store, osd, upstream, mode):
    op = prepare(pilot, declarations, store, osd)
    upstream.fail_after_create = mode == "lost_response"
    upstream.fail_before_create = mode == "not_sent"
    upstream.malformed = 123 if mode == "numeric_id" else "invalid" if mode == "malformed_response" else False
    result = action(pilot, op, "submit").json()
    assert result["stage"] == "uncertain"
    result = action(pilot, op, "submit").json()
    assert len(upstream.posts) == 1
    assert result["stage"] == ("uncertain" if mode == "not_sent" else "submitted")
    assert action(pilot, op, "discard").status_code == 409
    assert upstream.page_calls


def test_other_device_cannot_read_or_change_operation(pilot, declarations, store, osd, upstream):
    op = prepare(pilot, declarations, store, osd)
    with store.connection() as db:
        db.execute("UPDATE operations SET device_id='controller2' WHERE id=?", (op["id"],))
    assert action(pilot, op, "submit").status_code == 404
    assert pilot.get("/api/pilot/declarations").json()["operations"] == []
    assert not upstream.posts


def test_approval_and_lost_activation_response(pilot, declarations, store, osd, upstream):
    upstream.approved = False
    op = action(pilot, prepare(pilot, declarations, store, osd), "submit").json()
    start_now(store, upstream, op)
    assert action(pilot, op, "activate").status_code == 409
    upstream.records[op["declaration_id"]]["is_approved"] = True
    upstream.fail_after_state = True
    assert action(pilot, op, "activate").status_code == 503
    result = action(pilot, op, "activate").json()
    assert result["state"] == "activated"
    assert len(upstream.states) == 1
    with store.connection() as db:
        assert db.execute("SELECT bind_from FROM operations WHERE id=?", (op["id"],)).fetchone()[0]


def test_restart_recovers_inflight_creation(pilot, declarations, store, osd, upstream):
    op = prepare(pilot, declarations, store, osd)
    with store.connection() as db:
        db.execute("UPDATE operations SET stage='submitting' WHERE id=?", (op["id"],))
    Operations(declarations, store, pilot.app.state.forwarder.blender)
    assert action(pilot, op, "submit").json()["stage"] == "uncertain"
    assert not upstream.posts


def test_refresh_refuses_mismatched_remote_identity(pilot, declarations, store, osd, upstream):
    op = action(pilot, prepare(pilot, declarations, store, osd), "submit").json()
    upstream.records[op["declaration_id"]]["submitted_by"] = "unrelated"
    assert action(pilot, op, "activate").status_code == 502
    assert not upstream.states


def test_full_operation_telemetry_and_drain(pilot, declarations, store, osd, upstream):
    op = action(pilot, prepare(pilot, declarations, store, osd), "submit").json()
    start_now(store, upstream, op)
    assert action(pilot, op, "activate").json()["state"] == "activated"
    # A source sample captured before activation remains on the traffic route.
    ground(declarations, store, osd)
    with store.connection() as db:
        rows = db.execute("SELECT * FROM samples ORDER BY observed_at").fetchall()
    assert rows[0]["operation_id"] is None
    assert rows[-1]["operation_id"] == op["id"]
    assert action(pilot, op, "finish").json()["stage"] == "finishing"
    ground(declarations, store, osd)  # finishing stops new binding
    with store.connection() as db:
        assert (
            db.execute("SELECT operation_id FROM samples ORDER BY observed_at DESC LIMIT 1").fetchone()[0]
            is None
        )
    forwarder = pilot.app.state.forwarder
    while pilot.portal.call(forwarder.once):
        pass
    result = action(pilot, op, "finish").json()
    assert result["state"] == "ended"
    assert result["telemetry_counts"] == {"accepted": 1}
    assert len(upstream.telemetry) == 1 and len(upstream.traffic) == 2
    observation = upstream.telemetry[0]["observations"][0]
    assert observation["flight_details"]["id"] == op["declaration_id"]
    state = observation["current_states"][0]
    assert state["position"]["alt"] == 123.4 and state["position"]["height"]["distance"] == 0
    assert state["position"]["accuracy_h"] == "HAUnknown"
    assert state["track"] == 361 and state["vertical_speed"] == 63
    assert "operator_location" not in observation["flight_details"]
    assert action(pilot, op, "finish").json()["state"] == "ended"  # retry is safe
    assert [entry["state"] for entry in upstream.states] == [2, 5]


def test_remote_close_and_disabled_feature_do_not_reroute_samples(pilot, declarations, store, osd, upstream):
    op = action(pilot, prepare(pilot, declarations, store, osd), "submit").json()
    start_now(store, upstream, op)
    action(pilot, op, "activate")
    ground(declarations, store, osd)
    upstream.records[op["declaration_id"]]["state"] = 5
    while pilot.portal.call(pilot.app.state.forwarder.once):
        pass
    assert not upstream.telemetry
    assert len(upstream.traffic) == 1
    assert action(pilot, op, "refresh").json()["telemetry_counts"] == {"rejected": 1}
    # Source samples collected before activation were never relabelled.
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM samples WHERE operation_id IS NULL").fetchone()[0] == 1


def test_reconciliation_checks_all_pages_and_ignores_next_urls(pilot, declarations, store, osd, upstream):
    op = prepare(pilot, declarations, store, osd)
    upstream.fail_after_create = True
    action(pilot, op, "submit")
    blender = pilot.app.state.forwarder.blender
    original = upstream.__call__
    calls = []

    def paged(request):
        if request.url.path.endswith("/flight_declaration"):
            calls.append(request.url)
            page = int(request.url.params["page"])
            return httpx.Response(
                200,
                json={
                    "count": 101,
                    "results": [{}] * 100 if page == 1 else list(upstream.records.values()),
                    "next": "https://untrusted.example.org/steal-token",
                },
            )
        return original(request)

    blender.client._transport = httpx.MockTransport(paged)
    result = action(pilot, op, "refresh").json()
    assert result["declaration_id"] in upstream.records
    assert len(calls) == 2 and all(url.host == "localhost" for url in calls)
    assert len(upstream.posts) == 1


def test_outbox_survives_database_reopen_with_frozen_binding(pilot, declarations, store, osd, upstream):
    from dji_cloud_adaptor.store import Store

    op = action(pilot, prepare(pilot, declarations, store, osd), "submit").json()
    start_now(store, upstream, op)
    action(pilot, op, "activate")
    ground(declarations, store, osd)
    reopened = Store(store.path)
    with reopened.connection() as db:
        row = db.execute(
            "SELECT operation_id,observed_at,payload FROM samples WHERE operation_id IS NOT NULL"
        ).fetchone()
        assert row["operation_id"] == op["id"]
        original_payload = row["payload"]
    upstream.fail_telemetry = True
    while pilot.portal.call(pilot.app.state.forwarder.once):
        pass
    assert upstream.telemetry
    with reopened.connection() as db:
        assert (
            db.execute("SELECT payload FROM samples WHERE operation_id=?", (op["id"],)).fetchone()[0]
            == original_payload
        )
    assert action(pilot, op, "finish").json()["stage"] == "finishing"
    with reopened.connection() as db:
        db.execute("UPDATE samples SET observed_at=? WHERE operation_id=?", (time.time() - 61, op["id"]))
    assert action(pilot, op, "finish").json()["state"] == "ended"
    assert action(pilot, op, "refresh").json()["telemetry_counts"] == {"expired": 1}


def test_migration_preserves_existing_traffic_queue(tmp_path):
    import sqlite3

    from dji_cloud_adaptor.store import Store

    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE samples (id TEXT PRIMARY KEY, device_id TEXT, aircraft_sn TEXT, "
            "session_id TEXT, observed_at REAL, received_at REAL, payload TEXT, state TEXT, "
            "attempts INTEGER DEFAULT 0, next_attempt REAL DEFAULT 0, error TEXT, accepted_at REAL)"
        )
        db.execute(
            "INSERT INTO samples VALUES ('old','controller','aircraft','session',"
            "1,1,'{}','pending',0,0,NULL,NULL)"
        )
    row = Store(path).next_sample(2)
    assert row["id"] == "old" and row["operation_id"] is None


def test_network_pending_state_is_not_presented_as_accepted(pilot, declarations, store, osd, upstream):
    op = action(pilot, prepare(pilot, declarations, store, osd), "submit").json()
    upstream.records[op["declaration_id"]].update(state=0, is_approved=False)
    result = action(pilot, op, "refresh").json()
    assert result["state"] == "not_submitted" and not result["approved"]
    assert action(pilot, op, "activate").status_code == 409
    assert action(pilot, op, "cancel").json()["state"] == "withdrawn"
    assert [entry["state"] for entry in upstream.states] == [6]
