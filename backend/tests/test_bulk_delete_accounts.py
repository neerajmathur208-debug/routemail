"""
Backend tests for POST /api/accounts/bulk-delete

Covers:
- 400 on empty account_ids
- 401 when unauthenticated
- Cross-user isolation (silently skipped, deleted:0, skipped:N)
- Successful bulk delete when no active references (deleted:N)
- Safety: campaigns/email_queue/drip_contacts/replies counts unchanged
- Active-campaign protection: requires_force=true; db unchanged
- Active-drip protection
- Force override: deletes accounts, campaign rows + account_ids preserved
"""

import os
import uuid
import time
import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
assert BASE_URL and MONGO_URL and DB_NAME

PRIMARY_EMAIL = "drip.tester@example.com"
PRIMARY_PASSWORD = "DripTest123!"
PRIMARY_USER_ID = "user_35cc629e1385"

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]


def _api(p):
    return f"{BASE_URL}/api{p}"


@pytest.fixture(scope="module")
def primary_session():
    s = requests.Session()
    r = s.post(_api("/auth/login"), json={"email": PRIMARY_EMAIL, "password": PRIMARY_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    yield s


@pytest.fixture(scope="module")
def other_user():
    """Create a second verified user for cross-user isolation test."""
    email = f"TEST_bulkdel_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "BulkDelOther123!"
    s = requests.Session()
    r = s.post(_api("/auth/register"), json={"email": email, "password": pwd, "confirm_password": pwd, "name": "Bulk Other"}, timeout=20)
    assert r.status_code in (200, 201), f"register failed: {r.text}"
    _db.users.update_one({"email": email}, {"$set": {"email_verified": True}})
    r = s.post(_api("/auth/login"), json={"email": email, "password": pwd}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.text}"
    user_doc = _db.users.find_one({"email": email})
    yield {"session": s, "email": email, "user_id": user_doc["user_id"]}
    # cleanup
    _db.email_accounts.delete_many({"user_id": user_doc["user_id"]})
    _db.campaigns.delete_many({"user_id": user_doc["user_id"]})
    _db.users.delete_one({"email": email})


def _seed_account(user_id, suffix=""):
    acct_id = f"acct_TEST_bd_{uuid.uuid4().hex[:8]}{suffix}"
    doc = {
        "account_id": acct_id,
        "user_id": user_id,
        "email": f"{acct_id}@example.com",
        "name": "Bulk Delete Test",
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": f"{acct_id}@example.com",
        "smtp_password_encrypted": "fake",
        "imap_host": "imap.example.com",
        "imap_port": 993,
        "imap_username": f"{acct_id}@example.com",
        "imap_password_encrypted": "fake",
        "use_tls": True,
        "daily_limit": 50,
        "sent_today": 0,
        "status": "active",
        "created_at": "2025-01-01T00:00:00",
    }
    _db.email_accounts.insert_one(doc)
    return acct_id


@pytest.fixture
def cleanup_test_accounts():
    """Cleanup any TEST_bd accounts/campaigns at teardown."""
    yield
    _db.email_accounts.delete_many({"account_id": {"$regex": "^acct_TEST_bd_"}})
    _db.campaigns.delete_many({"campaign_id": {"$regex": "^camp_TEST_bd_"}})
    _db.drip_campaigns.delete_many({"drip_id": {"$regex": "^drip_TEST_bd_"}})


# ---- tests ----

class TestBulkDeleteAccounts:

    def test_empty_account_ids_returns_400(self, primary_session):
        r = primary_session.post(_api("/accounts/bulk-delete"), json={"account_ids": []}, timeout=20)
        assert r.status_code == 400
        body = r.json()
        assert "no accounts selected" in (body.get("detail") or "").lower()

    def test_unauth_returns_401(self):
        s = requests.Session()
        r = s.post(_api("/accounts/bulk-delete"), json={"account_ids": ["x"]}, timeout=20)
        assert r.status_code == 401

    def test_cross_user_silently_skipped(self, primary_session, other_user, cleanup_test_accounts):
        other_acct = _seed_account(other_user["user_id"])
        try:
            r = primary_session.post(
                _api("/accounts/bulk-delete"), json={"account_ids": [other_acct]}, timeout=20
            )
            assert r.status_code == 200
            body = r.json()
            assert body["deleted"] == 0
            assert body.get("skipped") == 1
            # Confirm not deleted in DB
            assert _db.email_accounts.find_one({"account_id": other_acct}) is not None
        finally:
            _db.email_accounts.delete_one({"account_id": other_acct})

    def test_bulk_delete_success_no_active(self, primary_session, cleanup_test_accounts):
        a1 = _seed_account(PRIMARY_USER_ID)
        a2 = _seed_account(PRIMARY_USER_ID)

        # snapshot counts
        camp_before = _db.campaigns.count_documents({"user_id": PRIMARY_USER_ID})
        queue_before = _db.email_queue.count_documents({"user_id": PRIMARY_USER_ID})
        dripc_before = _db.drip_contacts.count_documents({"user_id": PRIMARY_USER_ID})
        reply_before = _db.replies.count_documents({"user_id": PRIMARY_USER_ID})

        r = primary_session.post(
            _api("/accounts/bulk-delete"), json={"account_ids": [a1, a2], "force": False}, timeout=20
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["deleted"] == 2
        assert body["blocked"] == 0
        assert body["blocked_accounts"] == []
        assert body.get("requires_force") in (False, None)

        # DB verifies deletion
        assert _db.email_accounts.find_one({"account_id": a1}) is None
        assert _db.email_accounts.find_one({"account_id": a2}) is None

        # safety: untouched collections
        assert _db.campaigns.count_documents({"user_id": PRIMARY_USER_ID}) == camp_before
        assert _db.email_queue.count_documents({"user_id": PRIMARY_USER_ID}) == queue_before
        assert _db.drip_contacts.count_documents({"user_id": PRIMARY_USER_ID}) == dripc_before
        assert _db.replies.count_documents({"user_id": PRIMARY_USER_ID}) == reply_before

    def test_active_campaign_blocks_delete(self, primary_session, cleanup_test_accounts):
        a1 = _seed_account(PRIMARY_USER_ID)
        camp_id = f"camp_TEST_bd_{uuid.uuid4().hex[:8]}"
        _db.campaigns.insert_one({
            "campaign_id": camp_id,
            "user_id": PRIMARY_USER_ID,
            "name": "TEST_BD running campaign",
            "status": "running",
            "account_ids": [a1],
            "created_at": "2025-01-01T00:00:00",
        })

        r = primary_session.post(
            _api("/accounts/bulk-delete"), json={"account_ids": [a1], "force": False}, timeout=20
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["deleted"] == 0
        assert body["blocked"] == 1
        assert body.get("requires_force") is True
        assert any(b["account_id"] == a1 for b in body["blocked_accounts"])
        assert any(c["campaign_id"] == camp_id for c in body.get("active_campaigns", []))

        # DB: account still exists, campaign still exists
        assert _db.email_accounts.find_one({"account_id": a1}) is not None
        camp = _db.campaigns.find_one({"campaign_id": camp_id})
        assert camp is not None
        assert camp["status"] == "running"
        assert a1 in camp["account_ids"]

        # Force override
        r2 = primary_session.post(
            _api("/accounts/bulk-delete"), json={"account_ids": [a1], "force": True}, timeout=20
        )
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["deleted"] == 1

        # account gone, campaign preserved untouched
        assert _db.email_accounts.find_one({"account_id": a1}) is None
        camp2 = _db.campaigns.find_one({"campaign_id": camp_id})
        assert camp2 is not None
        assert camp2["status"] == "running"
        assert camp2["account_ids"] == [a1]

    def test_active_drip_blocks_delete(self, primary_session, cleanup_test_accounts):
        a1 = _seed_account(PRIMARY_USER_ID)
        drip_id = f"drip_TEST_bd_{uuid.uuid4().hex[:8]}"
        _db.drip_campaigns.insert_one({
            "drip_id": drip_id,
            "user_id": PRIMARY_USER_ID,
            "name": "TEST_BD running drip",
            "status": "running",
            "account_ids": [a1],
            "steps": [],
            "created_at": "2025-01-01T00:00:00",
        })
        try:
            r = primary_session.post(
                _api("/accounts/bulk-delete"), json={"account_ids": [a1], "force": False}, timeout=20
            )
            assert r.status_code == 200
            body = r.json()
            assert body["deleted"] == 0
            assert body.get("requires_force") is True
            assert any(d["drip_id"] == drip_id for d in body.get("active_drips", []))
            assert _db.email_accounts.find_one({"account_id": a1}) is not None
        finally:
            _db.drip_campaigns.delete_one({"drip_id": drip_id})
            _db.email_accounts.delete_one({"account_id": a1})

    def test_completed_campaign_does_not_block(self, primary_session, cleanup_test_accounts):
        """A campaign in a terminal/non-active status should NOT block deletion."""
        a1 = _seed_account(PRIMARY_USER_ID)
        camp_id = f"camp_TEST_bd_{uuid.uuid4().hex[:8]}"
        _db.campaigns.insert_one({
            "campaign_id": camp_id,
            "user_id": PRIMARY_USER_ID,
            "name": "TEST_BD completed",
            "status": "completed",
            "account_ids": [a1],
        })
        try:
            r = primary_session.post(
                _api("/accounts/bulk-delete"), json={"account_ids": [a1], "force": False}, timeout=20
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["deleted"] == 1
            assert body["blocked"] == 0
            # campaign preserved
            assert _db.campaigns.find_one({"campaign_id": camp_id}) is not None
        finally:
            _db.campaigns.delete_one({"campaign_id": camp_id})
