import pytest
from fastapi.testclient import TestClient

from localsms.config import build_runtime
from localsms.main import create_app


def make_client(app, ip="127.0.0.1", host="127.0.0.1:8765"):
    return TestClient(app, base_url=f"http://{host}", client=(ip, 50000))


@pytest.fixture
def rt(tmp_path):
    return build_runtime(tmp_path / "data", port=8765)


@pytest.fixture
def app(rt):
    return create_app(rt)


@pytest.fixture
def client(app):
    with make_client(app) as c:
        yield c


@pytest.fixture
def admin(app):
    return {"Authorization": f"Bearer {app.state.auth.admin_token}"}


@pytest.fixture
def device(client, admin):
    """Appairage réel d'un téléphone via l'API."""
    code = client.post("/api/v1/pairing/code", headers=admin).json()["code"]
    r = client.post(
        "/api/v1/pair",
        json={"code": code, "device_id": "phone-test-0001", "device_name": "Pixel de test"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['device_token']}", "id": r.json()["device_id"]}


def sms(i, address="+261321234567", body=None, type_=1, date=1_700_000_000_000):
    return {
        "sms_id": i,
        "address": address,
        "body": body if body is not None else f"Message numéro {i}",
        "date_ms": date + i * 1000,
        "type": type_,
        "read": True,
    }
