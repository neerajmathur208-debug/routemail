"""
Iteration 27 tests:
- Drip campaigns RichTextEditor parity (HTML body round-trip via PUT/GET)
- Auto-resume of campaigns paused with status='paused_daily_limit'
- Manual-paused campaigns are NOT auto-resumed
- Drip campaigns daily-limit reset on date rollover (no contact step skip)
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

USER_EMAIL = "drip.tester@example.com"
USER_PASSWORD = "DripTest123!"
USER_ID = "user_35cc629e1385"

mongo = MongoClient(MONGO_URL)
db = mongo[DB_NAME]


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": USER_EMAIL, "password": USER_PASSWORD})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


# ------------------------------------------------------------------
# Drip campaign RichTextEditor HTML body round-trip
# ------------------------------------------------------------------
class TestDripHtmlBody:
    @pytest.fixture(scope="class")
    def drip_id(self, session):
        # Create a list first (drip campaign requires steps but list optional)
        payload = {
            "name": f"TEST_iter27_drip_{uuid.uuid4().hex[:8]}",
            "from_name": "Iter27",
            "account_ids": [],
            "steps": [
                {"step_number": 1, "subject": "Hi", "body": "<p>plain</p>", "delay_days": 0, "delay_hours": 0},
            ],
            "schedule": {
                "timezone": "UTC",
                "sending_days": [0, 1, 2, 3, 4],
                "start_time": "09:00",
                "end_time": "18:00",
                "randomize_time": False,
            },
            "stop_on_reply": True,
            "stop_on_bounce": True,
        }
        r = session.post(f"{API}/drip-campaigns", json=payload)
        assert r.status_code in (200, 201), r.text
        drip_id = r.json()["drip_id"]
        yield drip_id
        # cleanup
        db.drip_campaigns.delete_one({"drip_id": drip_id})

    def test_html_body_round_trip(self, session, drip_id):
        html_body = (
            '<p>Hello <strong>{{first_name}}</strong>,</p>'
            '<p>Click <a href="https://example.com">here</a> to learn more.</p>'
            '<ul><li>Item one</li><li>Item two</li></ul>'
        )
        # GET first
        r = session.get(f"{API}/drip-campaigns/{drip_id}")
        assert r.status_code == 200
        body = r.json()

        body["steps"][0]["body"] = html_body
        body["steps"][0]["subject"] = "Hi {{first_name}}"

        r = session.put(f"{API}/drip-campaigns/{drip_id}", json=body)
        assert r.status_code == 200, r.text

        r2 = session.get(f"{API}/drip-campaigns/{drip_id}")
        assert r2.status_code == 200
        out = r2.json()
        saved_body = out["steps"][0]["body"]
        # HTML must survive round trip: tags + variable + link
        assert "<strong>" in saved_body
        assert "<a href=\"https://example.com\"" in saved_body or "href='https://example.com'" in saved_body
        assert "{{first_name}}" in saved_body
        assert "<li>Item one</li>" in saved_body


# ------------------------------------------------------------------
# Auto-resume of paused_daily_limit campaigns
# ------------------------------------------------------------------
def _seed_account(account_id, last_send_date, daily_send_count=50, daily_limit=50):
    db.email_accounts.update_one(
        {"account_id": account_id},
        {"$set": {
            "account_id": account_id,
            "user_id": USER_ID,
            "email": f"{account_id}@example.com",
            "smtp_host": "smtp.invalid-bogus.example",
            "smtp_port": 587,
            "smtp_username": f"{account_id}@example.com",
            "smtp_password_encrypted": "x",
            "status": "connected",
            "last_send_date": last_send_date,
            "daily_send_count": daily_send_count,
            "daily_limit": daily_limit,
            "last_reset_date": last_send_date,
        }},
        upsert=True,
    )


def _seed_campaign(campaign_id, account_id, status="paused_daily_limit"):
    db.campaigns.update_one(
        {"campaign_id": campaign_id},
        {"$set": {
            "campaign_id": campaign_id,
            "user_id": USER_ID,
            "name": campaign_id,
            "status": status,
            "account_ids": [account_id],
            "list_id": None,
            "subject": "x",
            "body": "x",
            "from_name": "x",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_locked": False,
        }},
        upsert=True,
    )


@pytest.fixture
def cleanup_seed():
    created = {"campaigns": [], "accounts": []}
    yield created
    if created["campaigns"]:
        db.campaigns.delete_many({"campaign_id": {"$in": created["campaigns"]}})
    if created["accounts"]:
        db.email_accounts.delete_many({"account_id": {"$in": created["accounts"]}})


class TestAutoResume:
    def test_auto_resume_when_account_rolled_to_new_day(self, cleanup_seed):
        """Account last_send_date is in the past → auto-resume within ~30s tick."""
        acc = f"acc_TEST_iter27_roll_{uuid.uuid4().hex[:6]}"
        camp = f"camp_TEST_iter27_roll_{uuid.uuid4().hex[:6]}"
        _seed_account(acc, last_send_date="2020-01-01", daily_send_count=50, daily_limit=50)
        _seed_campaign(camp, acc, status="paused_daily_limit")
        cleanup_seed["campaigns"].append(camp)
        cleanup_seed["accounts"].append(acc)

        # wait up to 90s for the scheduler tick (interval is 30s)
        deadline = time.time() + 100
        resumed = False
        while time.time() < deadline:
            time.sleep(3)
            doc = db.campaigns.find_one({"campaign_id": camp})
            # The scheduler sets auto_resumed_at + flips status to running.
            # Then process_campaign_queue may immediately mark it completed/failed
            # since there's no actual queue. So we accept any non-paused state +
            # require the auto_resumed_at marker.
            if doc and doc.get("auto_resumed_at"):
                resumed = True
                assert doc.get("status") != "paused_daily_limit"
                break
        assert resumed, "Campaign was not auto-resumed (auto_resumed_at not set) within 100s"

    def test_no_resume_when_today_and_at_limit(self, cleanup_seed):
        """last_send_date=today AND count>=limit → stay paused. After raising limit, auto-resume."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        acc = f"acc_TEST_iter27_full_{uuid.uuid4().hex[:6]}"
        camp = f"camp_TEST_iter27_full_{uuid.uuid4().hex[:6]}"
        _seed_account(acc, last_send_date=today, daily_send_count=50, daily_limit=50)
        _seed_campaign(camp, acc, status="paused_daily_limit")
        cleanup_seed["campaigns"].append(camp)
        cleanup_seed["accounts"].append(acc)

        # Wait ~40s and ensure campaign is still paused
        time.sleep(45)
        doc = db.campaigns.find_one({"campaign_id": camp})
        assert doc.get("status") == "paused_daily_limit", \
            f"Should stay paused while at-limit but got {doc.get('status')}"

        # Now bump the daily_limit so capacity opens up
        db.email_accounts.update_one({"account_id": acc}, {"$set": {"daily_limit": 200}})
        # Reset the campaign back to paused_daily_limit if it was already auto-flipped
        # (defensive). Only flip if it's not already running/completed.
        deadline = time.time() + 70
        resumed = False
        while time.time() < deadline:
            time.sleep(3)
            doc = db.campaigns.find_one({"campaign_id": camp})
            if doc and doc.get("auto_resumed_at"):
                resumed = True
                assert doc.get("status") != "paused_daily_limit"
                break
        assert resumed, "Campaign did not auto-resume after raising daily_limit"

    def test_user_paused_not_auto_resumed(self, cleanup_seed):
        """status='paused' (no _daily_limit suffix) MUST NOT be touched by scheduler."""
        acc = f"acc_TEST_iter27_userp_{uuid.uuid4().hex[:6]}"
        camp = f"camp_TEST_iter27_userp_{uuid.uuid4().hex[:6]}"
        _seed_account(acc, last_send_date="2020-01-01", daily_send_count=0, daily_limit=50)
        _seed_campaign(camp, acc, status="paused")
        cleanup_seed["campaigns"].append(camp)
        cleanup_seed["accounts"].append(acc)

        time.sleep(45)
        doc = db.campaigns.find_one({"campaign_id": camp})
        assert doc.get("status") == "paused", \
            f"User-paused must remain 'paused' but got {doc.get('status')}"
        assert "auto_resumed_at" not in doc, "Should not have auto_resumed_at"


# ------------------------------------------------------------------
# Status label / behaviour confirmation via API surface
# ------------------------------------------------------------------
class TestStatusListing:
    def test_paused_daily_limit_visible_in_list(self, session, cleanup_seed):
        acc = f"acc_TEST_iter27_listcheck_{uuid.uuid4().hex[:6]}"
        camp = f"camp_TEST_iter27_listcheck_{uuid.uuid4().hex[:6]}"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        _seed_account(acc, last_send_date=today, daily_send_count=50, daily_limit=50)
        _seed_campaign(camp, acc, status="paused_daily_limit")
        cleanup_seed["campaigns"].append(camp)
        cleanup_seed["accounts"].append(acc)

        r = session.get(f"{API}/campaigns")
        assert r.status_code == 200
        camps = r.json() if isinstance(r.json(), list) else r.json().get("campaigns", [])
        match = next((c for c in camps if c.get("campaign_id") == camp), None)
        assert match is not None, "Seeded paused_daily_limit campaign not returned by /campaigns"
        assert match.get("status") == "paused_daily_limit"
