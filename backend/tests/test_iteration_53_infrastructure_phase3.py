"""Iteration 53 — Phase 3 Infrastructure tests.

Covers POST /api/infrastructure/allocate + POST /api/infrastructure/planner:
  • allocate(4) → 4 inboxes from 4 distinct domains, avg=1.0
  • allocate(20) → only 16 (eligible cap), warning 'Insufficient eligible capacity'
  • domain_capacity_floor too high → allocated=0 + all domains skipped
  • min_remaining_per_inbox=1000 → excludes everything → allocated=0
  • validation 422: required=0, -1, >10000
  • planner(50000,4,30,5) → Insufficient, math sanity (total_emails, daily_volume, required_inboxes, additional_needed)
  • planner(1000,3,60) → Ready
  • planner validation 422
  • 403 for non-permitted regular user on both endpoints
  • Phase-1/Phase-2 regression sanity
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
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

SUPER_ADMIN_ID = "user_b3e333b0f467"
NORMAL_USER_ID = "user_35cc629e1385"


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


def _make_session(db, user_id):
    token = f"TEST_iter53_{uuid.uuid4().hex}"
    db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=2),
    })
    return token


def _client(token):
    s = requests.Session()
    s.cookies.set("session_token", token)
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def admin_token(mongo):
    tok = _make_session(mongo, SUPER_ADMIN_ID)
    yield tok
    mongo.user_sessions.delete_one({"session_token": tok})


@pytest.fixture(scope="module")
def user_token(mongo):
    tok = _make_session(mongo, NORMAL_USER_ID)
    # Ensure regular user does NOT have infra access
    mongo.users.update_one(
        {"user_id": NORMAL_USER_ID},
        {"$set": {"can_access_infrastructure": False}},
    )
    yield tok
    mongo.user_sessions.delete_one({"session_token": tok})


@pytest.fixture(scope="module")
def admin_client(admin_token):
    return _client(admin_token)


@pytest.fixture(scope="module")
def user_client(user_token):
    return _client(user_token)


# ---------- ALLOCATOR ----------

class TestAllocator:
    def test_allocate_4_diversified(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/infrastructure/allocate", json={"required": 4})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["requested"] == 4
        assert data["allocated"] == 4
        assert len(data["inboxes"]) == 4
        # 4 inboxes from 4 distinct domains
        domains = {row["domain"] for row in data["inboxes"]}
        assert len(domains) == 4, f"Expected 4 distinct domains, got: {domains}"
        assert len(data["domains_used"]) == 4
        assert data["avg_inboxes_per_domain"] == 1.0
        # eligible_count = 16 per spec
        assert data["eligible_count"] == 16
        # Shape per inbox
        keys = {"account_id", "email", "domain", "ownership", "daily_limit", "remaining_capacity", "status"}
        for row in data["inboxes"]:
            assert keys.issubset(row.keys())
            assert row["status"] not in {"Warming Up", "Paused", "Risky", "Fully Reserved"}

    def test_allocate_20_warns_insufficient(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/infrastructure/allocate", json={"required": 20})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["requested"] == 20
        assert data["allocated"] == 16  # only 16 eligible after filters
        assert data["eligible_count"] == 16
        assert any("Insufficient eligible capacity" in w for w in data["warnings"]), data["warnings"]

    def test_allocate_domain_capacity_floor_skips_all(self, admin_client):
        # Floor higher than any per-domain aggregate remaining capacity.
        r = admin_client.post(
            f"{BASE_URL}/api/infrastructure/allocate",
            json={"required": 4, "domain_capacity_floor": 9999},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["allocated"] == 0
        assert len(data["skipped_domains_near_exhaustion"]) >= 1
        assert data["eligible_count"] == 0

    def test_allocate_min_remaining_floor_excludes_all(self, admin_client):
        r = admin_client.post(
            f"{BASE_URL}/api/infrastructure/allocate",
            json={"required": 4, "min_remaining_per_inbox": 1000},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["allocated"] == 0
        assert data["eligible_count"] == 0

    @pytest.mark.parametrize("required", [0, -1, 10001])
    def test_allocate_validation_422(self, admin_client, required):
        r = admin_client.post(f"{BASE_URL}/api/infrastructure/allocate", json={"required": required})
        assert r.status_code == 422, f"required={required} expected 422 got {r.status_code}"

    def test_allocate_403_for_non_permitted_user(self, user_client):
        r = user_client.post(f"{BASE_URL}/api/infrastructure/allocate", json={"required": 4})
        assert r.status_code == 403, r.text


# ---------- PLANNER ----------

class TestPlanner:
    def test_planner_large_insufficient(self, admin_client):
        r = admin_client.post(
            f"{BASE_URL}/api/infrastructure/planner",
            json={"leads": 50000, "steps": 4, "duration_days": 30, "sending_days_per_week": 5},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "Insufficient Capacity"
        out = data["outputs"]
        assert out["total_emails"] == 200000  # 50000 * 4
        # sending_days_in_window = round(30 * 5/7) = round(21.428) = 21
        assert out["sending_days_in_window"] == 21
        # required_daily_volume = ceil(200000 / 21) = 9524
        assert out["required_daily_volume"] == 9524
        # required_inboxes = ceil(9524 / 50) = 191
        assert out["required_inboxes"] == 191
        assert out["available_inboxes"] == 16
        assert out["additional_inboxes_required"] == 175
        assert out["median_daily_limit"] == 50
        assert out["domain_diversity"] == 5
        assert any("Need" in w and "more" in w for w in data["warnings"]), data["warnings"]

    def test_planner_small_ready(self, admin_client):
        r = admin_client.post(
            f"{BASE_URL}/api/infrastructure/planner",
            json={"leads": 1000, "steps": 3, "duration_days": 60},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "Ready", data
        out = data["outputs"]
        assert out["required_inboxes"] <= out["available_inboxes"]
        # No 'Need X inboxes' warning
        assert not any("Need" in w and "more to fit" in w for w in data["warnings"]), data["warnings"]

    @pytest.mark.parametrize("payload", [
        {"leads": 0, "steps": 4, "duration_days": 30},
        {"leads": 1000, "steps": 0, "duration_days": 30},
        {"leads": 1000, "steps": 21, "duration_days": 30},
        {"leads": 1000, "steps": 4, "duration_days": 0},
        {"leads": 1000, "steps": 4, "duration_days": 30, "sending_days_per_week": 0},
        {"leads": 1000, "steps": 4, "duration_days": 30, "sending_days_per_week": 8},
    ])
    def test_planner_validation_422(self, admin_client, payload):
        r = admin_client.post(f"{BASE_URL}/api/infrastructure/planner", json=payload)
        assert r.status_code == 422, f"{payload} expected 422 got {r.status_code} {r.text}"

    def test_planner_403_for_non_permitted_user(self, user_client):
        r = user_client.post(
            f"{BASE_URL}/api/infrastructure/planner",
            json={"leads": 1000, "steps": 3, "duration_days": 60},
        )
        assert r.status_code == 403, r.text


# ---------- REGRESSION ----------

class TestRegression:
    def test_summary_still_works(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/infrastructure/summary")
        assert r.status_code == 200
        d = r.json()
        assert "inbox_counts" in d and "capacity" in d
        assert d["capacity"]["window_days"] == 120

    def test_inboxes_still_works(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/infrastructure/inboxes")
        assert r.status_code == 200
        d = r.json()
        assert len(d["inboxes"]) == 18  # 18 in test dataset
        for row in d["inboxes"]:
            assert "projected_window_total" in row

    def test_calendar_still_works(self, admin_client):
        # Pick first account
        r = admin_client.get(f"{BASE_URL}/api/infrastructure/inboxes")
        acc_id = r.json()["inboxes"][0]["account_id"]
        r2 = admin_client.get(f"{BASE_URL}/api/infrastructure/calendar/{acc_id}")
        assert r2.status_code == 200
        assert len(r2.json()["days"]) == 120

    def test_export_still_works(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/infrastructure/export?type=inboxes&format=csv")
        assert r.status_code == 200
        assert b"Projected (120d)" in r.content

    def test_auth_me(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200

    def test_campaigns(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/campaigns")
        assert r.status_code == 200

    def test_drip_campaigns(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/drip-campaigns")
        assert r.status_code == 200

    def test_accounts(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/accounts")
        assert r.status_code == 200
