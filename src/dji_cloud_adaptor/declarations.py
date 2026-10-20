"""Optional, device-scoped declaration planning and durable Blender lifecycle.

Creation is at-most-once per saved plan. An ambiguous response is reconciled by
client reference; it is never retried as a second POST.
"""

import asyncio
import hashlib
import json
import math
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
from pydantic import Field, field_validator

from .blender import BlenderClient, DeliveryError
from .config import Model

STATES = {
    0: "not_submitted",
    1: "accepted",
    2: "activated",
    3: "nonconforming",
    4: "contingent",
    5: "ended",
    6: "withdrawn",
    7: "cancelled",
    8: "rejected",
}
TERMINAL = {5, 6, 7, 8}


def iso(seconds):
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace("+00:00", "Z")


class Plan(Model):
    request_id: UUID
    aircraft_sn: str = Field(min_length=1, max_length=64)
    pilot_id: str = Field(min_length=1, max_length=64)
    radius_m: float = Field(ge=10, le=10000, allow_inf_nan=False)
    height_m: float = Field(gt=0, le=1000, allow_inf_nan=False)
    start: datetime
    duration_minutes: int = Field(ge=1, le=1440)
    on_ground: bool

    @field_validator("start")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("An explicit timezone is required")
        return value


class Action(Model):
    action: str = Field(pattern="^(submit|refresh|activate|finish|cancel|discard)$")


class DeclarationError(Exception):
    def __init__(self, reason, status=409):
        self.reason, self.status = reason, status


class Operations:
    def __init__(self, settings, store, blender: BlenderClient):
        self.settings, self.store, self.blender = settings, store, blender
        self.lock = asyncio.Lock()
        self.running = False
        # Called once at application startup, never by CLI readers of the database.
        with store.connection() as db:
            db.execute("UPDATE operations SET stage='uncertain' WHERE stage='submitting'")

    def pilots(self, device):
        return [p for p in self.settings.declarations.pilots if device.id in p.device_ids]

    async def run(self):
        self.running = True
        try:
            while True:
                async with self.lock:
                    with self.store.connection() as db:
                        rows = db.execute(
                            "SELECT * FROM operations WHERE remote_id IS NOT NULL "
                            "AND stage NOT IN ('closed','discarded')"
                        ).fetchall()
                    for row in rows:
                        try:
                            await self.refresh(dict(row))
                        except (DeclarationError, DeliveryError):
                            self.save(row["id"], checked_at=0, error="declaration_service_unavailable")
                await asyncio.sleep(10)
        finally:
            self.running = False

    def get(self, device, operation_id):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT * FROM operations WHERE id=? AND device_id=?", (str(operation_id), device.id)
            ).fetchone()
        if not row:
            raise DeclarationError("operation_not_found", 404)
        return dict(row)

    def save(self, operation_id, **values):
        allowed = {"stage", "remote_id", "remote_state", "approved", "error", "checked_at", "bind_from"}
        assert values and values.keys() <= allowed
        with self.store.connection() as db:
            db.execute(
                "UPDATE operations SET " + ",".join(f"{k}=?" for k in values) + " WHERE id=?",
                (*values.values(), operation_id),
            )

    def view(self, op):
        with self.store.connection() as db:
            counts = dict(
                db.execute(
                    "SELECT state,COUNT(*) FROM samples WHERE operation_id=? GROUP BY state", (op["id"],)
                )
            )
            accepted = db.execute(
                "SELECT MAX(accepted_at) FROM samples WHERE operation_id=?", (op["id"],)
            ).fetchone()[0]
        payload = json.loads(op["payload"])
        return {
            "id": op["id"],
            "aircraft_sn": op["aircraft_sn"],
            "pilot_name": op["pilot_name"],
            "stage": op["stage"],
            "declaration_id": op["remote_id"],
            "state": STATES.get(op["remote_state"], "unknown"),
            "approved": bool(op["approved"]),
            "error": op["error"],
            "checked_at": op["checked_at"],
            "start": payload["start_datetime"],
            "end": payload["end_datetime"],
            "plan": json.loads(op["plan"]),
            "geometry": payload["flight_declaration_geo_json"],
            "telemetry_counts": counts,
            "last_api_acceptance": accepted,
        }

    def options(self, device):
        config = self.settings.declarations
        if not config.enabled:
            return {"enabled": False}
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT * FROM operations WHERE device_id=? ORDER BY created_at DESC LIMIT 20", (device.id,)
            ).fetchall()
        return {
            "enabled": True,
            "pilots": [{"id": p.id, "name": p.name} for p in self.pilots(device)],
            "aircraft": [{"serial": a.serial, "name": a.name} for a in device.aircraft if not a.simulation],
            "limits": {
                "radius_m": config.max_radius_m,
                "height_m": config.max_height_m,
                "duration_minutes": config.max_duration_minutes,
            },
            "request_id": str(uuid4()),
            "server_time": time.time(),
            "operations": [self.view(dict(row)) for row in rows],
        }

    def prepare(self, device, plan):
        now = time.time()
        digest = hashlib.sha256(plan.model_dump_json().encode()).hexdigest()
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM operations WHERE id=?", (str(plan.request_id),)).fetchone()
            if existing:
                if existing["device_id"] != device.id or existing["request_hash"] != digest:
                    raise DeclarationError("plan_conflict")
                return self.view(dict(existing))
            config = self.settings.declarations
            pilot = next((p for p in self.pilots(device) if p.id == plan.pilot_id), None)
            aircraft = next(
                (a for a in device.aircraft if a.serial == plan.aircraft_sn and not a.simulation), None
            )
            if not pilot or not aircraft:
                raise DeclarationError("plan_not_allowed", 403)
            if not plan.on_ground:
                raise DeclarationError("ground_confirmation_required", 422)
            if (
                plan.radius_m > config.max_radius_m
                or plan.height_m > config.max_height_m
                or plan.duration_minutes > config.max_duration_minutes
            ):
                raise DeclarationError("plan_limits", 422)
            start = plan.start.timestamp()
            if not now + 15 <= start <= now + 86400:
                raise DeclarationError("plan_start", 422)
            if db.execute(
                "SELECT 1 FROM operations WHERE aircraft_sn=? AND stage NOT IN ('closed','discarded')",
                (aircraft.serial,),
            ).fetchone():
                raise DeclarationError("operation_already_open")
            row = db.execute(
                "SELECT * FROM samples WHERE device_id=? AND aircraft_sn=? ORDER BY observed_at DESC LIMIT 1",
                (device.id, aircraft.serial),
            ).fetchone()
            if not row or not 0 <= now - row["observed_at"] <= 10:
                raise DeclarationError("ground_sample_required")
            observation = json.loads(row["payload"])
            elevation = observation["metadata"].get("elevation")
            if elevation is None or abs(elevation) > 2:
                raise DeclarationError("ground_sample_required")
            lat, lon = observation["lat_dd"], observation["lon_dd"]
            if abs(lat) > 80 or abs(lon) > 179.8:
                raise DeclarationError("area_not_supported", 422)
            # Circumscribe the requested circle, rather than under-declaring its edges.
            radius = plan.radius_m / math.cos(math.pi / 32) + 1
            ring = []
            for index in range(32):
                bearing = -index * 2 * math.pi / 32
                angular = radius / 6371008.8
                phi, lam = math.radians(lat), math.radians(lon)
                phi2 = math.asin(
                    math.sin(phi) * math.cos(angular) + math.cos(phi) * math.sin(angular) * math.cos(bearing)
                )
                lam2 = lam + math.atan2(
                    math.sin(bearing) * math.sin(angular) * math.cos(phi),
                    math.cos(angular) - math.sin(phi) * math.sin(phi2),
                )
                ring.append([math.degrees(lam2), math.degrees(phi2)])
            if any(abs(point[0]) >= 180 for point in ring):
                raise DeclarationError("area_not_supported", 422)
            ring.append(ring[0])
            takeoff = observation["altitude_mm"] / 1000 - elevation
            properties = {
                "min_altitude": {"meters": takeoff - config.altitude_margin_m, "datum": "W84"},
                "max_altitude": {
                    "meters": takeoff + plan.height_m + config.altitude_margin_m,
                    "datum": "W84",
                },
                "source": "openutm-dji-cloud-adapter",
                "client_ref": str(plan.request_id),
                "request_hash": digest,
                "pilot_id": pilot.id,
                "operator_id": config.operator_id,
                "aircraft_sn": aircraft.serial,
                "takeoff_reference": {"lat": lat, "lon": lon, "altitude_w84_m": takeoff},
            }
            payload = {
                "originating_party": config.originating_party,
                "operator_id": config.operator_id,
                "submitted_by": pilot.id,
                "aircraft_id": aircraft.serial,
                "type_of_operation": 1,
                "expect_telemetry": True,
                "start_datetime": iso(start),
                "end_datetime": iso(start + plan.duration_minutes * 60),
                "flight_declaration_geo_json": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {"type": "Polygon", "coordinates": [ring]},
                            "properties": properties,
                        }
                    ],
                },
            }
            db.execute(
                "INSERT INTO operations(id,device_id,aircraft_sn,pilot_name,request_hash,plan,payload,"
                "created_at,start_at,end_at,stage) VALUES (?,?,?,?,?,?,?,?,?,?,'prepared')",
                (
                    str(plan.request_id),
                    device.id,
                    aircraft.serial,
                    pilot.name,
                    digest,
                    plan.model_dump_json(),
                    json.dumps(payload),
                    now,
                    start,
                    start + plan.duration_minutes * 60,
                ),
            )
        return self.view(self.get(device, plan.request_id))

    async def request(self, method, path, *, body=None, params=None):
        token = await self.blender.token()
        try:
            response = await self.blender.client.request(
                method,
                self.settings.blender.base_url.rstrip("/") + path,
                json=body,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 401 and self.settings.blender.oauth:
                token = await self.blender.token(force=True)
                response = await self.blender.client.request(
                    method,
                    self.settings.blender.base_url.rstrip("/") + path,
                    json=body,
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError:
            raise DeclarationError("declaration_service_unavailable", 503) from None
        if response.status_code not in (200, 201):
            raise DeclarationError("declaration_service_unavailable", 503)
        try:
            return response.json()
        except ValueError:
            raise DeclarationError("declaration_response_invalid", 502) from None

    def matches(self, op, remote):
        if not isinstance(remote, dict):
            return False
        try:
            geo = remote["flight_declaration_raw_geojson"]
            if isinstance(geo, str):
                geo = json.loads(geo)
            expected = json.loads(op["payload"])
            return (
                geo == expected["flight_declaration_geo_json"]
                and datetime.fromisoformat(remote["start_datetime"].replace("Z", "+00:00")).timestamp()
                == op["start_at"]
                and datetime.fromisoformat(remote["end_datetime"].replace("Z", "+00:00")).timestamp()
                == op["end_at"]
                and remote["originating_party"] == expected["originating_party"]
                and remote["submitted_by"] == expected["submitted_by"]
            )
        except (KeyError, ValueError, TypeError, AttributeError):
            return False

    def record(self, op, remote, *, verified=False):
        try:
            remote_id = str(UUID(remote["id"]))
            state, approved = remote["state"], remote["is_approved"]
            if type(state) is not int or state not in STATES or type(approved) not in (bool, int):
                raise ValueError()
            if approved not in (True, False, 0, 1):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise DeclarationError("declaration_response_invalid", 502) from None
        if op["remote_id"] and remote_id != op["remote_id"]:
            raise DeclarationError("declaration_response_invalid", 502)
        stage = (
            "closed" if state in TERMINAL else ("finishing" if op["stage"] == "finishing" else "submitted")
        )
        self.save(
            op["id"],
            remote_id=remote_id,
            remote_state=state,
            approved=int(approved),
            checked_at=time.time(),
            stage=stage,
            error=None,
        )
        if verified and state in {2, 3, 4} and not op["bind_from"] and stage != "finishing":
            self.save(op["id"], bind_from=time.time())

    async def refresh(self, op):
        try:
            await self._refresh(op)
        except (DeclarationError, DeliveryError):
            self.save(op["id"], checked_at=0, error="declaration_service_unavailable")
            raise

    async def _refresh(self, op):
        if op["remote_id"]:
            remote = await self.request(
                "GET", f"/flight_declaration_ops/flight_declaration/{op['remote_id']}"
            )
            if not self.matches(op, remote):
                raise DeclarationError("declaration_response_invalid", 502)
            self.record(op, remote, verified=True)
        elif op["stage"] in {"uncertain", "submitting"}:
            # Never follow URLs supplied by an upstream response (which could leak OAuth).
            dates = {
                "start_date": (datetime.fromtimestamp(op["start_at"], UTC) - timedelta(days=1)).date(),
                "end_date": (datetime.fromtimestamp(op["end_at"], UTC) + timedelta(days=1)).date(),
            }
            matches = []
            for page in range(1, 21):
                result = await self.request(
                    "GET",
                    "/flight_declaration_ops/flight_declaration",
                    params={**dates, "page": page, "page_size": 100},
                )
                if not isinstance(result, dict) or not isinstance(result.get("results"), list):
                    raise DeclarationError("declaration_response_invalid", 502)
                matches.extend(row for row in result["results"] if self.matches(op, row))
                count = result.get("count")
                if type(count) is not int or count < 0:
                    raise DeclarationError("declaration_response_invalid", 502)
                if page * 100 >= count:
                    break
            else:
                raise DeclarationError("reconciliation_limit", 409)
            if len(matches) == 1:
                self.record(op, matches[0], verified=True)
            elif len(matches) > 1:
                raise DeclarationError("declaration_duplicate", 409)
            # No match is not proof of failure: leave the plan uncertain and do not POST again.

    async def act(self, device, operation_id, action):
        async with self.lock:
            op = self.get(device, operation_id)
            owner = self.settings.aircraft_owner(op["aircraft_sn"])
            if not owner or owner[0].id != device.id or owner[1].simulation:
                raise DeclarationError("plan_not_allowed", 403)
            if action in {"submit", "activate"} and json.loads(op["plan"])["pilot_id"] not in {
                p.id for p in self.pilots(device)
            }:
                raise DeclarationError("plan_not_allowed", 403)
            if action == "discard":
                if op["stage"] != "prepared":
                    raise DeclarationError("discard_not_allowed")
                self.save(op["id"], stage="discarded")
            elif action == "submit" and op["stage"] == "prepared":
                if op["start_at"] <= time.time():
                    raise DeclarationError("plan_start", 422)
                # Acquire credentials before marking a possibly-sent request.
                try:
                    await self.blender.token()
                except DeliveryError:
                    raise DeclarationError("declaration_service_unavailable", 503) from None
                self.save(op["id"], stage="submitting")
                try:
                    result = await self.request(
                        "POST",
                        "/flight_declaration_ops/set_flight_declaration",
                        body=json.loads(op["payload"]),
                    )
                    self.record(op, result)
                except (DeclarationError, DeliveryError):
                    self.save(op["id"], stage="uncertain", error="submission_uncertain")
                # Creation response is provisional; refresh verifies identity and authoritative state.
                op = self.get(device, operation_id)
                if op["remote_id"]:
                    await self.refresh(op)
            elif action in {"refresh", "submit"}:
                await self.refresh(op)
            else:
                if op["stage"] in {"prepared", "discarded", "uncertain"}:
                    raise DeclarationError("transition_not_allowed")
                await self.refresh(op)
                op = self.get(device, operation_id)
                state, now = op["remote_state"], time.time()
                if action == "activate":
                    if state == 2 and op["stage"] != "finishing":
                        return self.view(op)
                    if state != 1 or not op["approved"] or not op["start_at"] <= now < op["end_at"]:
                        raise DeclarationError("activation_not_allowed")
                    target = 2
                elif action == "finish":
                    if state == 5:
                        return self.view(op)
                    if state not in {2, 3, 4}:
                        raise DeclarationError("transition_not_allowed")
                    self.save(op["id"], stage="finishing")
                    self.store.expire(now - self.settings.max_sample_age_seconds)
                    with self.store.connection() as db:
                        pending = db.execute(
                            "SELECT COUNT(*) FROM samples WHERE operation_id=? AND state='pending'",
                            (op["id"],),
                        ).fetchone()[0]
                    if pending:
                        return self.view(self.get(device, operation_id))
                    target = 5
                elif action == "cancel":
                    if state in {6, 7}:
                        return self.view(op)
                    if state not in {0, 1}:
                        raise DeclarationError("transition_not_allowed")
                    target = 6 if state == 0 else 7
                else:
                    raise DeclarationError("transition_not_allowed")
                # Read-before-write also makes a retry after a lost state response safe.
                self.save(op["id"], checked_at=0, error="transition_unconfirmed")
                await self.request(
                    "PUT",
                    f"/flight_declaration_ops/flight_declaration_state/{op['remote_id']}",
                    body={"state": target, "submitted_by": json.loads(op["payload"])["submitted_by"]},
                )
                await self.refresh(self.get(device, operation_id))
                op = self.get(device, operation_id)
                if op["remote_state"] != target:
                    raise DeclarationError("transition_not_confirmed")
                if target == 2:
                    self.save(op["id"], bind_from=time.time())
            return self.view(self.get(device, operation_id))
