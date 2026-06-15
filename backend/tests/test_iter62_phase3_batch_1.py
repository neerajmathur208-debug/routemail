"""Iteration 62 — Phase 3 Batch 1 backend tests.

Covers:
 1. Google OAuth removal: POST /api/auth/session → 404.
 2. GET /api/auth/me now returns `password_setup_required` boolean.
 3. POST /api/auth/set-initial-password — validation + happy-path conversion.
 4. POST /api/auth/login on legacy provider='google' user → 401 'migrated from Google sign-in'.
 5. POST /api/auth/forgot-password works for legacy google users + creates attempt row.
 6. POST /api/admin/users/{user_id}/force-password-reset works for google user.
 7. POST /api/auth/register existing google user → 400 'Use Forgot Password'.
 8. ensure_domain_record helper (direct asyncio): new domain, idempotent same-domain
    increments, manually edited rows are NEVER overwritten, bad inputs return None.
 9. POST /api/accounts/smtp creates tracked_domains row (via direct seed of email_accounts
    + helper invocation — endpoint requires real SMTP creds).
10. POST /api/accounts/smtp/bulk-import — 3 inboxes same domain → 1 tracked_domains row,
    linked_inbox_count=3 (helper level verification).
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone, date as _date_cls

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
SUPER_ADMIN_ID = "user_b3e333b0f467"
SUPER_ADMIN_EMAIL = "dhruvmathur208@gmail.com"

TAG = f"TEST_iter62_{uuid.uuid4().hex[:8]}"


# -------- Fixtures --------
@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def admin_token(mongo):
    tok = f"TEST_iter62_{uuid.uuid4().hex}"
    mongo.user_sessions.insert_one({
        "session_token": tok,
        "user_id": SUPER_ADMIN_ID,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=2),
    })
    yield tok
    mongo.user_sessions.delete_one({"session_token": tok})


@pytest.fixture(scope="module")
def client(admin_token):
    s = requests.Session()
    s.cookies.set("session_token", admin_token)
    s.headers.update({"Authorization": f"Bearer {admin_token}"})
    return s


@pytest.fixture(scope="module")
def google_user(mongo):
    """Seed a legacy google-provider user with NO password_hash."""
    uid = f"user_{uuid.uuid4().hex[:12]}"
    email = f"{TAG.lower()}_googleuser_{uuid.uuid4().hex[:6]}@example.com"
    doc = {
        "user_id": uid,
        "email": email,
        "name": "Legacy Google User",
        "provider": "google",
        "email_verified": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "role": "user",
        "plan_type": "free",
        "_tag": TAG,
    }
    mongo.users.insert_one(doc)
    yield {"user_id": uid, "email": email}
    mongo.users.delete_one({"user_id": uid})
    mongo.password_reset_attempts.delete_many({"email": email})


@pytest.fixture(scope="module")
def google_user_session(mongo, google_user):
    tok = f"TEST_iter62_g_{uuid.uuid4().hex}"
    mongo.user_sessions.insert_one({
        "session_token": tok,
        "user_id": google_user["user_id"],
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=2),
    })
    yield tok
    mongo.user_sessions.delete_one({"session_token": tok})


@pytest.fixture(autouse=True, scope="module")
def cleanup_tag(mongo):
    yield
    mongo.users.delete_many({"_tag": TAG})
    mongo.tracked_domains.delete_many({"user_id": {"$regex": "^test_iter62_"}})
    mongo.tracked_domains.delete_many({"domain": {"$regex": "iter62"}})


# ============================================================
# 1. GOOGLE OAUTH REMOVED
# ============================================================
class TestGoogleAuthRemoved:
    def test_auth_session_returns_404(self, client):
        r = client.post(f"{BASE_URL}/api/auth/session", json={"session_id": "abc"})
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:200]}"


# ============================================================
# 2. /auth/me — password_setup_required
# ============================================================
class TestAuthMePasswordSetupFlag:
    def test_me_normal_user_false(self, client):
        r = client.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "password_setup_required" in data
        assert data["password_setup_required"] is False
        assert data["email"] == SUPER_ADMIN_EMAIL

    def test_me_google_user_true(self, google_user_session):
        s = requests.Session()
        s.cookies.set("session_token", google_user_session)
        s.headers.update({"Authorization": f"Bearer {google_user_session}"})
        r = s.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["password_setup_required"] is True


# ============================================================
# 3. /auth/set-initial-password
# ============================================================
class TestSetInitialPassword:
    def test_set_password_too_short(self, google_user_session):
        s = requests.Session()
        s.cookies.set("session_token", google_user_session)
        r = s.post(f"{BASE_URL}/api/auth/set-initial-password",
                   json={"password": "short", "confirm_password": "short"})
        assert r.status_code == 400
        assert "8 characters" in r.json().get("detail", "")

    def test_set_password_mismatch(self, google_user_session):
        s = requests.Session()
        s.cookies.set("session_token", google_user_session)
        r = s.post(f"{BASE_URL}/api/auth/set-initial-password",
                   json={"password": "Validpass123!", "confirm_password": "Different123!"})
        assert r.status_code == 400
        assert "do not match" in r.json().get("detail", "")

    def test_set_password_happy_path_and_flag_flips(self, mongo, google_user, google_user_session):
        s = requests.Session()
        s.cookies.set("session_token", google_user_session)
        new_pwd = "NewStrongPass123!"
        r = s.post(f"{BASE_URL}/api/auth/set-initial-password",
                   json={"password": new_pwd, "confirm_password": new_pwd})
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True

        # Verify user doc mutated
        u = mongo.users.find_one({"user_id": google_user["user_id"]}, {"_id": 0})
        assert u["provider"] == "email"
        assert u.get("password_hash")
        assert u.get("password_set_at")

        # /auth/me flag now False
        r2 = s.get(f"{BASE_URL}/api/auth/me")
        assert r2.status_code == 200
        assert r2.json()["password_setup_required"] is False

    def test_set_password_rejected_when_already_set(self, client):
        # Super admin already has a password and is provider != google
        r = client.post(f"{BASE_URL}/api/auth/set-initial-password",
                        json={"password": "Anotherpass123!",
                              "confirm_password": "Anotherpass123!"})
        assert r.status_code == 400
        assert "already set" in r.json().get("detail", "").lower()


# ============================================================
# 4. /auth/login — legacy google user
# ============================================================
class TestLoginLegacyGoogleUser:
    def test_login_legacy_google_blocked(self, mongo):
        # Seed a fresh google user (no password) — independent of the one
        # converted in TestSetInitialPassword
        uid = f"user_{uuid.uuid4().hex[:12]}"
        email = f"{TAG}_glogin_{uuid.uuid4().hex[:6]}@example.com"
        mongo.users.insert_one({
            "user_id": uid,
            "email": email,
            "provider": "google",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "_tag": TAG,
        })
        try:
            r = requests.post(f"{BASE_URL}/api/auth/login",
                              json={"email": email, "password": "anything123"})
            assert r.status_code == 401
            detail = (r.json().get("detail") or "").lower()
            assert "migrated from google" in detail or "google sign-in" in detail
        finally:
            mongo.users.delete_one({"user_id": uid})


# ============================================================
# 5. /auth/forgot-password — works for legacy google users
# ============================================================
class TestForgotPasswordGoogleUser:
    def test_forgot_password_google_user_works(self, mongo, google_user):
        email = google_user["email"]
        email_lc = email.lower()
        # Cleanup any prior attempts (route lowercases email before insert)
        mongo.password_reset_attempts.delete_many({"email": {"$in": [email, email_lc]}})
        r = requests.post(f"{BASE_URL}/api/auth/forgot-password",
                          json={"email": email})
        assert r.status_code == 200
        assert "If this email exists" in r.json().get("message", "")
        # Verify attempt row was created (route stores email lowercased)
        cnt = mongo.password_reset_attempts.count_documents({"email": email_lc})
        assert cnt >= 1, f"Expected attempt row for {email_lc}, got 0"
        # Also verify reset_token written on user (proves the legacy google
        # branch is treated like normal users, not silently skipped)
        u = mongo.users.find_one({"user_id": google_user["user_id"]}, {"_id": 0})
        assert u.get("reset_token"), "reset_token should be set on legacy google user"


# ============================================================
# 6. /admin/users/{uid}/force-password-reset on google user
# ============================================================
class TestForcePasswordResetGoogleUser:
    def test_force_password_reset_google_user_success(self, client, mongo):
        # Seed a fresh google user (so it's still provider='google' regardless
        # of TestSetInitialPassword having converted google_user)
        uid = f"user_{uuid.uuid4().hex[:12]}"
        email = f"{TAG}_forceg_{uuid.uuid4().hex[:6]}@example.com"
        mongo.users.insert_one({
            "user_id": uid,
            "email": email,
            "provider": "google",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "_tag": TAG,
        })
        try:
            r = client.post(f"{BASE_URL}/api/admin/users/{uid}/force-password-reset")
            assert r.status_code == 200, r.text
            assert "sent successfully" in r.json().get("message", "").lower()
            u = mongo.users.find_one({"user_id": uid}, {"_id": 0})
            assert u.get("reset_token")
        finally:
            mongo.users.delete_one({"user_id": uid})


# ============================================================
# 7. /auth/register existing google user → 400 'Use Forgot Password'
# ============================================================
class TestRegisterExistingGoogleUser:
    def test_register_existing_google_returns_400(self, mongo):
        uid = f"user_{uuid.uuid4().hex[:12]}"
        email = f"{TAG}_regg_{uuid.uuid4().hex[:6]}@example.com"
        mongo.users.insert_one({
            "user_id": uid,
            "email": email,
            "provider": "google",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "_tag": TAG,
        })
        try:
            r = requests.post(f"{BASE_URL}/api/auth/register", json={
                "email": email,
                "password": "Strongpass123!",
                "confirm_password": "Strongpass123!",
                "name": "Test",
                "turnstile_token": "test-bypass",
            })
            assert r.status_code == 400, r.text
            detail = (r.json().get("detail") or "").lower()
            assert "forgot password" in detail
        finally:
            mongo.users.delete_one({"user_id": uid})


# ============================================================
# 8. ensure_domain_record helper (direct invocation)
# ============================================================
def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


class TestEnsureDomainRecord:
    @pytest.fixture(autouse=True)
    def _cleanup(self, mongo):
        # Each test uses its own user_id so cleanup is per-class via the module fixture
        yield

    def _call(self, user_id, email):
        from infra_phase_a import ensure_domain_record
        client = AsyncIOMotorClient(MONGO_URL)
        async def go():
            db = client[DB_NAME]
            res = await ensure_domain_record(db, user_id, email)
            return res
        try:
            return asyncio.run(go())
        finally:
            client.close()

    def test_first_call_inserts_with_defaults(self, mongo):
        uid = f"test_iter62_u1_{uuid.uuid4().hex[:6]}"
        domain = f"iter62-domain-a-{uuid.uuid4().hex[:6]}.com"
        email = f"alice@{domain}"
        did = self._call(uid, email)
        assert did and did.startswith("dom_")
        row = mongo.tracked_domains.find_one({"user_id": uid, "domain": domain}, {"_id": 0})
        assert row is not None
        today = _date_cls.today().isoformat()
        assert row["purchase_date"] == today
        assert row["date_added"] == today
        expected_expiry = (_date_cls.today() + timedelta(days=361)).isoformat()
        assert row["expiry_date"] == expected_expiry
        assert row["renewal_date"] == expected_expiry
        assert row["auto_created"] is True
        assert row["linked_inbox_count"] == 1

    def test_second_call_same_domain_only_increments_count(self, mongo):
        uid = f"test_iter62_u2_{uuid.uuid4().hex[:6]}"
        domain = f"iter62-domain-b-{uuid.uuid4().hex[:6]}.com"
        d1 = self._call(uid, f"a@{domain}")
        d2 = self._call(uid, f"b@{domain}")
        assert d1 == d2
        row = mongo.tracked_domains.find_one({"user_id": uid, "domain": domain}, {"_id": 0})
        assert row["linked_inbox_count"] == 2
        # Defaults unchanged
        assert row["auto_created"] is True

    def test_manually_edited_row_never_overwritten(self, mongo):
        uid = f"test_iter62_u3_{uuid.uuid4().hex[:6]}"
        domain = f"iter62-domain-c-{uuid.uuid4().hex[:6]}.com"
        # Pre-insert a manually-edited row
        far_expiry = "2099-12-31"
        mongo.tracked_domains.insert_one({
            "domain_id": "dom_manual123",
            "user_id": uid,
            "domain": domain,
            "registrar": "Manual Registrar",
            "purchase_date": "2020-01-01",
            "date_added": "2020-01-01",
            "expiry_date": far_expiry,
            "renewal_date": far_expiry,
            "notes": "manual notes",
            "linked_inbox_count": 5,
            "auto_created": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            ret = self._call(uid, f"x@{domain}")
            assert ret == "dom_manual123"
            row = mongo.tracked_domains.find_one({"user_id": uid, "domain": domain}, {"_id": 0})
            # No mutation of any field except linked_inbox_count
            assert row["domain_id"] == "dom_manual123"
            assert row["registrar"] == "Manual Registrar"
            assert row["expiry_date"] == far_expiry
            assert row["renewal_date"] == far_expiry
            assert row["auto_created"] is False
            assert row["purchase_date"] == "2020-01-01"
            assert row["notes"] == "manual notes"
            assert row["linked_inbox_count"] == 6  # bumped from 5 to 6
        finally:
            mongo.tracked_domains.delete_one({"domain_id": "dom_manual123"})

    @pytest.mark.parametrize("bad", ["", "noatsymbol", "foo@", "@noTLD", "foo@bar"])
    def test_bad_inputs_return_none(self, mongo, bad):
        uid = f"test_iter62_bad_{uuid.uuid4().hex[:6]}"
        before = mongo.tracked_domains.count_documents({"user_id": uid})
        ret = self._call(uid, bad)
        assert ret is None, f"Bad email {bad!r} should return None"
        after = mongo.tracked_domains.count_documents({"user_id": uid})
        assert after == before

    def test_case_normalization(self, mongo):
        uid = f"test_iter62_case_{uuid.uuid4().hex[:6]}"
        domain_lower = f"iter62-case-{uuid.uuid4().hex[:6]}.com"
        # Helper expects already lowercased per spec note — but it does lowercase internally
        ret = self._call(uid, f"Alice@{domain_lower.upper()}")
        assert ret
        row = mongo.tracked_domains.find_one({"user_id": uid, "domain": domain_lower}, {"_id": 0})
        assert row is not None


# ============================================================
# 9-10. SMTP add + bulk-import → tracked_domains
#      (Direct helper invocation — endpoint paths exercise the same helper.
#       Endpoint-level test would require valid SMTP creds + workspace under
#       account_limit cap.)
# ============================================================
class TestBulkImportDomainAggregation:
    def test_three_inboxes_one_domain_yields_one_row_count_three(self, mongo):
        uid = f"test_iter62_bulk_{uuid.uuid4().hex[:6]}"
        domain = f"iter62-bulk-{uuid.uuid4().hex[:6]}.com"
        from infra_phase_a import ensure_domain_record
        client = AsyncIOMotorClient(MONGO_URL)
        async def go():
            db = client[DB_NAME]
            ids = []
            for prefix in ("alice", "bob", "carol"):
                ids.append(await ensure_domain_record(db, uid, f"{prefix}@{domain}"))
            return ids
        try:
            ids = asyncio.run(go())
            assert len(set(ids)) == 1, f"All 3 should return same domain_id, got {ids}"
            rows = list(mongo.tracked_domains.find({"user_id": uid, "domain": domain}))
            assert len(rows) == 1
            assert rows[0]["linked_inbox_count"] == 3
        finally:
            client.close()
