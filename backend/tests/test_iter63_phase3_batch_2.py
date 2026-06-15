"""Iteration 63 — Phase 3 Batch 2 backend tests.

Covers:
 1. GET /api/infrastructure/inboxes — new query params: ownership, domain, status,
    warmup_status, min_remaining, search, sort_by (whitelist + safe fallback),
    sort_dir, limit (1-500), skip. Response: {inboxes, filter_options, total, skip, limit}.
    Each row has projected_window_total + projected_window_days=120.
 2. POST /api/infrastructure/planner — new fields daily_limit_per_inbox,
    preferred_inboxes_per_domain. Math validation per spec.
 3. Planner fallback: daily_limit_per_inbox=None → empirical median;
    preferred_inboxes_per_domain=None → 5.
 4. POST /api/infrastructure/planner/export?format=xlsx → 200 binary with correct
    Content-Type + Content-Disposition. Same for format=csv.
 5. Regression: GET /api/infrastructure/accounts/export?format=xlsx still works.
"""
import io
import math
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
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

TAG = f"TEST_iter63_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def admin_token(mongo):
    tok = f"TEST_iter63_{uuid.uuid4().hex}"
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


# ---------- GET /infrastructure/inboxes ------------------------------------

class TestInboxesEndpoint:
    """List + sort + filter + pagination on /infrastructure/inboxes."""

    def test_basic_shape(self, client):
        r = client.get(f"{BASE_URL}/api/infrastructure/inboxes?limit=5")
        assert r.status_code == 200, r.text
        data = r.json()
        assert set(["inboxes", "filter_options", "total", "skip", "limit"]).issubset(data.keys())
        assert isinstance(data["inboxes"], list)
        assert isinstance(data["filter_options"], dict)
        assert "ownership" in data["filter_options"]
        assert "domain" in data["filter_options"]
        assert isinstance(data["filter_options"]["ownership"], list)
        assert isinstance(data["filter_options"]["domain"], list)
        assert data["limit"] == 5
        assert data["skip"] == 0
        # ≤ limit rows
        assert len(data["inboxes"]) <= 5
        # Each row has projected_window_total + projected_window_days=120
        for row in data["inboxes"]:
            assert "projected_window_total" in row
            assert "projected_window_days" in row
            assert row["projected_window_days"] == 120
            assert isinstance(row["projected_window_total"], int)

    def test_filter_options_unfiltered_universe(self, client):
        """filter_options must reflect the full universe even when filtering."""
        r_all = client.get(f"{BASE_URL}/api/infrastructure/inboxes")
        r_filt = client.get(f"{BASE_URL}/api/infrastructure/inboxes?status=Available")
        assert r_all.status_code == 200 and r_filt.status_code == 200
        full_opts = r_all.json()["filter_options"]
        filt_opts = r_filt.json()["filter_options"]
        # Filtered options should still equal the unfiltered universe
        assert full_opts["ownership"] == filt_opts["ownership"]
        assert full_opts["domain"] == filt_opts["domain"]

    def test_pagination(self, client):
        """skip+limit slice properly; total stays consistent."""
        r1 = client.get(f"{BASE_URL}/api/infrastructure/inboxes?limit=5&skip=0")
        r2 = client.get(f"{BASE_URL}/api/infrastructure/inboxes?limit=5&skip=5")
        assert r1.status_code == 200 and r2.status_code == 200
        d1, d2 = r1.json(), r2.json()
        assert d1["total"] == d2["total"]
        # No overlap
        ids1 = {row["account_id"] for row in d1["inboxes"]}
        ids2 = {row["account_id"] for row in d2["inboxes"]}
        assert not (ids1 & ids2)

    def test_sort_by_domain(self, client):
        r = client.get(f"{BASE_URL}/api/infrastructure/inboxes?sort_by=domain&sort_dir=asc&limit=500")
        assert r.status_code == 200
        rows = r.json()["inboxes"]
        domains = [row["domain"] for row in rows]
        assert domains == sorted(domains)

    def test_sort_by_remaining_capacity_desc(self, client):
        r = client.get(f"{BASE_URL}/api/infrastructure/inboxes?sort_by=remaining_capacity&sort_dir=desc&limit=500")
        assert r.status_code == 200
        rows = r.json()["inboxes"]
        caps = [row["remaining_capacity"] for row in rows]
        assert caps == sorted(caps, reverse=True)

    def test_sort_by_invalid_falls_back_to_email(self, client):
        """sort_by outside whitelist must fall back to email (safe fallback)."""
        r = client.get(f"{BASE_URL}/api/infrastructure/inboxes?sort_by=__INVALID__&sort_dir=asc&limit=500")
        assert r.status_code == 200
        rows = r.json()["inboxes"]
        emails = [row["email"] for row in rows]
        assert emails == sorted(emails)

    def test_search_substring(self, client):
        """Search filters rows on email/domain/ownership substring."""
        # Pull any email to do a substring match
        r0 = client.get(f"{BASE_URL}/api/infrastructure/inboxes?limit=1")
        if r0.status_code != 200 or not r0.json()["inboxes"]:
            pytest.skip("No inboxes to search against")
        sample_email = r0.json()["inboxes"][0]["email"]
        token = sample_email.split("@")[0][:3].lower()
        r = client.get(f"{BASE_URL}/api/infrastructure/inboxes?search={token}&limit=500")
        assert r.status_code == 200
        for row in r.json()["inboxes"]:
            blob = " ".join([row["email"] or "", row.get("domain") or "", row.get("ownership") or ""]).lower()
            assert token in blob

    def test_min_remaining(self, client):
        r = client.get(f"{BASE_URL}/api/infrastructure/inboxes?min_remaining=1&limit=500")
        assert r.status_code == 200
        for row in r.json()["inboxes"]:
            assert row["remaining_capacity"] >= 1

    def test_limit_bounds(self, client):
        # limit=0 should fail (ge=1)
        r = client.get(f"{BASE_URL}/api/infrastructure/inboxes?limit=0")
        assert r.status_code == 422
        # limit=501 should fail (le=500)
        r = client.get(f"{BASE_URL}/api/infrastructure/inboxes?limit=501")
        assert r.status_code == 422


# ---------- POST /infrastructure/planner -----------------------------------

class TestPlanner:
    """Capacity Planner math + new diversification warnings."""

    def test_planner_math_with_explicit_inputs(self, client):
        """Spec: leads=10000,steps=3,duration=30,sdpw=5,daily_limit=46,preferred=5
        → required_inboxes=ceil(total/sending_days/46) and so on."""
        payload = {
            "leads": 10000, "steps": 3, "duration_days": 30,
            "sending_days_per_week": 5,
            "daily_limit_per_inbox": 46, "preferred_inboxes_per_domain": 5,
        }
        r = client.post(f"{BASE_URL}/api/infrastructure/planner", json=payload)
        assert r.status_code == 200, r.text
        out = r.json()["outputs"]
        # total emails
        total = 10000 * 3
        sending_days = int(round(30 * (5 / 7.0)))  # ≈ 21
        required_daily = math.ceil(total / sending_days)
        expected_ri = math.ceil(required_daily / 46)
        expected_rd = max(1, math.ceil(expected_ri / 5))
        assert out["required_inboxes"] == expected_ri
        assert out["required_domains"] == expected_rd
        assert out["daily_capacity_per_domain"] == 46 * 5  # 230
        assert out["daily_sends_per_inbox"] == 46
        assert out["daily_capacity_total"] == 46 * expected_ri

        # Fields present
        for k in ("additional_inboxes_required", "additional_domains_required",
                 "current_inboxes", "current_domains",
                 "current_avg_inboxes_per_domain", "current_daily_per_domain",
                 "median_daily_limit", "domain_diversity"):
            assert k in out, f"missing output field {k}"

    def test_planner_warnings_low_domain_diversity(self, client):
        """If domain_diversity ≤ 4, a low-diversity warning fires."""
        payload = {
            "leads": 100, "steps": 1, "duration_days": 7,
            "sending_days_per_week": 5,
            "daily_limit_per_inbox": 46, "preferred_inboxes_per_domain": 5,
        }
        r = client.post(f"{BASE_URL}/api/infrastructure/planner", json=payload)
        assert r.status_code == 200
        data = r.json()
        if data["outputs"]["domain_diversity"] <= 4 and data["outputs"]["available_inboxes"] > 0:
            assert any("Low domain diversification" in w for w in data["warnings"]), data["warnings"]

    def test_planner_warning_additional_domains(self, client):
        """Big leads ask → additional_domains_required > 0 → warning about needing more domains."""
        payload = {
            "leads": 100000, "steps": 5, "duration_days": 14,
            "sending_days_per_week": 5,
            "daily_limit_per_inbox": 46, "preferred_inboxes_per_domain": 5,
        }
        r = client.post(f"{BASE_URL}/api/infrastructure/planner", json=payload)
        assert r.status_code == 200
        data = r.json()
        if data["outputs"]["additional_domains_required"] > 0:
            assert any("Need" in w and "domains" in w for w in data["warnings"]), data["warnings"]

    def test_planner_fallback_when_inputs_are_none(self, client):
        """daily_limit_per_inbox=None → empirical median; preferred=None → 5."""
        payload = {
            "leads": 5000, "steps": 2, "duration_days": 20,
            "sending_days_per_week": 5,
            # explicitly omit daily_limit_per_inbox and preferred
        }
        r = client.post(f"{BASE_URL}/api/infrastructure/planner", json=payload)
        assert r.status_code == 200, r.text
        inp = r.json()["inputs"]
        # Fallback for preferred = 5
        assert inp["preferred_inboxes_per_domain"] == 5
        # daily_limit_per_inbox is a positive int (median or 50 fallback)
        assert isinstance(inp["daily_limit_per_inbox"], int) and inp["daily_limit_per_inbox"] >= 1


# ---------- POST /infrastructure/planner/export -----------------------------

class TestPlannerExport:
    """Phase 3 Batch 2 — Planner XLSX + CSV export."""

    PAYLOAD = {
        "leads": 10000, "steps": 3, "duration_days": 30,
        "sending_days_per_week": 5,
        "daily_limit_per_inbox": 46, "preferred_inboxes_per_domain": 5,
    }

    def test_xlsx_export(self, client):
        r = client.post(
            f"{BASE_URL}/api/infrastructure/planner/export?format=xlsx",
            json=self.PAYLOAD,
        )
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        cd = r.headers.get("content-disposition", "")
        assert "capacity-planner.xlsx" in cd
        # Binary blob starts with PK (zip signature for xlsx)
        assert r.content[:2] == b"PK"
        assert len(r.content) > 1000

    def test_csv_export(self, client):
        r = client.post(
            f"{BASE_URL}/api/infrastructure/planner/export?format=csv",
            json=self.PAYLOAD,
        )
        assert r.status_code == 200, r.text
        assert r.headers["content-type"].startswith("text/csv")
        cd = r.headers.get("content-disposition", "")
        assert "capacity-planner.csv" in cd
        body = r.content.decode()
        # Must include header row + key fields
        assert "Field,Value" in body
        assert "Required Inboxes" in body
        assert "Required Domains" in body
        assert "Daily Capacity / Domain" in body


# ---------- Regression: accounts export -------------------------------------

class TestAccountsExportRegression:
    """Phase A /accounts/export endpoint still works after Phase 3 Batch 2."""

    def test_accounts_export_xlsx(self, client):
        r = client.get(f"{BASE_URL}/api/infrastructure/accounts/export?format=xlsx")
        # Accept 200 (it exists) or 404 (if it was removed/renamed)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        assert r.headers["content-type"].startswith(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert r.content[:2] == b"PK"

    def test_accounts_export_csv(self, client):
        r = client.get(f"{BASE_URL}/api/infrastructure/accounts/export?format=csv")
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        assert r.headers["content-type"].startswith("text/csv")
