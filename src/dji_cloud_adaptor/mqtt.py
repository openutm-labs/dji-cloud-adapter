import json
import logging
import sqlite3

import paho.mqtt.client as mqtt

from .config import Settings
from .store import QueueFull, Store
from .telemetry import Ingestor, InvalidMessage

logger = logging.getLogger(__name__)


class MqttReceiver:
    def __init__(self, settings: Settings, store: Store):
        self.settings, self.store = settings, store
        self.ingestor = Ingestor(settings, store)
        self.connected = False
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt.client_id,
            clean_session=False,
            manual_ack=True,
        )
        self.client.username_pw_set(
            settings.mqtt.worker_username, settings.mqtt.worker_password.get_secret_value()
        )
        if settings.mqtt.tls:
            self.client.tls_set(ca_certs=settings.mqtt.ca_file)
        self.client.reconnect_delay_set(1, 30)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message

    def start(self):
        self.client.connect_async(self.settings.mqtt.host, self.settings.mqtt.port, keepalive=30)
        self.client.loop_start()

    def stop(self):
        self.client.disconnect()
        self.client.loop_stop()
        self.connected = False

    def on_connect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        if not reason_code.is_failure:
            # Exact allow-listed topics, never a fleet-wide '#' subscription.
            client.subscribe([(topic, 1) for topic in self.ingestor.subscriptions])

    def on_subscribe(self, client, userdata, mid, reason_codes, properties):
        self.connected = bool(reason_codes) and all(not reason.is_failure for reason in reason_codes)

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False

    def on_message(self, client, userdata, message):
        try:
            reply = self.ingestor.process(message.topic, message.payload, retained=message.retain)
            if reply:
                topic, payload = reply
                client.publish(topic, json.dumps(payload), qos=1, retain=False)
        except InvalidMessage as exc:
            try:
                self.store.increment(f"rejected_{exc}")
            except sqlite3.Error:
                logger.error("Cannot record message rejection")
                return
        except (QueueFull, sqlite3.Error):
            # Do not acknowledge a QoS1 message that wasn't committed. The broker
            # retains it for session recovery. QoS0 has no delivery guarantee.
            logger.error("Outbox unavailable; message not acknowledged")
            return
        except Exception:
            # Payloads, topics, secrets and coordinates must not enter normal logs.
            logger.error("MQTT processing failed; message not acknowledged")
            return
        if message.qos:
            client.ack(message.mid, message.qos)
