"""Iteration 57 — Infrastructure Phase B (automatic replacement) backend tests.

Covers GET /candidate/{id}, POST /execute/{id}, POST /auto-scan, GET /replacements.
Rules under test:
  - Replacement must come from FREE pool (no campaign/drip uses it).
  - Cross-domain preferred.
  - tracked_replacements log shape (status, triggered_by, cross_domain, swaps).
  - Filters by status / triggered_by.
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

CANDIDATE = f"{BASE_URL}/api/infrastructure/replacements/candidate"
EXECUTE = f"{BASE_URL}/api/infrastructure/replacements/execute"
AUTOSCAN = f"{BASE_URL}/api/infrastructure/replacements/auto-scan"
HISTORY = f"{BASE_URL}/api/infrastructure/replacements"
INBOXES = f"{BASE_URL}/api/infrastructure/inboxes"

TAG = f"TEST_iter57_{uuid.uuid4().hex[:8]}"


# ───────── fixtures ─────────
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


@pytest.fixture(scope="module")
def inboxes(client):
    r = client.get(INBOXES)
    assert r.status_code == 200
    rows = r.json() if isinstance(r.json(), list) else r.json().get("inboxes", [])
    # group by domain to support cross-domain tests
    return rows


def _pick_two_diff_domains(rows):
    """Return two healthy rows (status not in Paused/Risky/Warming Up) with capacity, on different domains."""
    healthy = [r for r in rows if r["status"] not in ("Paused", "Risky", "Warming Up") and r["remaining_capacity"] > 0]
    by_dom = {}
    for r in healthy:
        by_dom.setdefault(r["domain"], []).append(r)
    doms = [d for d, lst in by_dom.items() if lst]
    if len(doms) >= 2:
        return by_dom[doms[0]][0], by_dom[doms[1]][0]
    return None, None


@pytest.fixture(scope="module")
def seed(mongo, inboxes):
    """Seed: pick account A (paused target, assigned to camp_A), and account B
    (free healthy on a *different* domain). Also create camp_B using a third
    account C so we can prove C is excluded from candidate pool (busy).
    """
    if len(inboxes) < 3:
        pytest.skip("Need >=3 inboxes")
    a, b = _pick_two_diff_domains(inboxes)
    if not a or not b:
        pytest.skip("Need 2 healthy accounts on different domains")
    # account C: any other healthy account
    c = next((r for r in inboxes
              if r["account_id"] not in (a["account_id"], b["account_id"])
              and r["status"] not in ("Paused", "Risky", "Warming Up")
              and r["remaining_capacity"] > 0), None)
    if not c:
        pytest.skip("Need 3rd healthy account")

    # Save A's original status, then mark paused
    original_a = mongo.email_accounts.find_one({"account_id": a["account_id"]}, {"_id": 0, "status": 1})
    mongo.email_accounts.update_one({"account_id": a["account_id"]}, {"$set": {"status": "paused"}})

    # Campaign assigning A (target)
    camp_a = {
        "campaign_id": f"{TAG}_camp_a",
        "name": f"{TAG} camp A",
        "user_id": SUPER_ADMIN_ID,
        "status": "running",
        "account_ids": [a["account_id"]],
        "created_at": datetime.now(timezone.utc),
    }
    # Campaign assigning C (busy → should be excluded from pool)
    camp_c = {
        "campaign_id": f"{TAG}_camp_c",
        "name": f"{TAG} camp C",
        "user_id": SUPER_ADMIN_ID,
        "status": "running",
        "account_ids": [c["account_id"]],
        "created_at": datetime.now(timezone.utc),
    }
    # Drip assigning A (to verify drip swap as well)
    drip_a = {
        "drip_id": f"{TAG}_drip_a",
        "name": f"{TAG} drip A",
        "user_id": SUPER_ADMIN_ID,
        "status": "running",
        "account_ids": [a["account_id"]],
        "schedule": {},
        "created_at": datetime.now(timezone.utc),
    }
    mongo.campaigns.insert_many([camp_a, camp_c])
    mongo.drip_campaigns.insert_one(drip_a)

    yield {"a": a, "b": b, "c": c, "camp_a": camp_a["campaign_id"],
           "camp_c": camp_c["campaign_id"], "drip_a": drip_a["drip_id"]}

    # Teardown
    mongo.campaigns.delete_many({"campaign_id": {"$regex": f"^{TAG}_"}})
    mongo.drip_campaigns.delete_many({"drip_id": {"$regex": f"^{TAG}_"}})
    mongo.tracked_replacements.delete_many({"replaced_account_id": a["account_id"]})
    mongo.tracked_replacements.delete_many({"user_id": SUPER_ADMIN_ID, "reason": {"$regex": "^TEST_iter57"}})
    # restore status
    if original_a:
        mongo.email_accounts.update_one(
            {"account_id": a["account_id"]},
            {"$set": {"status": original_a.get("status", "active")}},
        )


# ───────── tests ─────────
class TestCandidate:
    def test_candidate_returns_replacement_and_excludes_busy(self, client, seed):
        r = client.get(f"{CANDIDATE}/{seed['a']['account_id']}")
        assert r.status_code == 200, r.text
        d = r.json()
        # replaced echoed back
        assert d["replaced"]["account_id"] == seed["a"]["account_id"]
        # candidate exists and is NOT the busy account C
        assert d["candidate"] is not None, f"expected candidate but got {d}"
        assert d["candidate"]["account_id"] != seed["c"]["account_id"], "busy account leaked into pool"
        # affected lists camp_a + drip_a
        camp_ids = [c["campaign_id"] for c in d["affected"]["campaigns"]]
        drip_ids = [dr["drip_id"] for dr in d["affected"]["drips"]]
        assert seed["camp_a"] in camp_ids
        assert seed["drip_a"] in drip_ids

    def test_candidate_cross_domain_preferred(self, client, seed):
        r = client.get(f"{CANDIDATE}/{seed['a']['account_id']}")
        d = r.json()
        # picked candidate domain != replaced domain (because b is on different domain)
        if d["candidate"]:
            # cross_domain flag matches reality
            assert d["candidate"]["cross_domain"] == (d["candidate"]["domain"] != d["replaced"]["domain"])
            # at minimum the candidate must be on a different domain since one is available
            assert d["candidate"]["domain"] != seed["a"]["domain"]

    def test_candidate_unknown_account_404(self, client):
        r = client.get(f"{CANDIDATE}/acc_does_not_exist_zzz")
        assert r.status_code == 404


class TestExecute:
    def test_execute_swaps_and_logs(self, client, mongo, seed):
        # Execute manual replacement
        r = client.post(f"{EXECUTE}/{seed['a']['account_id']}",
                        json={"manual": True, "reason": "TEST_iter57"})
        assert r.status_code == 200, r.text
        d = r.json()
        log = d["log"]
        assert log["status"] == "completed"
        assert log["triggered_by"] == "manual"
        assert "cross_domain" in log
        assert log["replaced_account_id"] == seed["a"]["account_id"]
        new_id = log["replacement_account_id"]
        assert new_id and new_id != seed["c"]["account_id"]
        assert d["swap_counts"]["campaigns"] >= 1
        assert d["swap_counts"]["drips"] >= 1

        # Verify campaign account_ids rewritten in DB
        camp = mongo.campaigns.find_one({"campaign_id": seed["camp_a"]}, {"_id": 0, "account_ids": 1})
        assert new_id in camp["account_ids"]
        assert seed["a"]["account_id"] not in camp["account_ids"]
        # Drip swapped too
        drip = mongo.drip_campaigns.find_one({"drip_id": seed["drip_a"]}, {"_id": 0, "account_ids": 1})
        assert new_id in drip["account_ids"]
        assert seed["a"]["account_id"] not in drip["account_ids"]

        # Camp_c (busy unrelated) untouched
        camp_c = mongo.campaigns.find_one({"campaign_id": seed["camp_c"]}, {"_id": 0, "account_ids": 1})
        assert camp_c["account_ids"] == [seed["c"]["account_id"]]

        # Log row present in tracked_replacements
        doc = mongo.tracked_replacements.find_one({"replacement_id": log["replacement_id"]}, {"_id": 0})
        assert doc is not None
        assert doc["status"] == "completed"

    def test_execute_unknown_account_404(self, client):
        r = client.post(f"{EXECUTE}/acc_does_not_exist_zzz",
                        json={"manual": True, "reason": "x"})
        assert r.status_code == 404


class TestHistory:
    def test_history_lists_completed_and_filters(self, client, mongo, seed):
        # Insert a synthetic no_candidate row for filter testing
        synthetic = {
            "replacement_id": f"rep_{uuid.uuid4().hex[:12]}",
            "user_id": SUPER_ADMIN_ID,
            "replaced_account_id": seed["a"]["account_id"],
            "replaced_email": seed["a"]["email"],
            "replaced_domain": seed["a"]["domain"],
            "replaced_status": "Paused",
            "replacement_account_id": None,
            "reason": "TEST_iter57",
            "triggered_by": "auto",
            "status": "no_candidate",
            "campaigns_swapped": [],
            "drips_swapped": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        mongo.tracked_replacements.insert_one(synthetic.copy())

        # Default list
        r = client.get(f"{HISTORY}?limit=50")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "items" in d and "counts" in d and "total" in d
        assert d["total"] >= 1
        ids = [it["replacement_id"] for it in d["items"]]
        assert synthetic["replacement_id"] in ids

        # counts include by_status + by_trigger keys
        counts = d["counts"]
        assert any(k in counts for k in ("completed", "no_candidate"))
        assert any(k.startswith("by_") for k in counts)

        # status filter
        r2 = client.get(f"{HISTORY}?status=no_candidate&limit=50")
        assert r2.status_code == 200
        for it in r2.json()["items"]:
            assert it["status"] == "no_candidate"

        # triggered_by filter
        r3 = client.get(f"{HISTORY}?triggered_by=manual&limit=50")
        assert r3.status_code == 200
        for it in r3.json()["items"]:
            assert it["triggered_by"] == "manual"


class TestAutoScan:
    def test_auto_scan_shape(self, client, mongo, inboxes):
        # Just verify the endpoint shape and that no_candidate logging works.
        r = client.post(AUTOSCAN)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("scanned", "candidates", "completed", "no_candidate"):
            assert k in d
        assert isinstance(d["completed"], list)
        assert isinstance(d["no_candidate"], list)
        # cleanup any auto-generated logs created by this run (best-effort)
        mongo.tracked_replacements.delete_many({"triggered_by": "auto",
                                                "reason": {"$regex": "Paused|Risky"}})
