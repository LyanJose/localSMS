import os
import stat
import sys

import pytest

from localsms import adb

SAMPLE = """List of devices attached
R58M12ABCDE            device usb:1-1 product:x model:SM_A525F device:a52q transport_id:3
emulator-5554          unauthorized transport_id:4
"""


def test_parse_devices():
    d = adb.parse_devices(SAMPLE)
    assert d[0] == {"serial": "R58M12ABCDE", "state": "device", "model": "SM_A525F"}
    assert d[1]["state"] == "unauthorized"


@pytest.mark.skipif(sys.platform == "win32", reason="script shell factice POSIX")
def test_with_fake_adb(tmp_path, client, admin, app):
    log = tmp_path / "calls.log"
    fake = tmp_path / "adb"
    fake.write_text(
        "#!/bin/sh\n"
        f'echo "$@" >> {log}\n'
        'if [ "$1" = "devices" ]; then\n'
        f"cat <<'EOT'\n{SAMPLE}EOT\n"
        "fi\nexit 0\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    app.state.runtime.settings.adb_path = str(fake)

    st = client.get("/api/v1/adb/status", headers=admin).json()
    assert st["available"] and len(st["devices"]) == 2

    r = client.post("/api/v1/adb/reverse", headers=admin, json={})
    assert r.status_code == 200 and r.json()["results"] == [{"serial": "R58M12ABCDE", "ok": True, "error": None}]
    assert "-s R58M12ABCDE reverse tcp:8765 tcp:8765" in log.read_text()
    assert client.post("/api/v1/adb/reverse", headers=admin, json={"serial": "a; rm -rf /"}).status_code == 422


def test_missing_adb(client, admin, app, monkeypatch):
    monkeypatch.setattr(adb, "find_adb", lambda custom="": None)
    assert client.get("/api/v1/adb/status", headers=admin).json()["available"] is False
    assert client.post("/api/v1/adb/reverse", headers=admin, json={}).status_code == 400
