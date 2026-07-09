"""Iteration 73 — Email account priority + multi-drip concurrency guardrails.

These tests protect the two behaviours the user explicitly asked us to
verify:

* **Priority**: when the same inbox is shared by multiple campaigns,
  the *older* campaign consumes today's remaining capacity first, and any
  unsent contacts on the newer campaign continue automatically after the
  daily reset (no permanent blocking).
* **Multiple drips**: concurrent drip campaigns are processed inside the
  same worker tick — one drip never blocks another when they use
  different inboxes.

We invoke ``process_drip_campaigns`` directly against a real Mongo
instance (via motor) with SMTP mocked out so no email actually leaves the
box. This gives us a fully deterministic end-to-end test without
depending on the running uvicorn instance.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

TAG = f"pri73_{uuid.uuid4().hex[:8]}"


# One event loop shared by every test in this module — motor's async
# collection handles bind themselves to whatever loop they were first
# created on, so recreating a loop per test raises "Event loop is closed".
_LOOP = asyncio.new_event_loop()


def _run(coro):
    return _LOOP.run_until_complete(coro)


@pytest.fixture(scope="module", autouse=True)
def _close_loop_at_end():
    yield
    _LOOP.close()


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(os.environ["MONGO_URL"])
    yield c[os.environ["DB_NAME"]]
    c.close()


def _iso(dt=None):
    dt = dt if dt is not None else datetime.now(timezone.utc)
    return dt.isoformat()


@pytest.fixture()
def seed(mongo):
    """Two drip campaigns sharing ONE inbox. Older one has 20 pending
    contacts, newer one has 20. Inbox daily_limit = 10 (so older should
    fully consume today's cap and newer should send 0 in the first tick).
    Plus a THIRD drip using a DIFFERENT inbox — should send normally even
    though the shared inbox is exhausted (concurrency check)."""
    user_id = f"{TAG}_user"
    mongo.users.insert_one({
        "user_id": user_id, "email": f"{TAG}@t.test", "name": "P",
        "email_verified": True, "created_at": _iso(), "tag": TAG,
    })

    shared_inbox_id = f"{TAG}_shared"
    dedicated_inbox_id = f"{TAG}_dedicated"

    # Sending window covers "now" — pick the current UTC hour ± 1 to guarantee
    # the drip worker doesn't drop everything because the window is closed.
    now_utc = datetime.now(timezone.utc)

    # A daily_limit of 10 for the shared inbox → older drip should fully
    # drain it. Dedicated inbox has 50/day → third drip sends freely.
    mongo.email_accounts.insert_many([
        {"account_id": shared_inbox_id, "user_id": user_id,
         "email": f"shared_{TAG}@t.test", "daily_limit": 10, "send_delay": 0,
         "daily_send_count": 0, "last_reset_date": now_utc.date().isoformat(),
         "smtp_host": "smtp.test", "smtp_port": 587, "smtp_username": "u",
         "smtp_password": "p", "smtp_encryption": "tls",
         "status": "connected", "created_at": _iso(), "tag": TAG},
        {"account_id": dedicated_inbox_id, "user_id": user_id,
         "email": f"dedicated_{TAG}@t.test", "daily_limit": 50, "send_delay": 0,
         "daily_send_count": 0, "last_reset_date": now_utc.date().isoformat(),
         "smtp_host": "smtp.test", "smtp_port": 587, "smtp_username": "u",
         "smtp_password": "p", "smtp_encryption": "tls",
         "status": "connected", "created_at": _iso(), "tag": TAG},
    ])

    schedule = {
        "start_date": now_utc.date().isoformat(),
        "start_time": "00:00", "end_time": "23:59",
        "sending_days": [0, 1, 2, 3, 4, 5, 6],
        "timezone": "UTC", "randomize_time": False,
    }

    # Drip A — OLDER, uses shared inbox
    drip_a = f"{TAG}_dripA"
    mongo.drip_campaigns.insert_one({
        "drip_id": drip_a, "user_id": user_id, "name": "OLDER shared",
        "status": "running", "account_ids": [shared_inbox_id],
        "steps": [{"subject": "Hi {{name}}", "body": "Body", "delay_days": 0}],
        "schedule": schedule,
        "total_contacts": 20, "total_sent": 0,
        "created_at": (now_utc - timedelta(hours=48)).isoformat(), "tag": TAG,
    })

    # Drip B — NEWER, uses shared inbox
    drip_b = f"{TAG}_dripB"
    mongo.drip_campaigns.insert_one({
        "drip_id": drip_b, "user_id": user_id, "name": "NEWER shared",
        "status": "running", "account_ids": [shared_inbox_id],
        "steps": [{"subject": "Yo {{name}}", "body": "Body", "delay_days": 0}],
        "schedule": schedule,
        "total_contacts": 20, "total_sent": 0,
        "created_at": (now_utc - timedelta(hours=24)).isoformat(), "tag": TAG,
    })

    # Drip C — DIFFERENT inbox — should send in parallel to A within the same tick
    drip_c = f"{TAG}_dripC"
    mongo.drip_campaigns.insert_one({
        "drip_id": drip_c, "user_id": user_id, "name": "Parallel dedicated",
        "status": "running", "account_ids": [dedicated_inbox_id],
        "steps": [{"subject": "Hey {{name}}", "body": "Body", "delay_days": 0}],
        "schedule": schedule,
        "total_contacts": 20, "total_sent": 0,
        "created_at": (now_utc - timedelta(hours=12)).isoformat(), "tag": TAG,
    })

    # Seed contacts (all eligible immediately)
    def _mk_contacts(drip_id, n, prefix):
        return [{
            "contact_id": f"{drip_id}_c_{i}",
            "drip_id": drip_id, "user_id": user_id,
            "email": f"{prefix}{i}@t.test", "name": f"P{i}",
            "status": "active", "current_step": 0,
            "next_send_at": (now_utc - timedelta(minutes=5)).isoformat(),
            "created_at": _iso(), "tag": TAG,
        } for i in range(n)]

    mongo.drip_contacts.insert_many(
        _mk_contacts(drip_a, 20, "a")
        + _mk_contacts(drip_b, 20, "b")
        + _mk_contacts(drip_c, 20, "c")
    )

    ctx = {"user_id": user_id, "shared_inbox_id": shared_inbox_id,
           "dedicated_inbox_id": dedicated_inbox_id,
           "drip_a": drip_a, "drip_b": drip_b, "drip_c": drip_c}
    yield ctx

    # cleanup — hardened so no other cross-user data can be touched
    for coll in ("users", "email_accounts", "drip_campaigns",
                 "drip_contacts", "drip_logs", "sent_emails"):
        mongo[coll].delete_many({"tag": TAG})
    mongo.drip_logs.delete_many({"drip_id": {"$in": [ctx["drip_a"], ctx["drip_b"], ctx["drip_c"]]}})
    mongo.sent_emails.delete_many({"drip_campaign_id": {"$in": [ctx["drip_a"], ctx["drip_b"], ctx["drip_c"]]}})


# ────────────────────────────────────────────────────────────────────────

async def _fake_send_ok(*args, **kwargs):
    """Stand-in for send_drip_email so we don't hit SMTP."""
    return {"success": True, "message_id": f"<msg_{uuid.uuid4().hex}@t.test>"}


def test_older_campaign_gets_shared_inbox_priority(seed):
    """After one tick, the OLDER drip must fully consume the shared inbox's
    daily cap (10 sends), the NEWER drip must send 0, and the drip on a
    DIFFERENT inbox must send normally in the same tick (concurrency)."""
    import server  # imported lazily so load_dotenv has run

    async def _tick():
        with patch("server.send_drip_email", new=_fake_send_ok):
            await server.process_drip_campaigns()

    _run(_tick())

    # Read back state from Mongo (sync client)
    from pymongo import MongoClient
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    a_sent = db.drip_logs.count_documents({"drip_id": seed["drip_a"], "status": "sent"})
    b_sent = db.drip_logs.count_documents({"drip_id": seed["drip_b"], "status": "sent"})
    c_sent = db.drip_logs.count_documents({"drip_id": seed["drip_c"], "status": "sent"})

    assert a_sent == 10, (
        f"Older drip should have consumed the shared inbox's 10-cap fully, got {a_sent}"
    )
    assert b_sent == 0, (
        f"Newer drip should have sent 0 on the shared inbox (older has priority), got {b_sent}"
    )
    assert c_sent > 0, (
        f"Third drip on a dedicated inbox should have run in parallel, got {c_sent}"
    )

    # Shared inbox's daily_send_count reflects only 10 sends, not 11+
    shared = db.email_accounts.find_one({"account_id": seed["shared_inbox_id"]})
    assert shared["daily_send_count"] == 10, shared


def test_newer_campaign_resumes_after_daily_reset(seed):
    """Simulate tomorrow: after resetting the shared inbox's daily counter
    the NEWER drip must be able to send. This proves no drip is
    *permanently* blocked by the priority rule."""
    import server

    async def _tick():
        with patch("server.send_drip_email", new=_fake_send_ok):
            await server.process_drip_campaigns()

    _run(_tick())

    # Reset the shared inbox's daily counter (simulating next-day rollover)
    from pymongo import MongoClient
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
    db.email_accounts.update_one(
        {"account_id": seed["shared_inbox_id"]},
        {"$set": {"daily_send_count": 0, "last_reset_date": tomorrow}},
    )

    # Mark all A contacts as completed so only B contacts remain eligible
    db.drip_contacts.update_many(
        {"drip_id": seed["drip_a"]},
        {"$set": {"status": "completed"}},
    )

    # Tick 2
    _run(_tick())

    b_sent = db.drip_logs.count_documents({"drip_id": seed["drip_b"], "status": "sent"})
    assert b_sent > 0, (
        f"Newer drip should have resumed after the shared inbox's daily reset, got {b_sent}"
    )


def test_multiple_drips_process_in_same_tick(seed):
    """All three running drips must all be touched inside one tick — proving
    the `for drip in drip_campaigns:` loop is not broken by an earlier
    campaign's completion or capacity-exhaustion."""
    import server

    async def _tick():
        with patch("server.send_drip_email", new=_fake_send_ok):
            await server.process_drip_campaigns()

    _run(_tick())

    from pymongo import MongoClient
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    # Every drip should have last_run_stats populated
    for drip_id in (seed["drip_a"], seed["drip_b"], seed["drip_c"]):
        d = db.drip_campaigns.find_one({"drip_id": drip_id}, {"last_run_stats": 1})
        assert d and d.get("last_run_stats"), (
            f"Drip {drip_id} was NOT processed in the tick — multi-drip concurrency broken"
        )
