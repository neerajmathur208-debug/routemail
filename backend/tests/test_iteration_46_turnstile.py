"""Iteration 46 — Cloudflare Turnstile CAPTCHA on /auth/login and /auth/register.

Tests:
- Login without turnstile_token → 400 with exact failure message.
- Login with bogus turnstile_token → 400 with exact failure message.
- Register without turnstile_token → 400, and user is NOT persisted to db.users.
- Register with bogus turnstile_token → 400, and user is NOT persisted.
- Regression: non-auth endpoints (session-cookie auth) still return 200 without any turnstile_token.
"""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to /app/frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
EXPECTED_MSG = "Security verification failed. Please try again."

ADMIN_EMAIL = "dhruvmathur208@gmail.com"
ADMIN_PASSWORD = "Perfect2026#"


@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    return client[DB_NAME]


# ===== Login gate =====
class TestLoginTurnstileGate:
    def test_login_without_turnstile_token_returns_400_with_exact_message(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert r.status_code == 400, f"got {r.status_code} body={r.text}"
        body = r.json()
        assert body.get("detail") == EXPECTED_MSG, f"detail mismatch: {body}"

    def test_login_with_bogus_turnstile_token_returns_400(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "turnstile_token": "INVALID",
            },
            timeout=15,
        )
        assert r.status_code == 400, f"got {r.status_code} body={r.text}"
        body = r.json()
        assert body.get("detail") == EXPECTED_MSG, f"detail mismatch: {body}"

    def test_login_with_empty_string_turnstile_token_returns_400(self):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "turnstile_token": "   ",
            },
            timeout=15,
        )
        assert r.status_code == 400
        assert r.json().get("detail") == EXPECTED_MSG


# ===== Register gate =====
class TestRegisterTurnstileGate:
    def test_register_without_turnstile_token_blocks_and_does_not_create_user(self, db):
        rand = uuid.uuid4().hex[:10]
        email = f"test.turnstile.{rand}@example.com"
        r = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "name": "TEST Turnstile",
                "email": email,
                "password": "TestPass123!",
                "confirm_password": "TestPass123!",
            },
            timeout=15,
        )
        assert r.status_code == 400, f"got {r.status_code} body={r.text}"
        assert r.json().get("detail") == EXPECTED_MSG

        # Verify user is NOT in db.users
        doc = db.users.find_one({"email": email})
        assert doc is None, f"User was unexpectedly persisted despite turnstile failure: {doc}"

    def test_register_with_bogus_turnstile_token_blocks_and_does_not_create_user(self, db):
        rand = uuid.uuid4().hex[:10]
        email = f"test.turnstile.{rand}@example.com"
        r = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "name": "TEST Turnstile",
                "email": email,
                "password": "TestPass123!",
                "confirm_password": "TestPass123!",
                "turnstile_token": "BOGUS_TOKEN_VALUE",
            },
            timeout=15,
        )
        assert r.status_code == 400, f"got {r.status_code} body={r.text}"
        assert r.json().get("detail") == EXPECTED_MSG

        doc = db.users.find_one({"email": email})
        assert doc is None, f"User was unexpectedly persisted: {doc}"


# ===== Regression: non-auth endpoints don't require Turnstile =====
class TestNonAuthEndpointsRegression:
    """Verify that the super admin can still call all non-auth endpoints with
    just their session cookie — no Turnstile required.

    Since /api/auth/login itself is gated by Turnstile and we cannot solve the
    challenge from pytest, we authenticate by injecting a session row directly
    into MongoDB. This mirrors what /api/auth/login does on success.
    """

    @pytest.fixture(scope="class")
    def session_cookie(self, db):
        import secrets
        from datetime import datetime, timezone, timedelta

        user = db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
        if not user:
            pytest.skip(f"Super admin {ADMIN_EMAIL} not seeded — cannot run regression")
        token = secrets.token_hex(16)
        db.user_sessions.insert_one({
            "session_token": token,
            "user_id": user["user_id"],
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=2),
            "created_at": datetime.now(timezone.utc),
        })
        yield token
        # Teardown
        db.user_sessions.delete_one({"session_token": token})

    @pytest.mark.parametrize("path", [
        "/api/campaigns",
        "/api/drip-campaigns",
        "/api/dne-lists",
        "/api/unibox/replies",
        "/api/accounts",
    ])
    def test_endpoint_returns_200(self, session_cookie, path):
        r = requests.get(
            f"{BASE_URL}{path}",
            cookies={"session_token": session_cookie},
            timeout=20,
        )
        assert r.status_code == 200, f"GET {path} → {r.status_code} body={r.text[:300]}"
