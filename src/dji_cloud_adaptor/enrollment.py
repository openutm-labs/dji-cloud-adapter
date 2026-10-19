"""Invitation-based self enrollment. All device secrets stay in the private SQLite volume."""

import hashlib
import json
import secrets
import sqlite3
import time
from uuid import uuid4

from pydantic import SecretStr

from .config import Aircraft, Device
from .store import Store


class EnrollmentError(Exception):
    pass


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def encode(value):
    return value.get_secret_value() if isinstance(value, SecretStr) else str(value)


class EnrollmentStore:
    def __init__(self, store: Store):
        self.store = store
        with store.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS enrollment_invites (
                    code_hash TEXT PRIMARY KEY, label TEXT NOT NULL,
                    expires_at REAL NOT NULL, device_id TEXT, revoked INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS enrollment_sessions (
                    token_hash TEXT PRIMARY KEY, invite_hash TEXT NOT NULL, expires_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS enrolled_devices (
                    id TEXT PRIMARY KEY, gateway_sn TEXT NOT NULL UNIQUE,
                    aircraft_sn TEXT NOT NULL UNIQUE, device_json TEXT NOT NULL,
                    connection_code TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending', created_at REAL NOT NULL
                );
            """)

    def invite(self, label, hours, *, now=None):
        now = time.time() if now is None else now
        code = "invite." + secrets.token_urlsafe(32)
        expires = now + hours * 3600
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO enrollment_invites(code_hash,label,expires_at) VALUES(?,?,?)",
                (digest(code), label, expires),
            )
        return code, expires

    def revoke_invitation(self, code):
        with self.store.connection() as db:
            db.execute("UPDATE enrollment_invites SET revoked=1 WHERE code_hash=?", (digest(code),))

    def start(self, code, *, now=None):
        now = time.time() if now is None else now
        token = secrets.token_urlsafe(32)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            invite = db.execute(
                "SELECT * FROM enrollment_invites WHERE code_hash=?", (digest(code),)
            ).fetchone()
            if not invite or invite["revoked"] or invite["expires_at"] <= now:
                raise EnrollmentError("invalid_invitation")
            if invite["device_id"]:
                device = db.execute(
                    "SELECT state FROM enrolled_devices WHERE id=?", (invite["device_id"],)
                ).fetchone()
                if not device or device["state"] != "pending":
                    raise EnrollmentError("invitation_used")
            expires = min(invite["expires_at"], now + 1200)
            db.execute("DELETE FROM enrollment_sessions WHERE expires_at<=?", (now,))
            db.execute(
                "INSERT INTO enrollment_sessions VALUES(?,?,?)", (digest(token), digest(code), expires)
            )
        return token, expires

    def session(self, token, *, now=None):
        now = time.time() if now is None else now
        with self.store.connection() as db:
            row = db.execute(
                """SELECT i.*,s.expires_at AS session_expires FROM enrollment_sessions s
                JOIN enrollment_invites i ON i.code_hash=s.invite_hash
                WHERE s.token_hash=? AND s.expires_at>? AND i.expires_at>? AND i.revoked=0""",
                (digest(token), now, now),
            ).fetchone()
            if not row:
                raise EnrollmentError("enrollment_session_expired")
            return dict(row)

    def reserve(self, token, gateway, aircraft_serial, model, name, max_devices, *, now=None):
        now = time.time() if now is None else now
        session = self.session(token, now=now)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            invitation = db.execute(
                "SELECT * FROM enrollment_invites WHERE code_hash=?", (session["code_hash"],)
            ).fetchone()
            if not invitation or invitation["revoked"] or invitation["expires_at"] <= now:
                raise EnrollmentError("invalid_invitation")
            if invitation["device_id"]:
                row = db.execute(
                    "SELECT * FROM enrolled_devices WHERE id=?", (invitation["device_id"],)
                ).fetchone()
                if not row or row["state"] == "revoked":
                    raise EnrollmentError("device_revoked")
                device = Device.model_validate_json(row["device_json"])
                if (
                    device.gateway_sn != gateway
                    or device.aircraft[0].serial != aircraft_serial
                    or device.aircraft[0].model != model
                ):
                    raise EnrollmentError("invitation_used")
                return device
            count = db.execute("SELECT COUNT(*) FROM enrolled_devices WHERE state!='revoked'").fetchone()[0]
            if count >= max_devices:
                raise EnrollmentError("enrollment_capacity")
            identifier = uuid4().hex[:12]
            code = identifier + "." + secrets.token_urlsafe(32)
            device = Device(
                id=identifier,
                name=name or model + " controller",
                gateway_sn=gateway,
                connection_code_sha256=digest(code),
                mqtt_password=secrets.token_urlsafe(32),
                aircraft=[Aircraft(serial=aircraft_serial, model=model, name=model, session_id=uuid4())],
            )
            try:
                db.execute(
                    "INSERT INTO enrolled_devices VALUES(?,?,?,?,?,?,?)",
                    (
                        device.id,
                        gateway,
                        aircraft_serial,
                        json.dumps(device.model_dump(), default=encode),
                        code,
                        "pending",
                        now,
                    ),
                )
            except sqlite3.IntegrityError:
                raise EnrollmentError("equipment_already_registered") from None
            db.execute(
                "UPDATE enrollment_invites SET device_id=? WHERE code_hash=?",
                (device.id, session["code_hash"]),
            )
            return device

    def devices(self, state="active"):
        with self.store.connection() as db:
            return [
                Device.model_validate_json(row[0])
                for row in db.execute(
                    "SELECT device_json FROM enrolled_devices WHERE state=? ORDER BY created_at", (state,)
                )
            ]

    def activate(self, device_id):
        with self.store.connection() as db:
            db.execute(
                "UPDATE enrolled_devices SET state='active' WHERE id=? AND state='pending'", (device_id,)
            )

    def code(self, device_id):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT connection_code FROM enrolled_devices WHERE id=? AND state='active'", (device_id,)
            ).fetchone()
            if not row:
                raise EnrollmentError("device_not_active")
            return row[0]

    def revoke(self, device_id):
        with self.store.connection() as db:
            db.execute("UPDATE enrolled_devices SET state='revoked' WHERE id=?", (device_id,))
            db.execute("UPDATE enrollment_invites SET revoked=1 WHERE device_id=?", (device_id,))

    def is_revoked(self, device_id):
        with self.store.connection() as db:
            return bool(
                db.execute(
                    "SELECT 1 FROM enrolled_devices WHERE id=? AND state='revoked'", (device_id,)
                ).fetchone()
            )
