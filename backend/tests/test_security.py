from conftest import make_client, sms


def test_health_is_public(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["app"] == "LocalSMS"


def test_admin_requires_token(client, admin):
    assert client.get("/api/v1/conversations").status_code == 401
    assert client.get("/api/v1/conversations", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/v1/conversations", headers=admin).status_code == 200


def test_device_token_cannot_access_admin(client, device):
    assert client.get("/api/v1/conversations", headers=device).status_code == 401


def test_admin_token_cannot_upload(client, admin):
    r = client.post("/api/v1/sms/batch", headers=admin, json={"messages": [sms(1)]})
    assert r.status_code == 401


def test_pairing_code_single_use_and_invalid(client, admin):
    code = client.post("/api/v1/pairing/code", headers=admin).json()["code"]
    body = {"code": code, "device_id": "abcdefgh-1", "device_name": "T"}
    assert client.post("/api/v1/pair", json=body).status_code == 200
    assert client.post("/api/v1/pair", json=body).status_code == 403  # déjà utilisé
    bad = {"code": "ZZZZZZZZ", "device_id": "abcdefgh-2", "device_name": "T"}
    assert client.post("/api/v1/pair", json=bad).status_code == 403


def test_pairing_bruteforce_is_rate_limited(client):
    body = {"code": "AAAAAAAA", "device_id": "abcdefgh-3", "device_name": "T"}
    codes = [client.post("/api/v1/pair", json=body).status_code for _ in range(12)]
    assert codes[:10] == [403] * 10
    assert codes[10] == 429


def test_revoked_device_is_rejected(client, admin, device):
    assert client.delete(f"/api/v1/devices/{device['id']}", headers=admin).status_code == 200
    r = client.post("/api/v1/sms/batch", headers=device, json={"messages": [sms(1)]})
    assert r.status_code == 401


def test_rotate_admin_token(client, admin, app):
    new = client.post("/api/v1/auth/rotate-admin-token", headers=admin).json()["token"]
    assert client.get("/api/v1/stats", headers=admin).status_code == 401
    assert client.get("/api/v1/stats", headers={"Authorization": f"Bearer {new}"}).status_code == 200
    assert app.state.runtime.admin_token_path.read_text().strip() == new


def test_loopback_only_by_default(app):
    with make_client(app, ip="192.168.1.50") as c:
        assert c.get("/api/v1/health").status_code == 403


def test_host_header_rebinding_blocked(app):
    with make_client(app, host="evil.example.com") as c:
        assert c.get("/api/v1/health").status_code == 400


def test_lan_mode_allows_private_ip_for_devices_not_admin(tmp_path):
    from localsms.config import build_runtime
    from localsms.main import create_app

    rt = build_runtime(tmp_path / "d", port=8765, lan=True)
    app = create_app(rt)
    adm = {"Authorization": f"Bearer {app.state.auth.admin_token}"}
    with make_client(app) as local:
        code = local.post("/api/v1/pairing/code", headers=adm).json()["code"]
    with make_client(app, ip="192.168.1.50", host="192.168.1.10:8765") as lan:
        r = lan.post("/api/v1/pair", json={"code": code, "device_id": "lan-device-1", "device_name": "LAN"})
        assert r.status_code == 200
        assert lan.get("/api/v1/stats", headers=adm).status_code == 403  # admin refusé depuis le LAN
    with make_client(app, ip="8.8.8.8", host="192.168.1.10:8765") as pub:
        assert pub.get("/api/v1/health").status_code == 403  # IP publique refusée


def test_lan_admin_flag(tmp_path):
    from localsms.config import build_runtime
    from localsms.main import create_app

    rt = build_runtime(tmp_path / "d", port=8765, lan=True, lan_admin=True)
    app = create_app(rt)
    adm = {"Authorization": f"Bearer {app.state.auth.admin_token}"}
    with make_client(app, ip="192.168.1.50", host="192.168.1.10:8765") as lan:
        assert lan.get("/api/v1/stats", headers=adm).status_code == 200


def test_security_headers(client):
    r = client.get("/api/v1/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
