import time

from conftest import sms

B = "/api/v1"


def upload(client, device, msgs):
    r = client.post(f"{B}/sms/batch", headers=device, json={"messages": msgs})
    assert r.status_code == 200, r.text
    return r.json()


def test_batch_insert_and_duplicates(client, device, admin):
    msgs = [sms(i) for i in range(1, 51)]
    assert upload(client, device, msgs) == {"received": 50, "inserted": 50, "duplicates": 0}
    # même lot renvoyé (reprise après déconnexion) : aucun doublon créé
    assert upload(client, device, msgs) == {"received": 50, "inserted": 0, "duplicates": 50}
    # même message, autre identifiant Android et autre format de numéro : toujours un doublon
    again = sms(1, address="0321234567")
    again["date_ms"] = msgs[0]["date_ms"]
    again["body"] = msgs[0]["body"]
    assert upload(client, device, [again])["duplicates"] == 1
    assert client.get(f"{B}/stats", headers=admin).json()["message_count"] == 50


def test_duplicate_inside_same_batch(client, device):
    m = sms(1)
    assert upload(client, device, [m, dict(m)]) == {"received": 2, "inserted": 1, "duplicates": 1}


def test_validation_errors(client, device):
    bad = [
        {"messages": []},
        {"messages": [{**sms(1), "address": ""}]},
        {"messages": [{**sms(1), "date_ms": -5}]},
        {"messages": [{**sms(1), "type": 99}]},
        {"messages": [sms(i) for i in range(501)]},
        {"messages": [{**sms(1), "body": "x" * 100_001}]},
        {"nope": 1},
    ]
    for payload in bad:
        r = client.post(f"{B}/sms/batch", headers=device, json=payload)
        assert r.status_code == 422, payload


def test_nul_bytes_are_stripped(client, device, admin):
    upload(client, device, [sms(1, body="a\x00b")])
    items = client.get(f"{B}/messages", headers=admin).json()["items"]
    assert items[0]["body"] == "ab"


def test_conversations_grouping_and_order(client, device, admin):
    upload(client, device, [sms(1, "+261321234567"), sms(2, "0321234567", date=1_700_000_100_000)])
    upload(client, device, [sms(3, "ORANGE", date=1_700_000_500_000), sms(4, "+33612345678", type_=2, date=1_700_000_300_000)])
    r = client.get(f"{B}/conversations", headers=admin).json()
    assert r["total"] == 3
    assert [c["address"] for c in r["items"]] == ["ORANGE", "+33612345678", "0321234567"]
    assert r["items"][2]["message_count"] == 2
    assert r["items"][1]["last_direction"] == "out"


def test_conversation_pagination(client, device, admin):
    upload(client, device, [sms(i, f"+26132000{i:04d}") for i in range(1, 26)])
    p1 = client.get(f"{B}/conversations?page=1&page_size=10", headers=admin).json()
    p3 = client.get(f"{B}/conversations?page=3&page_size=10", headers=admin).json()
    assert p1["total"] == 25 and len(p1["items"]) == 10 and len(p3["items"]) == 5
    assert client.get(f"{B}/conversations?page=0", headers=admin).status_code == 422
    assert client.get(f"{B}/conversations?page_size=1000", headers=admin).status_code == 422


def test_thread_cursor_pagination_is_stable(client, device, admin):
    upload(client, device, [sms(i) for i in range(1, 121)])
    key = client.get(f"{B}/conversations", headers=admin).json()["items"][0]["thread_key"]
    seen, cursor = [], None
    while True:
        url = f"{B}/conversations/{key}/messages?limit=50" + (f"&before={cursor}" if cursor else "")
        page = client.get(url, headers=admin).json()
        seen += [m["id"] for m in page["items"]]
        if cursor is None:
            # un nouveau message arrive pendant la pagination : l'ordre ne doit pas être perturbé
            upload(client, device, [sms(999, date=1_800_000_000_000)])
        if not page["has_more"]:
            break
        cursor = page["next_cursor"]
    assert len(seen) == 120 and len(set(seen)) == 120
    assert client.get(f"{B}/conversations/{key}/messages?before=abc", headers=admin).status_code == 422


def test_search_accents_numbers_and_dates(client, device, admin):
    upload(client, device, [
        sms(1, "+261321234567", "Rendez-vous à l'hôtel demain", date=1_700_000_000_000),
        sms(2, "+261341112233", "Code de vérification 482913", date=1_710_000_000_000),
        sms(3, "ORANGE", "Votre forfait est épuisé à 100%", date=1_720_000_000_000),
    ])
    s = lambda **p: client.get(f"{B}/messages", headers=admin, params=p).json()
    assert s(q="hotel")["total"] == 1
    assert s(q="HÔTEL")["total"] == 1
    assert s(q="verification")["total"] == 1
    assert s(q="482913")["items"][0]["address"] == "+261341112233"
    assert s(q="0321234567" if False else "321234567")["total"] == 1       # recherche par numéro
    assert s(q="orange")["total"] == 1                                       # expéditeur
    assert s(q="100%")["total"] == 1                                         # % littéral, non joker
    assert s(q="%")["total"] == 1
    assert s(q="_")["total"] == 0
    assert s(direction="out")["total"] == 0
    assert s(date_from=1_705_000_000_000, date_to=1_715_000_000_000)["total"] == 1
    assert s(address="+261 34 11 122 33")["total"] == 1
    assert s(q="introuvable")["total"] == 0


def test_sql_injection_attempt_is_harmless(client, device, admin):
    upload(client, device, [sms(1)])
    r = client.get(f"{B}/messages", headers=admin, params={"q": "'; DROP TABLE messages;--"})
    assert r.status_code == 200 and r.json()["total"] == 0
    assert client.get(f"{B}/stats", headers=admin).json()["message_count"] == 1


def test_contact_name_in_conversation(client, device, admin):
    m = sms(1)
    m["contact_name"] = "Rakoto Jean"
    upload(client, device, [m])
    conv = client.get(f"{B}/conversations", headers=admin).json()["items"][0]
    assert conv["contact_name"] == "Rakoto Jean"
    assert client.get(f"{B}/conversations?q=rakoto", headers=admin).json()["total"] == 1
    assert client.get(f"{B}/conversations?q=zzz", headers=admin).json()["total"] == 0


def test_heartbeat_and_device_state(client, device, admin):
    r = client.post(f"{B}/device/heartbeat", headers=device, json={"battery": 77, "charging": True, "app_version": "1.0.0", "pending": 12})
    assert r.status_code == 200
    d = client.get(f"{B}/devices", headers=admin).json()["items"][0]
    assert d["online"] is True and d["battery"] == 77 and d["charging"] is True and d["pending"] == 12
    assert d["transport"] == "usb"  # client loopback = adb reverse
    assert client.post(f"{B}/device/heartbeat", headers=device, json={"battery": 500}).status_code == 422


def test_device_goes_offline(client, device, admin, app):
    client.post(f"{B}/device/heartbeat", headers=device, json={"battery": 50})
    old = int(time.time() * 1000) - 5 * 60 * 1000
    with app.state.db.connect() as c:
        c.execute("UPDATE devices SET last_seen_at = ?", (old,))
    assert client.get(f"{B}/devices", headers=admin).json()["items"][0]["online"] is False


def test_unpair_keeps_messages(client, device, admin):
    upload(client, device, [sms(1)])
    assert client.delete(f"{B}/device/self", headers=device).json() == {"deleted": True}
    assert client.get(f"{B}/stats", headers=admin).json()["message_count"] == 1


def test_purge_requires_confirmation(client, device, admin):
    upload(client, device, [sms(1)])
    assert client.post(f"{B}/data/purge", headers=admin, json={"confirm": "oui"}).status_code == 422
    assert client.post(f"{B}/data/purge", headers=admin, json={"confirm": "SUPPRIMER"}).json() == {"deleted": 1}


def test_settings_roundtrip_and_restart_flag(client, admin, rt):
    r = client.put(f"{B}/settings", headers=admin, json={"lan_mode": True}).json()
    assert r["lan_mode"] is True and r["restart_required"] is True and r["effective"]["lan_mode"] is False
    assert '"lan_mode": true' in rt.settings_path.read_text()
    assert client.put(f"{B}/settings", headers=admin, json={"inconnu": 1}).status_code == 422
    r = client.put(f"{B}/settings", headers=admin, json={"lan_mode": False}).json()
    assert r["restart_required"] is False


def test_shutdown_unavailable_without_server(client, admin):
    assert client.post(f"{B}/system/shutdown", headers=admin).status_code == 503


def test_shutdown_sets_flag(client, admin, app):
    class Fake:
        should_exit = False

    app.state.server = Fake()
    assert client.post(f"{B}/system/shutdown", headers=admin).status_code == 200
    assert app.state.server.should_exit is True


def test_openapi_and_docs(client):
    spec = client.get("/openapi.json").json()
    assert "/api/v1/sms/batch" in spec["paths"]
    docs = client.get("/docs")
    assert docs.status_code == 200 and "/docs-static/swagger-ui-bundle.js" in docs.text
    assert client.get("/docs-static/swagger-ui-bundle.js").status_code == 200
