"""Iteration 69 — Warmup ↔ Campaign independence.

Locks in the invariant that warmup enabling never blocks an inbox from
campaign allocation, capacity aggregation, or drip execution.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

import server  # noqa: E402
from infra_phase3 import _allocate as allocate_fn  # noqa: E402
from infrastructure_routes import _compute_status  # noqa: E402


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


# ─────────────────── _compute_status: pure ─────────────────────────────────

def test_warming_inbox_status_is_not_warming_up_anymore():
    """A warming inbox with full capacity should now report as ``Available``
    (not ``Warming Up``). Warmup becomes a facet, not a status."""
    acc = {
        "status": "connected",
        "warmup_enabled": True,
        "warmup_status": "active",
    }
    s = _compute_status(acc, sent_today=0, daily_limit=50, active_campaign_count=0)
    assert s == "Available", f"got {s}, expected Available"


def test_warming_inbox_with_partial_use_is_partially_available():
    acc = {
        "status": "connected",
        "warmup_enabled": True,
        "warmup_status": "warming",
    }
    s = _compute_status(acc, sent_today=10, daily_limit=50, active_campaign_count=0)
    assert s == "Partially Available"


def test_paused_still_returns_paused_even_when_warming():
    acc = {
        "status": "paused",
        "paused": True,
        "warmup_enabled": True,
        "warmup_status": "active",
    }
    s = _compute_status(acc, sent_today=0, daily_limit=50, active_campaign_count=0)
    assert s == "Paused"


def test_disconnected_still_returns_risky_even_when_warming():
    acc = {
        "status": "disconnected",
        "warmup_enabled": True,
        "warmup_status": "active",
    }
    s = _compute_status(acc, sent_today=0, daily_limit=50, active_campaign_count=0)
    assert s == "Risky"


# ─────────────────── allocator: warmup not a blocker ──────────────────────

def _mk_inbox(aid, domain, remaining, status, projection=None):
    return {
        "account_id": aid, "email": f"{aid}@{domain}", "domain": domain,
        "status": status, "remaining_capacity": remaining,
        "daily_limit": remaining + 5, "ownership": "internal",
        "warmup_status": "Active",
        "warming_up": True,  # ← flag doesn't change eligibility any more
        "projected_window_total": sum((projection or {}).values()),
    }


def test_allocator_includes_warming_inboxes():
    """The old SKIP_STATUSES included Warming Up. With the refactor, an inbox
    whose status is Available (regardless of the warming_up facet) must be
    eligible for allocation."""
    inbox_a = _mk_inbox("A", "a.example", 40, "Available")
    inbox_b = _mk_inbox("B", "b.example", 40, "Available")
    result = allocate_fn([inbox_a, inbox_b], {}, required=2,
                        min_remaining_per_inbox=10, domain_capacity_floor=10)
    assert result["allocated"] == 2
    assert {r["account_id"] for r in result["inboxes"]} == {"A", "B"}


def test_allocator_still_excludes_paused_and_risky_and_full():
    inbox_ok = _mk_inbox("A", "a.example", 40, "Available")
    inbox_pause = _mk_inbox("B", "b.example", 40, "Paused")
    inbox_risky = _mk_inbox("C", "c.example", 40, "Risky")
    inbox_full = _mk_inbox("D", "d.example", 0, "Fully Reserved")
    result = allocate_fn(
        [inbox_ok, inbox_pause, inbox_risky, inbox_full], {},
        required=4, min_remaining_per_inbox=10, domain_capacity_floor=10,
    )
    assert result["allocated"] == 1
    assert result["inboxes"][0]["account_id"] == "A"


# ─────────── Drip worker: warmup-enabled inboxes still send ───────────────

def _fake_smtp(account, recipient, subject, body, from_name_override=None,
               in_reply_to=None, references=None):
    async def _inner():
        return {"success": True, "message_id": f"<{uuid.uuid4().hex}@stub>"}
    return _inner()


@pytest.mark.asyncio
async def test_drip_worker_uses_warmup_enabled_inbox():
    """Concrete end-to-end: an inbox that has ``warmup_enabled=True`` and
    ``warmup_status='active'`` must still be picked by the drip worker and
    successfully send. Warmup is a parallel process; it cannot suppress
    campaign sending."""
    db = server.db
    uid = f"user_iter69_{uuid.uuid4().hex[:6]}"
    drip_id = f"drip_iter69_{uuid.uuid4().hex[:6]}"
    acc_id = f"acc_iter69_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    await db.email_accounts.insert_one({
        "account_id": acc_id, "user_id": uid, "email": f"{acc_id}@x.com",
        "status": "connected", "daily_limit": 50, "daily_send_count": 0,
        "last_reset_date": now.strftime("%Y-%m-%d"), "send_delay": 0,
        "smtp_host": "x", "smtp_port": 587, "smtp_username": "x",
        "smtp_password_encrypted": "x",
        # ← THE KEY BIT: warmup is actively running
        "warmup_enabled": True,
        "warmup_status": "active",
    })
    await db.drip_campaigns.insert_one({
        "drip_id": drip_id, "user_id": uid, "name": "iter69",
        "status": "running",
        "created_at": now.isoformat(),
        "steps": [{"subject": "S", "body": "B", "delay_days": 0}],
        "account_ids": [acc_id],
        "schedule": {"timezone": "UTC", "sending_days": list(range(7)),
                     "start_time": "00:00", "end_time": "23:59",
                     "randomize_time": False},
        "stop_on_reply": False, "stop_on_bounce": False,
    })
    await db.drip_contacts.insert_one({
        "contact_id": f"dc_{uuid.uuid4().hex[:8]}",
        "drip_id": drip_id, "user_id": uid,
        "email": "to@x.com", "status": "active",
        "current_step": 0,
        "next_send_at": (now - timedelta(minutes=1)).isoformat(),
        "replied": False, "bounced": False, "data": {},
    })
    try:
        with patch.object(server, "send_drip_email", new=_fake_smtp):
            c = await db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
            await server.process_drip_campaign(c)
        after = await db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
        # The single eligible contact must have been sent — warmup did NOT
        # block it.
        assert after["last_run_stats"]["sent_contacts"] == 1
        assert after["last_run_stats"]["stop_reason"] == "all_eligible_sent"
        assert acc_id in after["last_run_stats"]["accounts_used"]
    finally:
        await db.drip_campaigns.delete_many({"drip_id": drip_id})
        await db.drip_contacts.delete_many({"drip_id": drip_id})
        await db.email_accounts.delete_many({"account_id": acc_id})


# ─────────── Inbox listing endpoint: warmup facet exposed ────────────────

@pytest.fixture(scope="module")
def session():
    from pymongo import MongoClient
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    user_id = f"user_iter69_{uuid.uuid4().hex[:6]}"
    db.users.insert_one({
        "user_id": user_id, "email": f"{user_id}@example.com",
        "name": "iter69", "email_verified": True,
        "can_access_infrastructure": True,
    })
    token = f"TEST_iter69_{uuid.uuid4().hex}"
    db.user_sessions.insert_one({
        "session_token": token, "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=2),
    })
    yield {"token": token, "user_id": user_id, "db": db}
    db.user_sessions.delete_one({"session_token": token})
    db.users.delete_one({"user_id": user_id})


def test_inboxes_endpoint_returns_warming_up_facet(session):
    db = session["db"]
    uid = session["user_id"]
    acc_id = f"acc_iter69_{uuid.uuid4().hex[:6]}"
    db.email_accounts.insert_one({
        "account_id": acc_id, "user_id": uid, "email": f"{acc_id}@x.com",
        "status": "connected", "daily_limit": 40, "daily_send_count": 0,
        "warmup_enabled": True, "warmup_status": "active",
    })
    try:
        r = requests.get(f"{BASE}/api/infrastructure/inboxes",
                         cookies={"session_token": session["token"]})
        assert r.status_code == 200, r.text
        inboxes = r.json().get("rows") or r.json().get("inboxes") or []
        my_row = next((x for x in inboxes if x["account_id"] == acc_id), None)
        assert my_row is not None, f"warmup inbox missing from inbox listing"
        # Status must be Available (not Warming Up)
        assert my_row["status"] in ("Available", "Partially Available"), my_row["status"]
        # The warmup facet must be exposed for the UI
        assert my_row["warming_up"] is True
    finally:
        db.email_accounts.delete_many({"account_id": acc_id})
