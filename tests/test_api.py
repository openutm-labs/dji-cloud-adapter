import hashlib
import time

import pytest
from conftest import CODE


def login(client):
    response = client.post("/api/pilot/login", json={"code": CODE})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['token']}"}


def test_credentials_and_private_status_require_authentication(client):
    for path in ("/api/pilot/bootstrap", "/api/pilot/config", "/api/pilot/status", "/api/admin/status"):
        response = client.get(path)
        assert response.status_code == 401
        assert "test-app-key" not in response.text


def test_connection_code_is_not_enough_to_read_mqtt_credentials(client):
    headers = login(client)
    assert client.get("/api/pilot/bootstrap", headers=headers).json()["app_id"] == "test-app"
    assert client.get("/api/pilot/config", headers=headers).status_code == 403
    assert client.get("/api/pilot/status", headers=headers).status_code == 403
    activated = client.post("/api/pilot/activate", headers=headers, json={"gateway_sn": "EXAMPLE-RC-001"})
    assert activated.status_code == 200
    assert activated.json()["mqtt"]["username"] == "pilot-controller1"
    assert "blender" not in activated.json()
    assert client.get("/api/pilot/status", headers=headers).status_code == 200


def test_wrong_controller_revokes_the_session(client):
    headers = login(client)
    assert (
        client.post("/api/pilot/activate", headers=headers, json={"gateway_sn": "OTHER-RC"}).status_code
        == 403
    )
    assert client.get("/api/pilot/bootstrap", headers=headers).status_code == 401


def test_expired_and_rotated_credentials_revoke_sessions(client, store, settings):
    headers = login(client)
    with store.connection() as db:
        db.execute("UPDATE sessions SET expires_at=?", (time.time() - 1,))
    assert client.get("/api/pilot/bootstrap", headers=headers).status_code == 401
    headers = login(client)
    settings.devices[0].connection_code_sha256 = hashlib.sha256(b"new-code").hexdigest()
    assert client.get("/api/pilot/bootstrap", headers=headers).status_code == 401


def test_logout_revokes_access(client):
    headers = login(client)
    assert client.post("/api/pilot/logout", headers=headers).status_code == 200
    assert client.get("/api/pilot/bootstrap", headers=headers).status_code == 401


def test_invalid_login_and_validation_do_not_echo_codes(client):
    secret = "x" * 200
    response = client.post("/api/pilot/login", json={"code": secret})
    assert response.status_code == 422 and secret not in response.text
    response = client.post("/api/pilot/login", json={"code": "bad-code-but-long-enough"})
    assert response.status_code == 401


def test_login_is_rate_limited_and_cross_origin_requests_are_blocked(client):
    for _ in range(20):
        client.post("/api/pilot/login", json={"code": "controller1.wrong-code-but-long-enough"})
    assert client.post("/api/pilot/login", json={"code": CODE}).status_code == 429
    assert (
        client.post(
            "/api/pilot/login", json={"code": CODE}, headers={"Origin": "https://unrelated.example"}
        ).status_code
        == 403
    )


def test_missing_dji_configuration_is_explained(client, settings):
    settings.dji.app_id = ""
    response = client.post("/api/pilot/login", json={"code": CODE})
    assert response.status_code == 503
    assert response.json()["detail"] == "dji_configuration_pending"


def test_readiness_does_not_claim_live_device_acceptance(client):
    assert client.get("/healthz").status_code == 200
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["checks"]["mqtt_connected"] is False


@pytest.mark.parametrize("path", ["/", "/static/portal.js", "/static/style.css"])
def test_portal_has_private_response_headers(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "script-src 'self'" in response.headers["content-security-policy"]
