import json
import stat
from pathlib import Path

import pytest
from pydantic import ValidationError

from dji_cloud_adaptor.cli import initialize, render_broker
from dji_cloud_adaptor.config import Settings, load_settings


def test_generated_config_and_handoff_files_stay_private(tmp_path):
    source = Path(__file__).parents[1] / "config.example.json"
    output = tmp_path / "private"
    initialize(source, output)
    settings = load_settings(output / "config.json")
    assert settings.admin_token.get_secret_value() != "**********"
    assert len(settings.devices[0].mqtt_password.get_secret_value()) >= 32
    assert not settings.dji.configured and not settings.blender.configured
    for path in output.rglob("*"):
        if path.is_file():
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert "connection_code" in json.loads((output / "controller-codes.json").read_text())[0]
    assert "connection_code" not in json.loads((output / "config.json").read_text())["devices"][0]
    with pytest.raises(ValueError, match="already exists"):
        initialize(source, output)


def test_broker_grants_are_scoped_and_no_role_can_publish_commands(settings, tmp_path):
    render_broker(settings, tmp_path)
    acl = (tmp_path / "acl").read_text()
    assert "#" not in acl and "+" not in acl
    assert "topic write thing/product/EXAMPLE-M3E-001/osd" in acl
    assert "topic write sys/product/EXAMPLE-RC-001/status_reply" in acl
    assert not any(
        "topic write" in line and suffix in line
        for line in acl.splitlines()
        for suffix in ("/services", "/drc/", "/property/set")
    )
    config = (tmp_path / "mosquitto.conf").read_text()
    assert "allow_anonymous false" in config


def test_public_plaintext_and_credential_urls_are_rejected(settings):
    for value in (
        "http://public.example.org",
        "https://user:password@public.example.org",
        "https://example.org?token=x",
    ):
        raw = settings.model_dump()
        raw["public_url"] = value
        with pytest.raises(ValidationError):
            Settings.model_validate(raw)


def test_aircraft_cannot_be_assigned_to_two_controllers(settings):
    raw = settings.model_dump()
    other = {**raw["devices"][0], "id": "controller2", "gateway_sn": "OTHER-RC"}
    raw["devices"].append(other)
    with pytest.raises(ValidationError, match="unique"):
        Settings.model_validate(raw)
