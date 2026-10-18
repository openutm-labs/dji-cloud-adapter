import hashlib
import ipaddress
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Aircraft(Model):
    serial: str = Field(pattern=IDENTIFIER.pattern)
    name: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    session_id: UUID

    @property
    def address(self) -> str:
        # Blender calls the field icao_address, but this is an opaque aircraft ID,
        # not an assigned ICAO address. Keep it within the API's 24-character limit.
        return "dji-" + hashlib.sha256(self.serial.encode()).hexdigest()[:20]


class Device(Model):
    id: str = Field(pattern=IDENTIFIER.pattern)
    name: str = Field(min_length=1, max_length=100)
    gateway_sn: str = Field(pattern=IDENTIFIER.pattern)
    connection_code_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    mqtt_password: SecretStr = Field(min_length=32)
    aircraft: list[Aircraft] = Field(min_length=1)

    @field_validator("mqtt_password")
    @classmethod
    def valid_broker_password(cls, value):
        if any(c in value.get_secret_value() for c in "\r\n\x00"):
            raise ValueError("Broker passwords must not contain control characters")
        return value

    @property
    def mqtt_username(self) -> str:
        return f"pilot-{self.id}"


class Dji(Model):
    app_id: str = ""
    app_key: SecretStr = SecretStr("")
    license: SecretStr = SecretStr("")

    @property
    def configured(self) -> bool:
        return bool(self.app_id and self.app_key.get_secret_value() and self.license.get_secret_value())


class Mqtt(Model):
    host: str = "mqtt"
    port: int = Field(default=1883, ge=1, le=65535)
    public_url: str
    worker_password: SecretStr = Field(min_length=32)
    worker_username: str = Field(default="adaptor-worker", pattern=IDENTIFIER.pattern)
    client_id: str = Field(pattern=IDENTIFIER.pattern)
    tls: bool = False
    ca_file: str | None = None

    @field_validator("worker_password")
    @classmethod
    def valid_broker_password(cls, value):
        return Device.valid_broker_password(value)


class OAuth(Model):
    token_url: str
    client_id: str = Field(min_length=1)
    client_secret: SecretStr = Field(min_length=1)
    scope: str = "flightblender.read flightblender.write"
    audience: str | None = None


class Blender(Model):
    base_url: str
    bearer_token: SecretStr = SecretStr("")
    oauth: OAuth | None = None
    traffic_source: int = Field(default=11, ge=0, le=11)
    source_type: int = Field(default=0, ge=0, le=1)

    @model_validator(mode="after")
    def one_auth_mode(self):
        if self.bearer_token.get_secret_value() and self.oauth:
            raise ValueError("Choose bearer_token or oauth, not both")
        return self

    @property
    def configured(self) -> bool:
        return bool(self.bearer_token.get_secret_value() or self.oauth)


def check_url(value: str, secure_schemes: set[str], development: bool) -> None:
    if any(c.isspace() or c == "\x00" for c in value):
        raise ValueError("URLs must not contain whitespace or control characters")
    url = urlsplit(value)
    if not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("URLs must have a host and no credentials, query or fragment")
    if url.scheme in secure_schemes:
        return
    # Plaintext is restricted to loopback or Docker service names in development.
    local = url.hostname in {"localhost", "mqtt", "blender-mock", "host.docker.internal"}
    try:
        local = local or ipaddress.ip_address(url.hostname).is_loopback
    except ValueError:
        pass
    if not (development and local and url.scheme in {"http", "ws"}):
        raise ValueError("Public URLs must use HTTPS/WSS; plaintext is local-development only")


class Settings(Model):
    version: int = Field(default=1, ge=1, le=1)
    public_url: str
    workspace_id: UUID
    workspace_name: str = Field(min_length=1, max_length=100)
    admin_token: SecretStr = Field(min_length=32)
    allow_insecure_development: bool = False
    dji: Dji = Field(default_factory=Dji)
    mqtt: Mqtt
    blender: Blender
    devices: list[Device] = Field(min_length=1)
    max_sample_age_seconds: int = Field(default=60, ge=5, le=300)
    max_future_seconds: int = Field(default=15, ge=0, le=60)
    session_hours: int = Field(default=12, ge=1, le=24)
    max_pending_samples: int = Field(default=100000, ge=100, le=1000000)
    retention_days: int = Field(default=7, ge=1, le=90)

    @model_validator(mode="after")
    def validate_deployment(self):
        check_url(self.public_url, {"https"}, self.allow_insecure_development)
        if urlsplit(self.public_url).path not in {"", "/"}:
            raise ValueError("Use a dedicated hostname, not a public_url subpath")
        check_url(self.mqtt.public_url, {"wss", "ssl"}, self.allow_insecure_development)
        check_url(self.blender.base_url, {"https"}, self.allow_insecure_development)
        if urlsplit(self.blender.base_url).path not in {"", "/"}:
            raise ValueError("Blender base_url must not contain a path")
        if self.blender.oauth:
            check_url(self.blender.oauth.token_url, {"https"}, self.allow_insecure_development)
        identifiers = [d.id for d in self.devices]
        gateways = [d.gateway_sn for d in self.devices]
        aircraft = [a.serial for d in self.devices for a in d.aircraft]
        sessions = [a.session_id for d in self.devices for a in d.aircraft]
        for values in (identifiers, gateways, aircraft, sessions):
            if len(values) != len(set(values)):
                raise ValueError("Device IDs, gateways, aircraft and session IDs must be unique")
        if set(gateways) & set(aircraft):
            raise ValueError("A controller cannot also be an aircraft")
        if self.mqtt.worker_username in {d.mqtt_username for d in self.devices}:
            raise ValueError("Worker and controller MQTT identities must differ")
        return self

    def device(self, device_id: str) -> Device | None:
        return next((d for d in self.devices if d.id == device_id), None)

    def aircraft_owner(self, serial: str) -> tuple[Device, Aircraft] | None:
        for d in self.devices:
            for a in d.aircraft:
                if a.serial == serial:
                    return d, a
        return None


def load_settings(path: Path) -> Settings:
    return Settings.model_validate(json.loads(path.read_text()))
