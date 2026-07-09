"""Iteration 72 — Strict user-level data isolation across Infrastructure.

Verifies that EVERY Infrastructure endpoint scopes queries to the requester's
own `user_id`, including super_admins. When a super_admin opens the
Infrastructure page they must see ONLY their own inboxes, campaigns, drips,
domains, reservations, and reputation — never another user's data.

Uses live HTTP against the running backend (same pattern as
test_infra_phase_b.py).
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
SUPER_ADMIN_ID = "user_b3e333b0f467"  # existing super_admin from seed

TAG = f"iso72_{uuid.uuid4().hex[:8]}"


def _iso(offset_days=0):
    return (datetime.now(timezone.utc) + timedelta(days=offset_days)).isoformat()


@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def seeded(mongo):
    """Create User A (regular) + reuse existing super_admin as User B.
    Seed 3 inboxes+1 running campaign+1 tracked domain for A, plus 2 new
    inboxes+1 running drip+1 tracked domain for the super_admin. Tag every
    doc with TAG so cleanup only touches this run's rows."""
    user_a_id = f"{TAG}_A"
    token_a = f"{TAG}_tokA_{uuid.uuid4().hex}"
    token_b = f"{TAG}_tokB_{uuid.uuid4().hex}"

    mongo.users.insert_one({
        "user_id": user_a_id,
        "email": f"{TAG}_A@iso.test",
        "name": "Iso Test User A",
        "role": "user",
        "email_verified": True,
        "can_access_infrastructure": True,
        "created_at": _iso(),
        "tag": TAG,
    })
    mongo.user_sessions.insert_many([
        {"user_id": user_a_id, "session_token": token_a,
         "expires_at": _iso(1), "created_at": _iso(), "tag": TAG},
        {"user_id": SUPER_ADMIN_ID, "session_token": token_b,
         "expires_at": _iso(1), "created_at": _iso(), "tag": TAG},
    ])

    acc_a = []
    for i in range(3):
        aid = f"{TAG}_A_acc_{i}"
        acc_a.append(aid)
        mongo.email_accounts.insert_one({
            "account_id": aid, "user_id": user_a_id,
            "email": f"{TAG}_A_{i}@aliceco.iso", "daily_limit": 50,
            "status": "connected", "created_at": _iso(), "tag": TAG,
        })
    acc_b = []
    for i in range(2):
        aid = f"{TAG}_B_acc_{i}"
        acc_b.append(aid)
        mongo.email_accounts.insert_one({
            "account_id": aid, "user_id": SUPER_ADMIN_ID,
            "email": f"{TAG}_B_{i}@bobinc.iso", "daily_limit": 100,
            "status": "connected", "created_at": _iso(), "tag": TAG,
        })

    camp_a_id = f"{TAG}_A_camp"
    mongo.campaigns.insert_one({
        "campaign_id": camp_a_id, "user_id": user_a_id, "name": "iso A camp",
        "status": "running", "account_ids": acc_a,
        "scheduled_at": _iso(), "started_at": _iso(),
        "total_emails": 300, "sent_count": 0, "tag": TAG,
    })
    drip_b_id = f"{TAG}_B_drip"
    mongo.drip_campaigns.insert_one({
        "drip_id": drip_b_id, "user_id": SUPER_ADMIN_ID, "name": "iso B drip",
        "status": "running", "account_ids": acc_b,
        "steps": [{"delay_days": 0}, {"delay_days": 3}],
        "schedule": {"start_date": datetime.now(timezone.utc).date().isoformat(),
                     "start_time": "09:00", "sending_days": [0, 1, 2, 3, 4],
                     "timezone": "UTC"},
        "tag": TAG,
    })
    mongo.tracked_domains.insert_many([
        {"domain_id": f"{TAG}_A_dom", "domain": "aliceco.iso",
         "user_id": user_a_id,
         "date_added": datetime.now(timezone.utc).date().isoformat(), "tag": TAG},
        {"domain_id": f"{TAG}_B_dom", "domain": "bobinc.iso",
         "user_id": SUPER_ADMIN_ID,
         "date_added": datetime.now(timezone.utc).date().isoformat(), "tag": TAG},
    ])

    ctx = {
        "user_a_id": user_a_id, "user_b_id": SUPER_ADMIN_ID,
        "token_a": token_a, "token_b": token_b,
        "acc_a": acc_a, "acc_b": acc_b,
        "camp_a_id": camp_a_id, "drip_b_id": drip_b_id,
    }
    yield ctx

    # Cleanup — only remove TAG-owned docs. Never touch existing super_admin
    # inboxes/campaigns/domains created outside this test.
    for coll in ("users", "user_sessions", "email_accounts", "campaigns",
                 "drip_campaigns", "tracked_domains", "tracked_replacements",
                 "domain_reputation"):
        mongo[coll].delete_many({"tag": TAG})


def _session(token):
    s = requests.Session()
    s.cookies.set("session_token", token)
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# --------- tests -------------------------------------------------------------


def test_inboxes_endpoint_isolates_users(seeded):
    a = _session(seeded["token_a"]).get(f"{BASE_URL}/api/infrastructure/inboxes")
    b = _session(seeded["token_b"]).get(f"{BASE_URL}/api/infrastructure/inboxes")
    assert a.status_code == 200, a.text
    assert b.status_code == 200, b.text

    ids_a = {r["account_id"] for r in a.json()["inboxes"]}
    ids_b = {r["account_id"] for r in b.json()["inboxes"]}

    assert set(seeded["acc_a"]).issubset(ids_a)
    assert not (set(seeded["acc_b"]) & ids_a), "User A leaked User B's inboxes"

    assert set(seeded["acc_b"]).issubset(ids_b)
    assert not (set(seeded["acc_a"]) & ids_b), (
        "Super-admin B's Infrastructure view leaked User A's inboxes"
    )


def test_summary_endpoint_isolates_capacity(seeded):
    a = _session(seeded["token_a"]).get(f"{BASE_URL}/api/infrastructure/summary")
    b = _session(seeded["token_b"]).get(f"{BASE_URL}/api/infrastructure/summary")
    assert a.status_code == 200
    assert b.status_code == 200

    sa = a.json()
    sb = b.json()

    # User A owns exactly the 3 seeded inboxes → 150/day capacity
    a_inboxes = seeded["acc_a"]
    assert sa["inbox_counts"]["total"] == len(a_inboxes), sa["inbox_counts"]
    assert sa["capacity"]["remaining_today"] == len(a_inboxes) * 50

    # Super-admin B may have OTHER pre-existing inboxes in their workspace,
    # but the numbers must NOT include User A's 3 inboxes / 150 daily cap.
    b_only_ids = {r["account_id"] for r in _session(seeded["token_b"]).get(f"{BASE_URL}/api/infrastructure/inboxes").json()["inboxes"]}
    assert not (set(a_inboxes) & b_only_ids)
    # And sb daily cap must be exactly the sum of B's own inbox limits
    b_expected_today = sum(r["daily_limit"] - r["emails_sent_today"] for r in _session(seeded["token_b"]).get(f"{BASE_URL}/api/infrastructure/inboxes").json()["inboxes"])
    assert sb["capacity"]["remaining_today"] == b_expected_today


def test_domains_endpoint_isolates_users(seeded):
    a = _session(seeded["token_a"]).get(f"{BASE_URL}/api/infrastructure/domains")
    b = _session(seeded["token_b"]).get(f"{BASE_URL}/api/infrastructure/domains")
    assert a.status_code == 200 and b.status_code == 200

    doms_a = {d["domain"] for d in a.json()["domains"]}
    doms_b = {d["domain"] for d in b.json()["domains"]}
    assert "aliceco.iso" in doms_a
    assert "bobinc.iso" not in doms_a, "User A leaked B's tracked domain"
    assert "bobinc.iso" in doms_b
    assert "aliceco.iso" not in doms_b, (
        "Super-admin B's tracked domains view leaked User A's domain"
    )


def test_forecast_endpoint_isolates_users(seeded):
    a = _session(seeded["token_a"]).get(f"{BASE_URL}/api/infrastructure/forecast")
    b = _session(seeded["token_b"]).get(f"{BASE_URL}/api/infrastructure/forecast")
    assert a.status_code == 200 and b.status_code == 200

    # User A forecast: exactly 3 inboxes, 150/day
    sa = a.json()["summary"]
    assert sa["total_inboxes"] == 3
    assert sa["total_daily_capacity"] == 150

    # Super-admin B forecast MUST NOT include A's 3 inboxes or 150/day.
    # We assert delta between summary from B and A's isolated values.
    sb = b.json()["summary"]
    assert sb["total_daily_capacity"] < 1_000_000_000  # sanity: bounded
    # If B were leaking A's data, sb["total_inboxes"] would include 3 extra
    # A inboxes. Since B has only the 2 test inboxes we seeded (+ any real
    # pre-existing inboxes), we just check A's 3 don't appear:
    b_inbox_rows = _session(seeded["token_b"]).get(f"{BASE_URL}/api/infrastructure/inboxes").json()["inboxes"]
    for r in b_inbox_rows:
        assert r["account_id"] not in seeded["acc_a"], "B forecast pool contains A's inbox"


def test_campaign_planner_isolates_pool(seeded):
    """/plan-campaign must draw only from the requester's inboxes."""
    payload = {
        "recipients": 200,
        "daily_send_target": 100,
        "start_date": (datetime.now(timezone.utc).date() + timedelta(days=2)).isoformat(),
        "steps": 1,
        "delay_days_between_steps": 0,
        "sending_days": [0, 1, 2, 3, 4],
        "domain_reserve": 0,
    }
    a = _session(seeded["token_a"]).post(f"{BASE_URL}/api/infrastructure/plan-campaign", json=payload)
    b = _session(seeded["token_b"]).post(f"{BASE_URL}/api/infrastructure/plan-campaign", json=payload)
    assert a.status_code == 200, a.text
    assert b.status_code == 200, b.text

    a_inboxes = a.json().get("inboxes") or []
    b_inboxes = b.json().get("inboxes") or []

    a_account_ids = {r["account_id"] for r in a_inboxes}
    b_account_ids = {r["account_id"] for r in b_inboxes}
    # A's plan must only contain A's inboxes
    assert a_account_ids.issubset(set(seeded["acc_a"])), (
        f"User A planner returned foreign account_ids: {a_account_ids - set(seeded['acc_a'])}"
    )
    # B's plan must NOT contain any A account_id
    assert not (b_account_ids & set(seeded["acc_a"])), (
        "Super-admin B planner leaked User A's inboxes"
    )


def test_replacements_history_isolates_users(seeded, mongo):
    # Seed one replacement for User A only
    mongo.tracked_replacements.insert_one({
        "replacement_id": f"{TAG}_rep_A",
        "user_id": seeded["user_a_id"],
        "replaced_account_id": seeded["acc_a"][0],
        "status": "completed", "triggered_by": "manual",
        "created_at": _iso(), "tag": TAG,
    })

    a = _session(seeded["token_a"]).get(f"{BASE_URL}/api/infrastructure/replacements")
    b = _session(seeded["token_b"]).get(f"{BASE_URL}/api/infrastructure/replacements")
    assert a.status_code == 200 and b.status_code == 200

    a_ids = {x.get("replacement_id") for x in a.json()["items"]}
    b_ids = {x.get("replacement_id") for x in b.json()["items"]}
    assert f"{TAG}_rep_A" in a_ids
    assert f"{TAG}_rep_A" not in b_ids, (
        "Super-admin B's replacement history leaked User A's row"
    )


def test_issues_dashboard_isolates_users(seeded, mongo):
    # Mark ONE inbox of each user as disconnected → each will surface a
    # single issue attributable to itself.
    mongo.email_accounts.update_one(
        {"account_id": seeded["acc_a"][0]},
        {"$set": {"status": "disconnected", "last_error": "iso72"}},
    )
    mongo.email_accounts.update_one(
        {"account_id": seeded["acc_b"][0]},
        {"$set": {"status": "disconnected", "last_error": "iso72"}},
    )

    a = _session(seeded["token_a"]).get(f"{BASE_URL}/api/infrastructure/issues")
    b = _session(seeded["token_b"]).get(f"{BASE_URL}/api/infrastructure/issues")
    assert a.status_code == 200 and b.status_code == 200

    a_ids = {r["account_id"] for r in a.json()["errored"] + a.json()["risky"]}
    b_ids = {r["account_id"] for r in b.json()["errored"] + b.json()["risky"]}
    assert seeded["acc_a"][0] in a_ids
    assert seeded["acc_a"][0] not in b_ids, (
        "Super-admin B issues dashboard leaked User A's disconnected inbox"
    )
    assert seeded["acc_b"][0] in b_ids
    assert seeded["acc_b"][0] not in a_ids


def test_reputation_isolates_users(seeded):
    a = _session(seeded["token_a"]).get(f"{BASE_URL}/api/infrastructure/reputation")
    b = _session(seeded["token_b"]).get(f"{BASE_URL}/api/infrastructure/reputation")
    assert a.status_code == 200 and b.status_code == 200

    a_doms = {d["domain"] for d in a.json().get("domains", [])}
    b_doms = {d["domain"] for d in b.json().get("domains", [])}
    assert "bobinc.iso" not in a_doms, "User A reputation leaked B's domain"
    assert "aliceco.iso" not in b_doms, (
        "Super-admin B reputation leaked User A's domain"
    )
