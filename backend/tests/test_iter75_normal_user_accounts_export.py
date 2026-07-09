"""Iteration 75 — Normal (non-admin) users can export their OWN email accounts
via the new /api/accounts/export endpoint (no infrastructure permission).

Tests:
1. Normal user gets HTTP 200 (not 404/403) with CSV body & correct headers.
2. Header row contains all expected columns (case-sensitive lowercase snake).
3. include_credentials=false hides password columns.
4. Plaintext SMTP+IMAP passwords equal originally-encrypted values.
5. Base regression columns still present (no removals).
6. IMAP password fallback (missing imap_password_encrypted, SMTP present + imap_host set → mirror).
7. Strict user isolation: User B cannot see User A's data.
8. Super admin's export shows only their own accounts (iter-72 isolation).
9. Round-trip: exported CSV rows contain every field required by /api/accounts/smtp/bulk-import.
10. Unauthenticated request returns 401.
"""
import csv
import io
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")

# Backend URL from frontend/.env (production external)
BASE_URL = None
with open("/app/frontend/.env") as f:
    for ln in f:
        if ln.startswith("REACT_APP_BACKEND_URL"):
            BASE_URL = ln.split("=", 1)[1].strip().strip('"').rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

TAG = f"exp75_{uuid.uuid4().hex[:8]}"

sys.path.insert(0, "/app/backend")
from server import encrypt_data  # noqa: E402


def _iso(d=None):
    return (d if d is not None else datetime.now(timezone.utc)).isoformat()


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    # teardown - remove ALL tag-prefixed docs
    for coll in ("users", "user_sessions", "email_accounts",
                 "campaigns", "drip_campaigns", "tracked_domains"):
        c[DB_NAME][coll].delete_many({"tag": TAG})
    c.close()


def _mk_user(mongo, uid, email, role="user"):
    token = f"{TAG}_tok_{uuid.uuid4().hex}"
    mongo.users.insert_one({
        "user_id": uid, "email": email, "name": uid,
        "role": role, "email_verified": True,
        "created_at": _iso(), "tag": TAG,
    })
    mongo.user_sessions.insert_one({
        "user_id": uid, "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "created_at": _iso(), "tag": TAG,
    })
    return token


@pytest.fixture(scope="module")
def user_a(mongo):
    uid = f"{TAG}_ua"
    token = _mk_user(mongo, uid, f"{TAG}_a@x.test", role="user")
    smtp_plain = "UserA-SMTP-P@ss!"
    imap_plain = "UserA-IMAP-K3y!"
    mongo.email_accounts.insert_one({
        "account_id": f"{TAG}_a_acct1", "user_id": uid,
        "email": f"{TAG}_a1@userA.export",
        "from_name": "Alice",
        "smtp_host": "smtp.userA.export", "smtp_port": 587,
        "smtp_username": f"{TAG}_a1@userA.export",
        "smtp_password_encrypted": encrypt_data(smtp_plain),
        "smtp_encryption": "tls",
        "imap_host": "imap.userA.export", "imap_port": 993,
        "imap_username": f"{TAG}_a1@userA.export",
        "imap_password_encrypted": encrypt_data(imap_plain),
        "imap_encryption": "ssl",
        "daily_limit": 42, "send_delay": 45,
        "warmup_enabled": True, "warmup_status": "warming",
        "status": "connected", "priority": 1,
        "created_at": _iso(), "tag": TAG,
    })
    return {
        "user_id": uid, "token": token,
        "smtp_plain": smtp_plain, "imap_plain": imap_plain,
        "email": f"{TAG}_a1@userA.export",
        "account_id": f"{TAG}_a_acct1",
    }


@pytest.fixture(scope="module")
def user_b(mongo):
    uid = f"{TAG}_ub"
    token = _mk_user(mongo, uid, f"{TAG}_b@x.test", role="user")
    smtp_plain = "UserB-Unique-P@ss!"
    mongo.email_accounts.insert_one({
        "account_id": f"{TAG}_b_acct1", "user_id": uid,
        "email": f"{TAG}_b1@userB.export",
        "from_name": "Bob",
        "smtp_host": "smtp.userB.export", "smtp_port": 465,
        "smtp_username": f"{TAG}_b1@userB.export",
        "smtp_password_encrypted": encrypt_data(smtp_plain),
        "smtp_encryption": "ssl",
        # Intentionally NO imap_password_encrypted; imap_host set → tests fallback.
        "imap_host": "imap.userB.export", "imap_port": 993,
        "imap_username": f"{TAG}_b1@userB.export",
        "daily_limit": 20, "send_delay": 30,
        "status": "connected",
        "created_at": _iso(), "tag": TAG,
    })
    return {
        "user_id": uid, "token": token,
        "smtp_plain": smtp_plain,
        "email": f"{TAG}_b1@userB.export",
        "account_id": f"{TAG}_b_acct1",
    }


def _sess(token):
    s = requests.Session()
    s.cookies.set("session_token", token)
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


EXPECTED_ALL_COLUMNS = [
    "email", "domain", "ownership",
    "smtp_host", "smtp_port", "smtp_username",
    "imap_host", "imap_port", "imap_username",
    "daily_limit", "status",
    "warmup_status", "last_activity", "date_added",
    "campaign_assignments", "notes",
    "from_name",
    "smtp_password", "smtp_ssl", "smtp_encryption",
    "imap_password", "imap_ssl", "imap_encryption",
    "send_delay", "warmup_enabled",
    "priority", "tags",
]

BASE_COLUMNS_16 = [
    "email", "domain", "ownership",
    "smtp_host", "smtp_port", "smtp_username",
    "imap_host", "imap_port", "imap_username",
    "daily_limit", "status",
    "warmup_status", "last_activity", "date_added",
    "campaign_assignments", "notes",
]


# ─── tests ────────────────────────────────────────────────────────────────

def test_1_normal_user_export_returns_200_with_csv(user_a):
    r = _sess(user_a["token"]).get(
        f"{BASE_URL}/api/accounts/export?format=csv&include_credentials=true"
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:400]}"
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd, f"missing attachment in Content-Disposition: {cd}"
    assert "RouteMail_Email_Accounts_with_credentials" in cd, cd
    # Body is a CSV
    reader = csv.DictReader(io.StringIO(r.text))
    fields = reader.fieldnames or []
    assert "email" in fields


def test_2_header_row_contains_all_expected_columns(user_a):
    r = _sess(user_a["token"]).get(
        f"{BASE_URL}/api/accounts/export?format=csv&include_credentials=true"
    )
    assert r.status_code == 200
    reader = csv.DictReader(io.StringIO(r.text))
    fields = reader.fieldnames or []
    missing = [c for c in EXPECTED_ALL_COLUMNS if c not in fields]
    assert not missing, f"missing expected columns: {missing}. Got: {fields}"


def test_3_include_credentials_false_hides_password_columns(user_a):
    r = _sess(user_a["token"]).get(
        f"{BASE_URL}/api/accounts/export?format=csv&include_credentials=false"
    )
    assert r.status_code == 200
    reader = csv.DictReader(io.StringIO(r.text))
    fields = reader.fieldnames or []
    assert "smtp_password" not in fields, "smtp_password leaked when include_credentials=false"
    assert "imap_password" not in fields, "imap_password leaked when include_credentials=false"
    assert user_a["smtp_plain"] not in r.text
    assert user_a["imap_plain"] not in r.text


def test_4_passwords_match_originals(user_a):
    r = _sess(user_a["token"]).get(
        f"{BASE_URL}/api/accounts/export?format=csv&include_credentials=true"
    )
    assert r.status_code == 200
    rows = list(csv.DictReader(io.StringIO(r.text)))
    row = next(rw for rw in rows if rw["email"] == user_a["email"])
    assert row["smtp_password"] == user_a["smtp_plain"]
    assert row["imap_password"] == user_a["imap_plain"]


def test_5_base_16_columns_present_no_regression(user_a):
    r = _sess(user_a["token"]).get(
        f"{BASE_URL}/api/accounts/export?format=csv&include_credentials=true"
    )
    reader = csv.DictReader(io.StringIO(r.text))
    fields = reader.fieldnames or []
    for col in BASE_COLUMNS_16:
        assert col in fields, f"base column '{col}' missing (regression)"


def test_6_imap_password_fallback_to_smtp(user_b):
    """User B's account has no imap_password_encrypted, but has imap_host + smtp password.
    The exported imap_password column must mirror smtp_password."""
    r = _sess(user_b["token"]).get(
        f"{BASE_URL}/api/accounts/export?format=csv&include_credentials=true"
    )
    assert r.status_code == 200
    rows = list(csv.DictReader(io.StringIO(r.text)))
    row = next(rw for rw in rows if rw["email"] == user_b["email"])
    assert row["smtp_password"] == user_b["smtp_plain"]
    assert row["imap_password"] == user_b["smtp_plain"], (
        f"IMAP fallback did not mirror SMTP password. imap_password={row['imap_password']!r}"
    )


def test_7_strict_isolation_between_normal_users(user_a, user_b):
    """User B's export must NOT contain User A's password/email/account_id."""
    r = _sess(user_b["token"]).get(
        f"{BASE_URL}/api/accounts/export?format=csv&include_credentials=true"
    )
    assert r.status_code == 200
    body = r.text
    assert user_a["smtp_plain"] not in body, "User A SMTP password leaked to User B"
    assert user_a["imap_plain"] not in body, "User A IMAP password leaked to User B"
    assert user_a["email"] not in body, "User A email leaked to User B"
    assert user_a["account_id"] not in body, "User A account_id leaked to User B"

    # And reverse: A's export doesn't contain B either
    r2 = _sess(user_a["token"]).get(
        f"{BASE_URL}/api/accounts/export?format=csv&include_credentials=true"
    )
    body2 = r2.text
    assert user_b["smtp_plain"] not in body2
    assert user_b["email"] not in body2


def test_8_super_admin_export_only_their_own(mongo):
    """iter-72 isolation contract: super admin on this endpoint sees only their own
    inboxes, not the whole platform."""
    # Login is behind Turnstile in this env; inject a real session directly.
    super_uid = "user_b3e333b0f467"
    token = f"{TAG}_super_{uuid.uuid4().hex}"
    mongo.user_sessions.insert_one({
        "user_id": super_uid, "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "created_at": _iso(), "tag": TAG,
    })

    r = _sess(token).get(
        f"{BASE_URL}/api/accounts/export?format=csv&include_credentials=true"
    )
    assert r.status_code == 200, r.text
    body = r.text
    rows = list(csv.DictReader(io.StringIO(body)))
    # Every row must belong to the super admin
    super_emails = set()
    for a in mongo.email_accounts.find({"user_id": super_uid}, {"email": 1}):
        super_emails.add(a.get("email"))

    for row in rows:
        assert row["email"] in super_emails, (
            f"super admin export contained non-owned account {row['email']!r} (iter-72 breach)"
        )
    # And critically, no tagged/isolated test users appear
    assert TAG not in body, "super admin export leaked tagged test-user data"


def test_9_round_trip_reimportable(user_a):
    """Parse exported CSV, normalize headers same as bulk-import, and verify
    every field the importer requires is present and non-empty."""
    r = _sess(user_a["token"]).get(
        f"{BASE_URL}/api/accounts/export?format=csv&include_credentials=true"
    )
    assert r.status_code == 200
    rows = list(csv.DictReader(io.StringIO(r.text)))
    row = next(rw for rw in rows if rw["email"] == user_a["email"])

    def _normalize_header(h: str) -> str:
        s = (h or "").strip().lower()
        s = re.sub(r"\([^)]*\)", "", s).strip()
        s = re.sub(r"[\s\-/]+", "_", s).strip("_")
        aliases = {
            "sending_delay": "delay_seconds", "send_delay": "delay_seconds",
            "delay_between_sends": "delay_seconds",
            "smtp_encryption": "smtp_ssl", "imap_encryption": "imap_ssl",
        }
        return aliases.get(s, s)

    norm = {_normalize_header(k): v for k, v in row.items()}

    required = ["email", "smtp_password", "smtp_host", "smtp_port",
                "delay_seconds", "daily_limit", "from_name"]
    for f in required:
        assert f in norm and str(norm[f]).strip() != "", (
            f"required importer field '{f}' missing/empty; got={norm.get(f)!r}"
        )
    assert norm["email"] == user_a["email"]
    assert norm["smtp_password"] == user_a["smtp_plain"]
    assert norm["smtp_host"] == "smtp.userA.export"
    assert norm["smtp_port"] == "587"
    assert norm["delay_seconds"] == "45"
    assert norm["daily_limit"] == "42"
    assert norm["from_name"] == "Alice"


def test_10_unauthenticated_request_is_401():
    r = requests.get(f"{BASE_URL}/api/accounts/export?format=csv&include_credentials=true")
    assert r.status_code == 401, (
        f"unauthenticated call should return 401, got {r.status_code}"
    )
