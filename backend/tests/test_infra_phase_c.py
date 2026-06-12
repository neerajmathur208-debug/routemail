"""Iteration 58 — Infrastructure Phase C tests.

Covers:
- POST /reputation/recompute  (populates domain_reputation collection)
- GET  /reputation             (summary + buckets + worst/best + cache_ttl_hours)
- Reputation formula sanity (zero-send + bounced inbox)
- GET  /issues                 (counts + paused/risky/errored arrays)
- POST /issues/bulk            (resume, pause, delete, replace, validation)
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = ln.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
SUPER_ADMIN_ID = "user_b3e333b0f467"

REP = f"{BASE_URL}/api/infrastructure/reputation"
RECOMPUTE = f"{BASE_URL}/api/infrastructure/reputation/recompute"
ISSUES = f"{BASE_URL}/api/infrastructure/issues"
BULK = f"{BASE_URL}/api/infrastructure/issues/bulk"

TAG = f"TEST_iter58_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def admin_token(mongo):
    tok = f"{TAG}_{uuid.uuid4().hex}"
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


# ───────── seed data (paused + disconnected + bounced inbox) ─────────
@pytest.fixture(scope="module")
def seeded(mongo):
    now = datetime.now(timezone.utc)
    paused_id = f"acc_{TAG}_paused"
    disc_id = f"acc_{TAG}_disc"
    bounce_id = f"acc_{TAG}_bounce"
    zero_id = f"acc_{TAG}_zero"

    accounts = [
        {
            "account_id": paused_id,
            "user_id": SUPER_ADMIN_ID,
            "email": f"{TAG.lower()}.paused@phase-c-test.com",
            "ownership": "test",
            "status": "paused",
            "paused": True,
            "daily_limit": 50,
            "daily_send_count": 0,
            "warmup_enabled": False,
            "created_at": (now - timedelta(days=60)).isoformat(),
        },
        {
            "account_id": disc_id,
            "user_id": SUPER_ADMIN_ID,
            "email": f"{TAG.lower()}.disc@phase-c-test.com",
            "ownership": "test",
            "status": "disconnected",
            "last_error": "Mailbox unreachable",
            "daily_limit": 50,
            "daily_send_count": 0,
            "warmup_enabled": False,
            "created_at": (now - timedelta(days=60)).isoformat(),
        },
        {
            "account_id": bounce_id,
            "user_id": SUPER_ADMIN_ID,
            "email": f"{TAG.lower()}.bounce@phase-c-bounce.com",
            "ownership": "test",
            "status": "connected",
            "daily_limit": 50,
            "daily_send_count": 0,
            "warmup_enabled": False,
            "created_at": (now - timedelta(days=60)).isoformat(),
        },
        {
            "account_id": zero_id,
            "user_id": SUPER_ADMIN_ID,
            "email": f"{TAG.lower()}.zero@phase-c-zero.com",
            "ownership": "test",
            "status": "connected",
            "daily_limit": 50,
            "daily_send_count": 0,
            "warmup_enabled": False,
            "created_at": (now - timedelta(days=30)).isoformat(),
        },
    ]
    mongo.email_accounts.insert_many(accounts)

    # Bounced emails for bounce_id in email_queue
    queue_docs = []
    for i in range(5):
        queue_docs.append({
            "queue_id": f"q_{TAG}_{i}",
            "sent_from_account": bounce_id,
            "status": "bounced",
            "sent_at": (now - timedelta(days=2)).isoformat(),
        })
    # And some sends so bounce_rate is real (5 bounce / 10 sends = 50%)
    for i in range(5):
        queue_docs.append({
            "queue_id": f"qs_{TAG}_{i}",
            "sent_from_account": bounce_id,
            "status": "sent",
            "sent_at": (now - timedelta(days=2)).isoformat(),
        })
    mongo.email_queue.insert_many(queue_docs)

    yield {"paused": paused_id, "disc": disc_id, "bounce": bounce_id, "zero": zero_id}

    # cleanup
    mongo.email_accounts.delete_many({"account_id": {"$in": [paused_id, disc_id, bounce_id, zero_id]}})
    mongo.email_queue.delete_many({"queue_id": {"$regex": f"^q.*_{TAG}_"}})
    mongo.domain_reputation.delete_many({"domain": {"$regex": "phase-c-"}})
    mongo.tracked_replacements.delete_many({"replaced_account_id": {"$in": [paused_id, disc_id, bounce_id, zero_id]}})


# ───────── Reputation tests ─────────

class TestReputation:
    def test_recompute_returns_count(self, client, seeded, mongo):
        r = client.post(RECOMPUTE)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["message"] == "Recomputed"
        assert isinstance(data["domain_count"], int)
        assert data["domain_count"] >= 3  # at least our 3 test domains

        # Verify per-(user,domain) docs exist
        bdoc = mongo.domain_reputation.find_one({"user_id": SUPER_ADMIN_ID, "domain": "phase-c-bounce.com"})
        assert bdoc is not None
        assert "score_30d" in bdoc and "score_7d" in bdoc
        assert "inboxes" in bdoc and len(bdoc["inboxes"]) >= 1
        assert bdoc["inbox_count"] >= 1

    def test_get_reputation_summary_shape(self, client, seeded):
        r = client.get(REP)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "domains" in data and "summary" in data and "stale" in data
        assert data["cache_ttl_hours"] == 24
        s = data["summary"]
        for k in ("avg_score_30d", "avg_score_7d", "total_domains", "buckets", "worst", "best"):
            assert k in s
        # bucket labels
        valid_buckets = {"excellent", "good", "fair", "poor", "critical"}
        for d in data["domains"]:
            assert d["bucket_30d"] in valid_buckets
            assert d["bucket_7d"] in valid_buckets
            assert "inboxes" in d

    def test_zero_send_inbox_score_formula(self, client, seeded, mongo):
        """No sends → reply=0, bounce=100, unsub=100, error=100, age~33 (30d/90), warmup=60.
        Expected score = 0.5*0 + 0.1*33.3 + 0.1*60 + 0.2*100 + 0.05*100 + 0.05*100
                       = 0 + 3.33 + 6.0 + 20 + 5 + 5 ≈ 39.3
        We just sanity check 25 <= score <= 55 for zero-send inbox of age ~30 days."""
        client.post(RECOMPUTE)
        doc = mongo.domain_reputation.find_one({"domain": "phase-c-zero.com"})
        assert doc is not None
        inbox = next((i for i in doc["inboxes"] if i["account_id"].endswith("_zero")), None)
        assert inbox is not None
        score = inbox["window_30d"]["score"]
        # No sends → reply/bounce/error/unsub components are score 0/100/100/100. Age ~30/90→33. Warmup=60.
        # 0.5*0 + 0.1*33 + 0.1*60 + 0.2*100 + 0.05*100 + 0.05*100 ≈ 39
        assert 25 <= score <= 55, f"zero-send score out of expected range: {score}"
        # No sends ⇒ counts.sends = 0
        assert inbox["window_30d"]["sends"] == 0
        assert inbox["window_30d"]["bounces"] == 0
        # bounce/unsub/error component each = 100 (no real sends → assume clean)
        assert inbox["window_30d"]["components"]["bounce"] == 100.0
        assert inbox["window_30d"]["components"]["error"] == 100.0
        assert inbox["window_30d"]["components"]["unsubscribe"] == 100.0

    def test_bounced_inbox_lowers_score(self, client, seeded, mongo):
        """5 bounces / 10 sends = 50% bounce rate → bounce_score clamped to 0."""
        client.post(RECOMPUTE)
        doc = mongo.domain_reputation.find_one({"domain": "phase-c-bounce.com"})
        assert doc is not None
        inbox = next((i for i in doc["inboxes"] if "bounce" in i["account_id"]), None)
        assert inbox is not None
        w30 = inbox["window_30d"]
        # "sends" in engine = status=="sent" only (does NOT include bounced).
        # We seeded 5 sent + 5 bounced → sends=5, bounces=5, bounce_rate=100%.
        assert w30["sends"] >= 5
        assert w30["bounces"] >= 5
        # bounce_score = clamp(100 - 50%*1000) = clamp(100-500) = 0
        assert w30["components"]["bounce"] == 0.0
        assert w30["bounce_rate"] >= 40.0


# ───────── Issues dashboard ─────────

class TestIssues:
    def test_get_issues_contains_seeded(self, client, seeded):
        r = client.get(ISSUES)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("counts", "paused", "risky", "errored"):
            assert k in data
        counts = data["counts"]
        assert counts["total"] == counts["paused"] + counts["risky"] + counts["errored"]

        paused_ids = {x["account_id"] for x in data["paused"]}
        errored_ids = {x["account_id"] for x in data["errored"]}
        risky_ids = {x["account_id"] for x in data["risky"]}
        assert seeded["paused"] in paused_ids
        # disconnected → errored bucket AND status="Risky" (because last_error set → Risky)
        assert seeded["disc"] in errored_ids or seeded["disc"] in risky_ids

    def test_bulk_invalid_action(self, client, seeded):
        r = client.post(BULK, json={"action": "invalid", "account_ids": [seeded["paused"]]})
        assert r.status_code == 400

    def test_bulk_empty_account_ids_422(self, client):
        r = client.post(BULK, json={"action": "resume", "account_ids": []})
        assert r.status_code == 422

    def test_bulk_unknown_ids_404(self, client):
        # Admin user — ownership filter doesn't apply, but unknown id → no matches → 404
        r = client.post(BULK, json={"action": "resume", "account_ids": ["acc_does_not_exist_xyz"]})
        assert r.status_code == 404

    def test_bulk_resume(self, client, seeded, mongo):
        r = client.post(BULK, json={"action": "resume", "account_ids": [seeded["paused"]]})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["action"] == "resume"
        assert seeded["paused"] in data["succeeded"]
        # DB state flipped
        acc = mongo.email_accounts.find_one({"account_id": seeded["paused"]})
        assert acc["status"] == "connected"
        assert acc["paused"] is False
        assert acc["last_error"] is None

    def test_bulk_pause(self, client, seeded, mongo):
        # Pause our zero-send account (currently connected)
        r = client.post(BULK, json={"action": "pause", "account_ids": [seeded["zero"]]})
        assert r.status_code == 200, r.text
        assert seeded["zero"] in r.json()["succeeded"]
        acc = mongo.email_accounts.find_one({"account_id": seeded["zero"]})
        assert acc["status"] == "paused"
        assert acc["paused"] is True

    def test_bulk_delete_removes_from_campaigns(self, client, seeded, mongo):
        # Create a fresh disposable account + campaign referencing it
        acc_id = f"acc_{TAG}_del"
        camp_id = f"camp_{TAG}_del"
        drip_id = f"drip_{TAG}_del"
        mongo.email_accounts.insert_one({
            "account_id": acc_id,
            "user_id": SUPER_ADMIN_ID,
            "email": f"{TAG.lower()}.del@phase-c-zero.com",
            "ownership": "test",
            "status": "connected",
            "daily_limit": 50,
            "warmup_enabled": False,
        })
        mongo.campaigns.insert_one({
            "campaign_id": camp_id,
            "user_id": SUPER_ADMIN_ID,
            "name": f"{TAG}_camp",
            "status": "running",
            "account_ids": [acc_id, "other_account_id"],
        })
        mongo.drip_campaigns.insert_one({
            "drip_id": drip_id,
            "user_id": SUPER_ADMIN_ID,
            "name": f"{TAG}_drip",
            "status": "running",
            "account_ids": [acc_id, "other_account_id"],
        })

        try:
            r = client.post(BULK, json={"action": "delete", "account_ids": [acc_id]})
            assert r.status_code == 200, r.text
            assert acc_id in r.json()["succeeded"]
            # Account deleted
            assert mongo.email_accounts.find_one({"account_id": acc_id}) is None
            # Pulled from campaigns / drip_campaigns
            c = mongo.campaigns.find_one({"campaign_id": camp_id})
            d = mongo.drip_campaigns.find_one({"drip_id": drip_id})
            assert acc_id not in (c.get("account_ids") or [])
            assert acc_id not in (d.get("account_ids") or [])
            assert "other_account_id" in c["account_ids"]
        finally:
            mongo.campaigns.delete_one({"campaign_id": camp_id})
            mongo.drip_campaigns.delete_one({"drip_id": drip_id})
            mongo.email_accounts.delete_one({"account_id": acc_id})

    def test_bulk_replace_no_candidate_logs(self, client, seeded, mongo):
        """Replace on disconnected account — likely no clean candidate; verify
        either success path or no_candidate logged in tracked_replacements."""
        before = mongo.tracked_replacements.count_documents({"replaced_account_id": seeded["disc"]})
        r = client.post(BULK, json={"action": "replace", "account_ids": [seeded["disc"]]})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["action"] == "replace"
        # Either succeeded or failed; in both cases a tracked_replacements doc must exist
        after = mongo.tracked_replacements.count_documents({"replaced_account_id": seeded["disc"]})
        assert after > before
        last = mongo.tracked_replacements.find_one(
            {"replaced_account_id": seeded["disc"]}, sort=[("created_at", -1)]
        )
        assert last["triggered_by"] == "manual"
        assert last["status"] in ("completed", "no_candidate")
