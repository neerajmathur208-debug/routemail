"""Iteration 73 — Reports module (CSV + JSON).

Verifies the new spec:
- GET /api/reports/campaigns returns rows filtered by date range /
  campaign type / name search, strictly scoped to the requester's user_id.
- GET /api/reports/campaigns/export.csv streams the 4-column CSV with the
  correct headers, escapes commas/quotes, and covers Campaigns + Drips.
- Large reports export correctly (100+ rows).
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

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for ln in f:
            if ln.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = ln.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

TAG = f"rep73_{uuid.uuid4().hex[:8]}"


def _iso(d=None):
    d = d if d is not None else datetime.now(timezone.utc)
    return d.isoformat()


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def seeded(mongo):
    user_id = f"{TAG}_u"
    token = f"{TAG}_tok_{uuid.uuid4().hex}"

    mongo.users.insert_one({
        "user_id": user_id, "email": f"{TAG}@rep.test",
        "name": "Reports Tester", "role": "user",
        "email_verified": True, "created_at": _iso(), "tag": TAG,
    })
    mongo.user_sessions.insert_one({
        "user_id": user_id, "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "created_at": _iso(), "tag": TAG,
    })

    # 3 campaigns with different dates for range filter testing
    now = datetime.now(timezone.utc)
    campaigns = [
        {"campaign_id": f"{TAG}_c1", "user_id": user_id, "name": "Q1 Outreach, Wave 1",
         "status": "completed", "total_emails": 500, "sent_count": 495,
         "created_at": (now - timedelta(days=30)).isoformat(),
         "started_at": (now - timedelta(days=29)).isoformat(),
         "tag": TAG},
        {"campaign_id": f"{TAG}_c2", "user_id": user_id, "name": 'Winter "Big" Push',
         "status": "running", "total_emails": 800, "sent_count": 200,
         "created_at": (now - timedelta(days=10)).isoformat(),
         "started_at": (now - timedelta(days=9)).isoformat(),
         "tag": TAG},
        {"campaign_id": f"{TAG}_c3", "user_id": user_id, "name": "Spring Warmup",
         "status": "scheduled", "total_emails": 300, "sent_count": 0,
         "created_at": now.isoformat(),
         "scheduled_at": (now + timedelta(days=1)).isoformat(),
         "tag": TAG},
    ]
    mongo.campaigns.insert_many(campaigns)

    # 2 drip campaigns
    drips = [
        {"drip_id": f"{TAG}_d1", "user_id": user_id, "name": "Nurture Drip A",
         "status": "running", "total_contacts": 150, "total_sent": 87,
         "steps": [{"delay_days": 0}, {"delay_days": 3}],
         "schedule": {"start_date": (now - timedelta(days=5)).date().isoformat()},
         "created_at": (now - timedelta(days=5)).isoformat(),
         "tag": TAG},
        {"drip_id": f"{TAG}_d2", "user_id": user_id, "name": "Onboarding Drip",
         "status": "paused", "total_contacts": 40, "total_sent": 12,
         "steps": [{"delay_days": 0}],
         "schedule": {"start_date": (now - timedelta(days=2)).date().isoformat()},
         "created_at": (now - timedelta(days=2)).isoformat(),
         "tag": TAG},
    ]
    mongo.drip_campaigns.insert_many(drips)

    ctx = {"user_id": user_id, "token": token,
           "camp_ids": [c["campaign_id"] for c in campaigns],
           "drip_ids": [d["drip_id"] for d in drips]}
    yield ctx

    # cleanup
    for coll in ("users", "user_sessions", "campaigns", "drip_campaigns"):
        mongo[coll].delete_many({"tag": TAG})


def _sess(token):
    s = requests.Session()
    s.cookies.set("session_token", token)
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ─── JSON endpoint ───────────────────────────────────────────────────────

def test_campaign_report_returns_both_types_by_default(seeded):
    r = _sess(seeded["token"]).get(f"{BASE_URL}/api/reports/campaigns")
    assert r.status_code == 200, r.text
    body = r.json()
    types = {row["type"] for row in body["rows"]}
    assert types == {"Campaign", "Drip Campaign"}, f"Expected both, got {types}"
    # 3 campaigns + 2 drips
    assert body["total"] == 5


def test_campaign_report_filter_type_campaign(seeded):
    r = _sess(seeded["token"]).get(
        f"{BASE_URL}/api/reports/campaigns?campaign_type=campaign"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3
    assert all(row["type"] == "Campaign" for row in body["rows"])


def test_campaign_report_filter_type_drip(seeded):
    r = _sess(seeded["token"]).get(
        f"{BASE_URL}/api/reports/campaigns?campaign_type=drip"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert all(row["type"] == "Drip Campaign" for row in body["rows"])


def test_campaign_report_invalid_type_rejected(seeded):
    r = _sess(seeded["token"]).get(
        f"{BASE_URL}/api/reports/campaigns?campaign_type=nope"
    )
    assert r.status_code == 400


def test_campaign_report_search_filter(seeded):
    r = _sess(seeded["token"]).get(
        f"{BASE_URL}/api/reports/campaigns?search=nurture"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["rows"][0]["name"] == "Nurture Drip A"


def test_campaign_report_date_range_filter(seeded):
    # Only c2 (10 days ago) + d1 (5 days) + d2 (2 days ago) fit a "last 14 days"
    # end-of-today window. c1 (30d ago) is excluded, and c3 (scheduled for
    # tomorrow) is also excluded because its date_sent falls after end_date.
    start = (datetime.now(timezone.utc) - timedelta(days=14)).date().isoformat()
    end = datetime.now(timezone.utc).date().isoformat()
    r = _sess(seeded["token"]).get(
        f"{BASE_URL}/api/reports/campaigns?start_date={start}&end_date={end}"
    )
    assert r.status_code == 200
    body = r.json()
    names = {row["name"] for row in body["rows"]}
    assert "Q1 Outreach, Wave 1" not in names, "30-day-old campaign should be excluded"
    assert "Winter \"Big\" Push" in names
    assert "Nurture Drip A" in names
    assert "Onboarding Drip" in names


def test_campaign_report_populates_prospects_and_sent(seeded):
    r = _sess(seeded["token"]).get(
        f"{BASE_URL}/api/reports/campaigns?campaign_type=campaign&search=Q1"
    )
    row = r.json()["rows"][0]
    assert row["total_prospects"] == 500
    assert row["emails_sent"] == 495
    # ISO YYYY-MM-DD date
    assert len(row["date_sent"]) == 10 and row["date_sent"][4] == "-"


# ─── CSV endpoint ────────────────────────────────────────────────────────

_EXPECTED_HEADERS = [
    "Campaign / Drip Campaign Name",
    "Total Prospects in the List",
    "Emails Sent",
    "Date Sent",
]


def _parse_csv(response_text: str):
    reader = csv.reader(io.StringIO(response_text))
    return list(reader)


def test_csv_export_headers_and_content(seeded):
    r = _sess(seeded["token"]).get(f"{BASE_URL}/api/reports/campaigns/export.csv")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/csv")
    cd = r.headers.get("content-disposition", "")
    assert 'attachment' in cd and '.csv' in cd, cd

    rows = _parse_csv(r.text)
    assert rows[0] == _EXPECTED_HEADERS, f"CSV headers mismatch: {rows[0]}"
    # 5 data rows expected
    data_rows = rows[1:]
    assert len(data_rows) == 5, f"Expected 5 rows, got {len(data_rows)}"


def test_csv_escapes_commas_and_quotes(seeded):
    r = _sess(seeded["token"]).get(f"{BASE_URL}/api/reports/campaigns/export.csv")
    rows = _parse_csv(r.text)
    names = [row[0] for row in rows[1:]]
    # "Q1 Outreach, Wave 1" has a comma
    assert "Q1 Outreach, Wave 1" in names, f"CSV lost comma-name row. Names: {names}"
    # 'Winter "Big" Push' has embedded quotes
    assert 'Winter "Big" Push' in names, f"CSV lost quoted-name row. Names: {names}"


def test_csv_export_type_filter_only_drip(seeded):
    r = _sess(seeded["token"]).get(
        f"{BASE_URL}/api/reports/campaigns/export.csv?campaign_type=drip"
    )
    assert r.status_code == 200
    rows = _parse_csv(r.text)
    data_rows = rows[1:]
    assert len(data_rows) == 2  # only drips
    names = {r[0] for r in data_rows}
    assert names == {"Nurture Drip A", "Onboarding Drip"}


def test_csv_export_is_not_empty_when_data_exists(seeded):
    """Guardrail: exporting when data exists must never produce a headers-only CSV."""
    r = _sess(seeded["token"]).get(f"{BASE_URL}/api/reports/campaigns/export.csv")
    rows = _parse_csv(r.text)
    assert len(rows) > 1, "CSV should contain at least header + one data row"


def test_csv_export_large_report(mongo, seeded):
    """Seed 200 additional campaigns, ensure the CSV export streams all of them."""
    extra = []
    now = datetime.now(timezone.utc)
    for i in range(200):
        extra.append({
            "campaign_id": f"{TAG}_bulk_{i}", "user_id": seeded["user_id"],
            "name": f"Bulk Test Campaign #{i}", "status": "completed",
            "total_emails": 50 + i, "sent_count": 40 + i,
            "created_at": (now - timedelta(days=(i % 60))).isoformat(),
            "started_at": (now - timedelta(days=(i % 60))).isoformat(),
            "tag": TAG,
        })
    mongo.campaigns.insert_many(extra)
    try:
        r = _sess(seeded["token"]).get(
            f"{BASE_URL}/api/reports/campaigns/export.csv?campaign_type=campaign"
        )
        assert r.status_code == 200
        rows = _parse_csv(r.text)
        # 3 seed campaigns + 200 bulk
        assert len(rows) - 1 >= 203, f"Large CSV row count too low: {len(rows) - 1}"
    finally:
        mongo.campaigns.delete_many({"campaign_id": {"$regex": f"^{TAG}_bulk_"}})


def test_csv_export_respects_user_isolation(mongo, seeded):
    """A different user must NEVER see the seeded user's rows in their CSV."""
    other_user = f"{TAG}_other"
    other_token = f"{TAG}_othertok_{uuid.uuid4().hex}"
    mongo.users.insert_one({
        "user_id": other_user, "email": f"{TAG}_other@iso.test",
        "name": "Other user", "role": "user", "email_verified": True,
        "created_at": _iso(), "tag": TAG,
    })
    mongo.user_sessions.insert_one({
        "user_id": other_user, "session_token": other_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "created_at": _iso(), "tag": TAG,
    })
    try:
        r = _sess(other_token).get(f"{BASE_URL}/api/reports/campaigns/export.csv")
        assert r.status_code == 200
        rows = _parse_csv(r.text)
        names = [row[0] for row in rows[1:]]
        assert "Q1 Outreach, Wave 1" not in names
        assert "Nurture Drip A" not in names
    finally:
        mongo.users.delete_one({"user_id": other_user})
        mongo.user_sessions.delete_one({"session_token": other_token})
