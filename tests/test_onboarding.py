"""Few-tap onboarding: short setup codes and remembered controllers."""

import json
import re
import sys
import time

import pytest
from conftest import CODE
from test_enrollment import body, enrollment_client, enrollment_settings  # noqa: F401

from dji_cloud_adaptor.enrollment import SETUP_ALPHABET, EnrollmentError, EnrollmentStore

DAY = 86400


def test_setup_codes_are_short_unambiguous_and_forgiving(store):
    registry = EnrollmentStore(store)
    code, _ = registry.invite("Field kit 1", 1, now=100)
    assert re.fullmatch(rf"[{SETUP_ALPHABET}]{{4}}-[{SETUP_ALPHABET}]{{4}}", code)
    assert not set("01OIL") & set(SETUP_ALPHABET)
    typed = " " + code.lower().replace("-", " ") + " "
    token, _ = registry.start(typed, now=101)
    assert registry.session(token, now=102)["label"] == "Field kit 1"


def test_earlier_long_invitations_still_work_and_stay_exact(store):
    registry = EnrollmentStore(store)
    code, _ = registry.invite("Earlier", 1, now=100, short=False)
    assert code.startswith("invite.")
    with pytest.raises(EnrollmentError, match="invalid_invitation"):
        registry.start(code.upper(), now=101)
    assert registry.start(code, now=101)


def test_cancelling_a_setup_code_accepts_how_it_was_written(store):
    registry = EnrollmentStore(store)
    code, _ = registry.invite("Cancelled", 1, now=100)
    registry.revoke_invitation(code.lower().replace("-", ""))
    with pytest.raises(EnrollmentError, match="invalid_invitation"):
        registry.start(code, now=101)


def test_setup_code_registers_through_the_api(enrollment_client):  # noqa: F811
    client, registry, _ = enrollment_client
    code, _ = registry.invite("Field kit 2", 2)
    start = client.post("/api/enrollment/start", json={"invitation_code": code.lower()})
    assert start.status_code == 200
    headers = {"Authorization": "Bearer " + start.json()["token"]}
    result = client.post("/api/enrollment/complete", headers=headers, json=body())
    assert result.status_code == 200
    assert result.json()["config"]["remember"] is True
    assert result.json()["config"]["expires_at"] > time.time() + 29 * DAY


def test_wrong_setup_codes_are_rate_limited(enrollment_client):  # noqa: F811
    client, _, _ = enrollment_client
    for _ in range(20):
        assert client.post("/api/enrollment/start", json={"invitation_code": "ABCD-EFGH"}).status_code == 401
    assert client.post("/api/enrollment/start", json={"invitation_code": "ABCD-EFGH"}).status_code == 429


def login(client):
    response = client.post("/api/pilot/login", json={"code": CODE})
    assert response.status_code == 200
    return response.json(), {"Authorization": "Bearer " + response.json()["token"]}


def test_connected_controller_is_remembered_and_each_reopen_extends_it(client, store):
    session, headers = login(client)
    assert session["expires_at"] > time.time() + 29 * DAY
    with store.connection() as db:
        db.execute("UPDATE sessions SET expires_at=?", (time.time() + DAY,))
    config = client.post("/api/pilot/activate", headers=headers, json={"gateway_sn": "EXAMPLE-RC-001"})
    assert config.status_code == 200
    assert config.json()["remember"] is True
    assert config.json()["expires_at"] > time.time() + 29 * DAY
    with store.connection() as db:
        assert db.execute("SELECT expires_at FROM sessions").fetchone()[0] > time.time() + 29 * DAY


def test_a_remembered_session_is_not_extended_for_another_controller(client, store):
    _, headers = login(client)
    with store.connection() as db:
        db.execute("UPDATE sessions SET expires_at=?", (time.time() + DAY,))
    other = client.post("/api/pilot/activate", headers=headers, json={"gateway_sn": "OTHER"})
    assert other.status_code == 403
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0


def test_remembering_can_be_turned_off(client, settings, store):
    settings.remember_controller_days = 0
    session, headers = login(client)
    assert session["expires_at"] < time.time() + settings.session_hours * 3600 + 5
    config = client.post("/api/pilot/activate", headers=headers, json={"gateway_sn": "EXAMPLE-RC-001"})
    assert config.json()["remember"] is False
    assert config.json()["expires_at"] < time.time() + settings.session_hours * 3600 + 5


def test_issue_invitation_can_show_the_setup_code(enrollment_settings, tmp_path, monkeypatch, capsys):  # noqa: F811
    from dji_cloud_adaptor import cli

    config = tmp_path / "config.json"
    cli.private_write(config, json.dumps(enrollment_settings.model_dump(), default=cli.secret_json))
    output = tmp_path / "invite.json"
    argv = ["dji-cloud-adaptor", "issue-invitation", "--config", str(config)]
    argv += ["--database", str(tmp_path / "queue.sqlite3"), "--output", str(output), "--show"]
    monkeypatch.setattr(sys, "argv", argv)
    cli.main()
    saved = json.loads(output.read_text())
    printed = capsys.readouterr().out
    assert f"Setup code: {saved['invitation_code']}" in printed
    assert "Address: http://localhost:18080" in printed
    for secret in ("test-app-key", "test-license", "test-admin-token-", "provisioner"):
        assert secret not in printed
