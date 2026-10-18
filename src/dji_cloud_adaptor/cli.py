import argparse
import hashlib
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from pydantic import SecretStr, ValidationError

from .config import Settings, load_settings


def private_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Refuse symlinks and create with private permissions before writing secrets.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(text)


def secret_json(value):
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return str(value)


def render_broker(settings: Settings, directory: Path):
    passwords = [f"{settings.mqtt.worker_username}:{settings.mqtt.worker_password.get_secret_value()}"]
    # Every role has exact topic grants. No flight-control or service-command grants.
    acl = [f"user {settings.mqtt.worker_username}"]
    for device in settings.devices:
        for prefix in ("sys", "thing"):
            acl.append(f"topic read {prefix}/product/{device.gateway_sn}/status")
        acl.append(f"topic write sys/product/{device.gateway_sn}/status_reply")
        acl.extend(f"topic read thing/product/{a.serial}/osd" for a in device.aircraft)
    for device in settings.devices:
        passwords.append(f"{device.mqtt_username}:{device.mqtt_password.get_secret_value()}")
        acl += ["", f"user {device.mqtt_username}"]
        for prefix in ("sys", "thing"):
            acl.append(f"topic write {prefix}/product/{device.gateway_sn}/status")
        acl.append(f"topic read sys/product/{device.gateway_sn}/status_reply")
        # Pilot 2 subscribes to its service inbox during connection. No role has
        # publish permission there, so this cannot enable remote aircraft control.
        for suffix in ("services", "requests_reply", "events_reply", "property/set"):
            acl.append(f"topic read thing/product/{device.gateway_sn}/{suffix}")
        acl.append(f"topic write thing/product/{device.gateway_sn}/osd")
        acl.append(f"topic write thing/product/{device.gateway_sn}/state")
        for aircraft in device.aircraft:
            acl += [
                f"topic write thing/product/{aircraft.serial}/osd",
                f"topic write thing/product/{aircraft.serial}/state",
            ]
    private_write(directory / "passwords.input", "\n".join(passwords) + "\n")
    private_write(directory / "acl", "\n".join(acl) + "\n")
    private_write(
        directory / "mosquitto.conf",
        """persistence true
persistence_location /mosquitto/data/
autosave_interval 30
allow_anonymous false
password_file /mosquitto/config/passwords
acl_file /mosquitto/config/acl
max_packet_size 262144
max_queued_messages 100000
queue_qos0_messages false
connection_messages false
log_dest stdout
log_type error
log_type warning
listener 1883
protocol mqtt
listener 9001
protocol websockets
""",
    )


def initialize(input_path: Path, output: Path):
    if output.exists():
        raise ValueError("Output directory already exists; refusing to replace credentials")
    raw = json.loads(input_path.read_text())
    codes = []
    devices = []
    for item in raw.pop("devices"):
        identifier = uuid4().hex[:12]
        code = f"{identifier}.{secrets.token_urlsafe(24)}"
        devices.append(
            {
                **item,
                "id": identifier,
                "connection_code_sha256": hashlib.sha256(code.encode()).hexdigest(),
                "mqtt_password": secrets.token_urlsafe(32),
                "aircraft": [{**a, "session_id": str(uuid4())} for a in item["aircraft"]],
            }
        )
        codes.append({"device_id": identifier, "device_name": item["name"], "connection_code": code})
    raw.setdefault("dji", {})
    raw["workspace_id"] = str(uuid4())
    raw["admin_token"] = secrets.token_urlsafe(32)
    raw["devices"] = devices
    raw["mqtt"] = {
        **raw["mqtt"],
        "worker_password": secrets.token_urlsafe(32),
        "client_id": "adaptor-" + uuid4().hex[:16],
    }
    settings = Settings.model_validate(raw)
    output.mkdir(mode=0o700, parents=True)
    (output / "data").mkdir(mode=0o700)
    private_write(
        output / "config.json", json.dumps(settings.model_dump(), default=secret_json, indent=2) + "\n"
    )
    private_write(output / "controller-codes.json", json.dumps(codes, indent=2) + "\n")
    private_write(
        output / "compose.env",
        f"ADAPTOR_UID={os.getuid()}\nADAPTOR_GID={os.getgid()}\n"
        f"ADAPTOR_DOMAIN={urlsplit(settings.public_url).hostname}\n",
    )
    render_broker(settings, output / "broker")
    return settings


def main():
    parser = argparse.ArgumentParser(description="Prepare private server configuration for DJI Cloud Adaptor")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="Generate controller codes, broker ACLs and private configuration")
    init.add_argument("--input", type=Path, required=True)
    init.add_argument("--output", type=Path, default=Path("runtime"))
    render = sub.add_parser(
        "render-broker", help="Regenerate broker files after changing private configuration"
    )
    render.add_argument("--config", type=Path, default=Path("runtime/config.json"))
    render.add_argument("--output", type=Path, default=Path("runtime/broker"))
    validate = sub.add_parser("check", help="Check config without printing secrets or contacting devices")
    validate.add_argument("--config", type=Path, default=Path("runtime/config.json"))
    args = parser.parse_args()
    try:
        if args.command == "init":
            initialize(args.input, args.output)
            print(f"Private configuration written to {args.output}; share controller codes privately.")
        elif args.command == "render-broker":
            render_broker(load_settings(args.config), args.output)
            print("Broker files regenerated. Restart the app and broker to apply access changes.")
        else:
            settings = load_settings(args.config)
            print(
                f"Configuration valid. DJI configured: {settings.dji.configured}; "
                f"Blender configured: {settings.blender.configured}."
            )
    except (ValueError, ValidationError, KeyError, OSError):
        # Pydantic errors can include the original input. Never print secret configuration.
        parser.exit(
            1, "Configuration could not be prepared. Check the input fields, URLs and file permissions.\n"
        )
