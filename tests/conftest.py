import hashlib
import time
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from dji_cloud_adaptor.api import create_app
from dji_cloud_adaptor.config import Settings
from dji_cloud_adaptor.store import Store

CODE = "controller1.test-connection-code-with-enough-entropy"


@pytest.fixture
def settings():
    return Settings.model_validate(
        {
            "public_url": "http://localhost:18080",
            "allow_insecure_development": True,
            "workspace_id": str(UUID(int=1)),
            "workspace_name": "Test lab",
            "admin_token": "test-admin-token-" * 3,
            "dji": {"app_id": "test-app", "app_key": "test-app-key", "license": "test-license"},
            "mqtt": {
                "host": "localhost",
                "port": 18884,
                "public_url": "ws://localhost:19001/mqtt",
                "worker_password": "worker-password-for-tests-only-0001",
                "client_id": "test-worker",
            },
            "blender": {"base_url": "http://localhost:18081", "bearer_token": "test-blender-token"},
            "devices": [
                {
                    "id": "controller1",
                    "name": "Test controller",
                    "gateway_sn": "EXAMPLE-RC-001",
                    "connection_code_sha256": hashlib.sha256(CODE.encode()).hexdigest(),
                    "mqtt_password": "pilot-password-for-tests-only-0001",
                    "aircraft": [
                        {
                            "serial": "EXAMPLE-M3E-001",
                            "name": "Test Mavic",
                            "model": "Mavic 3 Enterprise",
                            "session_id": str(UUID(int=2)),
                        }
                    ],
                }
            ],
        }
    )


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "queue.sqlite3")


@pytest.fixture
def client(settings, store):
    with TestClient(create_app(settings, store, background=False)) as client:
        yield client


@pytest.fixture
def osd():
    return {
        "tid": "test-tid",
        "bid": "test-bid",
        "timestamp": int(time.time() * 1000),
        "gateway": "EXAMPLE-RC-001",
        "data": {
            "latitude": 8.5,
            "longitude": -80.5,
            "height": 123.4,
            "elevation": 23.4,
            "horizontal_speed": 4.5,
            "mode_code": 3,
        },
    }
