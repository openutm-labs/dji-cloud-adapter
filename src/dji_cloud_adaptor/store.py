import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class QueueFull(Exception):
    pass


class Store:
    """A single-process durable outbox. One Uvicorn worker owns each database."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS samples (
                    id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    aircraft_sn TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    observed_at REAL NOT NULL,
                    received_at REAL NOT NULL,
                    payload TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt REAL NOT NULL DEFAULT 0,
                    error TEXT,
                    accepted_at REAL
                );
                CREATE INDEX IF NOT EXISTS samples_due ON samples(state, next_attempt);
                CREATE INDEX IF NOT EXISTS samples_device ON samples(device_id, received_at);
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    credential_revision TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    activated INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS topology (
                    device_id TEXT PRIMARY KEY,
                    observed_at REAL NOT NULL,
                    aircraft TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS counters (
                    name TEXT PRIMARY KEY,
                    value INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    aircraft_sn TEXT NOT NULL,
                    pilot_name TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    plan TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    start_at REAL NOT NULL,
                    end_at REAL NOT NULL,
                    stage TEXT NOT NULL,
                    remote_id TEXT,
                    remote_state INTEGER,
                    approved INTEGER DEFAULT 0,
                    checked_at REAL,
                    bind_from REAL,
                    error TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS operations_open_aircraft ON operations(aircraft_sn)
                    WHERE stage NOT IN ('closed','discarded');
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(samples)")}
            if "operation_id" not in columns:
                db.execute("ALTER TABLE samples ADD COLUMN operation_id TEXT")
            db.execute("CREATE INDEX IF NOT EXISTS samples_operation ON samples(operation_id,state)")
        path.chmod(0o600)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA synchronous=FULL")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def increment(self, name: str):
        with self.connection() as db:
            db.execute(
                "INSERT INTO counters(name,value) VALUES (?,1) ON CONFLICT(name) DO UPDATE SET value=value+1",
                (name,),
            )

    def enqueue(
        self,
        device_id: str,
        serial: str,
        session_id: str,
        observed_at: float,
        received_at: float,
        payload: dict,
        capacity: int,
        *,
        associate_operation: bool = False,
    ) -> bool:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        sample_id = hashlib.sha256(f"{serial}|{encoded}".encode()).hexdigest()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM samples WHERE id=?", (sample_id,)).fetchone():
                return False
            count = db.execute("SELECT COUNT(*) FROM samples WHERE state='pending'").fetchone()[0]
            if count >= capacity:
                raise QueueFull("Durable outbox is full")
            operation = None
            if associate_operation:
                operation = db.execute(
                    "SELECT id FROM operations WHERE device_id=? AND aircraft_sn=? "
                    "AND stage='submitted' AND remote_state IN (2,3,4) AND approved=1 "
                    "AND bind_from<=? AND start_at<=? AND end_at>? AND checked_at>=?",
                    (device_id, serial, observed_at, observed_at, observed_at, received_at - 30),
                ).fetchone()
            db.execute(
                "INSERT INTO samples(id,device_id,aircraft_sn,session_id,observed_at,received_at,"
                "payload,operation_id) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    sample_id,
                    device_id,
                    serial,
                    session_id,
                    observed_at,
                    received_at,
                    encoded,
                    operation[0] if operation else None,
                ),
            )
        return True

    def next_sample(self, now: float) -> dict | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM samples WHERE state='pending' AND next_attempt<=? "
                "ORDER BY observed_at LIMIT 1",
                (now,),
            ).fetchone()
            return dict(row) if row else None

    def resolve(self, sample_id: str, state: str, now: float, error: str | None = None):
        with self.connection() as db:
            db.execute(
                "UPDATE samples SET state=?,error=?,accepted_at=? WHERE id=?",
                (state, error, now if state == "accepted" else None, sample_id),
            )

    def retry(self, sample_id: str, attempts: int, next_attempt: float, error: str):
        with self.connection() as db:
            db.execute(
                "UPDATE samples SET attempts=?,next_attempt=?,error=? WHERE id=?",
                (attempts, next_attempt, error, sample_id),
            )

    def expire(self, cutoff: float):
        with self.connection() as db:
            db.execute(
                "UPDATE samples SET state='expired',error='too_old_for_live_feed' "
                "WHERE state='pending' AND observed_at<?",
                (cutoff,),
            )

    def prune(self, cutoff: float, now: float):
        with self.connection() as db:
            db.execute("DELETE FROM samples WHERE state!='pending' AND received_at<?", (cutoff,))
            db.execute("DELETE FROM sessions WHERE expires_at<?", (now,))

    def create_session(self, token: str, device_id: str, revision: str, expires_at: float):
        with self.connection() as db:
            db.execute(
                "INSERT INTO sessions(token_hash,device_id,credential_revision,expires_at) VALUES (?,?,?,?)",
                (hashlib.sha256(token.encode()).hexdigest(), device_id, revision, expires_at),
            )

    def session(self, token: str, now: float) -> dict | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM sessions WHERE token_hash=? AND expires_at>?",
                (hashlib.sha256(token.encode()).hexdigest(), now),
            ).fetchone()
            return dict(row) if row else None

    def activate(self, token_hash: str):
        with self.connection() as db:
            db.execute("UPDATE sessions SET activated=1 WHERE token_hash=?", (token_hash,))

    def delete_session(self, token: str):
        with self.connection() as db:
            db.execute(
                "DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),)
            )

    def update_topology(self, device_id: str, observed_at: float, aircraft: list[str]):
        with self.connection() as db:
            db.execute(
                "INSERT INTO topology(device_id,observed_at,aircraft) VALUES (?,?,?) "
                "ON CONFLICT(device_id) DO UPDATE SET observed_at=excluded.observed_at,"
                "aircraft=excluded.aircraft WHERE excluded.observed_at>=topology.observed_at",
                (device_id, observed_at, json.dumps(aircraft)),
            )

    def status(self, device_id: str | None = None) -> dict:
        where = " WHERE device_id=?" if device_id else ""
        params = (device_id,) if device_id else ()
        with self.connection() as db:
            counts = dict(
                db.execute("SELECT state,COUNT(*) FROM samples" + where + " GROUP BY state", params)
            )
            row = db.execute(
                "SELECT MAX(received_at),MAX(accepted_at),MAX(observed_at) FROM samples" + where,
                params,
            ).fetchone()
            latest_error = db.execute(
                "SELECT error FROM samples" + where + " ORDER BY received_at DESC LIMIT 1",
                params,
            ).fetchone()
            result = {
                "counts": counts,
                "last_received_at": row[0],
                "last_accepted_at": row[1],
                "last_observed_at": row[2],
                "last_error": latest_error[0] if latest_error else None,
            }
            if not device_id:
                result["counters"] = dict(db.execute("SELECT name,value FROM counters"))
            return result
