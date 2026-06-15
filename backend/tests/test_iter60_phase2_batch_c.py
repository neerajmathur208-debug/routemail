"""Iteration 60 — Phase 2 Batch C backend tests.

Covers:
 1. GET /api/sent-emails — list, pagination, body omitted.
 2. GET /api/sent-emails?q=… — case-insensitive search across recipient_email,
    subject, from_name, campaign_name, drip_campaign_name.
 3. GET /api/sent-emails — date_from / date_to / campaign_id / drip_id /
    account_id / folder_id filters; sort whitelist; limit clamp.
 4. GET /api/sent-emails/{sent_id} — returns full doc inc. body_html/body_text;
    404 on unknown id; 404 on cross-tenant doc.
 5. GET /api/sent-emails/by-recipient — latest match; case-insensitive
    recipient lookup; 404 on no match.
 6. GET /api/campaigns enriches folder_name / reply_count / lead_count.
 7. GET /api/drip-campaigns enriches the same.
"""
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

# ----------------------- Config -----------------------
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
SUPER_ADMIN_ID = "user_b3e333b0f467"
OTHER_USER_ID = "user_other_iter60"  # synthetic cross-tenant user

TAG = f"TEST_iter60_{uuid.uuid4().hex[:8]}"


def now_iso(offset_minutes=0):
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_minutes)).isoformat()


# ----------------------- Fixtures -----------------------
@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def admin_token(mongo):
    tok = f"TEST_iter60_{uuid.uuid4().hex}"
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


@pytest.fixture(scope="module")
def seeded(mongo):
    """Seed a few sent_emails docs, folders, campaigns, drip campaigns,
    replies, leads — used for filter + enrichment tests."""
    folder_id = f"foldr_{uuid.uuid4().hex[:10]}"
    campaign_id = f"camp_{uuid.uuid4().hex[:10]}"
    drip_id = f"drip_{uuid.uuid4().hex[:10]}"
    account_id = f"acct_{uuid.uuid4().hex[:10]}"

    mongo.lead_folders.insert_one({
        "_tag": TAG,
        "folder_id": folder_id,
        "user_id": SUPER_ADMIN_ID,
        "name": "TEST_iter60_BrandFolder",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    mongo.campaigns.insert_one({
        "_tag": TAG,
        "campaign_id": campaign_id,
        "user_id": SUPER_ADMIN_ID,
        "name": "TEST_iter60_Camp1",
        "folder_id": folder_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    mongo.drip_campaigns.insert_one({
        "_tag": TAG,
        "drip_id": drip_id,
        "user_id": SUPER_ADMIN_ID,
        "name": "TEST_iter60_Drip1",
        "folder_id": folder_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    # Replies for reply_count enrichment
    for i in range(2):
        mongo.replies.insert_one({
            "_tag": TAG,
            "reply_id": f"rep_{uuid.uuid4().hex[:10]}",
            "user_id": SUPER_ADMIN_ID,
            "campaign_id": campaign_id,
            "received_at": now_iso(-i),
        })
    mongo.replies.insert_one({
        "_tag": TAG,
        "reply_id": f"rep_{uuid.uuid4().hex[:10]}",
        "user_id": SUPER_ADMIN_ID,
        "drip_campaign_id": drip_id,
        "received_at": now_iso(),
    })
    # Leads for lead_count enrichment
    for i in range(3):
        mongo.leads.insert_one({
            "_tag": TAG,
            "lead_id": f"lead_{uuid.uuid4().hex[:10]}",
            "user_id": SUPER_ADMIN_ID,
            "source_campaign_id": campaign_id,
            "email": f"lead{i}@example.com",
        })
    for i in range(2):
        mongo.leads.insert_one({
            "_tag": TAG,
            "lead_id": f"lead_{uuid.uuid4().hex[:10]}",
            "user_id": SUPER_ADMIN_ID,
            "source_drip_id": drip_id,
            "email": f"dlead{i}@example.com",
        })

    # Sent emails (5 docs spanning different fields + dates)
    base_t = datetime.now(timezone.utc)
    sent_docs = [
        {
            "sent_id": f"sent_iter60_a_{uuid.uuid4().hex[:6]}",
            "recipient_email": "alice@acme.com",
            "subject": "TEST_iter60 Welcome Alice",
            "from_name": "TEST_iter60 SalesTeam",
            "campaign_id": campaign_id,
            "campaign_name": "TEST_iter60_Camp1",
            "drip_campaign_id": None,
            "drip_campaign_name": None,
            "account_id": account_id,
            "folder_id": folder_id,
            "body_html": "<p>Hi Alice — welcome!</p>",
            "body_text": "Hi Alice — welcome!",
            "sent_at": (base_t - timedelta(days=5)).isoformat(),
        },
        {
            "sent_id": f"sent_iter60_b_{uuid.uuid4().hex[:6]}",
            "recipient_email": "bob@beta.io",
            "subject": "TEST_iter60 Quick check Bob",
            "from_name": "TEST_iter60 Outreach",
            "campaign_id": campaign_id,
            "campaign_name": "TEST_iter60_Camp1",
            "drip_campaign_id": None,
            "drip_campaign_name": None,
            "account_id": account_id,
            "folder_id": folder_id,
            "body_html": "<p>Bob, got a min?</p>",
            "body_text": "Bob, got a min?",
            "sent_at": (base_t - timedelta(days=3)).isoformat(),
        },
        {
            "sent_id": f"sent_iter60_c_{uuid.uuid4().hex[:6]}",
            "recipient_email": "carol@gamma.io",
            "subject": "TEST_iter60 Drip step 1",
            "from_name": "TEST_iter60 DripBot",
            "campaign_id": None,
            "campaign_name": None,
            "drip_campaign_id": drip_id,
            "drip_campaign_name": "TEST_iter60_Drip1",
            "drip_step_number": 1,
            "account_id": account_id,
            "folder_id": folder_id,
            "body_html": "<p>Carol drip msg</p>",
            "body_text": "Carol drip msg",
            "sent_at": (base_t - timedelta(days=1)).isoformat(),
        },
        {
            "sent_id": f"sent_iter60_d_{uuid.uuid4().hex[:6]}",
            "recipient_email": "dave@delta.com",
            "subject": "TEST_iter60 Misc",
            "from_name": "TEST_iter60 Other",
            "campaign_id": None,
            "drip_campaign_id": None,
            "account_id": account_id,
            "folder_id": None,
            "body_html": "<p>dave hello</p>",
            "body_text": "dave hello",
            "sent_at": base_t.isoformat(),
        },
    ]
    for d in sent_docs:
        d["_tag"] = TAG
        d["user_id"] = SUPER_ADMIN_ID
    mongo.sent_emails.insert_many(sent_docs)

    # Cross-tenant doc (different user_id) — should NEVER appear in queries
    cross_id = f"sent_iter60_cross_{uuid.uuid4().hex[:6]}"
    mongo.sent_emails.insert_one({
        "_tag": TAG,
        "sent_id": cross_id,
        "user_id": OTHER_USER_ID,
        "recipient_email": "leak@evil.com",
        "subject": "TEST_iter60 Cross tenant",
        "body_html": "<p>SECRET</p>",
        "body_text": "SECRET",
        "sent_at": base_t.isoformat(),
        "account_id": account_id,
        "campaign_id": campaign_id,
    })

    yield {
        "folder_id": folder_id,
        "campaign_id": campaign_id,
        "drip_id": drip_id,
        "account_id": account_id,
        "sent_docs": sent_docs,
        "cross_id": cross_id,
    }


@pytest.fixture(scope="module", autouse=True)
def cleanup(mongo):
    yield
    for coll in ("campaigns", "drip_campaigns", "lead_folders", "leads",
                 "sent_emails", "replies"):
        try:
            mongo[coll].delete_many({"_tag": TAG})
        except Exception:
            pass


# =================== 1. List + pagination + body omitted ===================
class TestSentEmailList:
    def test_list_returns_shape(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails", params={"q": "TEST_iter60"})
        assert r.status_code == 200, r.text
        body = r.json()
        for k in ("items", "total", "limit", "skip"):
            assert k in body
        assert body["total"] >= 4
        assert body["limit"] == 50
        assert body["skip"] == 0
        assert isinstance(body["items"], list)
        assert len(body["items"]) >= 4

    def test_list_omits_body(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails", params={"q": "TEST_iter60"})
        assert r.status_code == 200
        for item in r.json()["items"]:
            assert "body_html" not in item
            assert "body_text" not in item
            # other identifying fields should be present
            assert "sent_id" in item
            assert "recipient_email" in item
            assert "subject" in item

    def test_list_pagination(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails",
                       params={"q": "TEST_iter60", "limit": 2, "skip": 0})
        assert r.status_code == 200
        body = r.json()
        assert body["limit"] == 2
        assert body["skip"] == 0
        assert len(body["items"]) == 2
        first_ids = [i["sent_id"] for i in body["items"]]

        r2 = client.get(f"{BASE_URL}/api/sent-emails",
                        params={"q": "TEST_iter60", "limit": 2, "skip": 2})
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["skip"] == 2
        second_ids = [i["sent_id"] for i in body2["items"]]
        # Pages must not overlap
        assert set(first_ids).isdisjoint(set(second_ids))

    def test_list_cross_tenant_excluded(self, client, seeded):
        # Search by exact cross-tenant recipient — must return zero rows
        r = client.get(f"{BASE_URL}/api/sent-emails",
                       params={"q": "leak@evil.com"})
        assert r.status_code == 200
        ids = [i["sent_id"] for i in r.json()["items"]]
        assert seeded["cross_id"] not in ids


# =================== 2. Search across fields ===================
class TestSentEmailSearch:
    def test_search_recipient(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails", params={"q": "alice@ACME"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(i["recipient_email"] == "alice@acme.com" for i in items)

    def test_search_subject(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails", params={"q": "Welcome Alice"})
        assert r.status_code == 200
        assert any("Welcome Alice" in i.get("subject", "") for i in r.json()["items"])

    def test_search_from_name(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails", params={"q": "salesteam"})
        assert r.status_code == 200
        assert any((i.get("from_name") or "").lower() == "test_iter60 salesteam"
                   for i in r.json()["items"])

    def test_search_campaign_name(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails", params={"q": "TEST_iter60_Camp1"})
        assert r.status_code == 200
        assert any(i.get("campaign_name") == "TEST_iter60_Camp1"
                   for i in r.json()["items"])

    def test_search_drip_name(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails", params={"q": "TEST_iter60_Drip1"})
        assert r.status_code == 200
        assert any(i.get("drip_campaign_name") == "TEST_iter60_Drip1"
                   for i in r.json()["items"])


# =================== 3. Filters + sort + limit clamp ===================
class TestSentEmailFilters:
    def test_filter_campaign_id(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails",
                       params={"campaign_id": seeded["campaign_id"]})
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 2
        for i in items:
            assert i.get("campaign_id") == seeded["campaign_id"]

    def test_filter_drip_id(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails",
                       params={"drip_id": seeded["drip_id"]})
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        for i in items:
            assert i.get("drip_campaign_id") == seeded["drip_id"]

    def test_filter_account_id(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails",
                       params={"account_id": seeded["account_id"], "limit": 500})
        assert r.status_code == 200
        items = r.json()["items"]
        # All 4 owner-tenant docs use this account_id
        owner_ids = {d["sent_id"] for d in seeded["sent_docs"]}
        returned_ids = {i["sent_id"] for i in items}
        assert owner_ids.issubset(returned_ids)

    def test_filter_folder_id(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails",
                       params={"folder_id": seeded["folder_id"]})
        assert r.status_code == 200
        for i in r.json()["items"]:
            assert i.get("folder_id") == seeded["folder_id"]

    def test_filter_date_range(self, client, seeded):
        # Only docs from 2 days ago onwards (catches c + d, not a + b)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        r = client.get(f"{BASE_URL}/api/sent-emails",
                       params={"q": "TEST_iter60", "date_from": cutoff})
        assert r.status_code == 200
        items = r.json()["items"]
        for i in items:
            assert i["sent_at"] >= cutoff

    def test_sort_whitelist_fallback(self, client, seeded):
        # Invalid sort_by falls back to sent_at
        r = client.get(f"{BASE_URL}/api/sent-emails",
                       params={"q": "TEST_iter60", "sort_by": "drop_table", "sort_dir": "desc"})
        assert r.status_code == 200
        items = r.json()["items"]
        timestamps = [i["sent_at"] for i in items]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_sort_recipient_asc(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails",
                       params={"q": "TEST_iter60", "sort_by": "recipient_email", "sort_dir": "asc"})
        assert r.status_code == 200
        emails = [i["recipient_email"] for i in r.json()["items"]]
        assert emails == sorted(emails)

    def test_limit_clamped(self, client, seeded):
        # limit=600 exceeds ceiling 500 — FastAPI validation rejects with 422
        r = client.get(f"{BASE_URL}/api/sent-emails", params={"limit": 600})
        assert r.status_code == 422


# =================== 4. Single sent-email by id ===================
class TestSentEmailById:
    def test_get_returns_full_body(self, client, seeded):
        sent_id = seeded["sent_docs"][0]["sent_id"]
        r = client.get(f"{BASE_URL}/api/sent-emails/{sent_id}")
        assert r.status_code == 200
        doc = r.json()
        assert doc["sent_id"] == sent_id
        assert doc["body_html"] == "<p>Hi Alice — welcome!</p>"
        assert doc["body_text"] == "Hi Alice — welcome!"
        assert "_id" not in doc  # ObjectId excluded

    def test_get_unknown_id_returns_404(self, client):
        r = client.get(f"{BASE_URL}/api/sent-emails/sent_iter60_does_not_exist")
        assert r.status_code == 404

    def test_get_cross_tenant_returns_404(self, client, seeded):
        # cross_id exists in DB but belongs to OTHER_USER_ID
        r = client.get(f"{BASE_URL}/api/sent-emails/{seeded['cross_id']}")
        assert r.status_code == 404


# =================== 5. by-recipient ===================
class TestSentEmailByRecipient:
    def test_latest_by_recipient_campaign(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails/by-recipient",
                       params={"recipient_email": "alice@acme.com",
                               "campaign_id": seeded["campaign_id"]})
        assert r.status_code == 200
        doc = r.json()
        assert doc["recipient_email"] == "alice@acme.com"
        assert doc["campaign_id"] == seeded["campaign_id"]
        assert "body_html" in doc

    def test_recipient_case_insensitive(self, client, seeded):
        # Stored lowercased but caller sends mixed case
        r = client.get(f"{BASE_URL}/api/sent-emails/by-recipient",
                       params={"recipient_email": "ALICE@ACME.COM",
                               "campaign_id": seeded["campaign_id"]})
        assert r.status_code == 200
        assert r.json()["recipient_email"] == "alice@acme.com"

    def test_by_recipient_drip(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails/by-recipient",
                       params={"recipient_email": "carol@gamma.io",
                               "drip_id": seeded["drip_id"]})
        assert r.status_code == 200
        assert r.json()["drip_campaign_id"] == seeded["drip_id"]

    def test_by_recipient_no_match_404(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/sent-emails/by-recipient",
                       params={"recipient_email": "ghost@nowhere.io",
                               "campaign_id": seeded["campaign_id"]})
        assert r.status_code == 404


# =================== 6. Campaign list enrichment ===================
class TestCampaignEnrichment:
    def test_campaign_has_folder_name_reply_count_lead_count(self, client, seeded):
        r = client.get(f"{BASE_URL}/api/campaigns")
        assert r.status_code == 200
        all_camps = r.json()
        target = next((c for c in all_camps
                       if c.get("campaign_id") == seeded["campaign_id"]), None)
        assert target is not None, "Seeded campaign missing from list"
        assert target.get("folder_name") == "TEST_iter60_BrandFolder"
        assert target.get("reply_count") == 2
        assert target.get("lead_count") == 3


# =================== 7. Drip list enrichment ===================
class TestDripEnrichment:
    def test_drip_has_folder_name_reply_count_lead_count(self, client, seeded, mongo):
        r = client.get(f"{BASE_URL}/api/drip-campaigns")
        assert r.status_code == 200
        all_drips = r.json()
        target = next((c for c in all_drips
                       if c.get("drip_id") == seeded["drip_id"]), None)
        assert target is not None, "Seeded drip campaign missing from list"
        assert target.get("folder_name") == "TEST_iter60_BrandFolder"
        assert target.get("reply_count") == 1
        # Drip lead_count depends on backend impl — check what server returns
        # Inspecting server.py shows it counts leads by source_drip_id
        assert target.get("lead_count") == 2
