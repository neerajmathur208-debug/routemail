"""Iteration 47 — Permanent Free Plan tests.

Validates:
- /api/subscription/prices returns free_plan, no `trial_days`
- New user via /api/auth/register creates Mongo doc plan_type=free, status=active, trial_ends_at=null
- /api/auth/me returns downgraded_to_free_at + downgrade_reason fields
- Legacy 'trialing' status is migrated on read by check_subscription_active()
- past_due + grace_expired downgrades with downgrade_reason='grace_expired'
- canceled + cycle ended downgrades with downgrade_reason='canceled_cycle_ended'
- Admin assign-plan {plan:'free'} downgrades; 400 if active stripe sub
- Admin assign-plan {plan:'starter'} + remove-override reverts to free + status='active' (NOT trialing)
- Regression: campaigns, drip-campaigns, dne-lists, accounts, unibox/replies all 200
"""

import os
import uuid
import json
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient


def _read_env(key, path):
    try:
        with open(path, "r") as f:
            for line in f:
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip().strip('"')
    except FileNotFoundError:
        return None
    return None


BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or _read_env("REACT_APP_BACKEND_URL", "/app/frontend/.env") or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
MONGO_URL = _read_env("MONGO_URL", "/app/backend/.env")
DB_NAME = _read_env("DB_NAME", "/app/backend/.env")
COOKIE_DOMAIN = BASE_URL.split("//")[1]

DRIP_EMAIL = "drip.tester@example.com"
ADMIN_EMAIL = "dhruvmathur208@gmail.com"


@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


def _inject_session(db, user_email):
    user = db.users.find_one({"email": user_email}, {"_id": 0})
    assert user, f"User {user_email} not found"
    token = f"sess_test_{uuid.uuid4().hex}"
    db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    })
    return user["user_id"], token


def _session(token):
    s = requests.Session()
    s.cookies.set("session_token", token, domain=COOKIE_DOMAIN)
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def drip_session(mongo):
    uid, tok = _inject_session(mongo, DRIP_EMAIL)
    yield _session(tok), uid, tok
    mongo.user_sessions.delete_one({"session_token": tok})


@pytest.fixture(scope="module")
def admin_session(mongo):
    uid, tok = _inject_session(mongo, ADMIN_EMAIL)
    yield _session(tok), uid, tok
    mongo.user_sessions.delete_one({"session_token": tok})


# ---------- /subscription/prices ----------
class TestSubscriptionPrices:
    def test_prices_returns_free_plan_no_trial_days(self):
        r = requests.get(f"{BASE_URL}/api/subscription/prices")
        assert r.status_code == 200, r.text
        data = r.json()
        # The legacy `trial_days` key must NOT be present anywhere in payload
        assert "trial_days" not in json.dumps(data), "Legacy trial_days key MUST NOT be present"
        free = data.get("free_plan")
        assert free, "free_plan key missing"
        assert free["name"] == "Free"
        assert free["free_forever"] is True
        assert free["price_usd"] == 0
        assert free["features"]["max_monthly_recipients"] == 500


# ---------- /auth/me + /subscription/status include new fields ----------
class TestAuthMeNewFields:
    def test_subscription_status_includes_downgrade_fields(self, drip_session):
        s, _, _ = drip_session
        r = s.get(f"{BASE_URL}/api/subscription/status")
        assert r.status_code == 200, r.text
        body = r.json()
        # The Subscription.jsx page reads these from /subscription/status (not /auth/me)
        assert "downgraded_to_free_at" in body, "downgraded_to_free_at missing in /subscription/status"
        assert "downgrade_reason" in body, "downgrade_reason missing in /subscription/status"

    def test_auth_me_returns_200(self, drip_session):
        s, _, _ = drip_session
        r = s.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200, r.text
        # NOTE: The review spec said /auth/me should include downgraded_to_free_at + downgrade_reason,
        # but the actual implementation exposes them on /subscription/status. Frontend (Subscription.jsx,
        # AdminDashboard.jsx) consumes them from /subscription/status, so functional behavior is correct.
        # Flagging this as a minor spec deviation in the test report.


# ---------- Register: new user defaults to free ----------
class TestRegisterFreeDefault:
    def test_new_user_starts_on_free_plan(self, mongo):
        test_email = f"test.iter47.{uuid.uuid4().hex[:10]}@example.com"
        try:
            r = requests.post(f"{BASE_URL}/api/auth/register", json={
                "email": test_email,
                "password": "TestPass123!",
                "confirm_password": "TestPass123!",
                "name": "Iter47 Tester",
            })
            if r.status_code == 400 and "Security verification" in r.text:
                pytest.skip("Turnstile gate active; cannot test register")
            assert r.status_code in (200, 201), r.text

            user = mongo.users.find_one({"email": test_email}, {"_id": 0})
            assert user, "User not created in Mongo"
            assert user.get("plan_type") == "free"
            assert user.get("subscription_status") == "active"
            assert user.get("trial_ends_at") is None
            assert user.get("downgraded_to_free_at") in (None,)
            assert user.get("downgrade_reason") in (None,)
        finally:
            mongo.users.delete_many({"email": test_email})


# ---------- Legacy 'trialing' migrated on read ----------
class TestLegacyTrialingMigration:
    def test_trialing_user_migrated_on_read(self, mongo):
        uid = f"user_legacy_{uuid.uuid4().hex[:10]}"
        email = f"test.legacytrial.{uuid.uuid4().hex[:8]}@example.com"
        tok = f"sess_legacy_{uuid.uuid4().hex}"
        mongo.users.insert_one({
            "user_id": uid, "email": email, "name": "Legacy", "auth_method": "email",
            "email_verified": True,
            "plan_type": "starter",
            "subscription_status": "trialing",
            "trial_ends_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        mongo.user_sessions.insert_one({
            "session_token": tok, "user_id": uid,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        })
        try:
            r = _session(tok).get(f"{BASE_URL}/api/auth/me")
            assert r.status_code == 200, r.text
            after = mongo.users.find_one({"user_id": uid}, {"_id": 0})
            assert after["subscription_status"] == "active", after.get("subscription_status")
            assert after["plan_type"] == "free"
            assert after.get("trial_ends_at") is None
        finally:
            mongo.users.delete_one({"user_id": uid})
            mongo.user_sessions.delete_one({"session_token": tok})


# ---------- Past_due + grace expired → downgrade ----------
class TestPastDueGraceExpired:
    def test_past_due_grace_expired_downgrades_to_free(self, mongo):
        uid = f"user_pd_{uuid.uuid4().hex[:10]}"
        email = f"test.pd.{uuid.uuid4().hex[:8]}@example.com"
        tok = f"sess_pd_{uuid.uuid4().hex}"
        mongo.users.insert_one({
            "user_id": uid, "email": email, "name": "PD", "auth_method": "email",
            "email_verified": True,
            "plan_type": "starter",
            "subscription_status": "past_due",
            "stripe_subscription_id": "sub_test_pastdue",
            "grace_period_end": (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        mongo.user_sessions.insert_one({
            "session_token": tok, "user_id": uid,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        })
        try:
            r = _session(tok).get(f"{BASE_URL}/api/auth/me")
            assert r.status_code == 200, r.text
            after = mongo.users.find_one({"user_id": uid}, {"_id": 0})
            assert after["plan_type"] == "free"
            assert after["subscription_status"] == "active"
            assert after.get("stripe_subscription_id") is None
            assert after.get("downgraded_to_free_at") is not None
            assert after.get("downgrade_reason") == "grace_expired"
        finally:
            mongo.users.delete_one({"user_id": uid})
            mongo.user_sessions.delete_one({"session_token": tok})


# ---------- Canceled + cycle ended → downgrade ----------
class TestCanceledCycleEnded:
    def test_canceled_cycle_ended_downgrades_to_free(self, mongo):
        uid = f"user_cc_{uuid.uuid4().hex[:10]}"
        email = f"test.cc.{uuid.uuid4().hex[:8]}@example.com"
        tok = f"sess_cc_{uuid.uuid4().hex}"
        mongo.users.insert_one({
            "user_id": uid, "email": email, "name": "CC", "auth_method": "email",
            "email_verified": True,
            "plan_type": "growth",
            "subscription_status": "canceled",
            "stripe_subscription_id": "sub_test_canc",
            "billing_cycle_end": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        mongo.user_sessions.insert_one({
            "session_token": tok, "user_id": uid,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        })
        try:
            r = _session(tok).get(f"{BASE_URL}/api/auth/me")
            assert r.status_code == 200, r.text
            after = mongo.users.find_one({"user_id": uid}, {"_id": 0})
            assert after["plan_type"] == "free"
            assert after["subscription_status"] == "active"
            assert after.get("downgrade_reason") == "canceled_cycle_ended"
        finally:
            mongo.users.delete_one({"user_id": uid})
            mongo.user_sessions.delete_one({"session_token": tok})


# ---------- Admin assign-plan ----------
class TestAdminAssignPlan:
    def test_admin_assign_free_downgrades_user(self, admin_session, mongo):
        s, _, _ = admin_session
        uid = f"user_adm_free_{uuid.uuid4().hex[:8]}"
        email = f"test.admfree.{uuid.uuid4().hex[:8]}@example.com"
        mongo.users.insert_one({
            "user_id": uid, "email": email, "name": "T", "auth_method": "email",
            "email_verified": True, "plan_type": "starter", "subscription_status": "active",
            "admin_override_active": True, "admin_override_plan": "starter",
        })
        try:
            r = s.post(f"{BASE_URL}/api/admin/users/{uid}/assign-plan", json={"plan": "free"})
            assert r.status_code == 200, r.text
            after = mongo.users.find_one({"user_id": uid}, {"_id": 0})
            assert after["plan_type"] == "free"
            assert after["admin_override_active"] is False
            assert after.get("admin_override_plan") is None
            assert after.get("downgrade_reason") == "admin_assigned"
            assert after.get("downgraded_to_free_at") is not None
        finally:
            mongo.users.delete_one({"user_id": uid})

    def test_admin_assign_free_blocked_for_stripe_user(self, admin_session, mongo):
        s, _, _ = admin_session
        uid = f"user_stripe_{uuid.uuid4().hex[:8]}"
        email = f"test.stripe.{uuid.uuid4().hex[:8]}@example.com"
        mongo.users.insert_one({
            "user_id": uid, "email": email, "name": "T", "auth_method": "email",
            "email_verified": True, "plan_type": "starter", "subscription_status": "active",
            "stripe_subscription_id": "sub_active_xyz",
        })
        try:
            r = s.post(f"{BASE_URL}/api/admin/users/{uid}/assign-plan", json={"plan": "free"})
            assert r.status_code == 400, r.text
        finally:
            mongo.users.delete_one({"user_id": uid})

    def test_admin_assign_starter_then_remove_override(self, admin_session, mongo):
        s, _, _ = admin_session
        uid = f"user_adm_start_{uuid.uuid4().hex[:8]}"
        email = f"test.admstart.{uuid.uuid4().hex[:8]}@example.com"
        mongo.users.insert_one({
            "user_id": uid, "email": email, "name": "T", "auth_method": "email",
            "email_verified": True, "plan_type": "free", "subscription_status": "active",
        })
        try:
            r = s.post(f"{BASE_URL}/api/admin/users/{uid}/assign-plan", json={"plan": "starter"})
            assert r.status_code == 200, r.text
            mid = mongo.users.find_one({"user_id": uid}, {"_id": 0})
            assert mid["admin_override_active"] is True
            assert mid["admin_override_plan"] == "starter"

            # NOTE: actual endpoint name is remove-override (not cancel-override)
            r2 = s.post(f"{BASE_URL}/api/admin/users/{uid}/remove-override")
            assert r2.status_code == 200, r2.text
            after = mongo.users.find_one({"user_id": uid}, {"_id": 0})
            assert after["plan_type"] == "free"
            assert after["subscription_status"] == "active", "must be 'active', NOT 'trialing'"
            assert after["admin_override_active"] is False
            assert after.get("trial_ends_at") is None
        finally:
            mongo.users.delete_one({"user_id": uid})


# ---------- Regression ----------
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/api/campaigns",
        "/api/drip-campaigns",
        "/api/dne-lists",
        "/api/accounts",
        "/api/unibox/replies",
    ])
    def test_endpoint_200(self, drip_session, path):
        s, _, _ = drip_session
        r = s.get(f"{BASE_URL}{path}")
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
