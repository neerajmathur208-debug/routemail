"""
Drip Campaigns feature end-to-end backend tests.

Covers:
- CRUD (create, list, get with stats, update, delete)
- Status guards (update/delete rejected while running)
- Contact enrollment from an email list with duplicate skipping
- Pagination + status filter on /contacts and /logs
- CSV export headers and content-type
- Start / Pause / Resume state transitions and validation errors
- Auth (401) + user isolation (404)
- MongoDB _id never leaked in any response

Uses the pre-seeded verified user from /app/memory/test_credentials.md.
A second throw-away user (TEST_drip_other_<uuid>@example.com) is created,
verified directly in Mongo, and used to test user isolation. Cleaned up at end.

SMTP account creation is bypassed by inserting a fake account directly into
`email_accounts` (since test_smtp_connection would fail against mocked hosts).
All test artifacts (drip_*, list_*, account_*, second user) are cleaned up.
"""

import os
import csv
import io
import uuid
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set in /app/frontend/.env"

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
assert MONGO_URL and DB_NAME, "MONGO_URL / DB_NAME must be set in /app/backend/.env"

PRIMARY_EMAIL = "drip.tester@example.com"
PRIMARY_PASSWORD = "DripTest123!"

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]


def _api(path: str) -> str:
    return f"{BASE_URL}/api{path}"


# ---------- helpers ----------

def _login(session: requests.Session, email: str, password: str) -> str:
    r = session.post(_api("/auth/login"), json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    token = session.cookies.get("session_token")
    assert token, "No session_token cookie returned"
    return token


def _no_mongo_id(obj):
    """Recursively assert no '_id' key in dicts/lists."""
    if isinstance(obj, dict):
        assert "_id" not in obj, f"MongoDB _id leaked: {list(obj.keys())}"
        for v in obj.values():
            _no_mongo_id(v)
    elif isinstance(obj, list):
        for item in obj:
            _no_mongo_id(item)


# ---------- fixtures ----------

@pytest.fixture(scope="session")
def primary_session():
    s = requests.Session()
    _login(s, PRIMARY_EMAIL, PRIMARY_PASSWORD)
    return s


@pytest.fixture(scope="session")
def primary_user_id(primary_session):
    r = primary_session.get(_api("/auth/me"), timeout=10)
    if r.status_code == 200:
        return r.json().get("user_id") or "user_35cc629e1385"
    return "user_35cc629e1385"


@pytest.fixture(scope="session")
def secondary_user():
    """Create second user directly in Mongo (verified), login via API."""
    import bcrypt
    from datetime import datetime, timezone
    suffix = uuid.uuid4().hex[:8]
    email = f"TEST_drip_other_{suffix}@example.com"
    password = "OtherUser123!"
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    _db.users.insert_one({
        "user_id": user_id,
        "email": email,
        "password_hash": pw_hash,
        "name": "Drip Other Tester",
        "email_verified": True,
        "provider": "email",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "plan_type": "free",
        "subscription_status": "active",
    })
    s = requests.Session()
    _login(s, email, password)
    yield {"session": s, "user_id": user_id, "email": email}
    # cleanup
    _db.users.delete_one({"user_id": user_id})
    _db.user_sessions.delete_many({"user_id": user_id})


@pytest.fixture(scope="session")
def seeded_list(primary_session, primary_user_id):
    """Create an email list with 3 emails; yield list_id."""
    payload = {
        "name": f"TEST_drip_list_{uuid.uuid4().hex[:6]}",
        "original_filename": "test.csv",
        "column_headers": ["email", "name"],
        "emails": [
            {"email": "drip.contact1@example.com", "name": "Alice"},
            {"email": "drip.contact2@example.com", "name": "Bob"},
            {"email": "drip.contact3@example.com", "name": "Carol"},
        ],
    }
    r = primary_session.post(_api("/lists"), json=payload, timeout=20)
    assert r.status_code == 200, f"List create failed: {r.status_code} {r.text}"
    list_id = r.json()["list_id"]
    yield list_id
    _db.email_lists.delete_one({"list_id": list_id})


@pytest.fixture(scope="session")
def seeded_account(primary_user_id):
    """Insert a fake connected email_account directly into Mongo (bypass SMTP test)."""
    from datetime import datetime, timezone
    account_id = f"account_TEST_{uuid.uuid4().hex[:10]}"
    _db.email_accounts.insert_one({
        "account_id": account_id,
        "user_id": primary_user_id,
        "account_type": "smtp",
        "email": f"TEST_drip_sender_{account_id[-6:]}@example.com",
        "display_name": "Drip Tester Sender",
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": "tester",
        "smtp_password_encrypted": "x",
        "smtp_encryption": "tls",
        "daily_limit": 50,
        "send_delay": 30,
        "status": "connected",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "last_reset_at": datetime.now(timezone.utc).isoformat(),
    })
    yield account_id
    _db.email_accounts.delete_one({"account_id": account_id})


@pytest.fixture
def created_drip(primary_session):
    """Create a fresh draft drip campaign for each test; cleanup after."""
    name = f"TEST_drip_{uuid.uuid4().hex[:6]}"
    r = primary_session.post(_api("/drip-campaigns"), json={"name": name}, timeout=20)
    assert r.status_code == 200, f"Create failed: {r.status_code} {r.text}"
    data = r.json()
    drip_id = data["drip_id"]
    yield data
    # cleanup — force paused/draft then delete
    _db.drip_campaigns.update_one({"drip_id": drip_id}, {"$set": {"status": "draft"}})
    _db.drip_campaigns.delete_one({"drip_id": drip_id})
    _db.drip_contacts.delete_many({"drip_id": drip_id})
    _db.drip_logs.delete_many({"drip_id": drip_id})


# ---------- Auth ----------

class TestAuth:
    def test_list_requires_auth(self):
        r = requests.get(_api("/drip-campaigns"), timeout=10)
        assert r.status_code == 401

    def test_create_requires_auth(self):
        r = requests.post(_api("/drip-campaigns"), json={"name": "x"}, timeout=10)
        assert r.status_code == 401

    def test_detail_requires_auth(self):
        r = requests.get(_api("/drip-campaigns/drip_fakefake"), timeout=10)
        assert r.status_code == 401


# ---------- CRUD ----------

class TestCRUD:
    def test_create_drip_returns_draft(self, primary_session):
        name = f"TEST_drip_{uuid.uuid4().hex[:6]}"
        r = primary_session.post(_api("/drip-campaigns"), json={"name": name}, timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        _no_mongo_id(data)
        assert data["name"] == name
        assert data["status"] == "draft"
        assert data["drip_id"].startswith("drip_")
        assert data["steps"] == []
        assert data["schedule"]["timezone"] == "UTC"
        # cleanup
        _db.drip_campaigns.delete_one({"drip_id": data["drip_id"]})

    def test_list_includes_created(self, primary_session, created_drip):
        r = primary_session.get(_api("/drip-campaigns"), timeout=10)
        assert r.status_code == 200
        items = r.json()
        _no_mongo_id(items)
        assert isinstance(items, list)
        assert any(c["drip_id"] == created_drip["drip_id"] for c in items)

    def test_get_detail_has_stats(self, primary_session, created_drip):
        r = primary_session.get(_api(f"/drip-campaigns/{created_drip['drip_id']}"), timeout=10)
        assert r.status_code == 200
        data = r.json()
        _no_mongo_id(data)
        assert "stats" in data
        for k in ["total_contacts", "active", "completed", "replied", "bounced", "emails_sent", "emails_failed"]:
            assert k in data["stats"], f"Missing stats key {k}"
            assert isinstance(data["stats"][k], int)

    def test_update_normalizes_step_numbers(self, primary_session, created_drip):
        steps = [
            {"step_number": 77, "subject": "s1", "body": "b1", "delay_days": 0, "delay_hours": 0},
            {"step_number": 3, "subject": "s2", "body": "b2", "delay_days": 1, "delay_hours": 0},
            {"step_number": 1, "subject": "s3", "body": "b3", "delay_days": 2, "delay_hours": 0},
        ]
        r = primary_session.put(_api(f"/drip-campaigns/{created_drip['drip_id']}"),
                                json={"steps": steps, "name": "TEST_drip_renamed"}, timeout=10)
        assert r.status_code == 200, r.text
        # verify via GET
        r2 = primary_session.get(_api(f"/drip-campaigns/{created_drip['drip_id']}"), timeout=10)
        data = r2.json()
        assert data["name"] == "TEST_drip_renamed"
        assert len(data["steps"]) == 3
        assert [s["step_number"] for s in data["steps"]] == [1, 2, 3]
        # subjects preserved in order
        assert data["steps"][0]["subject"] == "s1"
        assert data["steps"][2]["subject"] == "s3"

    def test_update_schedule_roundtrip(self, primary_session, created_drip):
        schedule = {
            "timezone": "America/New_York",
            "sending_days": [0, 2, 4],
            "start_time": "08:30",
            "end_time": "17:45",
            "randomize_time": True,
        }
        r = primary_session.put(_api(f"/drip-campaigns/{created_drip['drip_id']}"),
                                json={"schedule": schedule}, timeout=10)
        assert r.status_code == 200
        r2 = primary_session.get(_api(f"/drip-campaigns/{created_drip['drip_id']}"), timeout=10)
        got = r2.json()["schedule"]
        assert got == schedule

    def test_delete_draft(self, primary_session):
        r = primary_session.post(_api("/drip-campaigns"), json={"name": f"TEST_del_{uuid.uuid4().hex[:4]}"}, timeout=10)
        drip_id = r.json()["drip_id"]
        r2 = primary_session.delete(_api(f"/drip-campaigns/{drip_id}"), timeout=10)
        assert r2.status_code == 200
        r3 = primary_session.get(_api(f"/drip-campaigns/{drip_id}"), timeout=10)
        assert r3.status_code == 404


# ---------- Contacts ----------

class TestContactEnrollment:
    def test_enroll_and_dedupe(self, primary_session, created_drip, seeded_list):
        drip_id = created_drip["drip_id"]
        r = primary_session.post(_api(f"/drip-campaigns/{drip_id}/contacts"),
                                 json={"list_id": seeded_list}, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["added"] == 3
        assert body["total_contacts"] == 3
        # second enrollment should be all skipped
        r2 = primary_session.post(_api(f"/drip-campaigns/{drip_id}/contacts"),
                                  json={"list_id": seeded_list}, timeout=15)
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["added"] == 0
        assert body2["skipped_duplicates"] == 3
        assert body2["total_contacts"] == 3

    def test_list_contacts_pagination_and_status(self, primary_session, created_drip, seeded_list):
        drip_id = created_drip["drip_id"]
        primary_session.post(_api(f"/drip-campaigns/{drip_id}/contacts"),
                             json={"list_id": seeded_list}, timeout=15)
        r = primary_session.get(_api(f"/drip-campaigns/{drip_id}/contacts?skip=0&limit=2"), timeout=10)
        assert r.status_code == 200
        data = r.json()
        _no_mongo_id(data)
        assert data["total"] == 3
        assert len(data["contacts"]) == 2
        # status filter
        r2 = primary_session.get(_api(f"/drip-campaigns/{drip_id}/contacts?status=active"), timeout=10)
        assert r2.status_code == 200
        assert r2.json()["total"] == 3

    def test_enroll_nonexistent_list_returns_404(self, primary_session, created_drip):
        r = primary_session.post(_api(f"/drip-campaigns/{created_drip['drip_id']}/contacts"),
                                 json={"list_id": "list_doesnotexist"}, timeout=10)
        assert r.status_code == 404


# ---------- Logs / CSV ----------

class TestLogs:
    def test_logs_empty(self, primary_session, created_drip):
        r = primary_session.get(_api(f"/drip-campaigns/{created_drip['drip_id']}/logs"), timeout=10)
        assert r.status_code == 200
        d = r.json()
        _no_mongo_id(d)
        assert d["total"] == 0
        assert d["logs"] == []

    def test_logs_csv_export_headers(self, primary_session, created_drip):
        r = primary_session.get(_api(f"/drip-campaigns/{created_drip['drip_id']}/logs/export"), timeout=10)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert "attachment" in r.headers.get("content-disposition", "")
        reader = csv.reader(io.StringIO(r.text))
        rows = list(reader)
        assert rows[0] == ["Recipient", "Step", "Subject", "Sent From", "Status", "Sent At", "Error"]


# ---------- Start / Pause / Resume ----------

class TestStateTransitions:
    def test_start_rejects_empty_steps(self, primary_session, created_drip):
        r = primary_session.post(_api(f"/drip-campaigns/{created_drip['drip_id']}/start"), timeout=10)
        assert r.status_code == 400
        assert "step" in r.json().get("detail", "").lower()

    def test_start_rejects_no_accounts(self, primary_session, created_drip):
        drip_id = created_drip["drip_id"]
        primary_session.put(_api(f"/drip-campaigns/{drip_id}"),
                            json={"steps": [{"step_number": 1, "subject": "s", "body": "b"}]}, timeout=10)
        r = primary_session.post(_api(f"/drip-campaigns/{drip_id}/start"), timeout=10)
        assert r.status_code == 400
        assert "account" in r.json().get("detail", "").lower()

    def test_start_rejects_no_contacts(self, primary_session, created_drip, seeded_account):
        drip_id = created_drip["drip_id"]
        primary_session.put(_api(f"/drip-campaigns/{drip_id}"), json={
            "steps": [{"step_number": 1, "subject": "s", "body": "b"}],
            "account_ids": [seeded_account],
        }, timeout=10)
        r = primary_session.post(_api(f"/drip-campaigns/{drip_id}/start"), timeout=10)
        assert r.status_code == 400
        assert "contact" in r.json().get("detail", "").lower()

    def test_full_start_pause_resume_cycle(self, primary_session, created_drip, seeded_account, seeded_list):
        drip_id = created_drip["drip_id"]
        primary_session.put(_api(f"/drip-campaigns/{drip_id}"), json={
            "steps": [{"step_number": 1, "subject": "Hi", "body": "Hello"}],
            "account_ids": [seeded_account],
        }, timeout=10)
        primary_session.post(_api(f"/drip-campaigns/{drip_id}/contacts"),
                             json={"list_id": seeded_list}, timeout=15)

        # start
        r = primary_session.post(_api(f"/drip-campaigns/{drip_id}/start"), timeout=10)
        assert r.status_code == 200, r.text
        got = primary_session.get(_api(f"/drip-campaigns/{drip_id}"), timeout=10).json()
        assert got["status"] == "running"
        assert got.get("started_at")

        # update blocked while running
        r_up = primary_session.put(_api(f"/drip-campaigns/{drip_id}"), json={"name": "should fail"}, timeout=10)
        assert r_up.status_code == 400

        # delete blocked while running
        r_del = primary_session.delete(_api(f"/drip-campaigns/{drip_id}"), timeout=10)
        assert r_del.status_code == 400

        # pause
        r_p = primary_session.post(_api(f"/drip-campaigns/{drip_id}/pause"), timeout=10)
        assert r_p.status_code == 200
        assert primary_session.get(_api(f"/drip-campaigns/{drip_id}"), timeout=10).json()["status"] == "paused"

        # pause again rejected
        r_p2 = primary_session.post(_api(f"/drip-campaigns/{drip_id}/pause"), timeout=10)
        assert r_p2.status_code == 400

        # update while paused now allowed
        r_up2 = primary_session.put(_api(f"/drip-campaigns/{drip_id}"), json={"name": "TEST_drip_paused_rename"}, timeout=10)
        assert r_up2.status_code == 200

        # resume
        r_r = primary_session.post(_api(f"/drip-campaigns/{drip_id}/resume"), timeout=10)
        assert r_r.status_code == 200
        assert primary_session.get(_api(f"/drip-campaigns/{drip_id}"), timeout=10).json()["status"] == "running"

        # resume again rejected
        r_r2 = primary_session.post(_api(f"/drip-campaigns/{drip_id}/resume"), timeout=10)
        assert r_r2.status_code == 400


# ---------- User isolation ----------

class TestUserIsolation:
    def test_other_user_cannot_read(self, primary_session, secondary_user, created_drip):
        other = secondary_user["session"]
        r = other.get(_api(f"/drip-campaigns/{created_drip['drip_id']}"), timeout=10)
        assert r.status_code == 404

    def test_other_user_cannot_update(self, primary_session, secondary_user, created_drip):
        other = secondary_user["session"]
        r = other.put(_api(f"/drip-campaigns/{created_drip['drip_id']}"),
                      json={"name": "hax"}, timeout=10)
        assert r.status_code == 404

    def test_other_user_cannot_delete(self, primary_session, secondary_user, created_drip):
        other = secondary_user["session"]
        r = other.delete(_api(f"/drip-campaigns/{created_drip['drip_id']}"), timeout=10)
        assert r.status_code == 404

    def test_other_user_list_excludes(self, primary_session, secondary_user, created_drip):
        other = secondary_user["session"]
        r = other.get(_api("/drip-campaigns"), timeout=10)
        assert r.status_code == 200
        assert not any(c["drip_id"] == created_drip["drip_id"] for c in r.json())


# ---------- Existing /campaigns regression ----------

class TestStandardCampaignsRegression:
    def test_campaigns_list_still_works(self, primary_session):
        r = primary_session.get(_api("/campaigns"), timeout=10)
        assert r.status_code == 200
        _no_mongo_id(r.json())
