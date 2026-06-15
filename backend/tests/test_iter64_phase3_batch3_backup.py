"""Iteration 64 — Phase 3 Batch 3 backup/restore additions.

Verifies that the full-account backup ZIP now carries:
  • infrastructure.json with tracked_domains / domain_reputation / tracked_replacements
  • sent_emails.json + replies.json
  • X-Backup-Summary response header (count summary)
  • Restore endpoint correctly imports infrastructure + sent_emails + replies
  • /backup/import/full/preview surfaces counts for the new files
"""
import io
import json
import os
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

USER_ID = "user_35cc629e1385"  # drip.tester


@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def session(mongo):
    token = f"TEST_iter64_{uuid.uuid4().hex}"
    mongo.user_sessions.insert_one({
        "session_token": token,
        "user_id": USER_ID,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=2),
    })
    yield {"session_token": token}
    mongo.user_sessions.delete_one({"session_token": token})


@pytest.fixture
def seed_infra(mongo):
    domain = f"iter64-{uuid.uuid4().hex[:6]}.example.com"
    rep_domain = f"iter64rep-{uuid.uuid4().hex[:6]}.example.com"
    mongo.tracked_domains.insert_one({
        "user_id": USER_ID,
        "domain": domain,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    mongo.domain_reputation.insert_one({
        "user_id": USER_ID,
        "domain": rep_domain,
        "score_30d": 87,
    })
    repl_marker = uuid.uuid4().hex
    mongo.tracked_replacements.insert_one({
        "user_id": USER_ID,
        "from_domain": "a.example.com",
        "to_domain": "b.example.com",
        "marker": repl_marker,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    yield {"domain": domain, "rep_domain": rep_domain, "repl_marker": repl_marker}
    mongo.tracked_domains.delete_many({"user_id": USER_ID, "domain": domain})
    mongo.domain_reputation.delete_many({"user_id": USER_ID, "domain": rep_domain})
    mongo.tracked_replacements.delete_many({"user_id": USER_ID, "marker": repl_marker})


def test_full_export_includes_infrastructure_and_summary_header(session, seed_infra):
    r = requests.get(f"{BASE_URL}/api/backup/export/full", cookies=session)
    assert r.status_code == 200
    assert "X-Backup-Summary" in r.headers
    summary = json.loads(r.headers["X-Backup-Summary"])
    assert "counts" in summary
    assert summary["counts"]["tracked_domains"] >= 1
    assert summary["counts"]["domain_reputation_rows"] >= 1
    assert summary["counts"]["tracked_replacements"] >= 1
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = set(zf.namelist())
    assert "infrastructure.json" in names
    assert "sent_emails.json" in names
    assert "replies.json" in names
    infra = json.loads(zf.read("infrastructure.json"))
    assert any(d.get("domain") == seed_infra["domain"] for d in infra.get("tracked_domains", []))
    assert any(d.get("domain") == seed_infra["rep_domain"] for d in infra.get("domain_reputation", []))


def test_preview_reports_new_collection_counts(session, seed_infra):
    r = requests.get(f"{BASE_URL}/api/backup/export/full", cookies=session)
    assert r.status_code == 200
    r2 = requests.post(
        f"{BASE_URL}/api/backup/import/full/preview",
        cookies=session,
        files={"file": ("b.zip", r.content, "application/zip")},
    )
    assert r2.status_code == 200
    summary = r2.json()["summary"]
    for key in ("tracked_domains", "domain_reputation_rows", "tracked_replacements", "sent_emails", "replies"):
        assert key in summary, f"missing key {key} in preview summary"


def test_restore_imports_infrastructure_and_replays_history(session, seed_infra, mongo):
    # Export then restore in skip mode — existing infra is skipped, replacement
    # history is always appended (audit log behaviour).
    r = requests.get(f"{BASE_URL}/api/backup/export/full", cookies=session)
    assert r.status_code == 200
    before_repl = mongo.tracked_replacements.count_documents(
        {"user_id": USER_ID, "marker": seed_infra["repl_marker"]}
    )
    r2 = requests.post(
        f"{BASE_URL}/api/backup/import/full?conflict=skip",
        cookies=session,
        files={"file": ("b.zip", r.content, "application/zip")},
    )
    assert r2.status_code == 200
    results = r2.json()["results"]
    assert "infrastructure" in results
    infra_res = results["infrastructure"]
    assert infra_res["tracked_domains_skipped"] >= 1
    assert infra_res["domain_reputation_skipped"] >= 1
    assert infra_res["tracked_replacements_imported"] >= 1
    after_repl = mongo.tracked_replacements.count_documents(
        {"user_id": USER_ID, "marker": seed_infra["repl_marker"]}
    )
    assert after_repl > before_repl


def test_restore_replace_mode_overwrites_infrastructure(session, mongo):
    # Seed a known domain
    domain = f"iter64rep-mode-{uuid.uuid4().hex[:6]}.example.com"
    mongo.tracked_domains.insert_one({
        "user_id": USER_ID,
        "domain": domain,
        "status": "active",
        "marker": "ORIGINAL",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        # Build a custom backup zip containing the same domain with a different marker
        infra_payload = {
            "tracked_domains": [{"domain": domain, "status": "active", "marker": "RESTORED"}],
            "domain_reputation": [],
            "tracked_replacements": [],
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("metadata.json", json.dumps({"schema_version": 1, "exported_at": datetime.now(timezone.utc).isoformat()}))
            zf.writestr("infrastructure.json", json.dumps(infra_payload))
        buf.seek(0)
        r = requests.post(
            f"{BASE_URL}/api/backup/import/full?conflict=replace",
            cookies=session,
            files={"file": ("b.zip", buf.getvalue(), "application/zip")},
        )
        assert r.status_code == 200
        infra_res = r.json()["results"]["infrastructure"]
        assert infra_res["tracked_domains_replaced"] >= 1
        doc = mongo.tracked_domains.find_one({"user_id": USER_ID, "domain": domain}, {"_id": 0})
        assert doc and doc.get("marker") == "RESTORED"
    finally:
        mongo.tracked_domains.delete_many({"user_id": USER_ID, "domain": domain})


def test_restore_sent_emails_dedupes_by_message_id(session, mongo):
    msg_id = f"iter64-msg-{uuid.uuid4().hex}@example.com"
    payload_items = [{
        "message_id": msg_id,
        "sender_email": "from@example.com",
        "recipient_email": "to@example.com",
        "subject": "Iter64 dedup test",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "body_text": "hello",
    }]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("metadata.json", json.dumps({"schema_version": 1, "exported_at": datetime.now(timezone.utc).isoformat()}))
        zf.writestr("sent_emails.json", json.dumps(payload_items))
    buf.seek(0)
    zip_bytes = buf.getvalue()
    try:
        # First import — should insert
        r1 = requests.post(
            f"{BASE_URL}/api/backup/import/full?conflict=copy",
            cookies=session,
            files={"file": ("b.zip", zip_bytes, "application/zip")},
        )
        assert r1.status_code == 200
        assert r1.json()["results"]["sent_emails"]["imported"] == 1
        # Second import — same message_id should be skipped
        r2 = requests.post(
            f"{BASE_URL}/api/backup/import/full?conflict=copy",
            cookies=session,
            files={"file": ("b.zip", zip_bytes, "application/zip")},
        )
        assert r2.status_code == 200
        assert r2.json()["results"]["sent_emails"]["skipped"] == 1
        assert r2.json()["results"]["sent_emails"]["imported"] == 0
    finally:
        mongo.sent_emails.delete_many({"user_id": USER_ID, "message_id": msg_id})
