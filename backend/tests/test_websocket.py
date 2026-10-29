import pytest
from starlette.websockets import WebSocketDisconnect

from conftest import sms

B = "/api/v1"
H = {"host": "127.0.0.1:8765"}  # le TestClient WebSocket force sinon « testserver »


def test_ws_requires_auth_and_broadcasts(client, admin, device, app):
    token = app.state.auth.admin_token
    with client.websocket_connect("/ws", headers=H) as ws:
        ws.send_json({"type": "auth", "token": token})
        assert ws.receive_json()["type"] == "ready"
        r = client.post(f"{B}/sms/batch", headers=device, json={"messages": [sms(1, body="Bonjour en direct")], "sync_remaining": 0})
        assert r.status_code == 200
        events = [ws.receive_json(), ws.receive_json()]
        types = {e["type"] for e in events}
        assert types == {"sms_new", "sync_progress"}
        new = next(e for e in events if e["type"] == "sms_new")
        assert new["messages"][0]["body"] == "Bonjour en direct"
        # un doublon ne génère pas d'événement sms_new
        client.post(f"{B}/sms/batch", headers=device, json={"messages": [sms(1, body="Bonjour en direct")]})
        assert ws.receive_json()["type"] == "sync_progress"
        ws.send_text("ping")
        assert ws.receive_text() == "pong"


def test_ws_rejects_bad_token(client):
    with client.websocket_connect("/ws", headers=H) as ws:
        ws.send_json({"type": "auth", "token": "mauvais"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_ws_rejects_foreign_origin(client, app):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={**H, "origin": "http://evil.example"}) as ws:
            ws.receive_json()
