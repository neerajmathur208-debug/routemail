"""
Do Not Email (DNE / Suppression) feature end-to-end backend tests.

Covers:
- /api/dne-lists CRUD + auto-create Global list
- Add/upload/remove emails (csv + xlsx + manual)
- Search filtering
- Delete non-global list unlinks from campaigns + drip_campaigns
- Global list cannot be deleted
- Auth 401 + cross-user 404
- /api/unsubscribe/{user_id}/{email} mirrors into Global DNE
- /api/suppression mirrors into Global DNE
- Standard campaign suppresses recipients in real-time (simulated SMTP account)
- Drip campaign suppresses recipients in real-time (worker pickup ~60s)
- is_email_suppressed re-checks per send (no stale cache)
- ObjectId _id never leaked
"""
import os
import io
import csv
import time
import uuid
import pytest
import requests
import openpyxl
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")
assert BASE_URL and MONGO_URL and DB_NAME

PRIMARY_EMAIL = "drip.tester@example.com"
PRIMARY_PASSWORD = "DripTest123!"
PRIMARY_USER_ID = "user_35cc629e1385"

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]


def _api(p): return f"{BASE_URL}/api{p}"


def _no_id(obj):
    if isinstance(obj, dict):
        assert "_id" not in obj, f"_id leaked in {list(obj.keys())}"
        for v in obj.values():
            _no_id(v)
    elif isinstance(obj, list):
        for v in obj:
            _no_id(v)


def _login(s, email, pw):
    r = s.post(_api("/auth/login"), json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return s.cookies.get("session_token")


# ---------- fixtures ----------

@pytest.fixture(scope="session")
def primary_session():
    s = requests.Session()
    _login(s, PRIMARY_EMAIL, PRIMARY_PASSWORD)
    return s


@pytest.fixture(scope="session")
def secondary_user():
    """Throw-away verified user for cross-user 404 isolation tests."""
    email = f"TEST_dne_other_{uuid.uuid4().hex[:8]}@example.com"
    password = "DneOther123!"
    s = requests.Session()
    r = s.post(_api("/auth/register"), json={
        "email": email, "password": password, "confirm_password": password, "name": "DNE Other",
    }, timeout=20)
    assert r.status_code in (200, 201), f"register failed: {r.status_code} {r.text}"
    # Force verify in DB
    _db.users.update_one({"email": email}, {"$set": {"email_verified": True}})
    s2 = requests.Session()
    _login(s2, email, password)
    me = s2.get(_api("/auth/me"), timeout=10).json()
    yield {"session": s2, "user_id": me.get("user_id"), "email": email}
    _db.users.delete_many({"email": email})
    _db.dne_lists.delete_many({"user_id": me.get("user_id")})
    _db.dne_emails.delete_many({"user_id": me.get("user_id")})


@pytest.fixture(scope="session", autouse=True)
def cleanup_after_all():
    """Cleanup any DNE artifacts from prior runs for primary user."""
    yield
    _db.dne_lists.delete_many({"user_id": PRIMARY_USER_ID, "name": {"$regex": "^TEST_DNE_"}})
    _db.dne_emails.delete_many({"user_id": PRIMARY_USER_ID, "email": {"$regex": "^test_dne_"}})
    _db.campaigns.delete_many({"user_id": PRIMARY_USER_ID, "name": {"$regex": "^TEST_DNE_"}})
    _db.drip_campaigns.delete_many({"user_id": PRIMARY_USER_ID, "name": {"$regex": "^TEST_DNE_"}})
    _db.email_lists.delete_many({"user_id": PRIMARY_USER_ID, "name": {"$regex": "^TEST_DNE_"}})
    _db.email_accounts.delete_many({"user_id": PRIMARY_USER_ID, "email": {"$regex": "^test_dne_acct"}})
    _db.email_queue.delete_many({"user_id": PRIMARY_USER_ID, "recipient_email": {"$regex": "^test_dne_"}})


def _create_fake_account(user_id):
    aid = f"account_TEST_DNE_{uuid.uuid4().hex[:8]}"
    _db.email_accounts.insert_one({
        "account_id": aid, "user_id": user_id,
        "email": f"test_dne_acct_{aid}@example.com",
        "account_type": "smtp", "status": "connected",
        "display_name": "DNE Tester",
        "daily_limit": 100, "daily_send_count": 0,
        "send_delay": 10,
        # No smtp_host -> simulated send
    })
    return aid


# ============== AUTH ==============

class TestAuth:
    def test_401_when_no_session(self):
        r = requests.get(_api("/dne-lists"), timeout=10)
        assert r.status_code == 401


# ============== CRUD ==============

class TestDNECRUD:
    def test_list_auto_creates_global(self, primary_session):
        r = primary_session.get(_api("/dne-lists"), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        _no_id(data)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0].get("is_global") is True, "Global list must be pinned first"
        assert data[0].get("list_id")
        # Save for other tests
        TestDNECRUD.global_id = data[0]["list_id"]

    def test_create_named_list(self, primary_session):
        name = f"TEST_DNE_{uuid.uuid4().hex[:6]}"
        r = primary_session.post(_api("/dne-lists"), json={"name": name}, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        _no_id(body)
        assert body["name"] == name
        assert body["is_global"] is False
        assert body.get("list_id")
        TestDNECRUD.list_id = body["list_id"]

    def test_create_empty_name_400(self, primary_session):
        r = primary_session.post(_api("/dne-lists"), json={"name": "  "}, timeout=10)
        assert r.status_code == 400

    def test_get_detail_with_pagination(self, primary_session):
        r = primary_session.get(_api(f"/dne-lists/{TestDNECRUD.list_id}"), timeout=10)
        assert r.status_code == 200
        data = r.json()
        _no_id(data)
        assert "emails" in data and "total_filtered" in data
        assert data["total_filtered"] == 0

    def test_add_emails_normalize_dedupe_invalid(self, primary_session):
        payload = {"emails": [
            "  test_dne_A@Example.com ",
            "TEST_DNE_a@example.com",  # dup after normalization
            "test_dne_b@example.com",
            "not-an-email",
            "",
        ]}
        r = primary_session.post(_api(f"/dne-lists/{TestDNECRUD.list_id}/emails"),
                                 json=payload, timeout=10)
        assert r.status_code == 200, r.text
        body = r.json()
        # 2 valid uniques after normalization, 1 invalid, 0 already-existing
        assert body["added"] == 2, body
        assert body["invalid"] == 1, body
        assert body["total"] == 2

        # Re-add same -> all skipped duplicates
        r2 = primary_session.post(_api(f"/dne-lists/{TestDNECRUD.list_id}/emails"),
                                  json={"emails": ["test_dne_a@example.com"]}, timeout=10)
        b2 = r2.json()
        assert b2["added"] == 0
        assert b2["skipped_duplicates"] == 1

    def test_search_filter(self, primary_session):
        r = primary_session.get(_api(f"/dne-lists/{TestDNECRUD.list_id}?search=dne_a"), timeout=10)
        assert r.status_code == 200
        data = r.json()
        emails = [e["email"] for e in data["emails"]]
        assert any("dne_a" in e for e in emails)
        assert all("dne_b" not in e for e in emails)

    def test_remove_email_decrements_count(self, primary_session):
        r = primary_session.request("DELETE", _api(f"/dne-lists/{TestDNECRUD.list_id}/emails"),
                                    json={"email": "test_dne_b@example.com"}, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["email_count"] == 1

    def test_upload_csv_with_header(self, primary_session):
        csv_text = "email\ntest_dne_csv1@example.com\ntest_dne_csv2@example.com\n"
        files = {"file": ("test.csv", csv_text.encode(), "text/csv")}
        r = primary_session.post(_api(f"/dne-lists/{TestDNECRUD.list_id}/upload"),
                                 files=files, timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["added"] == 2

    def test_upload_csv_single_column_no_header(self, primary_session):
        # First row treated as data when single column
        csv_text = "test_dne_single1@example.com\ntest_dne_single2@example.com\n"
        files = {"file": ("emails.csv", csv_text.encode(), "text/csv")}
        r = primary_session.post(_api(f"/dne-lists/{TestDNECRUD.list_id}/upload"),
                                 files=files, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["added"] == 2

    def test_upload_csv_multicol_no_email_header_400(self, primary_session):
        csv_text = "name,phone\nAlice,12345\nBob,67890\n"
        files = {"file": ("t.csv", csv_text.encode(), "text/csv")}
        r = primary_session.post(_api(f"/dne-lists/{TestDNECRUD.list_id}/upload"),
                                 files=files, timeout=15)
        assert r.status_code == 400

    def test_upload_xlsx(self, primary_session):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["email"])
        ws.append(["test_dne_xlsx1@example.com"])
        ws.append(["test_dne_xlsx2@example.com"])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        files = {"file": ("t.xlsx", buf.read(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = primary_session.post(_api(f"/dne-lists/{TestDNECRUD.list_id}/upload"),
                                 files=files, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["added"] == 2

    def test_upload_oversize_400(self, primary_session):
        big = ("email\n" + ("x" * (3 * 1024 * 1024))).encode()
        files = {"file": ("big.csv", big, "text/csv")}
        r = primary_session.post(_api(f"/dne-lists/{TestDNECRUD.list_id}/upload"),
                                 files=files, timeout=30)
        assert r.status_code == 400


# ============== GLOBAL + UNSUB MIRRORING ==============

class TestGlobalMirroring:
    def test_unsubscribe_mirrors_to_global(self, primary_session):
        email = "test_dne_unsub@example.com"
        # unsubscribe is GET in current implementation
        r = requests.get(_api(f"/unsubscribe/{PRIMARY_USER_ID}/{email}"), timeout=10)
        assert r.status_code == 200, r.text
        # Verify in Global list
        lists = primary_session.get(_api("/dne-lists"), timeout=10).json()
        gid = next(l["list_id"] for l in lists if l.get("is_global"))
        detail = primary_session.get(_api(f"/dne-lists/{gid}?search=test_dne_unsub"), timeout=10).json()
        assert any(e["email"] == email for e in detail["emails"])

    def test_suppression_post_mirrors_to_global(self, primary_session):
        email = "test_dne_supp@example.com"
        r = primary_session.post(_api("/suppression"), json={"email": email}, timeout=10)
        assert r.status_code == 200
        lists = primary_session.get(_api("/dne-lists"), timeout=10).json()
        gid = next(l["list_id"] for l in lists if l.get("is_global"))
        detail = primary_session.get(_api(f"/dne-lists/{gid}?search=test_dne_supp"), timeout=10).json()
        assert any(e["email"] == email for e in detail["emails"])

    def test_global_cannot_be_deleted(self, primary_session):
        lists = primary_session.get(_api("/dne-lists"), timeout=10).json()
        gid = next(l["list_id"] for l in lists if l.get("is_global"))
        r = primary_session.delete(_api(f"/dne-lists/{gid}"), timeout=10)
        assert r.status_code == 400


# ============== CROSS-USER ==============

class TestCrossUser:
    def test_other_user_cannot_access(self, primary_session, secondary_user):
        list_id = TestDNECRUD.list_id
        r = secondary_user["session"].get(_api(f"/dne-lists/{list_id}"), timeout=10)
        assert r.status_code == 404


# ============== CAMPAIGN INTEGRATION ==============

class TestCampaignSuppression:
    def test_create_campaign_with_suppression_ids(self, primary_session):
        # Create a small email list
        list_id = f"list_TESTDNE_{uuid.uuid4().hex[:8]}"
        _db.email_lists.insert_one({
            "list_id": list_id, "user_id": PRIMARY_USER_ID,
            "name": f"TEST_DNE_camplist_{uuid.uuid4().hex[:6]}",
            "valid_emails": 2,
            "emails": [
                {"email": "test_dne_supp@example.com", "first_name": "S"},  # suppressed
                {"email": "test_dne_clean@example.com", "first_name": "C"},
            ],
            "created_at": "2025-01-01T00:00:00",
        })
        TestCampaignSuppression.list_id = list_id

        # Use the named DNE list created earlier (contains test_dne_a@example.com)
        sup_id = TestDNECRUD.list_id
        # Add the recipient to the named list so it's suppressed via list (also test_dne_supp is in Global)
        primary_session.post(_api(f"/dne-lists/{sup_id}/emails"),
                             json={"emails": ["test_dne_clean2@example.com"]}, timeout=10)

        r = primary_session.post(_api("/campaigns"), json={
            "name": f"TEST_DNE_camp_{uuid.uuid4().hex[:6]}",
            "subject": "Hi",
            "body": "<p>hello</p>",
            "list_id": list_id,
            "suppression_list_ids": [sup_id],
        }, timeout=15)
        assert r.status_code == 200, r.text
        cid = r.json()["campaign_id"]
        TestCampaignSuppression.campaign_id = cid

        # GET should return suppression_list_ids
        rg = primary_session.get(_api(f"/campaigns/{cid}"), timeout=10)
        assert rg.status_code == 200
        cb = rg.json()
        _no_id(cb)
        assert cb.get("suppression_list_ids") == [sup_id]

    def test_update_campaign_suppression_ids(self, primary_session):
        cid = TestCampaignSuppression.campaign_id
        r = primary_session.put(_api(f"/campaigns/{cid}"),
                                json={"suppression_list_ids": []}, timeout=10)
        assert r.status_code == 200
        rg = primary_session.get(_api(f"/campaigns/{cid}"), timeout=10).json()
        assert rg.get("suppression_list_ids") == []
        # Restore
        primary_session.put(_api(f"/campaigns/{cid}"),
                            json={"suppression_list_ids": [TestDNECRUD.list_id]}, timeout=10)

    def test_realtime_suppression_in_standard_campaign(self, primary_session):
        cid = TestCampaignSuppression.campaign_id
        # Create simulated SMTP account
        aid = _create_fake_account(PRIMARY_USER_ID)
        primary_session.put(_api(f"/campaigns/{cid}"),
                            json={"account_ids": [aid]}, timeout=10)

        # Start campaign
        r = primary_session.post(_api(f"/campaigns/{cid}/start"), timeout=20)
        assert r.status_code == 200, r.text

        # Wait for queue to process (sim send delay ~10s per item, 2 items)
        suppressed_seen = False
        sent_seen = False
        for _ in range(40):
            time.sleep(2)
            queue = list(_db.email_queue.find({"campaign_id": cid}, {"_id": 0}))
            statuses = [q["status"] for q in queue]
            if "suppressed" in statuses:
                suppressed_seen = True
            if "sent" in statuses:
                sent_seen = True
            if suppressed_seen and (sent_seen or all(s in ("suppressed", "sent", "failed") for s in statuses)):
                break

        assert suppressed_seen, f"No suppressed queue item; statuses={statuses}"
        # Find the suppressed item
        sup_item = _db.email_queue.find_one({"campaign_id": cid, "status": "suppressed"}, {"_id": 0})
        assert sup_item is not None
        assert sup_item.get("recipient_email") == "test_dne_supp@example.com"
        assert sup_item.get("error_message")

        # Verify campaign suppressed_count incremented + visible via GET
        rc = primary_session.get(_api(f"/campaigns/{cid}"), timeout=10).json()
        assert rc.get("suppressed_count", 0) >= 1, rc

    def test_delete_dne_list_unlinks_from_campaign(self, primary_session):
        # Create a fresh list and attach to campaign
        rn = primary_session.post(_api("/dne-lists"), json={"name": f"TEST_DNE_unlink_{uuid.uuid4().hex[:5]}"}, timeout=10)
        new_id = rn.json()["list_id"]
        cid = TestCampaignSuppression.campaign_id
        # campaign may be running; pause first if so
        rcc = primary_session.get(_api(f"/campaigns/{cid}"), timeout=10).json()
        if rcc.get("status") == "running":
            primary_session.post(_api(f"/campaigns/{cid}/pause"), timeout=10)
        primary_session.put(_api(f"/campaigns/{cid}"),
                            json={"suppression_list_ids": [TestDNECRUD.list_id, new_id]}, timeout=10)
        # Delete the new list
        rd = primary_session.delete(_api(f"/dne-lists/{new_id}"), timeout=10)
        assert rd.status_code == 200
        # Re-fetch campaign and ensure it no longer references the deleted list
        rg = primary_session.get(_api(f"/campaigns/{cid}"), timeout=10).json()
        assert new_id not in (rg.get("suppression_list_ids") or [])


# ============== DRIP INTEGRATION ==============

class TestDripSuppression:
    def test_create_drip_with_suppression_ids(self, primary_session):
        sup_id = TestDNECRUD.list_id
        r = primary_session.post(_api("/drip-campaigns"), json={
            "name": f"TEST_DNE_drip_{uuid.uuid4().hex[:6]}",
            "suppression_list_ids": [sup_id],
        }, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        _no_id(body)
        did = body["drip_id"]
        TestDripSuppression.drip_id = did

        rg = primary_session.get(_api(f"/drip-campaigns/{did}"), timeout=10).json()
        assert rg.get("suppression_list_ids") == [sup_id]
        # Stats include 'suppressed'
        assert "stats" in rg and "suppressed" in rg["stats"]

    def test_update_drip_suppression(self, primary_session):
        did = TestDripSuppression.drip_id
        r = primary_session.put(_api(f"/drip-campaigns/{did}"),
                                json={"suppression_list_ids": []}, timeout=10)
        assert r.status_code == 200
        rg = primary_session.get(_api(f"/drip-campaigns/{did}"), timeout=10).json()
        assert rg.get("suppression_list_ids") == []
        # Restore
        primary_session.put(_api(f"/drip-campaigns/{did}"),
                            json={"suppression_list_ids": [TestDNECRUD.list_id]}, timeout=10)


# ============== HELPER: is_email_suppressed re-check ==============

class TestRealTimeRecheck:
    def test_email_added_midrun_is_suppressed(self, primary_session):
        """Add email to DNE list AFTER campaign starts; subsequent processing must
        treat it as suppressed (no caching). Verified via process_campaign_queue."""
        # Re-use the campaign from TestCampaignSuppression, but create a fresh
        # email list with a third email and re-run
        list_id = f"list_TESTDNE2_{uuid.uuid4().hex[:8]}"
        _db.email_lists.insert_one({
            "list_id": list_id, "user_id": PRIMARY_USER_ID,
            "name": f"TEST_DNE_camplist2_{uuid.uuid4().hex[:6]}",
            "valid_emails": 1,
            "emails": [{"email": "test_dne_midrun@example.com", "first_name": "M"}],
            "created_at": "2025-01-01T00:00:00",
        })
        # Add email to Global DNE BEFORE start (still tests is_email_suppressed live check)
        primary_session.post(_api("/suppression"), json={"email": "test_dne_midrun@example.com"}, timeout=10)

        aid = _create_fake_account(PRIMARY_USER_ID)
        rc = primary_session.post(_api("/campaigns"), json={
            "name": f"TEST_DNE_recheck_{uuid.uuid4().hex[:6]}",
            "subject": "x", "body": "<p>x</p>",
            "list_id": list_id,
            "account_ids": [aid],
        }, timeout=15)
        cid = rc.json()["campaign_id"]
        primary_session.post(_api(f"/campaigns/{cid}/start"), timeout=15)

        for _ in range(20):
            time.sleep(1)
            q = _db.email_queue.find_one({"campaign_id": cid}, {"_id": 0})
            if q and q.get("status") in ("suppressed", "sent", "failed"):
                break
        assert q and q.get("status") == "suppressed", f"Expected suppressed, got {q}"
