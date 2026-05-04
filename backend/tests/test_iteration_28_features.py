"""
Iteration 28 tests:
- POST /api/lists/{list_id}/records  (validation, lowercase+trim, dedupe, counts, auth)
- DELETE /api/lists/{list_id}/records (404 missing, counts, auth/cross-user)
- is_email_suppressed: legacy suppression_list ALWAYS applied, Global DNE no longer auto-included
- GET /api/unsubscribe/{user_id}/{email}: writes legacy + Global DNE + flips active/paused
  drip_contacts to status='unsubscribed'
- POST /api/accounts/smtp/PUT /api/accounts/{id}/limit: no upper cap (500/1000), rejects bad input
"""
import os
import uuid
import pytest
import requests
import asyncio
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

USER_EMAIL = "drip.tester@example.com"
USER_PASSWORD = "DripTest123!"
USER_ID = "user_35cc629e1385"

mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def list_id(session):
    payload = {
        "name": f"TEST_iter28_list_{uuid.uuid4().hex[:8]}",
        "original_filename": "seed.csv",
        "column_headers": ["email", "first_name"],
        "emails": [
            {"email": "seed1@example.com", "first_name": "Seed1"},
        ],
    }
    r = session.post(f"{API}/lists", json=payload)
    assert r.status_code in (200, 201), r.text
    lid = r.json().get("list_id") or r.json().get("id") or r.json().get("_id")
    if not lid:
        body = r.json()
        lid = body.get("list_id") or (body.get("list") or {}).get("list_id")
    assert lid, f"No list_id returned: {r.text}"
    yield lid
    db.email_lists.delete_one({"list_id": lid, "user_id": USER_ID})


# -------------------------------------------------------------------
# POST /api/lists/{id}/records
# -------------------------------------------------------------------
class TestAddRecord:
    def test_add_valid_lowercases_and_trims(self, session, list_id):
        payload = {"data": {"email": "  ALICE+iter28@Example.COM ", "first_name": "  Alice  "}}
        r = session.post(f"{API}/lists/{list_id}/records", json=payload)
        assert r.status_code in (200, 201), r.text
        rec = r.json()["record"]
        assert rec["email"] == "alice+iter28@example.com"
        assert rec["first_name"] == "Alice"

        lst = db.email_lists.find_one({"list_id": list_id, "user_id": USER_ID})
        assert lst["total_rows"] == len(lst["emails"])
        assert any(e["email"] == "alice+iter28@example.com" for e in lst["emails"])
        # valid_emails counter must include the new one
        assert lst["valid_emails"] >= 2

    def test_add_invalid_email_400(self, session, list_id):
        r = session.post(f"{API}/lists/{list_id}/records",
                         json={"data": {"email": "not-an-email"}})
        assert r.status_code == 400
        assert "invalid" in r.text.lower() or "email" in r.text.lower()

    def test_add_empty_email_400(self, session, list_id):
        r = session.post(f"{API}/lists/{list_id}/records", json={"data": {"email": "   "}})
        assert r.status_code == 400

    def test_add_duplicate_case_insensitive_400(self, session, list_id):
        # alice was added in previous test (lowercase); send mixed-case
        r = session.post(f"{API}/lists/{list_id}/records",
                         json={"data": {"email": "Alice+Iter28@example.com"}})
        assert r.status_code == 400
        assert "exist" in r.text.lower() or "duplicate" in r.text.lower()

    def test_add_to_unknown_list_404(self, session):
        r = session.post(f"{API}/lists/nonexistent_list_id/records",
                         json={"data": {"email": "x@example.com"}})
        assert r.status_code == 404

    def test_add_unauthenticated_blocked(self, list_id):
        anon = requests.Session()
        r = anon.post(f"{API}/lists/{list_id}/records",
                      json={"data": {"email": "anon@example.com"}})
        assert r.status_code in (401, 403)

    def test_add_cross_user_returns_404(self, session, list_id):
        # Make a fake list belonging to a DIFFERENT user. drip.tester must not see it.
        fake_list_id = f"list_TEST_iter28_other_{uuid.uuid4().hex[:8]}"
        db.email_lists.insert_one({
            "list_id": fake_list_id,
            "user_id": "user_OTHER_iter28",
            "name": "OtherUserList",
            "emails": [], "valid_emails": 0, "total_rows": 0,
            "column_headers": ["email"],
        })
        try:
            r = session.post(f"{API}/lists/{fake_list_id}/records",
                             json={"data": {"email": "x@example.com"}})
            assert r.status_code == 404
        finally:
            db.email_lists.delete_one({"list_id": fake_list_id})


# -------------------------------------------------------------------
# DELETE /api/lists/{id}/records
# -------------------------------------------------------------------
class TestDeleteRecord:
    def test_delete_email_present_decrements_counts(self, session, list_id):
        # Seed via direct API
        session.post(f"{API}/lists/{list_id}/records",
                     json={"data": {"email": "to-delete-iter28@example.com"}})
        before = db.email_lists.find_one({"list_id": list_id, "user_id": USER_ID})
        before_total = before["total_rows"]

        r = session.delete(f"{API}/lists/{list_id}/records",
                           json={"email": "TO-DELETE-iter28@Example.com"})
        assert r.status_code == 200, r.text

        after = db.email_lists.find_one({"list_id": list_id, "user_id": USER_ID})
        assert after["total_rows"] == before_total - 1
        assert not any(e["email"] == "to-delete-iter28@example.com" for e in after["emails"])

    def test_delete_email_not_present_404(self, session, list_id):
        r = session.delete(f"{API}/lists/{list_id}/records",
                           json={"email": "nothere-iter28@example.com"})
        assert r.status_code == 404

    def test_delete_unknown_list_404(self, session):
        r = session.delete(f"{API}/lists/nope_iter28/records",
                           json={"email": "x@example.com"})
        assert r.status_code == 404

    def test_delete_unauthenticated_blocked(self, list_id):
        anon = requests.Session()
        r = anon.delete(f"{API}/lists/{list_id}/records",
                        json={"email": "x@example.com"})
        assert r.status_code in (401, 403)


# -------------------------------------------------------------------
# is_email_suppressed: legacy ALWAYS, Global no longer auto-applied
# -------------------------------------------------------------------
class TestIsEmailSuppressed:
    """Direct call into the helper to verify behaviour without sending mail."""

    @pytest.fixture(scope="class")
    def helper(self):
        import sys, importlib
        sys.path.insert(0, "/app/backend")
        server = importlib.import_module("server")
        # Re-bind motor client to a fresh AsyncIOMotorClient so it uses our test loop.
        from motor.motor_asyncio import AsyncIOMotorClient
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        client = AsyncIOMotorClient(MONGO_URL, io_loop=loop)
        server.db = client[DB_NAME]
        yield server, loop
        loop.close()

    def test_legacy_suppression_always_applied(self, helper):
        server, loop = helper
        email = f"legacy-{uuid.uuid4().hex[:8]}@iter28.com"
        db.suppression_list.insert_one({
            "user_id": USER_ID, "email": email,
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            res = loop.run_until_complete(server.is_email_suppressed(USER_ID, email, []))
            assert res is True, "Legacy suppression_list must always block"
            res2 = loop.run_until_complete(server.is_email_suppressed(USER_ID, email, None))
            assert res2 is True
        finally:
            db.suppression_list.delete_one({"user_id": USER_ID, "email": email})

    def test_global_dne_not_auto_applied(self, helper):
        server, loop = helper
        # Find Global DNE list_id (or create one by calling unsubscribe). Read directly.
        global_doc = db.dne_lists.find_one({"user_id": USER_ID, "is_global": True})
        if not global_doc:
            # Force creation through the unsubscribe endpoint to avoid private helper
            tmp_email = f"warmup-{uuid.uuid4().hex[:6]}@iter28.com"
            requests.get(f"{API}/unsubscribe/{USER_ID}/{tmp_email}")
            global_doc = db.dne_lists.find_one({"user_id": USER_ID, "is_global": True})
            assert global_doc, "Global DNE list still not created"
            db.suppression_list.delete_one({"user_id": USER_ID, "email": tmp_email})
            db.dne_emails.delete_one({"user_id": USER_ID, "email": tmp_email})

        global_id = global_doc["list_id"]

        email = f"globalonly-{uuid.uuid4().hex[:8]}@iter28.com"
        db.dne_emails.insert_one({
            "user_id": USER_ID, "list_id": global_id, "email": email,
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            res_no_select = loop.run_until_complete(server.is_email_suppressed(USER_ID, email, []))
            assert res_no_select is False, "Global DNE should NOT be auto-applied"
            res_select = loop.run_until_complete(server.is_email_suppressed(USER_ID, email, [global_id]))
            assert res_select is True
        finally:
            db.dne_emails.delete_one({"user_id": USER_ID, "list_id": global_id, "email": email})


# -------------------------------------------------------------------
# /api/unsubscribe writes legacy + Global + flips drip_contacts
# -------------------------------------------------------------------
class TestUnsubscribeEndpoint:
    def test_unsubscribe_writes_three_sources_and_flips_drip_contacts(self):
        email = f"unsub-{uuid.uuid4().hex[:8]}@iter28.com"
        # Seed two drip_contacts: one active, one paused, plus an UNRELATED one that must NOT change
        contact_active = f"dc_TEST_iter28_active_{uuid.uuid4().hex[:6]}"
        contact_paused = f"dc_TEST_iter28_paused_{uuid.uuid4().hex[:6]}"
        contact_other_email = f"dc_TEST_iter28_other_{uuid.uuid4().hex[:6]}"
        contact_other_user = f"dc_TEST_iter28_otheruser_{uuid.uuid4().hex[:6]}"

        db.drip_contacts.insert_many([
            {"contact_id": contact_active, "user_id": USER_ID,
             "drip_id": "drip_TEST_iter28", "email": email, "status": "active"},
            {"contact_id": contact_paused, "user_id": USER_ID,
             "drip_id": "drip_TEST_iter28", "email": email, "status": "paused"},
            {"contact_id": contact_other_email, "user_id": USER_ID,
             "drip_id": "drip_TEST_iter28", "email": "different@iter28.com", "status": "active"},
            {"contact_id": contact_other_user, "user_id": "user_OTHER_iter28",
             "drip_id": "drip_TEST_iter28", "email": email, "status": "active"},
        ])

        try:
            # Hit endpoint (no auth required)
            r = requests.get(f"{API}/unsubscribe/{USER_ID}/{email}")
            assert r.status_code == 200, r.text

            # 1) suppression_list
            assert db.suppression_list.find_one({"user_id": USER_ID, "email": email}) is not None

            # 2) Global DNE
            global_doc = db.dne_lists.find_one({"user_id": USER_ID, "is_global": True})
            assert global_doc is not None
            assert db.dne_emails.find_one({
                "user_id": USER_ID, "list_id": global_doc["list_id"], "email": email
            }) is not None

            # 3) drip_contacts: same user + email → unsubscribed; others untouched
            assert db.drip_contacts.find_one({"contact_id": contact_active})["status"] == "unsubscribed"
            assert "unsubscribed_at" in db.drip_contacts.find_one({"contact_id": contact_active})
            assert db.drip_contacts.find_one({"contact_id": contact_paused})["status"] == "unsubscribed"
            assert db.drip_contacts.find_one({"contact_id": contact_other_email})["status"] == "active"
            assert db.drip_contacts.find_one({"contact_id": contact_other_user})["status"] == "active"

            # Idempotent: second call must not 500
            r2 = requests.get(f"{API}/unsubscribe/{USER_ID}/{email}")
            assert r2.status_code == 200
        finally:
            db.suppression_list.delete_one({"user_id": USER_ID, "email": email})
            global_doc = db.dne_lists.find_one({"user_id": USER_ID, "is_global": True})
            if global_doc:
                db.dne_emails.delete_one({
                    "user_id": USER_ID, "list_id": global_doc["list_id"], "email": email
                })
            db.drip_contacts.delete_many({"contact_id": {"$in": [
                contact_active, contact_paused, contact_other_email, contact_other_user
            ]}})


# -------------------------------------------------------------------
# daily_limit cap removed
# -------------------------------------------------------------------
class TestDailyLimitNoCap:
    @pytest.fixture(scope="class")
    def seeded_account_id(self):
        # Insert a fake account directly (avoid real SMTP test on POST /accounts/smtp)
        acc_id = f"acc_TEST_iter28_{uuid.uuid4().hex[:8]}"
        db.email_accounts.insert_one({
            "account_id": acc_id,
            "user_id": USER_ID,
            "account_type": "smtp",
            "email": f"smtp_{acc_id}@iter28.com",
            "display_name": "Iter28 SMTP",
            "smtp_host": "smtp.example.com", "smtp_port": 587,
            "smtp_username": "u", "smtp_password_encrypted": "x",
            "smtp_encryption": "tls",
            "daily_limit": 50, "send_delay": 30,
            "status": "connected",
            "daily_send_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_reset_at": datetime.now(timezone.utc).isoformat(),
        })
        yield acc_id
        db.email_accounts.delete_one({"account_id": acc_id})

    def test_put_limit_500(self, session, seeded_account_id):
        r = session.put(f"{API}/accounts/{seeded_account_id}/limit",
                        json={"daily_limit": 500})
        assert r.status_code == 200, r.text
        assert r.json()["daily_limit"] == 500
        assert db.email_accounts.find_one({"account_id": seeded_account_id})["daily_limit"] == 500

    def test_put_limit_1000(self, session, seeded_account_id):
        r = session.put(f"{API}/accounts/{seeded_account_id}/limit",
                        json={"daily_limit": 1000})
        assert r.status_code == 200, r.text
        assert r.json()["daily_limit"] == 1000

    def test_put_limit_zero_normalises_to_one(self, session, seeded_account_id):
        # Endpoint coerces with max(1, int(...)) so 0/-5 should land on 1
        r = session.put(f"{API}/accounts/{seeded_account_id}/limit",
                        json={"daily_limit": 0})
        assert r.status_code == 200
        assert r.json()["daily_limit"] == 1

    def test_put_limit_non_integer_400(self, session, seeded_account_id):
        r = session.put(f"{API}/accounts/{seeded_account_id}/limit",
                        json={"daily_limit": "not-a-number"})
        assert r.status_code in (400, 422)

    def test_put_limit_unknown_account_404(self, session):
        r = session.put(f"{API}/accounts/missing_iter28/limit",
                        json={"daily_limit": 100})
        assert r.status_code == 404
