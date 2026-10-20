import asyncio
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .blender import BlenderClient, DeliveryError, Forwarder
from .broker import BrokerProvisioner, BrokerUnavailable
from .config import IDENTIFIER, Settings, load_settings
from .declarations import Action, DeclarationError, Operations, Plan
from .enrollment import EnrollmentError, EnrollmentStore
from .mqtt import MqttReceiver
from .store import Store

WEB = Path(os.environ.get("ADAPTOR_WEB", str(Path(__file__).parent / "web")))


class Login(BaseModel):
    code: str = Field(min_length=20, max_length=150)


class Activate(BaseModel):
    gateway_sn: str = Field(pattern=IDENTIFIER.pattern)


class EnrollmentLogin(BaseModel):
    invitation_code: str = Field(min_length=30, max_length=150)


class EnrollmentDevice(BaseModel):
    gateway_sn: str = Field(pattern=IDENTIFIER.pattern)
    aircraft_sn: str = Field(pattern=IDENTIFIER.pattern)
    aircraft_model: str = Field(min_length=1, max_length=100)
    name: str = Field(default="", max_length=80)


def create_app(settings: Settings, store: Store, *, background=True, transport=None) -> FastAPI:
    registry = EnrollmentStore(store)
    static_devices = list(settings.devices)
    provisioning_lock = asyncio.Lock()
    synced, disabled = set(), set()

    def refresh_devices():
        devices = static_devices + registry.devices()
        try:
            Settings.model_validate({**settings.model_dump(), "devices": devices})
        except ValueError:
            raise EnrollmentError("registration_conflict") from None
        settings.devices = devices

    refresh_devices()
    receiver = MqttReceiver(settings, store)

    async def provision(device):
        fleet = static_devices + [d for d in registry.devices() if d.id != device.id] + [device]
        await asyncio.to_thread(app.state.provisioner.sync, device, fleet)
        registry.activate(device.id)
        synced.add(device.id)
        refresh_devices()
        if receiver.client.is_connected():
            receiver.refresh_subscriptions()

    async def reconcile():
        while True:
            try:
                async with provisioning_lock:
                    refresh_devices()
                    for device in registry.devices("revoked"):
                        if device.id not in disabled:
                            await asyncio.to_thread(app.state.provisioner.revoke, device)
                            disabled.add(device.id)
                    for device in registry.devices() + registry.devices("pending"):
                        if device.id not in synced:
                            await provision(device)
            except (BrokerUnavailable, EnrollmentError):
                # Retry from durable registry state; never log credentials or serials.
                pass
            await asyncio.sleep(5)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient(timeout=10, follow_redirects=False, transport=transport) as client:
            blender = BlenderClient(settings, client)
            operations = Operations(settings, store, blender)
            app.state.operations = operations
            forwarder = Forwarder(settings, store, blender, operations=operations)
            app.state.forwarder = forwarder
            task = None
            enrollment_task = None
            operations_task = None
            if background:
                receiver.start()
                task = asyncio.create_task(forwarder.run())
                if settings.declarations.enabled:
                    operations_task = asyncio.create_task(operations.run())
                if settings.mqtt.provisioner_password.get_secret_value():
                    enrollment_task = asyncio.create_task(reconcile())
            try:
                yield
            finally:
                if operations_task:
                    operations_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await operations_task
                if enrollment_task:
                    enrollment_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await enrollment_task
                if task:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                    await asyncio.to_thread(receiver.stop)

    app = FastAPI(title="DJI Cloud Adaptor", lifespan=lifespan, docs_url=None, openapi_url=None)
    app.state.receiver = receiver
    app.state.registry = registry
    app.state.provisioner = BrokerProvisioner(settings)
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
        if (
            not device
            or registry.is_revoked(device.id)
            or not hmac.compare_digest(row["credential_revision"], device.connection_code_sha256)
        ):
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
            "declarations_enabled": settings.declarations.enabled,
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

    def enrollment_available():
        if not settings.enrollment.enabled:
            raise HTTPException(404, "enrollment_not_available")
        if not settings.dji.configured:
            raise HTTPException(503, "dji_configuration_pending")

    @app.get("/api/enrollment/options")
    async def enrollment_options():
        return {
            "enabled": settings.enrollment.enabled,
            "models": settings.enrollment.allowed_models if settings.enrollment.enabled else [],
            "workspace_name": settings.workspace_name,
        }

    @app.post("/api/enrollment/start")
    async def enrollment_start(body: EnrollmentLogin, request: Request):
        enrollment_available()
        enrollment_rate(request)
        try:
            token, expires = registry.start(body.invitation_code)
        except EnrollmentError as exc:
            raise HTTPException(401, str(exc)) from None
        return {"token": token, "expires_at": expires}

    def enrollment_rate(request):
        now = time.time()
        queue = attempts[(request.client.host if request.client else "unknown", "enrollment")]
        while queue and queue[0] < now - 60:
            queue.popleft()
        if len(queue) >= 20:
            raise HTTPException(429, "try_later")
        queue.append(now)
        if len(attempts) > 10000:
            for key in list(attempts):
                if not attempts[key] or attempts[key][-1] < now - 60:
                    del attempts[key]

    @app.get("/api/enrollment/bootstrap")
    async def enrollment_bootstrap(request: Request):
        enrollment_available()
        try:
            registry.session(bearer(request))
        except EnrollmentError as exc:
            raise HTTPException(401, str(exc)) from None
        return {
            "app_id": settings.dji.app_id,
            "app_key": settings.dji.app_key.get_secret_value(),
            "license": settings.dji.license.get_secret_value(),
        }

    @app.post("/api/enrollment/complete")
    async def enrollment_complete(body: EnrollmentDevice, request: Request):
        enrollment_available()
        enrollment_rate(request)
        if body.aircraft_model not in settings.enrollment.allowed_models:
            raise HTTPException(422, "unsupported_model")
        if body.gateway_sn == body.aircraft_sn:
            raise HTTPException(422, "equipment_identity_invalid")
        async with provisioning_lock:
            try:
                registry.session(bearer(request))
                existing = (
                    static_devices
                    + registry.devices()
                    + registry.devices("pending")
                    + registry.devices("revoked")
                )
                for device in existing:
                    if (
                        body.gateway_sn in {a.serial for a in device.aircraft}
                        or any(
                            a.serial == body.aircraft_sn and device.gateway_sn != body.gateway_sn
                            for a in device.aircraft
                        )
                        or body.aircraft_sn == device.gateway_sn
                    ):
                        raise EnrollmentError("equipment_already_registered")
                if any(d.gateway_sn == body.gateway_sn for d in static_devices):
                    raise EnrollmentError("equipment_already_registered")
                device = registry.reserve(
                    bearer(request),
                    body.gateway_sn,
                    body.aircraft_sn,
                    body.aircraft_model,
                    body.name,
                    settings.enrollment.max_devices,
                )
                await provision(device)
                # Return the same code/session after a lost response, without taking over another device.
                token = secrets.token_urlsafe(32)
                expires = time.time() + settings.session_hours * 3600
                store.create_session(token, device.id, device.connection_code_sha256, expires)
                row = store.session(token, time.time())
                store.activate(row["token_hash"])
                return {
                    "token": token,
                    "connection_code": registry.code(device.id),
                    "config": device_config(row, device),
                }
            except EnrollmentError as exc:
                status = 401 if str(exc) in {"enrollment_session_expired", "invalid_invitation"} else 409
                raise HTTPException(status, str(exc)) from None
            except BrokerUnavailable:
                raise HTTPException(503, "registration_pending") from None

    @app.get("/readyz")
    async def ready():
        forwarder = getattr(app.state, "forwarder", None)
        checks = {
            "mqtt_connected": receiver.connected,
            "forwarder_running": bool(forwarder and forwarder.running),
            "dji_configured": settings.dji.configured,
            "blender_configured": settings.blender.configured,
        }
        if settings.declarations.enabled:
            checks["declaration_worker_running"] = app.state.operations.running
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
        if (
            not device
            or registry.is_revoked(device.id)
            or not hmac.compare_digest(digest, device.connection_code_sha256)
        ):
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

    def declaration_device(request):
        _, device = session(request)
        if not settings.declarations.enabled:
            raise HTTPException(404, "declarations_not_available")
        return device

    @app.exception_handler(DeclarationError)
    async def declaration_error(request, exc):
        return JSONResponse({"detail": exc.reason}, status_code=exc.status)

    @app.exception_handler(DeliveryError)
    async def declaration_auth_error(request, exc):
        return JSONResponse({"detail": "declaration_service_unavailable"}, status_code=503)

    @app.get("/api/pilot/declarations")
    async def declaration_options(request: Request):
        return app.state.operations.options(declaration_device(request))

    @app.post("/api/pilot/declarations")
    async def prepare_declaration(body: Plan, request: Request):
        device = declaration_device(request)
        async with app.state.operations.lock:
            return app.state.operations.prepare(device, body)

    @app.post("/api/pilot/declarations/{operation_id}")
    async def declaration_action(operation_id: UUID, body: Action, request: Request):
        return await app.state.operations.act(declaration_device(request), operation_id, body.action)

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
