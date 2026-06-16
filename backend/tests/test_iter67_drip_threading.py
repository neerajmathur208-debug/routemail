"""Iteration 67 — Drip subject variables, empty-subject threading,
test-email preview, and variable cleanup audit.
"""
import asyncio
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
from template_render import render_template  # noqa: E402


# Shared event loop so Motor's connection pool survives across tests.
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─────────────────────────── PURE RENDERER ────────────────────────────────

def test_renderer_strips_unresolved_brackets():
    """Unresolved {{vars}} / {} / {{}} must NEVER reach the recipient."""
    out = render_template("Hi {{first_name}}, your code is {{secret_token}}", {"first_name": "John"})
    assert out == "Hi John, your code is "
    # No stray braces of any kind
    for forbidden in ("{{", "}}", "{first_name}", "[John]", "(John)", "{John}"):
        assert forbidden not in out


def test_renderer_no_double_brace_around_value():
    """If the variable resolves, the OUTPUT must be the bare value with no
    decorating brackets — `{{first_name}}` => `John`, never `{{John}}`."""
    out = render_template("Hi {{first_name}},", {"first_name": "John"})
    assert out == "Hi John,"
    assert "{{John}}" not in out
    assert "{John}" not in out


def test_renderer_supports_legacy_single_brace():
    out = render_template("Hi {first_name},", {"first_name": "John"})
    assert out == "Hi John,"


# ─────────────────────── PREVIEW ENDPOINT (HTTP) ──────────────────────────

BASE = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL"):
            BASE = line.split("=", 1)[1].strip().rstrip("/")


@pytest.fixture(scope="module")
def session():
    """Create a stand-alone test user + session token. Cleaned up after."""
    from pymongo import MongoClient
    import os
    db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    user_id = f"user_iter67_{uuid.uuid4().hex[:6]}"
    db.users.insert_one({
        "user_id": user_id,
        "email": f"{user_id}@example.com",
        "name": "iter67",
        "email_verified": True,
    })
    token = f"TEST_iter67_{uuid.uuid4().hex}"
    db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=2),
    })
    yield {"session_token": token, "user_id": user_id}
    db.user_sessions.delete_one({"session_token": token})
    db.users.delete_one({"user_id": user_id})


def test_preview_renders_subject_variables_via_http(session):
    r = requests.post(
        f"{BASE}/api/campaigns/test-email/preview",
        cookies={"session_token": session["session_token"]},
        json={
            "subject": "Quick question, {{first_name}}",
            "body": "Hi {{first_name}}, working at {{company}}?",
            "recipient_data": {"first_name": "John", "company": "Acme"},
        },
    )
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["rendered_subject"] == "Quick question, John"
    assert out["rendered_body"] == "Hi John, working at Acme?"
    assert out["is_threaded_reply"] is False
    assert out["unresolved_variables"] == []


def test_preview_unresolved_variables_are_listed(session):
    r = requests.post(
        f"{BASE}/api/campaigns/test-email/preview",
        cookies={"session_token": session["session_token"]},
        json={
            "subject": "Hi {{first_name}}",
            "body": "Working at {{company}}? Re: {{topic}}",
            "recipient_data": {"first_name": "John"},  # company + topic missing
        },
    )
    assert r.status_code == 200
    out = r.json()
    assert out["rendered_subject"] == "Hi John"
    # Missing variables disappear entirely, NO leftover brackets
    for forbidden in ("{{", "}}", "{company}", "[company]"):
        assert forbidden not in out["rendered_body"]
    assert sorted(out["unresolved_variables"]) == ["company", "topic"]


def test_preview_empty_subject_uses_prior_with_re_prefix(session):
    r = requests.post(
        f"{BASE}/api/campaigns/test-email/preview",
        cookies={"session_token": session["session_token"]},
        json={
            "subject": "",
            "body": "Just bumping this for {{first_name}}.",
            "prior_subject": "Quick question, {{first_name}}",
            "recipient_data": {"first_name": "John"},
        },
    )
    assert r.status_code == 200
    out = r.json()
    assert out["rendered_subject"] == "Re: Quick question, John"
    assert out["is_threaded_reply"] is True


def test_preview_does_not_double_re_prefix(session):
    """If the user's first step already starts with 'Re:', don't add another."""
    r = requests.post(
        f"{BASE}/api/campaigns/test-email/preview",
        cookies={"session_token": session["session_token"]},
        json={
            "subject": "",
            "body": "x",
            "prior_subject": "Re: Follow up",
        },
    )
    assert r.status_code == 200
    assert r.json()["rendered_subject"] == "Re: Follow up"


def test_send_test_email_rejects_empty_subject_without_prior(session):
    """Empty subject without prior_subject => 400 (cannot magic a subject)."""
    r = requests.post(
        f"{BASE}/api/campaigns/send-test",
        cookies={"session_token": session["session_token"]},
        json={
            "test_email": "anything@example.com",
            "subject": "",
            "body": "hi",
        },
    )
    assert r.status_code == 400
    assert "subject" in r.text.lower()


# ───────────────────── DRIP WORKER — threading ────────────────────────────

@pytest.fixture
def stub_smtp():
    """Replace SMTP send with a stub that records call args."""
    sent_calls = []

    def fake_send(account, recipient, subject, body, from_name_override=None, in_reply_to=None, references=None):
        async def _inner():
            mid = f"<{uuid.uuid4().hex}@stub>"
            sent_calls.append({
                "recipient": recipient,
                "subject": subject,
                "in_reply_to": in_reply_to,
                "references": references or [],
                "message_id": mid,
            })
            return {"success": True, "message_id": mid}
        return _inner()

    with patch.object(server, "send_drip_email", new=fake_send):
        yield sent_calls


def _yesterday():
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


async def _seed_drip(num_steps=2, user_id=None, recipient="thread@example.com", contact_data=None):
    """Insert a drip campaign + one contact ready to be sent right now."""
    db = server.db
    user_id = user_id or f"user_iter67_{uuid.uuid4().hex[:6]}"
    drip_id = f"drip_iter67_{uuid.uuid4().hex[:6]}"
    acc_id = f"acc_iter67_{uuid.uuid4().hex[:6]}"
    now = datetime.now(timezone.utc)
    await db.email_accounts.insert_one({
        "account_id": acc_id, "user_id": user_id, "email": f"{acc_id}@example.com",
        "status": "connected", "daily_limit": 100, "daily_send_count": 0,
        "last_reset_date": now.strftime("%Y-%m-%d"), "send_delay": 0,
        "smtp_host": "x", "smtp_port": 587, "smtp_username": "x",
        "smtp_password_encrypted": "x", "smtp_use_ssl": False,
    })
    steps = [{"subject": "Quick question, {{first_name}}", "body": "Hi {{first_name}}", "delay_days": 0}]
    for i in range(1, num_steps):
        steps.append({"subject": "", "body": f"Follow-up {i} body", "delay_days": 0})
    await db.drip_campaigns.insert_one({
        "drip_id": drip_id, "user_id": user_id, "name": "iter67",
        "status": "running", "steps": steps, "account_ids": [acc_id],
        "schedule": {"timezone": "UTC", "sending_days": list(range(7)),
                     "start_time": "00:00", "end_time": "23:59", "randomize_time": False},
        "stop_on_reply": False, "stop_on_bounce": False,
    })
    await db.drip_contacts.insert_one({
        "contact_id": f"dc_{uuid.uuid4().hex[:10]}",
        "drip_id": drip_id, "user_id": user_id,
        "email": recipient, "status": "active",
        "current_step": 0, "next_send_at": (now - timedelta(minutes=1)).isoformat(),
        "replied": False, "bounced": False,
        "data": contact_data or {"first_name": "John"},
    })
    return drip_id, user_id, acc_id


async def _force_step(drip_id, step_num, set_next_send_at_to_past=True):
    """Move the contact onto a specific step ready to be sent right now."""
    update = {"$set": {"current_step": step_num}}
    if set_next_send_at_to_past:
        update["$set"]["next_send_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    await server.db.drip_contacts.update_one({"drip_id": drip_id}, update)


async def _cleanup(drip_id, user_id, acc_id):
    db = server.db
    await db.drip_campaigns.delete_many({"drip_id": drip_id})
    await db.drip_contacts.delete_many({"drip_id": drip_id})
    await db.drip_logs.delete_many({"drip_id": drip_id})
    await db.email_accounts.delete_many({"account_id": acc_id})
    await db.sent_emails.delete_many({"drip_campaign_id": drip_id})


@pytest.mark.asyncio
async def test_drip_step1_subject_renders_variables(stub_smtp):
    drip_id, user_id, acc_id = await _seed_drip(num_steps=2)
    try:
        campaign = await server.db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
        await server.process_drip_campaign(campaign)
        # Step 1 send should have a rendered subject with John in it
        assert stub_smtp, "no SMTP send recorded"
        c = stub_smtp[-1]
        assert c["subject"] == "Quick question, John"
        # Step 1 must NOT carry threading headers
        assert c["in_reply_to"] is None
        assert not c["references"]
    finally:
        await _cleanup(drip_id, user_id, acc_id)


@pytest.mark.asyncio
async def test_drip_step2_empty_subject_threads_with_re_prefix(stub_smtp):
    drip_id, user_id, acc_id = await _seed_drip(num_steps=2)
    try:
        # Tick 1 — send step 1
        campaign = await server.db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
        await server.process_drip_campaign(campaign)
        step1 = stub_smtp[-1]
        assert step1["subject"] == "Quick question, John"
        # Move contact onto step 2 and reset its next_send_at
        await _force_step(drip_id, step_num=1)
        # Tick 2 — send step 2 (empty subject)
        await server.process_drip_campaign(campaign)
        step2 = stub_smtp[-1]
        # Auto-threaded: "Re: Quick question, John"
        assert step2["subject"] == "Re: Quick question, John"
        assert step2["in_reply_to"] == step1["message_id"]
        assert step2["references"] == [step1["message_id"]]
    finally:
        await _cleanup(drip_id, user_id, acc_id)


@pytest.mark.asyncio
async def test_drip_step3_empty_subject_chains_full_references(stub_smtp):
    drip_id, user_id, acc_id = await _seed_drip(num_steps=3)
    try:
        campaign = await server.db.drip_campaigns.find_one({"drip_id": drip_id}, {"_id": 0})
        # Step 1
        await server.process_drip_campaign(campaign)
        mid1 = stub_smtp[-1]["message_id"]
        # Step 2
        await _force_step(drip_id, step_num=1)
        await server.process_drip_campaign(campaign)
        step2 = stub_smtp[-1]
        mid2 = step2["message_id"]
        assert step2["subject"] == "Re: Quick question, John"
        # Step 3
        await _force_step(drip_id, step_num=2)
        await server.process_drip_campaign(campaign)
        step3 = stub_smtp[-1]
        assert step3["subject"] == "Re: Quick question, John"
        assert step3["in_reply_to"] == mid2  # newest prior
        assert step3["references"] == [mid1, mid2]  # full chain in order
    finally:
        await _cleanup(drip_id, user_id, acc_id)
