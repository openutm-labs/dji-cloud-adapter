import json
import time

import httpx
import pytest
from pydantic import SecretStr

from dji_cloud_adaptor.blender import BlenderClient, DeliveryError, Forwarder
from dji_cloud_adaptor.config import OAuth
from dji_cloud_adaptor.telemetry import Ingestor

TOPIC = "thing/product/EXAMPLE-M3E-001/osd"


async def test_blender_receives_the_documented_observation_envelope(settings, store, osd):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(201, json={"message": "OK", "status": 201})

    Ingestor(settings, store).process(TOPIC, json.dumps(osd).encode())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await Forwarder(settings, store, BlenderClient(settings, client)).once()
    request = requests[0]
    assert request.url.path == "/flight_stream/set_air_traffic/00000000-0000-0000-0000-000000000002"
    assert request.headers["authorization"] == "Bearer test-blender-token"
    data = json.loads(request.content)
    assert list(data) == ["observations"]
    assert data["observations"][0]["altitude_mm"] == 123400
    assert store.status()["counts"] == {"accepted": 1}


async def test_transient_failure_retries_without_losing_or_retiming_sample(settings, store, osd):
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(503 if len(requests) == 1 else 201)

    Ingestor(settings, store).process(TOPIC, json.dumps(osd).encode())
    now = time.time()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        worker = Forwarder(settings, store, BlenderClient(settings, client))
        await worker.once(now=now)
        assert store.status()["counts"] == {"pending": 1}
        assert await worker.once(now=now + 1) is False
        await worker.once(now=now + 3)
    assert requests[0] == requests[1]
    assert store.status()["counts"] == {"accepted": 1}


async def test_old_queued_samples_are_archived_not_republished_as_live(settings, store, osd):
    called = []
    Ingestor(settings, store).process(TOPIC, json.dumps(osd).encode())
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: called.append(r))) as client:
        await Forwarder(settings, store, BlenderClient(settings, client)).once(now=time.time() + 61)
    assert not called
    assert store.status()["counts"] == {"expired": 1}


async def test_oauth_renews_once_after_401(settings, store, osd):
    settings.blender.bearer_token = SecretStr("")
    settings.blender.oauth = OAuth(
        token_url="http://localhost/token",
        client_id="client",
        client_secret="client-secret",
        audience="expected-audience",
    )
    calls = {"token": 0, "api": 0}

    def handler(request):
        if request.url.path == "/token":
            calls["token"] += 1
            assert b"grant_type=client_credentials" in request.content
            assert b"audience=expected-audience" in request.content
            return httpx.Response(200, json={"access_token": f"token-{calls['token']}", "expires_in": 300})
        calls["api"] += 1
        return httpx.Response(401 if calls["api"] == 1 else 201)

    Ingestor(settings, store).process(TOPIC, json.dumps(osd).encode())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await Forwarder(settings, store, BlenderClient(settings, client)).once()
    assert calls == {"token": 2, "api": 2}
    assert store.status()["counts"] == {"accepted": 1}


@pytest.mark.parametrize("status", [401, 403, 503])
async def test_bad_auth_is_not_marked_as_delivered(settings, store, osd, status):
    Ingestor(settings, store).process(TOPIC, json.dumps(osd).encode())
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(status))) as client:
        await Forwarder(settings, store, BlenderClient(settings, client)).once()
    assert store.status()["counts"] == {"pending": 1}
    assert store.status()["last_error"] == f"blender_http_{status}"


async def test_invalid_schema_is_retained_for_diagnosis_not_retried_forever(settings, store, osd):
    Ingestor(settings, store).process(TOPIC, json.dumps(osd).encode())
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(422))) as client:
        await Forwarder(settings, store, BlenderClient(settings, client)).once()
    assert store.status()["counts"] == {"rejected": 1}


async def test_removing_device_stops_its_pending_delivery(settings, store, osd):
    Ingestor(settings, store).process(TOPIC, json.dumps(osd).encode())
    settings.devices = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(201))) as client:
        await Forwarder(settings, store, BlenderClient(settings, client)).once()
    assert store.status()["last_error"] == "device_assignment_changed"


async def test_access_check_only_reads_protected_health(settings):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.path == "/surveillance_monitoring_ops/health/"
        assert request.headers["authorization"] == "Bearer test-blender-token"
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await BlenderClient(settings, client).check_access()
    assert len(requests) == 1


async def test_access_check_refreshes_oauth_once_after_read_401(settings):
    settings.blender.bearer_token = SecretStr("")
    settings.blender.oauth = OAuth(
        token_url="http://localhost/token", client_id="client", client_secret="private-client-secret"
    )
    calls = {"token": 0, "read": 0}

    def handler(request):
        if request.url.path == "/token":
            assert request.method == "POST"
            calls["token"] += 1
            return httpx.Response(200, json={"access_token": f"token-{calls['token']}"})
        assert request.method == "GET"
        assert request.url.path == "/surveillance_monitoring_ops/health/"
        calls["read"] += 1
        return httpx.Response(401 if calls["read"] == 1 else 200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await BlenderClient(settings, client).check_access()
    assert calls == {"token": 2, "read": 2}


@pytest.mark.parametrize("status", [302, 401, 403, 500])
async def test_access_check_reports_only_status_not_server_body(settings, status):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(status, text="private-server-details"))
    ) as client:
        with pytest.raises(DeliveryError, match=f"^blender_read_http_{status}$"):
            await BlenderClient(settings, client).check_access()
