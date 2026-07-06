"""Iteration 68 — Concurrent drip execution + shared-inbox priority +
global email-list search + dashboard capacity + schedule-aware allocate.
"""
import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

import server  # noqa: E402
from infra_phase3 import _allocate as allocate_fn  # noqa: E402


BASE = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL"):
            BASE = line.split("=", 1)[1].strip().rstrip("/")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def session():
    from pymongo import MongoClient
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    user_id = f"user_iter68_{uuid.uuid4().hex[:6]}"
    db.users.insert_one({
        "user_id": user_id, "email": f"{user_id}@example.com",
        "name": "iter68", "email_verified": True,
        "can_access_infrastructure": True,
    })
    token = f"TEST_iter68_{uuid.uuid4().hex}"
    db.user_sessions.insert_one({
        "session_token": token, "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=2),
    })
    yield {"token": token, "user_id": user_id, "db": db}
    db.user_sessions.delete_one({"session_token": token})
    db.users.delete_one({"user_id": user_id})


# ─────────────────── ITEM 3 — GLOBAL LIST SEARCH ──────────────────────────

def test_global_email_list_search(session):
    db = session["db"]
    uid = session["user_id"]
    list1_id = f"list_{uuid.uuid4().hex[:8]}"
    list2_id = f"list_{uuid.uuid4().hex[:8]}"
    db.email_lists.insert_many([
        {"list_id": list1_id, "user_id": uid, "name": "Q1 outbound",
         "created_at": datetime.now(timezone.utc).isoformat(),
         "emails": [
             {"email": "john@acme.example", "first_name": "John", "company": "Acme"},
             {"email": "jane@zeta.example", "first_name": "Jane", "company": "Zeta"},
         ]},
        {"list_id": list2_id, "user_id": uid, "name": "Q2 partners",
         "created_at": datetime.now(timezone.utc).isoformat(),
         "emails": [
             {"email": "bob@acme.example", "first_name": "Bob", "company": "Acme"},
         ]},
    ])
    try:
        # 1. Match by email substring — finds all 3 rows (all have "example").
        r = requests.get(f"{BASE}/api/lists/search-global?q=example",
                         cookies={"session_token": session["token"]})
        assert r.status_code == 200
        out = r.json()
        assert out["total_matches"] == 3
        emails = sorted(x["email"] for x in out["results"])
        assert emails == ["bob@acme.example", "jane@zeta.example", "john@acme.example"]
        # Each result carries its source list_name + list_id.
        for row in out["results"]:
            assert row["list_id"] in {list1_id, list2_id}
            assert row["list_name"] in {"Q1 outbound", "Q2 partners"}

        # 2. Match by first_name — case-insensitive.
        r = requests.get(f"{BASE}/api/lists/search-global?q=JOHN",
                         cookies={"session_token": session["token"]})
        assert r.json()["total_matches"] == 1

        # 3. Match by company — spans multiple lists (Acme is in both).
        r = requests.get(f"{BASE}/api/lists/search-global?q=Acme",
                         cookies={"session_token": session["token"]})
        assert r.json()["total_matches"] == 2  # John + Bob (both Acme)
    finally:
        db.email_lists.delete_many({"list_id": {"$in": [list1_id, list2_id]}})


# ────────────────── ITEM 4 — DASHBOARD CAPACITY ───────────────────────────

def test_dashboard_capacity_widget(session):
    db = session["db"]
    uid = session["user_id"]
    acc1 = f"acc_{uuid.uuid4().hex[:6]}"
    acc2 = f"acc_{uuid.uuid4().hex[:6]}"
    acc3 = f"acc_{uuid.uuid4().hex[:6]}"
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db.email_accounts.insert_many([
        {"account_id": acc1, "user_id": uid, "email": f"{acc1}@x.com",
         "status": "connected", "daily_limit": 100, "daily_send_count": 30,
         "last_reset_date": today, "last_send_date": today},
        {"account_id": acc2, "user_id": uid, "email": f"{acc2}@x.com",
         "status": "connected", "daily_limit": 50, "daily_send_count": 0,
         "last_reset_date": today, "last_send_date": today},
        {"account_id": acc3, "user_id": uid, "email": f"{acc3}@x.com",
         "status": "connected", "daily_limit": 40, "daily_send_count": 0,
         "last_reset_date": today, "last_send_date": today},
    ])
    # Running drip using acc1 + acc2 (shared → engaged capacity should reflect both).
    drip_id = f"drip_{uuid.uuid4().hex[:8]}"
    db.drip_campaigns.insert_one({
        "drip_id": drip_id, "user_id": uid, "name": "engage",
        "status": "running", "account_ids": [acc1, acc2],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "steps": [], "schedule": {},
    })
    try:
        r = requests.get(f"{BASE}/api/dashboard/capacity",
                         cookies={"session_token": session["token"]})
        assert r.status_code == 200
        out = r.json()
        # Total = 100 + 50 + 40 = 190
        assert out["total_daily_capacity"] == 190
        # Remaining today: (100-30) + 50 + 40 = 160
        assert out["total_remaining_today"] == 160
        # Reserved by the running drip: acc1 + acc2 = (100-30) + 50 = 120
        assert out["reserved_capacity"] == 120
        # Available = 160 - 120 = 40 (acc3 is not in any campaign)
        assert out["available_capacity"] == 40
        assert out["engaged_accounts"] == 2
        assert out["total_accounts"] == 3
        assert out["running_drips"] == 1
        assert out["running_campaigns"] == 0
    finally:
        db.email_accounts.delete_many({"account_id": {"$in": [acc1, acc2, acc3]}})
        db.drip_campaigns.delete_many({"drip_id": drip_id})


# ─────────── ITEMS 1 + 2 — CONCURRENT + PRIORITY DRIPS ────────────────────

def _fake_smtp(account, recipient, subject, body, from_name_override=None,
               in_reply_to=None, references=None):
    async def _inner():
        return {"success": True, "message_id": f"<{uuid.uuid4().hex}@stub>"}
    return _inner()


@pytest.mark.asyncio
async def test_multiple_drips_execute_in_same_tick(session):
    """Two running drips must both be processed in a single call to
    process_drip_campaigns() — no one-at-a-time queueing."""
    db = server.db
    uid = session["user_id"]
    acc_id = f"acc_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    await db.email_accounts.insert_one({
        "account_id": acc_id, "user_id": uid, "email": f"{acc_id}@x.com",
        "status": "connected", "daily_limit": 100, "daily_send_count": 0,
        "last_reset_date": now.strftime("%Y-%m-%d"), "send_delay": 0,
        "smtp_host": "x", "smtp_port": 587, "smtp_username": "x",
        "smtp_password_encrypted": "x",
    })
    drip_a = f"drip_A_{uuid.uuid4().hex[:6]}"
    drip_b = f"drip_B_{uuid.uuid4().hex[:6]}"
    base = {
        "user_id": uid, "status": "running",
        "steps": [{"subject": "S", "body": "B", "delay_days": 0}],
        "account_ids": [acc_id],
        "schedule": {"timezone": "UTC", "sending_days": list(range(7)),
                     "start_time": "00:00", "end_time": "23:59",
                     "randomize_time": False},
        "stop_on_reply": False, "stop_on_bounce": False,
    }
    # Campaign A created FIRST (older) — must have priority.
    await db.drip_campaigns.insert_one({
        "drip_id": drip_a, "name": "A_older",
        "created_at": (now - timedelta(days=5)).isoformat(),
        **base,
    })
    await db.drip_campaigns.insert_one({
        "drip_id": drip_b, "name": "B_newer",
        "created_at": now.isoformat(),
        **base,
    })
    for drip_id in (drip_a, drip_b):
        await db.drip_contacts.insert_one({
            "contact_id": f"dc_{uuid.uuid4().hex[:8]}",
            "drip_id": drip_id, "user_id": uid,
            "email": f"to_{drip_id}@x.com",
            "status": "active", "current_step": 0,
            "next_send_at": (now - timedelta(minutes=1)).isoformat(),
            "replied": False, "bounced": False, "data": {},
        })
    try:
        with patch.object(server, "send_drip_email", new=_fake_smtp):
            await server.process_drip_campaigns()
        after_a = await db.drip_campaigns.find_one({"drip_id": drip_a}, {"_id": 0})
        after_b = await db.drip_campaigns.find_one({"drip_id": drip_b}, {"_id": 0})
        # BOTH campaigns must have run in this single tick.
        assert after_a["last_run_stats"]["sent_contacts"] == 1
        assert after_b["last_run_stats"]["sent_contacts"] == 1
    finally:
        await db.drip_campaigns.delete_many({"drip_id": {"$in": [drip_a, drip_b]}})
        await db.drip_contacts.delete_many({"drip_id": {"$in": [drip_a, drip_b]}})
        await db.email_accounts.delete_many({"account_id": acc_id})


@pytest.mark.asyncio
async def test_older_drip_wins_priority_on_shared_inbox(session):
    """Shared inbox: 40/day limit, Campaign A needs 30, Campaign B needs 30.
    A is older → A sends its 30, B sends what's left (10)."""
    db = server.db
    uid = session["user_id"]
    acc_id = f"acc_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    await db.email_accounts.insert_one({
        "account_id": acc_id, "user_id": uid, "email": f"{acc_id}@x.com",
        "status": "connected", "daily_limit": 40, "daily_send_count": 0,
        "last_reset_date": now.strftime("%Y-%m-%d"), "send_delay": 0,
        "smtp_host": "x", "smtp_port": 587, "smtp_username": "x",
        "smtp_password_encrypted": "x",
    })
    drip_a = f"drip_older_{uuid.uuid4().hex[:6]}"
    drip_b = f"drip_newer_{uuid.uuid4().hex[:6]}"
    base = {
        "user_id": uid, "status": "running",
        "steps": [{"subject": "S", "body": "B", "delay_days": 0}],
        "account_ids": [acc_id],
        "schedule": {"timezone": "UTC", "sending_days": list(range(7)),
                     "start_time": "00:00", "end_time": "23:59",
                     "randomize_time": False},
        "stop_on_reply": False, "stop_on_bounce": False,
    }
    await db.drip_campaigns.insert_one({
        "drip_id": drip_a, "name": "older",
        "created_at": (now - timedelta(days=30)).isoformat(),
        **base,
    })
    await db.drip_campaigns.insert_one({
        "drip_id": drip_b, "name": "newer",
        "created_at": now.isoformat(),
        **base,
    })
    for drip_id in (drip_a, drip_b):
        docs = [{
            "contact_id": f"dc_{uuid.uuid4().hex[:10]}",
            "drip_id": drip_id, "user_id": uid,
            "email": f"to_{drip_id}_{i}@x.com",
            "status": "active", "current_step": 0,
            "next_send_at": (now - timedelta(minutes=1)).isoformat(),
            "replied": False, "bounced": False, "data": {},
        } for i in range(30)]
        await db.drip_contacts.insert_many(docs)
    try:
        with patch.object(server, "send_drip_email", new=_fake_smtp):
            await server.process_drip_campaigns()
        after_a = await db.drip_campaigns.find_one({"drip_id": drip_a}, {"_id": 0})
        after_b = await db.drip_campaigns.find_one({"drip_id": drip_b}, {"_id": 0})
        # A (older) claimed 30. B got the remaining 10. Combined = 40 limit.
        sent_a = after_a["last_run_stats"]["sent_contacts"]
        sent_b = after_b["last_run_stats"]["sent_contacts"]
        assert sent_a + sent_b == 40, f"sent_a={sent_a} sent_b={sent_b}"
        assert sent_a >= sent_b, "Older campaign must not be starved by newer one"
        assert sent_a >= 20, f"Older campaign only got {sent_a}, expected priority"
    finally:
        await db.drip_campaigns.delete_many({"drip_id": {"$in": [drip_a, drip_b]}})
        await db.drip_contacts.delete_many({"drip_id": {"$in": [drip_a, drip_b]}})
        await db.email_accounts.delete_many({"account_id": acc_id})


# ─────────── ITEM 5 — SCHEDULE-AWARE ALLOCATE ────────────────────────────

def _mk_inbox(aid, domain, remaining, projection_by_date):
    """Build an inbox row shaped like `load_inboxes_fn` output."""
    return {
        "account_id": aid, "email": f"{aid}@{domain}", "domain": domain,
        "status": "Active", "remaining_capacity": remaining,
        "daily_limit": remaining, "ownership": "internal",
        "warmup_status": "Complete", "warmup_days_remaining": 0,
        "projected_window_total": sum(projection_by_date.values()),
    }


def test_allocate_schedule_aware_filters_saturated_future_days():
    """Two inboxes on separate domains, both have plenty of capacity today
    (100 each). One inbox is SATURATED on the specific future day the
    campaign will send on. The allocator must skip it."""
    from datetime import date as _d
    step2_date = (_d.today() + timedelta(days=7)).isoformat()
    # inbox A has 20 units available on step2_date (below the 50 estimate)
    inbox_a = _mk_inbox("A", "a.example", 100, {step2_date: 20})
    # inbox B has 200 units available on step2_date (well above the estimate)
    inbox_b = _mk_inbox("B", "b.example", 100, {step2_date: 200})
    projection = {
        "A": {step2_date: 20},
        "B": {step2_date: 200},
    }
    # 1) Without schedule input, both inboxes qualify (baseline).
    baseline = allocate_fn([inbox_a, inbox_b], projection, required=2,
                            min_remaining_per_inbox=10, domain_capacity_floor=10)
    assert baseline["allocated"] == 2

    # 2) With schedule + per_day_send_estimate, only B should qualify.
    filtered = allocate_fn(
        [inbox_a, inbox_b], projection, required=2,
        min_remaining_per_inbox=10, domain_capacity_floor=10,
        execution_dates=[step2_date], per_day_send_estimate=50,
    )
    assert filtered["allocated"] == 1
    assert filtered["inboxes"][0]["account_id"] == "B"
    assert any("Schedule-aware" in w for w in filtered["warnings"])


def test_allocate_endpoint_computes_execution_dates_from_schedule(session):
    """POST /allocate with start_date + steps + delay generates the right
    future date list and returns it in the response."""
    # Aim for a well-defined start_date so we can predict the dates.
    start = (date.today() + timedelta(days=10)).isoformat()
    r = requests.post(
        f"{BASE}/api/infrastructure/allocate",
        cookies={"session_token": session["token"]},
        json={
            "required": 2,
            "start_date": start,
            "steps": 3,
            "delay_days_between_steps": 7,
            "sending_days": [0, 1, 2, 3, 4],  # weekdays only
            "per_day_send_estimate": 10,
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()
    # Response must echo the computed execution_dates
    assert "execution_dates" in out
    assert len(out["execution_dates"]) == 3
    # Every execution date must fall on an allowed weekday (0-4 = Mon-Fri).
    for iso in out["execution_dates"]:
        wd = date.fromisoformat(iso).weekday()
        assert wd in {0, 1, 2, 3, 4}, f"{iso} is weekday {wd}, expected Mon-Fri"
