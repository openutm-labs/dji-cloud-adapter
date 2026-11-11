import asyncio
import json
import time
from datetime import UTC, datetime

import httpx

from .config import Settings
from .store import Store


class DeliveryError(Exception):
    def __init__(self, reason: str, *, permanent: bool = False):
        super().__init__(reason)
        self.reason, self.permanent = reason, permanent


class BlenderClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings, self.client = settings, client
        self._token, self._expires = "", 0.0
        self._lock = asyncio.Lock()

    async def token(self, *, force=False) -> str:
        config = self.settings.blender
        if config.bearer_token.get_secret_value():
            return config.bearer_token.get_secret_value()
        if not config.oauth:
            raise DeliveryError("blender_credentials_missing")
        async with self._lock:
            if not force and self._token and self._expires > time.monotonic():
                return self._token
            oauth = config.oauth
            data = {
                "grant_type": "client_credentials",
                "client_id": oauth.client_id,
                "client_secret": oauth.client_secret.get_secret_value(),
                "scope": oauth.scope,
            }
            if oauth.audience:
                data["audience"] = oauth.audience
            try:
                response = await self.client.post(oauth.token_url, data=data)
                if response.status_code != 200:
                    raise DeliveryError(f"token_http_{response.status_code}")
                body = response.json()
                token = body["access_token"]
                if not isinstance(token, str) or not token:
                    raise ValueError("missing access token")
                duration = float(body.get("expires_in", 300))
                if not 0 < duration <= 86400:
                    raise ValueError("invalid token lifetime")
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                raise DeliveryError("token_request_failed") from exc
            self._token = token
            self._expires = time.monotonic() + max(0, duration - 30)
            return token

    async def send(self, sample: dict):
        token = await self.token()
        if time.time() - sample["observed_at"] > self.settings.max_sample_age_seconds:
            raise DeliveryError("too_old_for_live_feed", permanent=True)
        url = (
            self.settings.blender.base_url.rstrip("/")
            + f"/flight_stream/set_air_traffic/{sample['session_id']}"
        )
        observation = json.loads(sample["payload"])
        observation["metadata"]["source_event_id"] = sample["id"]
        try:
            response = await self.client.post(
                url,
                json={"observations": [observation]},
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 401 and self.settings.blender.oauth:
                token = await self.token(force=True)
                if time.time() - sample["observed_at"] > self.settings.max_sample_age_seconds:
                    raise DeliveryError("too_old_for_live_feed", permanent=True)
                response = await self.client.post(
                    url,
                    json={"observations": [observation]},
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError as exc:
            raise DeliveryError("blender_unreachable") from exc
        if response.status_code not in (201, 202):
            permanent = 400 <= response.status_code < 500 and response.status_code not in {
                401,
                403,
                408,
                409,
                425,
                429,
            }
            raise DeliveryError(f"blender_http_{response.status_code}", permanent=permanent)

    async def check_access(self) -> None:
        """Verify token acquisition and a protected read without submitting traffic."""
        token = await self.token()
        url = self.settings.blender.base_url.rstrip("/") + "/surveillance_monitoring_ops/health/"
        try:
            response = await self.client.get(url, headers={"Authorization": f"Bearer {token}"})
            if response.status_code == 401 and self.settings.blender.oauth:
                token = await self.token(force=True)
                response = await self.client.get(url, headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError as exc:
            raise DeliveryError("blender_unreachable") from exc
        if response.status_code != 200:
            raise DeliveryError(f"blender_read_http_{response.status_code}")

    async def send_operation(self, sample, operation):
        """Send measured aircraft data using Blender's operation telemetry contract."""
        config = self.settings.declarations
        if not config.enabled:
            raise DeliveryError("declarations_disabled", permanent=True)
        if not operation["start_at"] <= sample["observed_at"] < operation["end_at"]:
            raise DeliveryError("outside_operation_window", permanent=True)
        if not operation["start_at"] <= time.time() < operation["end_at"]:
            raise DeliveryError("operation_window_closed", permanent=True)
        value = json.loads(sample["payload"])
        position = {
            "lat": value["lat_dd"],
            "lng": value["lon_dd"],
            "alt": value["altitude_mm"] / 1000,
            "accuracy_h": "HAUnknown",
            "accuracy_v": "VAUnknown",
            "height": None,
        }
        if "elevation" in value["metadata"]:
            position["height"] = {"reference": "TakeoffLocation", "distance": value["metadata"]["elevation"]}
        state = {
            "timestamp": {
                "value": datetime.fromtimestamp(sample["observed_at"], UTC).isoformat(),
                "format": "RFC3339",
            },
            "timestamp_accuracy": config.timestamp_accuracy_s,
            "position": position,
            "speed_accuracy": "SAUnknown",
            "operational_status": "Undeclared",
            "speed": value["metadata"].get("horizontal_speed", 255),
            "track": 361,
            "vertical_speed": 63,
        }
        payload = json.loads(operation["payload"])
        body = {
            "observations": [
                {
                    "current_states": [state],
                    "flight_details": {
                        "id": operation["remote_id"],
                        "operator_id": payload["operator_id"],
                        "uas_id": {"serial_number": sample["aircraft_sn"]},
                        "operation_description": "DJI Cloud API telemetry; RID compliance not asserted",
                    },
                }
            ]
        }
        token = await self.token()
        url = self.settings.blender.base_url.rstrip("/") + "/flight_stream/set_telemetry"
        for attempt in range(2):
            if time.time() >= operation["end_at"]:
                raise DeliveryError("operation_window_closed", permanent=True)
            if time.time() - sample["observed_at"] > self.settings.max_sample_age_seconds:
                raise DeliveryError("too_old_for_live_feed", permanent=True)
            try:
                response = await self.client.put(url, json=body, headers={"Authorization": f"Bearer {token}"})
            except httpx.HTTPError:
                raise DeliveryError("blender_unreachable") from None
            if response.status_code == 401 and self.settings.blender.oauth and attempt == 0:
                token = await self.token(force=True)
                continue
            if response.status_code != 201:
                raise DeliveryError(
                    f"operation_telemetry_http_{response.status_code}",
                    permanent=response.status_code in {400, 404, 410, 422},
                )
            return


class Forwarder:
    def __init__(self, settings: Settings, store: Store, blender: BlenderClient, *, operations=None):
        self.settings, self.store, self.blender = settings, store, blender
        self.running = False
        self.operations = operations

    async def once(self, *, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        self.store.expire(now - self.settings.max_sample_age_seconds)
        sample = self.store.next_sample(now)
        if not sample:
            return False
        # A device removed/reassigned in configuration must not forward its old queue.
        owner = self.settings.aircraft_owner(sample["aircraft_sn"])
        if (
            not owner
            or owner[0].id != sample["device_id"]
            or str(owner[1].session_id) != sample["session_id"]
        ):
            self.store.resolve(sample["id"], "rejected", now, "device_assignment_changed")
            return True
        try:
            if sample.get("operation_id"):
                if not self.settings.declarations.enabled or not self.operations:
                    raise DeliveryError("declarations_disabled", permanent=True)
                from .declarations import DeclarationError

                async with self.operations.lock:
                    operation = self.operations.get(owner[0], sample["operation_id"])
                    try:
                        await self.operations.refresh(operation)
                    except DeclarationError:
                        raise DeliveryError("operation_status_unavailable") from None
                    operation = self.operations.get(owner[0], sample["operation_id"])
                    if operation["remote_state"] not in {2, 3, 4} or not operation["approved"]:
                        raise DeliveryError("operation_not_active", permanent=True)
                    await self.blender.send_operation(sample, operation)
            else:
                await self.blender.send(sample)
        except DeliveryError as exc:
            if exc.permanent:
                state = "expired" if exc.reason == "too_old_for_live_feed" else "rejected"
                self.store.resolve(sample["id"], state, now, exc.reason)
            else:
                attempts = sample["attempts"] + 1
                self.store.retry(sample["id"], attempts, now + min(30, 2 ** min(attempts, 5)), exc.reason)
        else:
            # HTTP acceptance is not proof that Blender's asynchronous task persisted it.
            self.store.resolve(sample["id"], "accepted", time.time())
        return True

    async def run(self):
        self.running = True
        last_prune = 0.0
        try:
            while True:
                worked = await self.once()
                now = time.time()
                if now - last_prune > 3600:
                    self.store.prune(now - self.settings.retention_days * 86400, now)
                    last_prune = now
                await asyncio.sleep(0.01 if worked else 0.5)
        finally:
            self.running = False
