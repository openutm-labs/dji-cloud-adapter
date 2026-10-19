import os
import time

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from dji_cloud_adaptor.api import create_app
from dji_cloud_adaptor.broker import BrokerProvisioner
from dji_cloud_adaptor.enrollment import EnrollmentError, EnrollmentStore

pytest_plugins = ["test_mqtt_integration"]


@pytest.fixture
def enrollment_settings(settings):
    settings.enrollment.enabled = True
    settings.mqtt.provisioner_password = SecretStr("test-provisioner-password-" * 3)
    return settings


class Provisioner:
    def __init__(self):
        self.fail = False
        self.synced = []

    def sync(self, device, fleet):
        from dji_cloud_adaptor.broker import BrokerUnavailable

        if self.fail:
            raise BrokerUnavailable()
        self.synced.append((device, fleet))


@pytest.fixture
def enrollment_client(enrollment_settings, store):
    app = create_app(enrollment_settings, store, background=False)
    app.state.provisioner = Provisioner()
    with TestClient(app) as client:
        yield client, app.state.registry, app.state.provisioner


def start(client, registry):
    code, expires = registry.invite("Test operator", 72)
    response = client.post("/api/enrollment/start", json={"invitation_code": code})
    assert response.status_code == 200
    return code, {"Authorization": "Bearer " + response.json()["token"]}


def body(**updates):
    return {
        "gateway_sn": "NEW-RC-001",
        "aircraft_sn": "NEW-AIRCRAFT-001",
        "aircraft_model": "Mavic 3 Enterprise",
        "name": "Survey controller",
        **updates,
    }


def test_invitation_expiry_and_single_controller_use(store):
    registry = EnrollmentStore(store)
    code, expires = registry.invite("Pilot", 1, now=100)
    with pytest.raises(EnrollmentError, match="invalid_invitation"):
        registry.start(code, now=expires)
    token, _ = registry.start(code, now=101)
    device = registry.reserve(token, "RC", "UAV", "Matrice 400", "", 100, now=102)
    assert registry.reserve(token, "RC", "UAV", "Matrice 400", "", 100, now=103).id == device.id
    registry.activate(device.id)
    with pytest.raises(EnrollmentError, match="invitation_used"):
        registry.start(code, now=104)
    with pytest.raises(EnrollmentError, match="invitation_used"):
        registry.reserve(token, "OTHER", "OTHER-UAV", "Matrice 400", "", 100, now=104)


def test_enrollment_bootstrap_needs_valid_invitation_and_rate_limits(enrollment_client):
    client, registry, _ = enrollment_client
    assert client.get("/api/enrollment/bootstrap").status_code == 401
    for _ in range(20):
        assert (
            client.post("/api/enrollment/start", json={"invitation_code": "invalid-" * 6}).status_code == 401
        )
    assert client.post("/api/enrollment/start", json={"invitation_code": "invalid-" * 6}).status_code == 429


@pytest.mark.parametrize("model", ["Mavic 3 Enterprise", "Matrice 400"])
def test_operator_self_enrolls_without_preconfigured_serials(enrollment_client, model):
    client, registry, provisioner = enrollment_client
    code, headers = start(client, registry)
    assert client.get("/api/enrollment/bootstrap", headers=headers).status_code == 200
    response = client.post("/api/enrollment/complete", headers=headers, json=body(aircraft_model=model))
    assert response.status_code == 200
    data = response.json()
    assert provisioner.synced[0][0].gateway_sn == "NEW-RC-001"
    assert data["config"]["mqtt"]["username"].startswith("pilot-")
    assert "app_key" not in data and "client_secret" not in response.text
    login = client.post("/api/pilot/login", json={"code": data["connection_code"]})
    assert login.status_code == 200
    pilot_headers = {"Authorization": "Bearer " + login.json()["token"]}
    assert (
        client.post("/api/pilot/activate", headers=pilot_headers, json={"gateway_sn": "WRONG"}).status_code
        == 403
    )
    assert client.post("/api/enrollment/start", json={"invitation_code": code}).status_code == 401
    retry = client.post("/api/enrollment/complete", headers=headers, json=body(aircraft_model=model))
    assert retry.status_code == 200
    assert retry.json()["connection_code"] == data["connection_code"]


@pytest.mark.parametrize("update", [{"aircraft_model": "Air 2S"}, {"aircraft_sn": "NEW-RC-001"}])
def test_unsupported_or_same_device_registration_fails(enrollment_client, update):
    client, registry, provisioner = enrollment_client
    _, headers = start(client, registry)
    assert client.post("/api/enrollment/complete", headers=headers, json=body(**update)).status_code == 422
    assert not provisioner.synced


def test_registered_equipment_cannot_be_taken_over(enrollment_client):
    client, registry, provisioner = enrollment_client
    _, headers = start(client, registry)
    assert client.post("/api/enrollment/complete", headers=headers, json=body()).status_code == 200
    _, other = start(client, registry)
    assert client.post("/api/enrollment/complete", headers=other, json=body()).status_code == 409
    assert (
        client.post("/api/enrollment/complete", headers=other, json=body(gateway_sn="DIFFERENT")).status_code
        == 409
    )
    assert (
        client.post(
            "/api/enrollment/complete",
            headers=other,
            json=body(gateway_sn="EXAMPLE-RC-001", aircraft_sn="DIFFERENT"),
        ).status_code
        == 409
    )


def test_broker_outage_keeps_registration_private_and_recoverable(enrollment_client):
    client, registry, provisioner = enrollment_client
    code, headers = start(client, registry)
    provisioner.fail = True
    response = client.post("/api/enrollment/complete", headers=headers, json=body())
    assert response.status_code == 503 and response.json() == {"detail": "registration_pending"}
    assert not registry.devices() and len(registry.devices("pending")) == 1
    resumed = client.post("/api/enrollment/start", json={"invitation_code": code})
    assert resumed.status_code == 200
    provisioner.fail = False
    headers = {"Authorization": "Bearer " + resumed.json()["token"]}
    assert client.post("/api/enrollment/complete", headers=headers, json=body()).status_code == 200
    assert len(registry.devices()) == 1


def test_registration_persists_and_revocation_blocks_new_login(enrollment_client, enrollment_settings, store):
    client, registry, _ = enrollment_client
    _, headers = start(client, registry)
    result = client.post("/api/enrollment/complete", headers=headers, json=body()).json()
    fresh = enrollment_settings.model_copy(update={"devices": enrollment_settings.devices[:1]})
    app = create_app(fresh, store, background=False)
    with TestClient(app) as reopened:
        assert reopened.post("/api/pilot/login", json={"code": result["connection_code"]}).status_code == 200
    registry.revoke(registry.devices()[0].id)
    fresh = enrollment_settings.model_copy(update={"devices": enrollment_settings.devices[:1]})
    with TestClient(create_app(fresh, store, background=False)) as reopened:
        assert reopened.post("/api/pilot/login", json={"code": result["connection_code"]}).status_code == 401


def test_enrollment_disabled_by_default(client):
    assert client.get("/api/enrollment/options").json()["enabled"] is False
    assert client.post("/api/enrollment/start", json={"invitation_code": "invite-" * 8}).status_code == 404


@pytest.mark.skipif(os.environ.get("RUN_MQTT_INTEGRATION") != "1", reason="Real broker required")
def test_dynamic_broker_provisions_isolated_device_and_persists(enrollment_settings, store, request):
    from test_mqtt_integration import pilot

    settings = enrollment_settings
    tcp, ws, container = request.getfixturevalue("broker")
    settings.mqtt.host, settings.mqtt.port = "localhost", tcp
    registry = EnrollmentStore(store)
    invitation, _ = registry.invite("Operator", 1)
    token, _ = registry.start(invitation)
    device = registry.reserve(token, "SELF-RC", "SELF-UAV", "Matrice 400", "", 100)
    provisioner = BrokerProvisioner(settings)
    provisioner.sync(device, settings.devices + [device])
    # Every broker command is idempotent for crash/retry recovery.
    provisioner.sync(device, settings.devices + [device])
    settings.devices = [device]
    client, reason = pilot(settings, tcp)
    assert not reason.is_failure
    client.disconnect()
    client.loop_stop()
    # Controller cannot publish broker-control commands, aircraft services, or another aircraft's OSD.
    from test_mqtt_integration import wait_for

    refused = []
    client, reason = pilot(settings, tcp)
    client.on_publish = lambda c, u, mid, rc, props: refused.append(rc.is_failure)
    for topic in (
        "$CONTROL/dynamic-security/v1",
        "thing/product/SELF-RC/services",
        "thing/product/OTHER/osd",
    ):
        client.publish(topic, "{}", qos=1)
    wait_for(lambda: len(refused) == 3)
    assert all(refused)
    client.disconnect()
    client.loop_stop()
    import subprocess

    subprocess.run(["docker", "restart", container], check=True, capture_output=True)
    time.sleep(0.3)
    # Published port can change on restart; get the actual one.
    tcp = int(
        subprocess.check_output(["docker", "port", container, "1883/tcp"], text=True)
        .strip()
        .rsplit(":", 1)[1]
    )
    client, reason = pilot(settings, tcp)
    assert not reason.is_failure
    client.disconnect()
    client.loop_stop()
    settings.mqtt.port = tcp
    provisioner.revoke(device)
    client, reason = pilot(settings, tcp)
    assert reason.is_failure
    client.disconnect()
    client.loop_stop()


@pytest.mark.skipif(os.environ.get("RUN_MQTT_INTEGRATION") != "1", reason="Real broker required")
def test_empty_fleet_self_registration_streams_without_restart(enrollment_settings, store, request, osd):
    import json

    import httpx
    from test_mqtt_integration import pilot, wait_for

    settings = enrollment_settings
    settings.devices = []
    tcp, _, _ = request.getfixturevalue("broker")
    settings.mqtt.host, settings.mqtt.port = "localhost", tcp
    received = []

    def sink(request):
        assert request.url.host == "localhost"
        assert "/flight_stream/set_air_traffic/" in request.url.path
        received.append(json.loads(request.content))
        return httpx.Response(201)

    app = create_app(settings, store, transport=httpx.MockTransport(sink))
    with TestClient(app) as client:
        wait_for(lambda: client.get("/readyz").status_code == 200)
        _, headers = start(client, app.state.registry)
        result = client.post("/api/enrollment/complete", headers=headers, json=body())
        assert result.status_code == 200
        sender, reason = pilot(settings, tcp)
        assert not reason.is_failure
        try:
            wait_for(lambda: app.state.receiver.connected)
            osd["timestamp"] = int(time.time() * 1000)
            osd["gateway"] = "NEW-RC-001"
            sender.publish("thing/product/NEW-AIRCRAFT-001/osd", json.dumps(osd), qos=1).wait_for_publish(5)
            wait_for(lambda: store.status()["counts"].get("accepted") == 1)
            assert len(received) == 1
        finally:
            sender.disconnect()
            sender.loop_stop()
    fresh = settings.model_copy(update={"devices": []})
    reopened_app = create_app(fresh, store, transport=httpx.MockTransport(sink))
    with TestClient(reopened_app) as reopened:
        wait_for(lambda: reopened.get("/readyz").status_code == 200)
        assert (
            reopened.post("/api/pilot/login", json={"code": result.json()["connection_code"]}).status_code
            == 200
        )


def test_cancelled_invitation_and_immediate_api_revocation(enrollment_client):
    client, registry, _ = enrollment_client
    cancelled, _ = registry.invite("Cancelled operator", 1)
    registry.revoke_invitation(cancelled)
    assert client.post("/api/enrollment/start", json={"invitation_code": cancelled}).status_code == 401
    _, headers = start(client, registry)
    result = client.post("/api/enrollment/complete", headers=headers, json=body()).json()
    registry.revoke(registry.devices()[0].id)
    assert client.post("/api/pilot/login", json={"code": result["connection_code"]}).status_code == 401
    assert (
        client.get("/api/pilot/status", headers={"Authorization": "Bearer " + result["token"]}).status_code
        == 401
    )
