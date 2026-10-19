import json
import math
import time

from .config import Settings
from .store import Store


class InvalidMessage(ValueError):
    """Do not echo invalid payloads: topology can contain DJI device secrets."""


def number(value, lower: float, upper: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise InvalidMessage("invalid_number")
    if not math.isfinite(value) or not lower <= value <= upper:
        raise InvalidMessage("number_out_of_range")
    return float(value)


class Ingestor:
    def __init__(self, settings: Settings, store: Store):
        self.settings, self.store = settings, store

    @property
    def subscriptions(self) -> list[str]:
        topics = []
        for device in self.settings.devices:
            topics += [f"sys/product/{device.gateway_sn}/status", f"thing/product/{device.gateway_sn}/status"]
            topics += [f"thing/product/{a.serial}/osd" for a in device.aircraft]
        return topics

    def process(self, topic: str, payload: bytes, *, retained=False, now: float | None = None):
        now = time.time() if now is None else now
        if retained:
            raise InvalidMessage("retained_message")
        if topic not in self.subscriptions or len(payload) > 262144:
            raise InvalidMessage("topic_or_size")
        try:
            body = json.loads(payload)
        except (ValueError, UnicodeDecodeError, RecursionError) as exc:
            raise InvalidMessage("invalid_json") from exc
        if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
            raise InvalidMessage("invalid_envelope")
        observed = number(body.get("timestamp"), 1_000_000_000_000, 9_999_999_999_999) / 1000
        if now - observed > self.settings.max_sample_age_seconds:
            raise InvalidMessage("stale_message")
        if observed - now > self.settings.max_future_seconds:
            raise InvalidMessage("future_message")
        parts = topic.split("/")
        serial, kind = parts[2], parts[3]
        if kind == "status":
            return self.topology(serial, body, observed, now)
        owner = self.settings.aircraft_owner(serial)
        if owner is None:
            raise InvalidMessage("unknown_aircraft")
        device, aircraft = owner
        if body.get("gateway") not in (None, device.gateway_sn):
            raise InvalidMessage("gateway_mismatch")
        data = body["data"]
        # OSD also contains battery/payload-only packets. Never fill their missing
        # coordinates from an older packet or mistake the controller's GPS for UAV GPS.
        if not {"latitude", "longitude", "height"} <= data.keys():
            self.store.increment("non_position_osd")
            return None
        lat = number(data["latitude"], -90, 90)
        lon = number(data["longitude"], -180, 180)
        if lat == 0 and lon == 0:
            raise InvalidMessage("unset_position")
        height = number(data["height"], -1000, 20000)
        metadata = {
            "source": "dji_cloud_api",
            "aircraft_model": aircraft.model,
            "aircraft_name": aircraft.name,
            "aircraft_id": aircraft.address,
            "workspace_id": str(self.settings.workspace_id),
            "altitude_reference": "WGS84_ellipsoid",
            "timestamp_unit": "milliseconds",
            "source_timestamp_ms": int(body["timestamp"]),
            "identifier_type": "opaque_dji_id_not_icao",
            "rid_compliance_asserted": False,
        }
        if aircraft.simulation:
            metadata.update(
                source="dji_cloud_api_simulation",
                simulation=True,
                simulation_run_id=str(aircraft.simulation.run_id),
            )
        for field, low, high in [
            ("elevation", -1000, 20000),
            ("horizontal_speed", 0, 200),
            ("vertical_speed", -200, 200),
            ("attitude_head", -360, 360),
            ("mode_code", 0, 100),
        ]:
            if field in data:
                metadata[field] = number(data[field], low, high)
        observation = {
            "lat_dd": lat,
            "lon_dd": lon,
            "altitude_mm": height * 1000,
            "timestamp": int(body["timestamp"]),
            "icao_address": aircraft.address,
            "traffic_source": (
                aircraft.simulation.traffic_source
                if aircraft.simulation
                else self.settings.blender.traffic_source
            ),
            "source_type": self.settings.blender.source_type,
            "metadata": metadata,
        }
        inserted = self.store.enqueue(
            device.id,
            serial,
            str(aircraft.session_id),
            observed,
            now,
            observation,
            self.settings.max_pending_samples,
        )
        if not inserted:
            self.store.increment("duplicate_osd")
        return None

    def topology(self, gateway: str, body: dict, observed: float, now: float):
        device = next((d for d in self.settings.devices if d.gateway_sn == gateway), None)
        if device is None or body.get("method") != "update_topo":
            raise InvalidMessage("unsupported_topology")
        if body.get("gateway") not in (None, gateway):
            raise InvalidMessage("gateway_mismatch")
        for field in ("tid", "bid"):
            if not isinstance(body.get(field), str) or not 1 <= len(body[field]) <= 128:
                raise InvalidMessage("invalid_correlation_id")
        children = body["data"].get("sub_devices")
        if not isinstance(children, list) or len(children) > 16:
            raise InvalidMessage("invalid_sub_devices")
        allowed = {a.serial for a in device.aircraft}
        serials = []
        for child in children:
            if not isinstance(child, dict) or child.get("sn") not in allowed:
                raise InvalidMessage("unregistered_sub_device")
            serials.append(child["sn"])
        self.store.update_topology(device.id, observed, serials)
        # Only a receipt/topology acknowledgement. No aircraft service/control commands.
        reply = {
            "tid": body["tid"],
            "bid": body["bid"],
            "timestamp": int(now * 1000),
            "method": "update_topo",
            "data": {"result": 0},
        }
        return f"sys/product/{gateway}/status_reply", reply
