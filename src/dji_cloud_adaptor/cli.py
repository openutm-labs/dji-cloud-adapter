import argparse
import asyncio
import hashlib
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pydantic import SecretStr, ValidationError

from .blender import BlenderClient, DeliveryError
from .broker import BrokerProvisioner, BrokerUnavailable, initial_security
from .config import Settings, load_settings
from .enrollment import EnrollmentError, EnrollmentStore
from .store import Store


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
    if settings.mqtt.provisioner_password.get_secret_value():
        private_write(directory / "dynamic-security.json", json.dumps(initial_security(settings)) + "\n")
        private_write(
            directory / "mosquitto.conf",
            """persistence true
persistence_location /mosquitto/data/
autosave_interval 30
allow_anonymous false
plugin /usr/lib/mosquitto_dynamic_security.so
plugin_opt_config_file /mosquitto/data/dynamic-security.json
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
        return
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
    if raw.get("enrollment", {}).get("enabled"):
        raw["mqtt"].setdefault("provisioner_password", secrets.token_urlsafe(32))
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
    access = sub.add_parser(
        "check-blender", help="Verify Blender authentication and a protected GET; sends no telemetry"
    )
    access.add_argument("--config", type=Path, default=Path("runtime/config.json"))
    invitation = sub.add_parser(
        "issue-invitation", help="Write a one-controller invitation to a private file"
    )
    invitation.add_argument("--config", type=Path, default=Path("runtime/config.json"))
    invitation.add_argument("--database", type=Path, default=Path("runtime/data/queue.sqlite3"))
    invitation.add_argument("--output", type=Path, required=True)
    invitation.add_argument("--label", default="Operator invitation")
    invitation.add_argument("--hours", type=int, choices=range(1, 169), default=72, metavar="1..168")
    revoke = sub.add_parser("revoke-device", help="Revoke a self-enrolled device and its broker access")
    revoke.add_argument("--config", type=Path, default=Path("runtime/config.json"))
    revoke.add_argument("--database", type=Path, default=Path("runtime/data/queue.sqlite3"))
    revoke.add_argument("--device", required=True)
    recover = sub.add_parser(
        "export-device-code", help="Recover a self-enrolled device code to a private file"
    )
    recover.add_argument("--database", type=Path, default=Path("runtime/data/queue.sqlite3"))
    recover.add_argument("--device", required=True)
    recover.add_argument("--output", type=Path, required=True)
    revoke_invite = sub.add_parser(
        "revoke-invitation", help="Cancel an invitation from its private hand-off file"
    )
    revoke_invite.add_argument("--database", type=Path, default=Path("runtime/data/queue.sqlite3"))
    revoke_invite.add_argument("--invitation-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            initialize(args.input, args.output)
            print(f"Private configuration written to {args.output}; share controller codes privately.")
        elif args.command == "render-broker":
            render_broker(load_settings(args.config), args.output)
            print("Broker files regenerated. Restart the app and broker to apply access changes.")
        elif args.command == "check-blender":
            asyncio.run(check_blender(load_settings(args.config)))
            print(
                "Blender authentication and protected read succeeded. "
                "No telemetry was submitted; write access and downstream processing remain unverified."
            )
        elif args.command == "issue-invitation":
            settings = load_settings(args.config)
            if not settings.enrollment.enabled or args.output.exists():
                raise ValueError("Enrollment disabled or output already exists")
            code, expires = EnrollmentStore(Store(args.database)).invite(args.label[:100], args.hours)
            private_write(
                args.output,
                json.dumps(
                    {"url": settings.public_url, "invitation_code": code, "expires_at": expires}, indent=2
                )
                + "\n",
            )
            print("Invitation saved privately. One controller per invitation; no serials needed in advance.")
        elif args.command == "revoke-device":
            settings = load_settings(args.config)
            registry = EnrollmentStore(Store(args.database))
            devices = registry.devices() + registry.devices("pending") + registry.devices("revoked")
            device = next((d for d in devices if d.id == args.device), None)
            if not device or not settings.mqtt.provisioner_password.get_secret_value():
                raise ValueError("Device or broker provisioning unavailable")
            registry.revoke(device.id)
            BrokerProvisioner(settings).revoke(device)
            print("Device revoked. The running service will remove its registration on its next refresh.")
        elif args.command == "export-device-code":
            if args.output.exists():
                raise ValueError("Output already exists")
            code = EnrollmentStore(Store(args.database)).code(args.device)
            private_write(args.output, json.dumps({"device_id": args.device, "connection_code": code}) + "\n")
            print(
                "Connection code recovered to the private output file; share only with the assigned operator."
            )
        elif args.command == "revoke-invitation":
            code = json.loads(args.invitation_file.read_text())["invitation_code"]
            EnrollmentStore(Store(args.database)).revoke_invitation(code)
            print("Invitation cancelled. Revoke an already registered device separately if required.")
        else:
            settings = load_settings(args.config)
            print(
                f"Configuration valid. DJI configured: {settings.dji.configured}; "
                f"Blender configured: {settings.blender.configured}."
            )
    except DeliveryError as exc:
        parser.exit(1, f"Blender access check failed: {exc.reason}. Credentials and responses suppressed.\n")
    except (BrokerUnavailable, EnrollmentError):
        parser.exit(
            1, "Enrollment operation could not finish. Check private configuration and broker access.\n"
        )
    except (ValueError, ValidationError, KeyError, OSError):
        # Pydantic errors can include the original input. Never print secret configuration.
        parser.exit(
            1, "Configuration could not be prepared. Check the input fields, URLs and file permissions.\n"
        )


async def check_blender(settings: Settings):
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        await BlenderClient(settings, client).check_access()
