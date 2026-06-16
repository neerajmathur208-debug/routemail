"""Iteration 66 — Drip campaign sending bugs.

Locks in three structural fixes to `process_drip_campaign` /
`process_drip_contact`:
  1. No hidden 100-contact cap per worker tick.
  2. Fair least-loaded account rotation (no `hash(contact_id) % len` pinning).
  3. `last_run_stats` + `last_run_stop_reason` are persisted on the campaign
     and the right `stop_reason` is recorded for each terminal condition.

These tests stub out the actual SMTP send so they run hermetically against
the real Mongo connection used by the backend module.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

sys.path.insert(0, "/app/backend")

import server  # noqa: E402  (server has heavy import side-effects)

# All tests in this module share Motor's connection pool which is bound to
# the first event loop it touches. Force one module-scoped loop so subsequent
# tests don't crash with "Event loop is closed".
@pytest.fixture(scope="module")
def event_loop():  # noqa: D401 — pytest-asyncio fixture override
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _local_now_in_window(tz_str="UTC"):
    """Return (start_time, end_time) strings that bracket the current UTC
    time so the schedule-window gate inside the worker is open."""
    import pytz
    tz = pytz.timezone(tz_str)
    now_local = datetime.now(timezone.utc).astimezone(tz)
    start_h = max(now_local.hour - 1, 0)
    end_h = min(now_local.hour + 2, 23)
    return f"{start_h:02d}:00", f"{end_h:02d}:59"


def _make_account(user_id, daily_limit=40, account_id=None, sent_today=0):
    aid = account_id or f"acc_{uuid.uuid4().hex[:8]}"
    return {
        "account_id": aid,
        "user_id": user_id,
        "email": f"{aid}@example.com",
        "status": "connected",
        "daily_limit": daily_limit,
        "daily_send_count": sent_today,
        "last_reset_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "send_delay": 0,
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": f"{aid}@example.com",
        "smtp_password_encrypted": "x",
        "smtp_use_ssl": False,
    }


async def _setup_drip(num_contacts, num_accounts, daily_limit=40):
    db = server.db
    user_id = f"user_iter66_{uuid.uuid4().hex[:6]}"
    drip_id = f"drip_iter66_{uuid.uuid4().hex[:6]}"

    # Schedule window open in UTC right now
    s, e = _local_now_in_window("UTC")

    accounts = [_make_account(user_id, daily_limit=daily_limit) for _ in range(num_accounts)]
    await db.email_accounts.insert_many(accounts)

    campaign = {
        "drip_id": drip_id,
        "user_id": user_id,
        "name": "iter66 drip",
        "status": "running",
        "steps": [{"subject": "S1", "body": "B1", "delay_days": 0, "delay_hours": 0}],
        "account_ids": [a["account_id"] for a in accounts],
        "schedule": {
            "timezone": "UTC",
            "sending_days": list(range(7)),  # any day
            "start_time": s,
            "end_time": e,
            "randomize_time": False,
        },
        "stop_on_reply": False,
        "stop_on_bounce": False,
    }
    await db.drip_campaigns.insert_one(campaign)

    contacts = []
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    for i in range(num_contacts):
        contacts.append({
            "contact_id": f"dc_{uuid.uuid4().hex[:10]}",
            "drip_id": drip_id,
            "user_id": user_id,
            "email": f"to_{i}@example.com",
            "status": "active",
            "current_step": 0,
            "next_send_at": past,
            "replied": False,
            "bounced": False,
            "data": {},
        })
    if contacts:
        await db.drip_contacts.insert_many(contacts)
    return drip_id, user_id, [a["account_id"] for a in accounts]


async def _cleanup(drip_id, user_id, account_ids):
    db = server.db
    await db.drip_campaigns.delete_many({"drip_id": drip_id})
    await db.drip_contacts.delete_many({"drip_id": drip_id})
    await db.drip_logs.delete_many({"drip_id": drip_id})
    await db.email_accounts.delete_many({"account_id": {"$in": account_ids}})


def _fake_smtp_send(account, recipient, subject, body, from_name_override=None):
    """Stub that emulates a successful SMTP send."""
    async def _inner():
        return {"success": True, "message_id": f"<{uuid.uuid4().hex}@stub>"}
    return _inner()


@pytest.mark.asyncio
async def test_drip_processes_more_than_100_contacts_in_single_tick():
    """The old code had a hidden `.to_list(100)` cap. With 250 contacts +
    ample account capacity, a SINGLE tick should send all 250."""
    drip_id, user_id, acc_ids = await _setup_drip(num_contacts=250, num_accounts=10, daily_limit=50)
    try:
        with patch.object(server, "send_drip_email", new=_fake_smtp_send):
            campaign = await server.db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
            await server.process_drip_campaign(campaign)
        # Read back persisted diagnostics
        after = await server.db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
        stats = after["last_run_stats"]
        assert stats["eligible_contacts"] == 250
        assert stats["sent_contacts"] == 250
        assert stats["stop_reason"] == "all_eligible_sent"
        sent_logs = await server.db.drip_logs.count_documents({"drip_id": drip_id, "status": "sent"})
        assert sent_logs == 250
    finally:
        await _cleanup(drip_id, user_id, acc_ids)


@pytest.mark.asyncio
async def test_fair_rotation_uses_all_accounts():
    """Hash-based pinning would lopside the send distribution. Least-loaded
    selection should spread sends approximately evenly across all 10 accounts
    when total demand (50) < total capacity (10 × 40 = 400)."""
    drip_id, user_id, acc_ids = await _setup_drip(num_contacts=50, num_accounts=10, daily_limit=40)
    try:
        with patch.object(server, "send_drip_email", new=_fake_smtp_send):
            campaign = await server.db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
            await server.process_drip_campaign(campaign)
        after = await server.db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
        used = after["last_run_stats"]["accounts_used"]
        # ALL 10 accounts must have participated (no idle account when capacity is healthy)
        assert len(used) == 10, f"Only {len(used)} of 10 accounts used: {used}"
        # Spread should be roughly even (50 sends / 10 accounts = 5 each, ±1)
        for aid, count in used.items():
            assert 3 <= count <= 7, f"Skewed distribution: {aid}={count}"
    finally:
        await _cleanup(drip_id, user_id, acc_ids)


@pytest.mark.asyncio
async def test_stops_with_daily_capacity_reason_when_all_accounts_saturated():
    """3 accounts × 10/day = 30 capacity, but 100 contacts. Worker should
    send 30, then break with stop_reason=daily_capacity_reached."""
    drip_id, user_id, acc_ids = await _setup_drip(num_contacts=100, num_accounts=3, daily_limit=10)
    try:
        with patch.object(server, "send_drip_email", new=_fake_smtp_send):
            campaign = await server.db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
            await server.process_drip_campaign(campaign)
        after = await server.db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
        stats = after["last_run_stats"]
        assert stats["sent_contacts"] == 30
        assert stats["stop_reason"] == "daily_capacity_reached"
        # All 3 accounts should be at limit
        accs = await server.db.email_accounts.find(
            {"account_id": {"$in": acc_ids}}, {"_id": 0, "daily_send_count": 1, "daily_limit": 1}
        ).to_list(10)
        for a in accs:
            assert a["daily_send_count"] >= a["daily_limit"]
    finally:
        await _cleanup(drip_id, user_id, acc_ids)


@pytest.mark.asyncio
async def test_no_eligible_contacts_records_correct_stop_reason():
    drip_id, user_id, acc_ids = await _setup_drip(num_contacts=0, num_accounts=2, daily_limit=10)
    try:
        with patch.object(server, "send_drip_email", new=_fake_smtp_send):
            campaign = await server.db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
            await server.process_drip_campaign(campaign)
        after = await server.db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
        stats = after["last_run_stats"]
        assert stats["sent_contacts"] == 0
        assert stats["stop_reason"] == "no_eligible_contacts"
    finally:
        await _cleanup(drip_id, user_id, acc_ids)


@pytest.mark.asyncio
async def test_stale_account_counters_are_reset_at_top_of_tick():
    """Account with `last_reset_date` = yesterday and `daily_send_count` = 50
    must be reset to 0 before the per-tick rotation reads it (otherwise the
    fair-rotation would skip it as 'saturated')."""
    drip_id, user_id, acc_ids = await _setup_drip(num_contacts=5, num_accounts=1, daily_limit=10)
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    await server.db.email_accounts.update_many(
        {"account_id": {"$in": acc_ids}},
        {"$set": {"last_reset_date": yesterday, "daily_send_count": 999}},
    )
    try:
        with patch.object(server, "send_drip_email", new=_fake_smtp_send):
            campaign = await server.db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
            await server.process_drip_campaign(campaign)
        after = await server.db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
        assert after["last_run_stats"]["sent_contacts"] == 5
        accs = await server.db.email_accounts.find(
            {"account_id": {"$in": acc_ids}}, {"_id": 0, "daily_send_count": 1}
        ).to_list(10)
        for a in accs:
            assert a["daily_send_count"] == 5  # 5 sends after reset (not 999+5)
    finally:
        await _cleanup(drip_id, user_id, acc_ids)
