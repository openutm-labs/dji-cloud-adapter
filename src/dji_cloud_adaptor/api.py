import asyncio
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .blender import BlenderClient, Forwarder
from .config import IDENTIFIER, Settings, load_settings
from .mqtt import MqttReceiver
from .store import Store

WEB = Path(os.environ.get("ADAPTOR_WEB", str(Path(__file__).parent / "web")))


class Login(BaseModel):
    code: str = Field(min_length=20, max_length=150)


class Activate(BaseModel):
    gateway_sn: str = Field(pattern=IDENTIFIER.pattern)


def create_app(settings: Settings, store: Store, *, background=True, transport=None) -> FastAPI:
    receiver = MqttReceiver(settings, store)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, transport=transport) as client:
            forwarder = Forwarder(settings, store, BlenderClient(settings, client))
            app.state.forwarder = forwarder
            task = None
            if background:
                receiver.start()
                task = asyncio.create_task(forwarder.run())
            try:
                yield
            finally:
                if task:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                    await asyncio.to_thread(receiver.stop)

    app = FastAPI(title="DJI Cloud Adaptor", lifespan=lifespan, docs_url=None, openapi_url=None)
    app.state.receiver = receiver
    # This process is the rate-limit boundary; deploy exactly one worker per database.
    attempts = defaultdict(deque)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # FastAPI's default response echoes invalid input, including connection codes.
        return JSONResponse({"detail": "invalid_fields"}, status_code=422)

    @app.middleware("http")
    async def headers(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") != settings.public_url.rstrip("/"):
                return JSONResponse({"detail": "origin_not_allowed"}, status_code=403)
        length = request.headers.get("content-length", "0")
        if len(length) > 8 or not length.isdigit() or int(length) > 16384:
            return JSONResponse({"detail": "request_too_large"}, status_code=413)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        return response

    def bearer(request: Request) -> str:
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer ") or len(authorization) > 1024:
            raise HTTPException(401, "sign_in_required")
        return authorization[7:]

    def session(request: Request, *, activated=True):
        token = bearer(request)
        row = store.session(token, time.time())
        device = settings.device(row["device_id"]) if row else None
        if not device or not hmac.compare_digest(row["credential_revision"], device.connection_code_sha256):
            raise HTTPException(401, "sign_in_required")
        if activated and not row["activated"]:
            raise HTTPException(403, "controller_verification_required")
        return row, device

    def device_config(row, device):
        return {
            "public_url": settings.public_url.rstrip("/"),
            "workspace_id": str(settings.workspace_id),
            "workspace_name": settings.workspace_name,
            "device_name": device.name,
            "expires_at": row["expires_at"],
            "mqtt": {
                "host": settings.mqtt.public_url,
                "username": device.mqtt_username,
                "password": device.mqtt_password.get_secret_value(),
            },
        }

    @app.get("/")
    async def home():
        return FileResponse(WEB / "index.html")

    @app.get("/healthz")
    async def health():
        with store.connection() as db:
            db.execute("SELECT 1")
        return {"status": "ok"}

    @app.get("/readyz")
    async def ready():
        forwarder = getattr(app.state, "forwarder", None)
        checks = {
            "mqtt_connected": receiver.connected,
            "forwarder_running": bool(forwarder and forwarder.running),
            "dji_configured": settings.dji.configured,
            "blender_configured": settings.blender.configured,
        }
        return JSONResponse(
            {"ready": all(checks.values()), "checks": checks},
            status_code=200 if all(checks.values()) else 503,
        )

    @app.post("/api/pilot/login")
    async def login(body: Login, request: Request):
        now = time.time()
        ip = request.client.host if request.client else "unknown"
        # Do not trust an arbitrary X-Forwarded-For header as a rate-limit key.
        device_id = body.code.split(".", 1)[0]
        device = settings.device(device_id)
        # Separate configured controllers behind one proxy/NAT. Unknown IDs share
        # one bucket instead of allocating an unbounded bucket per guessed ID.
        queue = attempts[(ip, device.id if device else "unknown")]
        while queue and queue[0] < now - 60:
            queue.popleft()
        if len(queue) >= 20:
            raise HTTPException(429, "try_later")
        queue.append(now)
        if len(attempts) > 10000:
            for key in list(attempts):
                if not attempts[key] or attempts[key][-1] < now - 60:
                    del attempts[key]
        digest = hashlib.sha256(body.code.encode()).hexdigest()
        if not device or not hmac.compare_digest(digest, device.connection_code_sha256):
            raise HTTPException(401, "invalid_connection_code")
        if not settings.dji.configured:
            raise HTTPException(503, "dji_configuration_pending")
        token = secrets.token_urlsafe(32)
        expires = now + settings.session_hours * 3600
        store.create_session(token, device.id, device.connection_code_sha256, expires)
        return {"token": token, "expires_at": expires}

    @app.get("/api/pilot/bootstrap")
    async def bootstrap(request: Request):
        session(request, activated=False)
        return {
            "app_id": settings.dji.app_id,
            "app_key": settings.dji.app_key.get_secret_value(),
            "license": settings.dji.license.get_secret_value(),
        }

    @app.post("/api/pilot/activate")
    async def activate(body: Activate, request: Request):
        row, device = session(request, activated=False)
        if not hmac.compare_digest(body.gateway_sn, device.gateway_sn):
            store.delete_session(bearer(request))
            raise HTTPException(403, "wrong_controller")
        store.activate(row["token_hash"])
        return device_config(row, device)

    @app.get("/api/pilot/config")
    async def config(request: Request):
        row, device = session(request)
        return device_config(row, device)

    @app.get("/api/pilot/status")
    async def status(request: Request):
        _, device = session(request)
        result = store.status(device.id)
        result.update(
            device_name=device.name,
            workspace_name=settings.workspace_name,
            mqtt_receiver_connected=receiver.connected,
            server_time=time.time(),
            blender_configured=settings.blender.configured,
        )
        return result

    @app.post("/api/pilot/logout")
    async def logout(request: Request):
        store.delete_session(bearer(request))
        return {"status": "signed_out"}

    @app.get("/api/admin/status")
    async def admin_status(request: Request):
        if not hmac.compare_digest(bearer(request), settings.admin_token.get_secret_value()):
            raise HTTPException(401, "sign_in_required")
        return {
            "mqtt_connected": receiver.connected,
            "queue": store.status(),
            "devices": [{"id": d.id, "name": d.name, **store.status(d.id)} for d in settings.devices],
        }

    app.mount("/static", StaticFiles(directory=WEB), name="static")
    return app


def build_app() -> FastAPI:
    try:
        settings = load_settings(Path(os.environ.get("ADAPTOR_CONFIG", "runtime/config.json")))
    except (ValueError, OSError):
        # Validation exceptions can echo secret input into Uvicorn's startup log.
        raise RuntimeError("Private configuration invalid; run dji-cloud-adaptor check") from None
    store = Store(Path(os.environ.get("ADAPTOR_DATABASE", "runtime/queue.sqlite3")))
    return create_app(settings, store)
