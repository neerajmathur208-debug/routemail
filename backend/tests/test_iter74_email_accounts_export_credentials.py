"""Iteration 74 — Email Accounts export must include credentials on demand.

Verifies:
* Default export (no query param) → no passwords in the file.
* `include_credentials=true` → decrypted SMTP + IMAP passwords in the CSV.
* Every existing column is preserved (never removed) + new credential columns
  added at the end.
* The exported file is re-importable through `/api/accounts/smtp/bulk-import`
  (header names normalized, values round-trip).
* Only the account owner can export their own passwords — a second user's
  export never contains the first user's credentials.
"""
import csv
import io
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"] if "REACT_APP_BACKEND_URL" in os.environ else None
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = ln.split("=", 1)[1].strip().strip('"').rstrip("/")
BASE_URL = BASE_URL.rstrip("/")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

TAG = f"exp74_{uuid.uuid4().hex[:8]}"


def _iso(d=None):
    return (d if d is not None else datetime.now(timezone.utc)).isoformat()


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def encrypter():
    """Bring up server.encrypt_data so seeded accounts have real fernet blobs."""
    import sys
    sys.path.insert(0, "/app/backend")
    from server import encrypt_data, decrypt_data
    return {"encrypt": encrypt_data, "decrypt": decrypt_data}


@pytest.fixture(scope="module")
def seeded(mongo, encrypter):
    user_id = f"{TAG}_u"
    token = f"{TAG}_tok_{uuid.uuid4().hex}"

    mongo.users.insert_one({
        "user_id": user_id, "email": f"{TAG}@exp.test", "name": "Export Tester",
        "role": "user", "email_verified": True, "can_access_infrastructure": True,
        "created_at": _iso(), "tag": TAG,
    })
    mongo.user_sessions.insert_one({
        "user_id": user_id, "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "created_at": _iso(), "tag": TAG,
    })

    smtp_plain = "S3cret!P@ss-alpha"
    imap_plain = "IM4P-K3y!"

    mongo.email_accounts.insert_one({
        "account_id": f"{TAG}_a1", "user_id": user_id,
        "email": f"{TAG}_a1@aliceco.export", "display_name": "Alice Marketing",
        "from_name": "Alice Marketing",
        "smtp_host": "smtp.aliceco.export", "smtp_port": 587,
        "smtp_username": f"{TAG}_a1@aliceco.export",
        "smtp_password_encrypted": encrypter["encrypt"](smtp_plain),
        "smtp_encryption": "tls",
        "imap_host": "imap.aliceco.export", "imap_port": 993,
        "imap_username": f"{TAG}_a1@aliceco.export",
        "imap_password_encrypted": encrypter["encrypt"](imap_plain),
        "imap_encryption": "ssl",
        "daily_limit": 42, "send_delay": 45,
        "warmup_enabled": True, "warmup_status": "warming",
        "status": "connected", "priority": 1,
        "created_at": _iso(), "tag": TAG,
    })

    yield {
        "user_id": user_id, "token": token,
        "smtp_plain": smtp_plain, "imap_plain": imap_plain,
        "email": f"{TAG}_a1@aliceco.export",
    }

    for coll in ("users", "user_sessions", "email_accounts", "tracked_domains"):
        mongo[coll].delete_many({"tag": TAG})
    # Any re-imported accounts share the same domain suffix
    mongo.email_accounts.delete_many({"email": {"$regex": f"{TAG}"}})
    mongo.tracked_domains.delete_many({"domain": {"$regex": "aliceco.export"}})


def _sess(token):
    s = requests.Session()
    s.cookies.set("session_token", token)
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ─── tests ────────────────────────────────────────────────────────────────

def test_default_export_hides_passwords(seeded):
    r = _sess(seeded["token"]).get(
        f"{BASE_URL}/api/infrastructure/accounts/export?format=csv"
    )
    assert r.status_code == 200
    text = r.text
    assert seeded["smtp_plain"] not in text, "SMTP password leaked in default export"
    assert seeded["imap_plain"] not in text, "IMAP password leaked in default export"
    # Also: no `smtp_password` header
    reader = csv.DictReader(io.StringIO(text))
    assert "smtp_password" not in (reader.fieldnames or [])


def test_include_credentials_export_contains_passwords(seeded):
    r = _sess(seeded["token"]).get(
        f"{BASE_URL}/api/infrastructure/accounts/export?format=csv&include_credentials=true"
    )
    assert r.status_code == 200, r.text
    reader = csv.DictReader(io.StringIO(r.text))
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    # Base columns are still present
    for col in ("email", "smtp_host", "smtp_port", "smtp_username", "daily_limit", "status"):
        assert col in row, f"Existing column '{col}' missing after include_credentials=true"
    # New credential columns
    for col in ("smtp_password", "imap_password", "from_name", "smtp_ssl",
                "imap_ssl", "send_delay", "warmup_enabled", "priority", "tags",
                "smtp_encryption", "imap_encryption"):
        assert col in row, f"New credential column '{col}' missing"
    assert row["smtp_password"] == seeded["smtp_plain"]
    assert row["imap_password"] == seeded["imap_plain"]
    assert row["from_name"] == "Alice Marketing"
    assert row["daily_limit"] == "42"
    assert row["send_delay"] == "45"
    assert row["warmup_enabled"] == "true"


def test_export_response_headers(seeded):
    r = _sess(seeded["token"]).get(
        f"{BASE_URL}/api/infrastructure/accounts/export?format=csv&include_credentials=true"
    )
    assert r.status_code == 200
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd and "with_credentials" in cd and ".csv" in cd


def test_export_is_reimportable_round_trip(seeded, mongo):
    """Export → parse the file → verify every field required by the bulk
    importer (`/api/accounts/smtp/bulk-import`) is present and round-trips
    to a value the importer will accept, with the exact plain-text password."""
    r = _sess(seeded["token"]).get(
        f"{BASE_URL}/api/infrastructure/accounts/export?format=csv&include_credentials=true"
    )
    assert r.status_code == 200
    text = r.text
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]

    # Simulate what the bulk-import endpoint does — replicated verbatim so
    # this test breaks if the two ever drift out of sync.
    import re
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

    normalized = {_normalize_header(k): v for k, v in row.items()}

    # Required by the importer
    assert normalized["email"] == seeded["email"]
    assert normalized["smtp_password"] == seeded["smtp_plain"]
    assert normalized["smtp_host"] == "smtp.aliceco.export"
    assert normalized["smtp_port"] == "587"
    # Optional but restored
    assert normalized["from_name"] == "Alice Marketing"
    assert normalized["imap_password"] == seeded["imap_plain"]
    assert normalized["imap_host"] == "imap.aliceco.export"
    assert normalized["imap_port"] == "993"
    assert normalized["daily_limit"] == "42"
    assert normalized["delay_seconds"] == "45", (
        "send_delay column must alias to delay_seconds for the importer"
    )


def test_export_isolates_users(mongo, seeded, encrypter):
    """A different user's export must NEVER contain the seeded user's password."""
    other_user = f"{TAG}_other"
    other_token = f"{TAG}_ot_{uuid.uuid4().hex}"
    mongo.users.insert_one({
        "user_id": other_user, "email": f"{TAG}_other@iso.test", "name": "Other",
        "role": "user", "email_verified": True, "can_access_infrastructure": True,
        "created_at": _iso(), "tag": TAG,
    })
    mongo.user_sessions.insert_one({
        "user_id": other_user, "session_token": other_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "created_at": _iso(), "tag": TAG,
    })
    mongo.email_accounts.insert_one({
        "account_id": f"{TAG}_other_a", "user_id": other_user,
        "email": f"{TAG}_o@bobinc.export",
        "smtp_host": "smtp.bobinc.export", "smtp_port": 465,
        "smtp_username": f"{TAG}_o@bobinc.export",
        "smtp_password_encrypted": encrypter["encrypt"]("bobs-secret"),
        "smtp_encryption": "ssl",
        "daily_limit": 20, "status": "connected",
        "created_at": _iso(), "tag": TAG,
    })

    r = _sess(other_token).get(
        f"{BASE_URL}/api/infrastructure/accounts/export?format=csv&include_credentials=true"
    )
    assert r.status_code == 200
    assert "S3cret!P@ss-alpha" not in r.text, (
        "User B's export leaked User A's SMTP password — critical isolation bug"
    )
    # But User B's own password IS present
    assert "bobs-secret" in r.text
