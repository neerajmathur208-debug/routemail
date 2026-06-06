"""Iteration 42 backend tests — campaign/drip export, import, and convert-to-drip.

Exercises:
- GET  /api/campaigns/{id}/export
- POST /api/campaigns/import           (uniqueness, double-import suffix)
- POST /api/campaigns/{id}/convert-to-drip  (source must remain untouched)
- GET  /api/drip-campaigns/{id}/export
- POST /api/drip-campaigns/import      (0-steps → 400)
- Anonymous access → 401/403
- Regression smoke on existing list/duplicate endpoints.
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

EMAIL = "drip.tester@example.com"
PASSWORD = "DripTest123!"


# ----------------------------- fixtures -----------------------------
@pytest.fixture(scope="module")
def session() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    assert s.cookies.get("session_token"), "no session cookie"
    return s


@pytest.fixture(scope="module")
def seed_campaign(session):
    """Create a normal campaign to act as the source for export/convert tests."""
    name = f"TEST_iter42_camp_{uuid.uuid4().hex[:6]}"
    body_html = "<p>Hello <b>world</b></p>"
    payload = {
        "name": name,
        "subject": "Iter42 subject",
        "body": body_html,
        "body_text": "Hello world",
        "from_name": "Iter42 Tester",
        "add_unsubscribe_footer": True,
        "tracking_opens": True,
        "tracking_clicks": False,
        "send_range_mode": "all",
    }
    r = session.post(f"{API}/campaigns", json=payload, timeout=20)
    assert r.status_code in (200, 201), f"campaign create failed {r.status_code}: {r.text}"
    cid = r.json().get("campaign_id") or r.json().get("id")
    assert cid, f"no campaign_id in response: {r.json()}"
    yield {"campaign_id": cid, "name": name, "payload": payload}
    # cleanup
    session.delete(f"{API}/campaigns/{cid}", timeout=15)


@pytest.fixture(scope="module")
def seed_drip(session):
    """Create a drip campaign with 2 steps."""
    name = f"TEST_iter42_drip_{uuid.uuid4().hex[:6]}"
    payload = {
        "name": name,
        "from_name": "Drip Iter42",
        "steps": [
            {"step_number": 1, "subject": "Drip s1", "body": "<p>step1</p>", "delay_days": 0, "delay_hours": 0},
            {"step_number": 2, "subject": "Drip s2", "body": "<p>step2</p>", "delay_days": 2, "delay_hours": 3},
        ],
        "stop_on_reply": True,
        "stop_on_bounce": True,
        "tracking_opens": True,
        "tracking_clicks": True,
        "add_unsubscribe_footer": False,
    }
    r = session.post(f"{API}/drip-campaigns", json=payload, timeout=20)
    assert r.status_code in (200, 201), f"drip create failed {r.status_code}: {r.text}"
    did = r.json().get("drip_id") or r.json().get("id")
    assert did, f"no drip_id: {r.json()}"
    yield {"drip_id": did, "name": name}
    session.delete(f"{API}/drip-campaigns/{did}", timeout=15)


# ----------------------------- auth gating -----------------------------
class TestAuthGating:
    def test_export_campaign_anon(self):
        r = requests.get(f"{API}/campaigns/some-id/export", timeout=10)
        assert r.status_code in (401, 403), r.status_code

    def test_import_campaign_anon(self):
        r = requests.post(f"{API}/campaigns/import", json={"type": "campaign", "campaign": {"name": "x"}}, timeout=10)
        assert r.status_code in (401, 403), r.status_code

    def test_convert_anon(self):
        r = requests.post(f"{API}/campaigns/some-id/convert-to-drip", timeout=10)
        assert r.status_code in (401, 403), r.status_code

    def test_export_drip_anon(self):
        r = requests.get(f"{API}/drip-campaigns/some-id/export", timeout=10)
        assert r.status_code in (401, 403), r.status_code

    def test_import_drip_anon(self):
        r = requests.post(f"{API}/drip-campaigns/import", json={"type": "drip_campaign", "drip": {"name": "x", "steps": [{"step_number": 1, "subject": "s", "body": "b"}]}}, timeout=10)
        assert r.status_code in (401, 403), r.status_code


# ----------------------------- campaign export -----------------------------
class TestCampaignExport:
    def test_export_payload_shape(self, session, seed_campaign):
        r = session.get(f"{API}/campaigns/{seed_campaign['campaign_id']}/export", timeout=15)
        assert r.status_code == 200, r.text
        # content-type may have charset suffix
        ct = r.headers.get("content-type", "")
        assert "application/json" in ct, ct
        data = r.json()
        assert data.get("schema_version") == 1
        assert data.get("type") == "campaign"
        camp = data.get("campaign")
        assert isinstance(camp, dict)
        # required fields present
        for key in [
            "name", "subject", "body", "body_text", "from_name", "list_name",
            "account_emails", "dne_list_names", "send_range_mode", "send_range_start",
            "send_range_end", "scheduled_at", "schedule_timezone",
            "add_unsubscribe_footer", "tracking_opens", "tracking_clicks", "created_at",
        ]:
            assert key in camp, f"missing key {key} in export"
        assert camp["name"] == seed_campaign["name"]
        assert camp["subject"] == seed_campaign["payload"]["subject"]
        assert camp["body"] == seed_campaign["payload"]["body"]
        # operational fields MUST NOT leak
        forbidden = {"recipient_progress", "sent_logs", "analytics", "replies", "_id"}
        assert forbidden.isdisjoint(set(camp.keys()))
        assert forbidden.isdisjoint(set(data.keys()))

    def test_export_unknown_404(self, session):
        r = session.get(f"{API}/campaigns/does-not-exist-xyz/export", timeout=10)
        assert r.status_code == 404


# ----------------------------- campaign import -----------------------------
class TestCampaignImport:
    def test_import_creates_draft_and_name_collides(self, session, seed_campaign):
        # 1st import — name collides with original → should add " (Imported)"
        export = session.get(f"{API}/campaigns/{seed_campaign['campaign_id']}/export", timeout=15).json()
        r1 = session.post(f"{API}/campaigns/import", json=export, timeout=20)
        assert r1.status_code == 200, r1.text
        j1 = r1.json()
        assert j1["status"] == "draft"
        assert j1["name"] != seed_campaign["name"]
        assert "(Imported" in j1["name"]
        cid1 = j1["campaign_id"]

        # 2nd import — should get auto-incremented suffix
        r2 = session.post(f"{API}/campaigns/import", json=export, timeout=20)
        assert r2.status_code == 200, r2.text
        j2 = r2.json()
        cid2 = j2["campaign_id"]
        assert cid1 != cid2
        assert j2["name"] != j1["name"]
        assert "(Imported" in j2["name"]

        # GET to verify both persist as DRAFT and original is untouched
        all_camps = session.get(f"{API}/campaigns", timeout=15).json()
        items = all_camps if isinstance(all_camps, list) else all_camps.get("campaigns") or all_camps.get("items") or []
        ids = {c.get("campaign_id") or c.get("id"): c for c in items}
        for cid in (cid1, cid2):
            assert cid in ids, f"imported {cid} not in list"
            assert ids[cid].get("status") == "draft"

        # cleanup
        session.delete(f"{API}/campaigns/{cid1}", timeout=10)
        session.delete(f"{API}/campaigns/{cid2}", timeout=10)

    def test_import_invalid_payload(self, session):
        r = session.post(f"{API}/campaigns/import", json={"type": "drip_campaign", "drip": {}}, timeout=10)
        assert r.status_code == 400, r.text


# ----------------------------- convert to drip -----------------------------
class TestConvertToDrip:
    def test_convert_does_not_touch_source(self, session, seed_campaign):
        cid = seed_campaign["campaign_id"]
        before_resp = session.get(f"{API}/campaigns/{cid}", timeout=10)
        assert before_resp.status_code == 200
        before = before_resp.json()
        # strip _id just in case
        before.pop("_id", None)

        r = session.post(f"{API}/campaigns/{cid}/convert-to-drip", timeout=20)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["status"] == "draft"
        assert j["source_campaign_id"] == cid
        new_drip_id = j["drip_id"]
        assert new_drip_id and j["name"]

        # source unchanged
        after = session.get(f"{API}/campaigns/{cid}", timeout=10).json()
        after.pop("_id", None)
        # compare critical fields
        for k in ("name", "subject", "body", "status", "from_name"):
            assert before.get(k) == after.get(k), f"source field '{k}' changed: {before.get(k)} != {after.get(k)}"

        # verify new drip exists with one step + same subject/body
        dr = session.get(f"{API}/drip-campaigns/{new_drip_id}", timeout=10)
        assert dr.status_code == 200, dr.text
        drip = dr.json()
        assert drip.get("status") == "draft"
        steps = drip.get("steps") or []
        assert len(steps) == 1
        assert steps[0].get("subject") == before.get("subject")
        assert steps[0].get("body") == before.get("body")
        assert drip.get("from_name") == before.get("from_name")

        # cleanup the drip
        session.delete(f"{API}/drip-campaigns/{new_drip_id}", timeout=10)


# ----------------------------- drip export -----------------------------
class TestDripExport:
    def test_drip_export_shape(self, session, seed_drip):
        r = session.get(f"{API}/drip-campaigns/{seed_drip['drip_id']}/export", timeout=15)
        assert r.status_code == 200, r.text
        assert "application/json" in r.headers.get("content-type", "")
        data = r.json()
        assert data.get("schema_version") == 1
        assert data.get("type") == "drip_campaign"
        drip = data.get("drip")
        assert isinstance(drip, dict)
        for key in [
            "name", "from_name", "list_name", "account_emails", "dne_list_names",
            "steps", "schedule", "stop_on_reply", "stop_on_bounce",
            "tracking_opens", "tracking_clicks", "add_unsubscribe_footer", "created_at",
        ]:
            assert key in drip, f"missing drip key {key}"
        steps = drip["steps"]
        assert isinstance(steps, list) and len(steps) == 2
        for s in steps:
            assert "delay_days" in s and "delay_hours" in s
        # operational fields should not leak
        forbidden = {"recipient_progress", "sent_logs", "analytics", "replies", "drip_contacts", "_id"}
        assert forbidden.isdisjoint(set(drip.keys()))
        assert forbidden.isdisjoint(set(data.keys()))


# ----------------------------- drip import -----------------------------
class TestDripImport:
    def test_drip_import_creates_draft_and_unique_name(self, session, seed_drip):
        export = session.get(f"{API}/drip-campaigns/{seed_drip['drip_id']}/export", timeout=15).json()
        r1 = session.post(f"{API}/drip-campaigns/import", json=export, timeout=20)
        assert r1.status_code == 200, r1.text
        j1 = r1.json()
        assert j1["status"] == "draft"
        assert j1["steps_imported"] == 2
        assert "(Imported" in j1["name"]
        did1 = j1["drip_id"]

        r2 = session.post(f"{API}/drip-campaigns/import", json=export, timeout=20)
        assert r2.status_code == 200, r2.text
        j2 = r2.json()
        did2 = j2["drip_id"]
        assert did1 != did2
        assert j2["name"] != j1["name"]

        session.delete(f"{API}/drip-campaigns/{did1}", timeout=10)
        session.delete(f"{API}/drip-campaigns/{did2}", timeout=10)

    def test_drip_import_zero_steps_400(self, session):
        bad = {"schema_version": 1, "type": "drip_campaign", "drip": {"name": "TEST_iter42_empty", "steps": []}}
        r = session.post(f"{API}/drip-campaigns/import", json=bad, timeout=10)
        assert r.status_code == 400, r.text

    def test_drip_import_wrong_type_400(self, session):
        bad = {"type": "campaign", "campaign": {"name": "wrong"}}
        r = session.post(f"{API}/drip-campaigns/import", json=bad, timeout=10)
        assert r.status_code == 400


# ----------------------------- regression smoke -----------------------------
class TestRegressionSmoke:
    def test_campaigns_list_200(self, session):
        r = session.get(f"{API}/campaigns", timeout=15)
        assert r.status_code == 200

    def test_drip_campaigns_list_200(self, session):
        r = session.get(f"{API}/drip-campaigns", timeout=15)
        assert r.status_code == 200

    def test_campaign_duplicate_200(self, session, seed_campaign):
        r = session.post(f"{API}/campaigns/{seed_campaign['campaign_id']}/duplicate", timeout=15)
        assert r.status_code in (200, 201), r.text
        dup_id = r.json().get("campaign_id")
        if dup_id:
            session.delete(f"{API}/campaigns/{dup_id}", timeout=10)

    def test_drip_duplicate_200(self, session, seed_drip):
        r = session.post(f"{API}/drip-campaigns/{seed_drip['drip_id']}/duplicate", timeout=15)
        assert r.status_code in (200, 201), r.text
        dup_id = r.json().get("drip_id")
        if dup_id:
            session.delete(f"{API}/drip-campaigns/{dup_id}", timeout=10)
