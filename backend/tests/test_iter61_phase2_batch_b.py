"""Iteration 61 — Phase 2 Batch B (Unibox rebuild) backend tests.

Covers:
 1. GET /api/unibox/replies extended filters/search/sort/pagination/enrichment.
 2. POST /api/unibox/replies/move (incl. folder_id=None and 404 on unknown folder).
 3. POST /api/unibox/replies/archive (toggle archived + filter respects flag).
 4. POST /api/unibox/replies/delete.
 5. POST /api/unibox/dne/domain/preview + /api/unibox/dne/domain (idempotent).
 6. Cross-tenant isolation on bulk endpoints.
 7. Regression: GET /api/leads/folders still returns reply_count + unassigned_reply_count.
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

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
SUPER_ADMIN_ID = "user_b3e333b0f467"
OTHER_USER_ID = "user_dfda57d9d20a"  # other super admin used as foreign tenant

TAG = f"TEST_iter61_{uuid.uuid4().hex[:8]}"


# -------- Fixtures --------
@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def admin_token(mongo):
    tok = f"TEST_iter61_{uuid.uuid4().hex}"
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
def seed(mongo):
    """Seed folder + email_account + assorted replies for testing."""
    now = datetime.now(timezone.utc)
    folder = {
        "folder_id": f"foldr_{uuid.uuid4().hex[:10]}",
        "user_id": SUPER_ADMIN_ID,
        "name": f"{TAG}_Brand",
        "created_at": now.isoformat(),
        "_tag": TAG,
    }
    mongo.lead_folders.insert_one(folder)

    account = {
        "account_id": f"acct_{uuid.uuid4().hex[:10]}",
        "user_id": SUPER_ADMIN_ID,
        "email": f"{TAG}_sender@routemail.test",
        "from_name": f"{TAG} Sender",
        "_tag": TAG,
    }
    mongo.email_accounts.insert_one(account)

    # Replies: 4 main user replies + 1 cross-tenant.
    def make_reply(idx, **overrides):
        base = {
            "reply_id": f"rep_{uuid.uuid4().hex[:12]}",
            "user_id": SUPER_ADMIN_ID,
            "account_id": account["account_id"],
            "received_on_email": account["email"],
            "from_email": f"{TAG}_contact{idx}@acme.com",
            "subject": f"{TAG} subject {idx}",
            "body": f"{TAG} body {idx}",
            "received_at": (now - timedelta(days=idx)).isoformat(),
            "read": False,
            "archived": False,
            "campaign_id": None,
            "campaign_name": None,
            "drip_campaign_id": None,
            "drip_campaign_name": None,
            "folder_id": None,
            "_tag": TAG,
            "created_at": now.isoformat(),
        }
        base.update(overrides)
        return base

    r1 = make_reply(1, folder_id=folder["folder_id"], campaign_id="cmp_x",
                    campaign_name=f"{TAG}_Camp", from_email=f"{TAG}_a@acme.com")
    r2 = make_reply(2, drip_campaign_id="drip_x", drip_campaign_name=f"{TAG}_Drip",
                    from_email=f"{TAG}_b@widgets.io", archived=True)
    r3 = make_reply(3, folder_id=folder["folder_id"], from_email=f"{TAG}_c@acme.com",
                    received_at=(now - timedelta(days=40)).isoformat())
    r4 = make_reply(4, from_email=f"{TAG}_d@unique-domain-iter61.com",
                    body=f"{TAG} UNIQUEKEYWORD61 body")
    cross = make_reply(99, user_id=OTHER_USER_ID,
                       from_email=f"{TAG}_foreign@acme.com")

    mongo.replies.insert_many([r1, r2, r3, r4, cross])

    yield {
        "folder": folder,
        "account": account,
        "replies": {"r1": r1, "r2": r2, "r3": r3, "r4": r4, "cross": cross},
    }


@pytest.fixture(scope="module", autouse=True)
def cleanup(mongo, seed):
    yield
    for coll in ("replies", "lead_folders", "email_accounts", "dne_lists",
                 "dne_emails", "leads", "email_list_contacts", "drip_contacts"):
        try:
            mongo[coll].delete_many({"_tag": TAG})
        except Exception:
            pass
    # also cleanup wildcard DNE entries created during testing
    mongo.dne_emails.delete_many({"user_id": SUPER_ADMIN_ID, "source": "unibox_domain",
                                  "email": {"$regex": "iter61"}})


# ================== GET /api/unibox/replies ==================
class TestListReplies:
    def test_default_excludes_archived(self, client, seed):
        r = client.get(f"{BASE_URL}/api/unibox/replies", params={"q": TAG, "limit": 50})
        assert r.status_code == 200
        data = r.json()
        # r2 is archived → must NOT appear
        ids = [it["reply_id"] for it in data["items"]]
        assert seed["replies"]["r2"]["reply_id"] not in ids
        # r1,r3,r4 expected
        assert seed["replies"]["r1"]["reply_id"] in ids
        assert seed["replies"]["r4"]["reply_id"] in ids
        # No cross-tenant
        assert seed["replies"]["cross"]["reply_id"] not in ids
        # response shape
        assert "total" in data and "unread_count" in data
        assert data["limit"] == 50 and data["skip"] == 0

    def test_archived_true_returns_only_archived(self, client, seed):
        r = client.get(f"{BASE_URL}/api/unibox/replies", params={"q": TAG, "archived": "true"})
        assert r.status_code == 200
        ids = [it["reply_id"] for it in r.json()["items"]]
        assert seed["replies"]["r2"]["reply_id"] in ids
        assert seed["replies"]["r1"]["reply_id"] not in ids

    def test_folder_id_filter(self, client, seed):
        fid = seed["folder"]["folder_id"]
        r = client.get(f"{BASE_URL}/api/unibox/replies", params={"q": TAG, "folder_id": fid})
        assert r.status_code == 200
        ids = [it["reply_id"] for it in r.json()["items"]]
        assert seed["replies"]["r1"]["reply_id"] in ids
        assert seed["replies"]["r3"]["reply_id"] in ids
        assert seed["replies"]["r4"]["reply_id"] not in ids

    def test_unassigned_folder(self, client, seed):
        r = client.get(f"{BASE_URL}/api/unibox/replies",
                       params={"q": TAG, "folder_id": "__unassigned__"})
        assert r.status_code == 200
        ids = [it["reply_id"] for it in r.json()["items"]]
        assert seed["replies"]["r4"]["reply_id"] in ids
        assert seed["replies"]["r1"]["reply_id"] not in ids

    def test_campaign_id_filter(self, client, seed):
        r = client.get(f"{BASE_URL}/api/unibox/replies",
                       params={"q": TAG, "campaign_id": "cmp_x"})
        ids = [it["reply_id"] for it in r.json()["items"]]
        assert ids == [seed["replies"]["r1"]["reply_id"]]

    def test_drip_id_filter(self, client, seed):
        r = client.get(f"{BASE_URL}/api/unibox/replies",
                       params={"q": TAG, "drip_id": "drip_x", "archived": "true"})
        ids = [it["reply_id"] for it in r.json()["items"]]
        assert seed["replies"]["r2"]["reply_id"] in ids

    def test_account_id_filter(self, client, seed):
        r = client.get(f"{BASE_URL}/api/unibox/replies",
                       params={"q": TAG, "account_id": seed["account"]["account_id"]})
        assert r.status_code == 200
        assert len(r.json()["items"]) >= 3

    def test_domain_filter(self, client, seed):
        r = client.get(f"{BASE_URL}/api/unibox/replies",
                       params={"q": TAG, "domain": "unique-domain-iter61.com"})
        ids = [it["reply_id"] for it in r.json()["items"]]
        assert ids == [seed["replies"]["r4"]["reply_id"]]

    def test_date_preset_last_7(self, client, seed):
        r = client.get(f"{BASE_URL}/api/unibox/replies",
                       params={"q": TAG, "date_preset": "last_7"})
        ids = [it["reply_id"] for it in r.json()["items"]]
        # r3 is 40 days old → excluded
        assert seed["replies"]["r3"]["reply_id"] not in ids
        assert seed["replies"]["r1"]["reply_id"] in ids

    def test_q_freetext_search(self, client, seed):
        r = client.get(f"{BASE_URL}/api/unibox/replies", params={"q": "UNIQUEKEYWORD61"})
        ids = [it["reply_id"] for it in r.json()["items"]]
        assert ids == [seed["replies"]["r4"]["reply_id"]]

    def test_sort_by_whitelist_fallback(self, client, seed):
        # Invalid sort_by should fall back to received_at (no 500)
        r = client.get(f"{BASE_URL}/api/unibox/replies",
                       params={"q": TAG, "sort_by": "drop_table; DROP", "sort_dir": "asc"})
        assert r.status_code == 200

    def test_sort_by_from_email_asc(self, client, seed):
        r = client.get(f"{BASE_URL}/api/unibox/replies",
                       params={"q": TAG, "sort_by": "from_email", "sort_dir": "asc"})
        emails = [it["from_email"] for it in r.json()["items"]]
        assert emails == sorted(emails)

    def test_limit_clamp_invalid(self, client):
        r = client.get(f"{BASE_URL}/api/unibox/replies", params={"limit": 600})
        assert r.status_code == 422

    def test_pagination_skip(self, client, seed):
        r1 = client.get(f"{BASE_URL}/api/unibox/replies",
                        params={"q": TAG, "limit": 1, "skip": 0,
                                "sort_by": "received_at", "sort_dir": "asc"})
        r2 = client.get(f"{BASE_URL}/api/unibox/replies",
                        params={"q": TAG, "limit": 1, "skip": 1,
                                "sort_by": "received_at", "sort_dir": "asc"})
        assert r1.json()["items"][0]["reply_id"] != r2.json()["items"][0]["reply_id"]

    def test_enrichment_fields(self, client, seed):
        r = client.get(f"{BASE_URL}/api/unibox/replies", params={"q": TAG})
        items = r.json()["items"]
        # find r1
        r1 = next(it for it in items if it["reply_id"] == seed["replies"]["r1"]["reply_id"])
        assert r1["domain"] == "acme.com"
        assert r1["folder_name"] == seed["folder"]["name"]
        assert r1["sending_account_email"] == seed["account"]["email"]


# ================== POST /api/unibox/replies/move ==================
class TestMoveReplies:
    def test_move_to_folder(self, client, seed, mongo):
        # move r4 into folder
        fid = seed["folder"]["folder_id"]
        r = client.post(f"{BASE_URL}/api/unibox/replies/move", json={
            "reply_ids": [seed["replies"]["r4"]["reply_id"]], "folder_id": fid
        })
        assert r.status_code == 200
        assert r.json()["modified"] == 1
        # persisted
        doc = mongo.replies.find_one({"reply_id": seed["replies"]["r4"]["reply_id"]})
        assert doc["folder_id"] == fid
        # restore
        mongo.replies.update_one({"reply_id": seed["replies"]["r4"]["reply_id"]},
                                 {"$set": {"folder_id": None}})

    def test_move_to_unassigned(self, client, seed, mongo):
        r = client.post(f"{BASE_URL}/api/unibox/replies/move", json={
            "reply_ids": [seed["replies"]["r1"]["reply_id"]]
        })
        assert r.status_code == 200
        doc = mongo.replies.find_one({"reply_id": seed["replies"]["r1"]["reply_id"]})
        assert doc["folder_id"] is None
        # restore
        mongo.replies.update_one({"reply_id": seed["replies"]["r1"]["reply_id"]},
                                 {"$set": {"folder_id": seed["folder"]["folder_id"]}})

    def test_move_unknown_folder_404(self, client, seed):
        r = client.post(f"{BASE_URL}/api/unibox/replies/move", json={
            "reply_ids": [seed["replies"]["r1"]["reply_id"]], "folder_id": "foldr_nope"
        })
        assert r.status_code == 404

    def test_move_empty_400(self, client):
        r = client.post(f"{BASE_URL}/api/unibox/replies/move", json={"reply_ids": []})
        assert r.status_code == 400

    def test_move_cross_tenant_silent(self, client, seed, mongo):
        cross_id = seed["replies"]["cross"]["reply_id"]
        r = client.post(f"{BASE_URL}/api/unibox/replies/move", json={
            "reply_ids": [cross_id], "folder_id": seed["folder"]["folder_id"]
        })
        assert r.status_code == 200
        assert r.json()["modified"] == 0
        doc = mongo.replies.find_one({"reply_id": cross_id})
        assert doc["folder_id"] is None  # untouched


# ================== POST /api/unibox/replies/archive ==================
class TestArchiveReplies:
    def test_archive_then_unarchive(self, client, seed, mongo):
        rid = seed["replies"]["r1"]["reply_id"]
        # Archive
        r = client.post(f"{BASE_URL}/api/unibox/replies/archive", json={
            "reply_ids": [rid], "archived": True
        })
        assert r.status_code == 200
        # GET default excludes archived
        listed = client.get(f"{BASE_URL}/api/unibox/replies", params={"q": TAG}).json()
        ids = [it["reply_id"] for it in listed["items"]]
        assert rid not in ids
        # archived=true returns it
        listed2 = client.get(f"{BASE_URL}/api/unibox/replies",
                             params={"q": TAG, "archived": "true"}).json()
        ids2 = [it["reply_id"] for it in listed2["items"]]
        assert rid in ids2
        # Unarchive
        client.post(f"{BASE_URL}/api/unibox/replies/archive", json={
            "reply_ids": [rid], "archived": False
        })
        doc = mongo.replies.find_one({"reply_id": rid})
        assert doc["archived"] is False

    def test_archive_empty_400(self, client):
        r = client.post(f"{BASE_URL}/api/unibox/replies/archive", json={"reply_ids": []})
        assert r.status_code == 400


# ================== POST /api/unibox/replies/delete ==================
class TestDeleteReplies:
    def test_delete_persists(self, client, mongo):
        # seed a throwaway reply
        rid = f"rep_{uuid.uuid4().hex[:12]}"
        mongo.replies.insert_one({
            "reply_id": rid, "user_id": SUPER_ADMIN_ID,
            "from_email": f"{TAG}_del@x.com", "subject": f"{TAG} del",
            "received_at": datetime.now(timezone.utc).isoformat(),
            "archived": False, "read": False, "_tag": TAG,
        })
        r = client.post(f"{BASE_URL}/api/unibox/replies/delete", json={"reply_ids": [rid]})
        assert r.status_code == 200
        assert r.json()["deleted"] == 1
        assert mongo.replies.find_one({"reply_id": rid}) is None

    def test_delete_empty_400(self, client):
        r = client.post(f"{BASE_URL}/api/unibox/replies/delete", json={"reply_ids": []})
        assert r.status_code == 400

    def test_delete_cross_tenant(self, client, seed, mongo):
        cross_id = seed["replies"]["cross"]["reply_id"]
        r = client.post(f"{BASE_URL}/api/unibox/replies/delete",
                        json={"reply_ids": [cross_id]})
        assert r.status_code == 200
        assert r.json()["deleted"] == 0
        assert mongo.replies.find_one({"reply_id": cross_id}) is not None


# ================== POST /api/unibox/dne/domain ==================
class TestDomainDNE:
    def test_preview_counts(self, client, seed, mongo):
        # seed a few leads for the domain
        mongo.leads.insert_one({
            "lead_id": f"lead_{uuid.uuid4().hex[:8]}",
            "user_id": SUPER_ADMIN_ID,
            "contact_email": f"someone@unique-domain-iter61.com",
            "folder_id": seed["folder"]["folder_id"],
            "_tag": TAG,
        })
        r = client.post(f"{BASE_URL}/api/unibox/dne/domain/preview",
                        json={"domain": "unique-domain-iter61.com"})
        assert r.status_code == 200
        data = r.json()
        assert data["domain"] == "unique-domain-iter61.com"
        assert data["lead_count"] >= 1
        assert data["reply_count"] >= 1
        assert "estimated_suppressed" in data

    def test_preview_invalid_domain_400(self, client):
        r = client.post(f"{BASE_URL}/api/unibox/dne/domain/preview",
                        json={"domain": ""})
        assert r.status_code == 400
        r2 = client.post(f"{BASE_URL}/api/unibox/dne/domain/preview",
                         json={"domain": "no-tld-here"})
        assert r2.status_code == 400

    def test_add_domain_then_idempotent(self, client, mongo):
        dom = f"iter61-suppress-{uuid.uuid4().hex[:6]}.com"
        r1 = client.post(f"{BASE_URL}/api/unibox/dne/domain", json={"domain": dom})
        assert r1.status_code == 200
        body1 = r1.json()
        assert body1["added"] is True
        assert body1["domain"] == dom
        # Verify wildcard stored
        entry = mongo.dne_emails.find_one({"user_id": SUPER_ADMIN_ID, "email": f"@{dom}"})
        assert entry is not None
        assert entry.get("source") == "unibox_domain"
        # Idempotent
        r2 = client.post(f"{BASE_URL}/api/unibox/dne/domain", json={"domain": dom})
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["added"] is False
        assert "Already suppressed" in body2.get("message", "")
        # cleanup
        mongo.dne_emails.delete_many({"user_id": SUPER_ADMIN_ID, "email": f"@{dom}"})

    def test_add_domain_invalid_400(self, client):
        r = client.post(f"{BASE_URL}/api/unibox/dne/domain", json={"domain": "@"})
        assert r.status_code == 400


# ================== Regression: /api/leads/folders ==================
class TestFoldersRegression:
    def test_folder_reply_counts(self, client, seed):
        r = client.get(f"{BASE_URL}/api/leads/folders")
        assert r.status_code == 200
        data = r.json()
        assert "folders" in data
        assert "unassigned_reply_count" in data
        # Find our seeded folder
        f = next((x for x in data["folders"] if x["folder_id"] == seed["folder"]["folder_id"]), None)
        assert f is not None
        assert "reply_count" in f
        assert "lead_count" in f
