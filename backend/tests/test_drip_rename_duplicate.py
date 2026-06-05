"""
Backend tests for new Drip Campaign Rename + Duplicate endpoints.

Covers:
- POST /api/drip-campaigns/{drip_id}/rename (success, blank, duplicate, self-rename, 404, auth)
- POST /api/drip-campaigns/{drip_id}/duplicate (deep copy, fresh ids, reset counters, no drip_contacts, 404, auth)
- Cross-user isolation
"""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
assert MONGO_URL and DB_NAME

PRIMARY_EMAIL = "drip.tester@example.com"
PRIMARY_PASSWORD = "DripTest123!"

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]


def _api(path):
    return f"{BASE_URL}/api{path}"


def _login(s, email, password):
    r = s.post(_api("/auth/login"), json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r


# ---------- fixtures ----------

@pytest.fixture(scope="module")
def primary_session():
    s = requests.Session()
    _login(s, PRIMARY_EMAIL, PRIMARY_PASSWORD)
    return s


@pytest.fixture(scope="module")
def primary_user_id(primary_session):
    r = primary_session.get(_api("/auth/me"), timeout=10)
    return r.json().get("user_id")


@pytest.fixture(scope="module")
def secondary_user():
    import bcrypt
    suffix = uuid.uuid4().hex[:8]
    email = f"TEST_drip_rd_{suffix}@example.com"
    password = "OtherUser123!"
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    _db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "password_hash": pw_hash,
        "name": "Drip RD Other",
        "email_verified": True,
        "provider": "email",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "plan_type": "free",
        "subscription_status": "active",
    })
    s = requests.Session()
    _login(s, email, password)
    yield {"session": s, "user_id": user_id, "email": email}
    _db.users.delete_one({"user_id": user_id})
    _db.user_sessions.delete_many({"user_id": user_id})
    _db.drip_campaigns.delete_many({"user_id": user_id})


def _make_drip(session, name=None, steps=None, account_ids=None,
               schedule=None, suppression_list_ids=None,
               tracking_opens=True, tracking_clicks=True,
               add_unsubscribe_footer=False, from_name=None,
               stop_on_reply=True, stop_on_bounce=True):
    """Create a drip campaign via API then directly enrich it in Mongo with rich fields."""
    payload = {"name": name or f"TEST_RD_{uuid.uuid4().hex[:6]}"}
    r = session.post(_api("/drip-campaigns"), json=payload, timeout=20)
    assert r.status_code == 200, f"create failed: {r.status_code} {r.text}"
    drip_id = r.json()["drip_id"]

    update = {}
    if steps is not None:
        update["steps"] = steps
    if account_ids is not None:
        update["account_ids"] = account_ids
    if schedule is not None:
        update["schedule"] = schedule
    if suppression_list_ids is not None:
        update["suppression_list_ids"] = suppression_list_ids
    if from_name is not None:
        update["from_name"] = from_name
    update["tracking_opens"] = tracking_opens
    update["tracking_clicks"] = tracking_clicks
    update["add_unsubscribe_footer"] = add_unsubscribe_footer
    update["stop_on_reply"] = stop_on_reply
    update["stop_on_bounce"] = stop_on_bounce
    if update:
        _db.drip_campaigns.update_one({"drip_id": drip_id}, {"$set": update})
    return drip_id


@pytest.fixture
def created_drip(primary_session):
    drip_id = _make_drip(primary_session)
    yield drip_id
    _db.drip_campaigns.delete_one({"drip_id": drip_id})
    _db.drip_contacts.delete_many({"drip_id": drip_id})


@pytest.fixture
def rich_drip(primary_session):
    """Drip with all rich fields populated to verify deep copy."""
    steps = [
        {"order": 1, "subject": "Hi {{name}}", "body": "<p>Hello A</p>", "delay_days": 0},
        {"order": 2, "subject": "Follow-up", "body": "<p>Hello B</p>", "delay_days": 3},
    ]
    drip_id = _make_drip(
        primary_session,
        name=f"TEST_RD_rich_{uuid.uuid4().hex[:6]}",
        steps=steps,
        account_ids=["account_TEST_aaa", "account_TEST_bbb"],
        schedule={"timezone": "UTC", "send_days": ["mon", "tue"], "send_hour_start": 9, "send_hour_end": 17},
        suppression_list_ids=["list_supp_x"],
        tracking_opens=False,
        tracking_clicks=False,
        add_unsubscribe_footer=True,
        from_name="Custom Sender",
        stop_on_reply=False,
        stop_on_bounce=False,
    )
    # Add some fake drip_contacts to ensure they DON'T get copied
    _db.drip_contacts.insert_many([
        {"drip_id": drip_id, "email": "c1@example.com", "status": "sent"},
        {"drip_id": drip_id, "email": "c2@example.com", "status": "sent"},
    ])
    # Set non-draft state to verify duplicate resets it
    _db.drip_campaigns.update_one(
        {"drip_id": drip_id},
        {"$set": {
            "status": "running",
            "total_sent": 42,
            "total_contacts": 100,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    yield drip_id
    _db.drip_campaigns.delete_one({"drip_id": drip_id})
    _db.drip_contacts.delete_many({"drip_id": drip_id})


# ---------- RENAME ----------

class TestRename:
    def test_rename_unauthenticated(self):
        r = requests.post(_api("/drip-campaigns/drip_anything/rename"),
                          json={"name": "x"}, timeout=10)
        assert r.status_code == 401

    def test_rename_success_only_updates_name(self, primary_session, created_drip):
        # Snapshot before
        before = _db.drip_campaigns.find_one({"drip_id": created_drip}, {"_id": 0})
        new_name = f"TEST_RD_renamed_{uuid.uuid4().hex[:6]}"
        r = primary_session.post(_api(f"/drip-campaigns/{created_drip}/rename"),
                                 json={"name": new_name}, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["drip_id"] == created_drip
        assert data["name"] == new_name

        # Re-fetch via API
        r2 = primary_session.get(_api(f"/drip-campaigns/{created_drip}"), timeout=10)
        assert r2.status_code == 200
        d = r2.json()
        assert d["name"] == new_name
        assert d["drip_id"] == created_drip
        # Untouched fields
        assert d.get("steps") == before.get("steps")
        assert d.get("account_ids") == before.get("account_ids")
        assert d.get("total_sent") == before.get("total_sent", 0)
        assert d.get("total_contacts") == before.get("total_contacts", 0)
        assert d.get("status") == before.get("status")
        assert d.get("created_at") == before.get("created_at")

    def test_rename_blank_returns_400(self, primary_session, created_drip):
        for bad in ["", "   ", "\t\n"]:
            r = primary_session.post(_api(f"/drip-campaigns/{created_drip}/rename"),
                                     json={"name": bad}, timeout=10)
            assert r.status_code == 400, f"name={bad!r} → {r.status_code}"
            detail = r.json().get("detail", "")
            assert "blank" in detail.lower(), detail

    def test_rename_duplicate_name_returns_400(self, primary_session):
        n1 = f"TEST_RD_dup_a_{uuid.uuid4().hex[:5]}"
        n2 = f"TEST_RD_dup_b_{uuid.uuid4().hex[:5]}"
        d1 = _make_drip(primary_session, name=n1)
        d2 = _make_drip(primary_session, name=n2)
        try:
            r = primary_session.post(_api(f"/drip-campaigns/{d2}/rename"),
                                     json={"name": n1}, timeout=10)
            assert r.status_code == 400
            assert "already exists" in r.json().get("detail", "").lower()
        finally:
            _db.drip_campaigns.delete_many({"drip_id": {"$in": [d1, d2]}})

    def test_rename_same_name_self_allowed(self, primary_session):
        name = f"TEST_RD_self_{uuid.uuid4().hex[:6]}"
        d = _make_drip(primary_session, name=name)
        try:
            r = primary_session.post(_api(f"/drip-campaigns/{d}/rename"),
                                     json={"name": name}, timeout=10)
            assert r.status_code == 200, r.text
            assert r.json()["name"] == name
        finally:
            _db.drip_campaigns.delete_one({"drip_id": d})

    def test_rename_nonexistent_returns_404(self, primary_session):
        r = primary_session.post(_api("/drip-campaigns/drip_doesnotexist/rename"),
                                 json={"name": "whatever"}, timeout=10)
        assert r.status_code == 404

    def test_rename_cross_user_returns_404(self, primary_session, secondary_user):
        d = _make_drip(primary_session, name=f"TEST_RD_iso_{uuid.uuid4().hex[:5]}")
        try:
            r = secondary_user["session"].post(
                _api(f"/drip-campaigns/{d}/rename"),
                json={"name": "Hacked"}, timeout=10,
            )
            assert r.status_code == 404
            # Confirm name unchanged
            doc = _db.drip_campaigns.find_one({"drip_id": d}, {"_id": 0, "name": 1})
            assert doc["name"].startswith("TEST_RD_iso_")
        finally:
            _db.drip_campaigns.delete_one({"drip_id": d})


# ---------- DUPLICATE ----------

class TestDuplicate:
    def test_duplicate_unauthenticated(self):
        r = requests.post(_api("/drip-campaigns/anything/duplicate"), timeout=10)
        assert r.status_code == 401

    def test_duplicate_nonexistent_returns_404(self, primary_session):
        r = primary_session.post(_api("/drip-campaigns/drip_nope_404/duplicate"), timeout=10)
        assert r.status_code == 404

    def test_duplicate_cross_user_returns_404(self, primary_session, secondary_user):
        d = _make_drip(primary_session, name=f"TEST_RD_iso2_{uuid.uuid4().hex[:5]}")
        try:
            r = secondary_user["session"].post(_api(f"/drip-campaigns/{d}/duplicate"), timeout=10)
            assert r.status_code == 404
        finally:
            _db.drip_campaigns.delete_one({"drip_id": d})

    def test_duplicate_creates_clean_draft_deep_copy(self, primary_session, rich_drip):
        original = _db.drip_campaigns.find_one({"drip_id": rich_drip}, {"_id": 0})
        original_name = original["name"]

        r = primary_session.post(_api(f"/drip-campaigns/{rich_drip}/duplicate"), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        new_id = data["drip_id"]
        try:
            # Response shape
            assert new_id != rich_drip
            assert data["status"] == "draft"
            assert data["name"] == f"{original_name} (Copy)"

            # Verify the new document
            new_doc = _db.drip_campaigns.find_one({"drip_id": new_id}, {"_id": 0})
            assert new_doc is not None
            assert new_doc["status"] == "draft"
            assert new_doc["total_sent"] == 0
            assert new_doc["total_contacts"] == 0
            assert new_doc.get("started_at") is None
            assert new_doc.get("completed_at") is None
            assert new_doc.get("paused_at") is None
            assert new_doc["user_id"] == original["user_id"]

            # Config fields copied
            assert new_doc["account_ids"] == original["account_ids"]
            assert new_doc["schedule"] == original["schedule"]
            assert new_doc["suppression_list_ids"] == original["suppression_list_ids"]
            assert new_doc["tracking_opens"] == original["tracking_opens"]
            assert new_doc["tracking_clicks"] == original["tracking_clicks"]
            assert new_doc["add_unsubscribe_footer"] == original["add_unsubscribe_footer"]
            assert new_doc["from_name"] == original["from_name"]
            assert new_doc["stop_on_reply"] == original["stop_on_reply"]
            assert new_doc["stop_on_bounce"] == original["stop_on_bounce"]

            # Steps deep-copy: same content, but independent lists
            assert new_doc["steps"] == original["steps"]
            assert new_doc["steps"] is not original["steps"]

            # Deep-copy: modifying new doc's step shouldn't affect original
            _db.drip_campaigns.update_one(
                {"drip_id": new_id},
                {"$set": {"steps.0.subject": "MUTATED"}},
            )
            re_orig = _db.drip_campaigns.find_one({"drip_id": rich_drip}, {"_id": 0})
            assert re_orig["steps"][0]["subject"] == original["steps"][0]["subject"]
            assert re_orig["steps"][0]["subject"] != "MUTATED"

            # drip_contacts NOT copied
            assert _db.drip_contacts.count_documents({"drip_id": new_id}) == 0
            # Original's contacts still intact
            assert _db.drip_contacts.count_documents({"drip_id": rich_drip}) == 2
        finally:
            _db.drip_campaigns.delete_one({"drip_id": new_id})

    def test_duplicate_then_rename_independent(self, primary_session, created_drip):
        """Renaming the duplicate must not affect the original (and vice versa)."""
        original_name = _db.drip_campaigns.find_one({"drip_id": created_drip})["name"]
        r = primary_session.post(_api(f"/drip-campaigns/{created_drip}/duplicate"), timeout=10)
        assert r.status_code == 200
        new_id = r.json()["drip_id"]
        try:
            new_name = f"TEST_RD_dup_renamed_{uuid.uuid4().hex[:5]}"
            r2 = primary_session.post(_api(f"/drip-campaigns/{new_id}/rename"),
                                      json={"name": new_name}, timeout=10)
            assert r2.status_code == 200
            # Original unchanged
            orig_after = _db.drip_campaigns.find_one({"drip_id": created_drip})
            assert orig_after["name"] == original_name
        finally:
            _db.drip_campaigns.delete_one({"drip_id": new_id})
