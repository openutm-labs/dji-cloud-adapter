"""Private Mosquitto dynamic-security control; never exposed to a pilot client."""

import hashlib
import json
import secrets
import threading

import paho.mqtt.client as mqtt

from .config import Device, Settings

CONTROL = "$CONTROL/dynamic-security/v1"


class BrokerUnavailable(Exception):
    pass


def grants(device: Device):
    sends = [
        f"sys/product/{device.gateway_sn}/status",
        f"thing/product/{device.gateway_sn}/status",
        f"thing/product/{device.gateway_sn}/osd",
        f"thing/product/{device.gateway_sn}/state",
    ]
    receives = [f"sys/product/{device.gateway_sn}/status_reply"]
    receives += [
        f"thing/product/{device.gateway_sn}/{suffix}"
        for suffix in ("services", "requests_reply", "events_reply", "property/set")
    ]
    sends += [f"thing/product/{a.serial}/{suffix}" for a in device.aircraft for suffix in ("osd", "state")]
    return sends, receives


def worker_grants(devices: list[Device]):
    sends, receives = [], []
    for device in devices:
        sends.append(f"sys/product/{device.gateway_sn}/status_reply")
        receives += [f"{prefix}/product/{device.gateway_sn}/status" for prefix in ("sys", "thing")]
        receives += [f"thing/product/{a.serial}/osd" for a in device.aircraft]
    return sends, receives


def acls(sends, receives):
    return [
        {"acltype": kind, "topic": topic, "allow": True, "priority": 1}
        for kind, topics in (
            ("publishClientSend", sends),
            ("publishClientReceive", receives),
            ("subscribeLiteral", receives),
        )
        for topic in topics
    ]


class BrokerProvisioner:
    def __init__(self, settings: Settings):
        self.settings = settings

    def command(self, command: str, **fields):
        correlation = secrets.token_hex(16)
        done, subscribed = threading.Event(), threading.Event()
        result = []
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="enroll-" + secrets.token_hex(8))
        config = self.settings.mqtt
        client.username_pw_set(config.provisioner_username, config.provisioner_password.get_secret_value())
        if config.tls:
            client.tls_set(ca_certs=config.ca_file)

        def connected(client, userdata, flags, reason_code, properties):
            if reason_code.is_failure:
                done.set()
            else:
                client.subscribe(CONTROL + "/response", qos=1)

        def on_subscribe(client, userdata, mid, reasons, properties):
            if reasons and all(not reason.is_failure for reason in reasons):
                subscribed.set()
            else:
                done.set()

        def message(client, userdata, msg):
            try:
                for response in json.loads(msg.payload).get("responses", []):
                    if response.get("correlationData") == correlation:
                        result.append(response)
                        done.set()
            except (ValueError, TypeError, AttributeError):
                pass

        client.on_connect, client.on_subscribe, client.on_message = connected, on_subscribe, message
        try:
            client.connect(config.host, config.port, keepalive=10)
            client.loop_start()
            if not subscribed.wait(5):
                raise BrokerUnavailable("broker_provisioning_unavailable")
            client.publish(
                CONTROL,
                json.dumps({"commands": [{"command": command, "correlationData": correlation, **fields}]}),
                qos=1,
            ).wait_for_publish(5)
            if not done.wait(5) or not result:
                raise BrokerUnavailable("broker_provisioning_unavailable")
            return result[0]
        except (OSError, RuntimeError, ValueError):
            raise BrokerUnavailable("broker_provisioning_unavailable") from None
        finally:
            client.disconnect()
            client.loop_stop()

    def require(self, command, **fields):
        response = self.command(command, **fields)
        if response.get("error"):
            # Broker responses may contain identifying data; do not echo them.
            raise BrokerUnavailable("broker_provisioning_unavailable")
        return response.get("data", {})

    def role(self, name, permissions):
        exists = self.command("getRole", rolename=name)
        self.require("createRole" if exists.get("error") else "modifyRole", rolename=name, acls=permissions)

    def sync(self, device: Device, fleet: list[Device]):
        role = "device-" + device.id
        self.role(role, acls(*grants(device)))
        self.role("adaptor-worker", acls(*worker_grants(fleet)))
        exists = self.command("getClient", username=device.mqtt_username)
        self.require(
            "createClient" if exists.get("error") else "modifyClient",
            username=device.mqtt_username,
            password=device.mqtt_password.get_secret_value(),
            roles=[{"rolename": role, "priority": 1}],
        )
        self.require("enableClient", username=device.mqtt_username)

    def revoke(self, device: Device):
        response = self.command("getClient", username=device.mqtt_username)
        if not response.get("error"):
            self.require("disableClient", username=device.mqtt_username)


def password_hash(password):
    """Mosquitto dynsec's documented SHA-512 PBKDF2 representation."""
    import base64

    salt = secrets.token_bytes(12)
    iterations = 100000
    hashed = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, iterations)
    return {
        "password": base64.b64encode(hashed).decode(),
        "salt": base64.b64encode(salt).decode(),
        "iterations": iterations,
    }


def initial_security(settings: Settings):
    roles = [
        {"rolename": "adaptor-provisioner", "acls": acls([CONTROL], [CONTROL + "/response"])},
        {"rolename": "adaptor-worker", "acls": acls(*worker_grants(settings.devices))},
    ]
    clients = [
        {
            "username": username,
            **password_hash(password),
            "roles": [{"rolename": role, "priority": 1}],
        }
        for username, password, role in (
            (
                settings.mqtt.provisioner_username,
                settings.mqtt.provisioner_password.get_secret_value(),
                "adaptor-provisioner",
            ),
            (
                settings.mqtt.worker_username,
                settings.mqtt.worker_password.get_secret_value(),
                "adaptor-worker",
            ),
        )
    ]
    for device in settings.devices:
        role = "device-" + device.id
        roles.append({"rolename": role, "acls": acls(*grants(device))})
        clients.append(
            {
                "username": device.mqtt_username,
                **password_hash(device.mqtt_password.get_secret_value()),
                "roles": [{"rolename": role, "priority": 1}],
            }
        )
    return {
        "defaultACLAccess": {
            "publishClientSend": False,
            "publishClientReceive": False,
            "subscribe": False,
            "unsubscribe": True,
        },
        "clients": clients,
        "groups": [],
        "roles": roles,
    }
