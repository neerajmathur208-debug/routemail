"""Iteration 48 — Stripe key rotation + Sidebar support footer regression."""
import os
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # fall back to reading frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

SUPER_ADMIN_USER_ID = "user_b3e333b0f467"  # dhruvmathur208@gmail.com


@pytest.fixture(scope="module")
def admin_session():
    """Inject a session row directly to bypass Turnstile CAPTCHA."""
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    token = f"TEST_iter48_{uuid.uuid4().hex}"
    db.user_sessions.insert_one({
        "session_token": token,
        "user_id": SUPER_ADMIN_USER_ID,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
    })
    yield token
    db.user_sessions.delete_one({"session_token": token})
    client.close()


@pytest.fixture(scope="module")
def auth_client(admin_session):
    s = requests.Session()
    s.cookies.set("session_token", admin_session)
    s.headers.update({"Authorization": f"Bearer {admin_session}"})
    return s


# === Stripe key rotation regression ===
def test_health():
    r = requests.get(f"{BASE_URL}/api/health", timeout=15)
    assert r.status_code == 200
    assert r.json().get("status") == "healthy"


def test_subscription_prices_ok():
    r = requests.get(f"{BASE_URL}/api/subscription/prices", timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "plans" in body
    assert isinstance(body["plans"], list)
    assert len(body["plans"]) >= 2


# === Auth + protected endpoint regression ===
def test_auth_me(auth_client):
    r = auth_client.get(f"{BASE_URL}/api/auth/me", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("user_id") == SUPER_ADMIN_USER_ID


@pytest.mark.parametrize("path", [
    "/api/campaigns",
    "/api/drip-campaigns",
    "/api/accounts",
    "/api/unibox/replies",
    "/api/dne-lists",
])
def test_protected_endpoints(auth_client, path):
    r = auth_client.get(f"{BASE_URL}{path}", timeout=20)
    assert r.status_code == 200, f"{path} returned {r.status_code}: {r.text[:200]}"


# === Security greps ===
# NOTE: We intentionally read the secret values from environment variables rather
# than hardcoding them, so this test file is safe to commit / push to GitHub
# (GitHub Secret Protection blocks pushes that contain raw `sk_live_*` strings).
# Set these in /app/backend/.env (already gitignored) to actually run the asserts;
# if they are missing the tests are skipped — they are pure leak-detection greps
# and have no value without a real key to look for.
def test_new_stripe_key_only_in_backend_env():
    import subprocess
    new_key = os.environ.get("STRIPE_SECRET_KEY")
    if not new_key or not new_key.startswith("sk_"):
        pytest.skip("STRIPE_SECRET_KEY not set in environment — skipping leak check")
    res = subprocess.run(
        ["grep", "-rl", new_key, "/app",
         "--exclude-dir=.git", "--exclude-dir=node_modules",
         "--exclude-dir=tests", "--exclude-dir=__pycache__",
         "--exclude-dir=test_reports"],
        capture_output=True, text=True,
    )
    matches = [m for m in res.stdout.strip().split("\n") if m]
    assert matches == ["/app/backend/.env"], f"Stripe key leak: {matches}"


def test_old_stripe_key_fully_removed():
    import subprocess
    # The previous (rotated-out) Stripe key. We do not hardcode it; we read it
    # from STRIPE_OLD_KEY_FOR_LEAK_CHECK (set locally in /app/backend/.env only
    # while a rotation is in progress, otherwise the test is skipped).
    old_key = os.environ.get("STRIPE_OLD_KEY_FOR_LEAK_CHECK")
    if not old_key or not old_key.startswith("sk_"):
        pytest.skip("STRIPE_OLD_KEY_FOR_LEAK_CHECK not set — skipping post-rotation leak check")
    res = subprocess.run(
        ["grep", "-rl", old_key, "/app",
         "--exclude-dir=.git", "--exclude-dir=node_modules",
         "--exclude-dir=tests", "--exclude-dir=__pycache__",
         "--exclude-dir=test_reports"],
        capture_output=True, text=True,
    )
    matches = [m for m in res.stdout.strip().split("\n") if m]
    assert matches == [], f"Old Stripe key still present in: {matches}"


def test_no_stripe_secret_in_frontend_src():
    import subprocess
    res = subprocess.run(
        ["grep", "-rn", "sk_live_", "/app/frontend/src"],
        capture_output=True, text=True,
    )
    assert res.stdout.strip() == "", f"sk_live_ found in frontend src: {res.stdout}"


# === Sidebar footer source verification ===
def test_sidebar_footer_present_in_source():
    with open("/app/frontend/src/components/Sidebar.jsx") as f:
        src = f.read()
    assert 'data-testid="sidebar-support-footer"' in src
    assert 'data-testid="support-email-link"' in src
    assert 'href="mailto:support@routemail.co"' in src
    assert "Need help?" in src
    assert "For any queries or support, please contact" in src
