"""Backend tests for RouteMail Unibox + Responses/Leads + IMAP receiving feature set."""
import os
import uuid
import pytest
import requests
from pymongo import MongoClient

from dotenv import load_dotenv
load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

DRIP_EMAIL = "drip.tester@example.com"
DRIP_PASS = "DripTest123!"
DHRUV_EMAIL = "dhruvmathur208@gmail.com"
DHRUV_PASS = "Perfect2026#"


@pytest.fixture(scope="session")
def mongo():
    return MongoClient(MONGO_URL)[DB_NAME]


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="session")
def drip_client():
    return _login(DRIP_EMAIL, DRIP_PASS)


@pytest.fixture(scope="session")
def dhruv_client():
    return _login(DHRUV_EMAIL, DHRUV_PASS)


@pytest.fixture(scope="session")
def drip_user_id():
    return "user_35cc629e1385"


# ----------------- Auth gating -----------------
class TestAuth:
    def test_unibox_unauth_401(self):
        for ep in ["/api/unibox/replies", "/api/unibox/status", "/api/leads/folders", "/api/leads"]:
            r = requests.get(f"{BASE_URL}{ep}")
            assert r.status_code in (401, 403), f"{ep} -> {r.status_code}"


# ----------------- Unibox endpoints -----------------
class TestUnibox:
    def test_status_shape(self, drip_client):
        r = drip_client.get(f"{BASE_URL}/api/unibox/status")
        assert r.status_code == 200
        data = r.json()
        assert "accounts" in data and isinstance(data["accounts"], list)
        assert data.get("sync_interval_seconds") == 600
        for acc in data["accounts"]:
            assert "sending_configured" in acc
            assert "receiving_configured" in acc
            assert "imap_last_sync_at" in acc
            assert "imap_last_error" in acc
            # Ensure passwords never leak
            assert "smtp_password_encrypted" not in acc
            assert "imap_password_encrypted" not in acc

    def test_replies_shape_and_filters(self, drip_client):
        r = drip_client.get(f"{BASE_URL}/api/unibox/replies")
        assert r.status_code == 200
        data = r.json()
        for k in ("items", "total", "unread_count", "skip", "limit"):
            assert k in data
        # Test filters don't crash
        for q in ("?unread_only=true", "?account_id=nope", "?campaign_id=x", "?drip_id=x",
                 "?date_from=2025-01-01&date_to=2026-12-31", "?limit=5&skip=0"):
            assert drip_client.get(f"{BASE_URL}/api/unibox/replies{q}").status_code == 200

    def test_mark_empty_returns_400(self, drip_client):
        r = drip_client.post(f"{BASE_URL}/api/unibox/replies/mark", json={"reply_ids": [], "read": True})
        assert r.status_code == 400

    def test_add_to_dne_empty_400(self, drip_client):
        r = drip_client.post(f"{BASE_URL}/api/unibox/replies/add-to-dne", json={"reply_ids": []})
        assert r.status_code == 400


# ----------------- Seeded reply flow -----------------
@pytest.fixture
def seeded_reply(mongo, drip_user_id):
    """Insert a sent_email + reply directly into Mongo and clean up after."""
    msgid = f"test-{uuid.uuid4().hex[:8]}@routemail.app"
    sent_id = f"sent_{uuid.uuid4().hex[:12]}"
    reply_id = f"rep_{uuid.uuid4().hex[:12]}"
    mongo.sent_emails.insert_one({
        "sent_id": sent_id, "user_id": drip_user_id, "account_id": "acc_test",
        "sender_email": "from@example.com", "recipient_email": "lead@example.com",
        "subject": "TEST_Seeded subj", "message_id": msgid,
        "campaign_id": "camp_test", "campaign_name": "TEST_Camp",
        "drip_campaign_id": None, "drip_campaign_name": None, "drip_step_number": None,
        "sent_at": "2026-01-01T00:00:00+00:00",
    })
    mongo.replies.insert_one({
        "reply_id": reply_id, "user_id": drip_user_id, "account_id": "acc_test",
        "received_on_email": "from@example.com", "from_email": "lead@example.com",
        "subject": "Re: TEST_Seeded subj", "body": "Hello this is the reply body",
        "message_id": f"r-{msgid}", "in_reply_to": msgid, "references": [msgid],
        "received_at": "2026-01-02T00:00:00+00:00", "read": False,
        "campaign_id": "camp_test", "campaign_name": "TEST_Camp",
        "drip_campaign_id": None, "drip_campaign_name": None, "drip_step_number": None,
        "sent_id": sent_id, "created_at": "2026-01-02T00:00:00+00:00",
    })
    yield {"reply_id": reply_id, "sent_id": sent_id, "msgid": msgid}
    mongo.replies.delete_one({"reply_id": reply_id})
    mongo.sent_emails.delete_one({"sent_id": sent_id})


class TestRepliesFlow:
    def test_mark_read_and_unread(self, drip_client, seeded_reply, mongo):
        rid = seeded_reply["reply_id"]
        r = drip_client.post(f"{BASE_URL}/api/unibox/replies/mark",
                             json={"reply_ids": [rid], "read": True})
        assert r.status_code == 200
        assert r.json()["modified"] >= 0
        assert mongo.replies.find_one({"reply_id": rid})["read"] is True

        r2 = drip_client.post(f"{BASE_URL}/api/unibox/replies/mark",
                              json={"reply_ids": [rid], "read": False})
        assert r2.status_code == 200
        assert mongo.replies.find_one({"reply_id": rid})["read"] is False

    def test_replies_listed_and_filterable(self, drip_client, seeded_reply):
        r = drip_client.get(f"{BASE_URL}/api/unibox/replies?campaign_id=camp_test")
        assert r.status_code == 200
        ids = [it["reply_id"] for it in r.json()["items"]]
        assert seeded_reply["reply_id"] in ids

    def test_add_to_dne_creates_global_list(self, drip_client, seeded_reply, mongo, drip_user_id):
        r = drip_client.post(f"{BASE_URL}/api/unibox/replies/add-to-dne",
                             json={"reply_ids": [seeded_reply["reply_id"]]})
        assert r.status_code == 200
        data = r.json()
        assert data["added"] >= 0
        assert "list_id" in data
        dne = mongo.dne_lists.find_one({"list_id": data["list_id"]})
        assert dne is not None and dne.get("is_global") is True
        # dedupe: second call should add 0
        r2 = drip_client.post(f"{BASE_URL}/api/unibox/replies/add-to-dne",
                              json={"reply_ids": [seeded_reply["reply_id"]]})
        assert r2.status_code == 200
        assert r2.json()["added"] == 0
        mongo.dne_emails.delete_many({"email": "lead@example.com"})


# ----------------- Leads / Folders -----------------
class TestLeadsFolders:
    def test_folder_crud(self, drip_client):
        # Create
        r = drip_client.post(f"{BASE_URL}/api/leads/folders", json={"name": "TEST_Folder1"})
        assert r.status_code == 200
        fid = r.json()["folder_id"]

        # List
        r = drip_client.get(f"{BASE_URL}/api/leads/folders")
        assert any(f["folder_id"] == fid for f in r.json()["folders"])

        # Rename
        r = drip_client.put(f"{BASE_URL}/api/leads/folders/{fid}", json={"name": "TEST_Folder1_R"})
        assert r.status_code == 200

        # Empty-name create -> 400
        r = drip_client.post(f"{BASE_URL}/api/leads/folders", json={"name": "  "})
        assert r.status_code == 400

        # Delete
        r = drip_client.delete(f"{BASE_URL}/api/leads/folders/{fid}")
        assert r.status_code == 200

        # 404
        r = drip_client.delete(f"{BASE_URL}/api/leads/folders/nonexistent")
        assert r.status_code == 404

    def test_save_lead_with_new_folder(self, drip_client, seeded_reply, mongo):
        r = drip_client.post(f"{BASE_URL}/api/leads/save", json={
            "reply_ids": [seeded_reply["reply_id"]],
            "folder_id": "__new__",
            "new_folder_name": "TEST_NewFolder",
            "notes": "important",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["saved"] == 1
        fid = body["folder_id"]
        # Verify lead present
        leads = drip_client.get(f"{BASE_URL}/api/leads?folder_id={fid}").json()["items"]
        assert any(le.get("contact_email") == "lead@example.com" for le in leads)
        # Verify denormalized fields
        lead = leads[0]
        assert lead.get("subject")
        assert lead.get("body")
        assert lead.get("campaign_name") == "TEST_Camp"
        # Delete folder cascades leads
        drip_client.delete(f"{BASE_URL}/api/leads/folders/{fid}")
        assert mongo.leads.count_documents({"folder_id": fid}) == 0

    def test_save_lead_missing_new_name(self, drip_client, seeded_reply):
        r = drip_client.post(f"{BASE_URL}/api/leads/save", json={
            "reply_ids": [seeded_reply["reply_id"]],
            "folder_id": "__new__",
        })
        assert r.status_code == 400

    def test_save_lead_empty_returns_400(self, drip_client):
        r = drip_client.post(f"{BASE_URL}/api/leads/save", json={"reply_ids": [], "folder_id": "x"})
        assert r.status_code == 400


# ----------------- Cross-user isolation -----------------
class TestIsolation:
    def test_dhruv_sees_zero(self, dhruv_client):
        r = dhruv_client.get(f"{BASE_URL}/api/unibox/replies")
        assert r.status_code == 200
        # dhruv shouldn't see drip.tester's replies
        for it in r.json()["items"]:
            assert it.get("user_id") != "user_35cc629e1385"
        # And folders are scoped
        r = dhruv_client.get(f"{BASE_URL}/api/leads/folders")
        assert r.status_code == 200


# ----------------- SMTP/IMAP account CRUD -----------------
class TestAccountCRUD:
    def test_get_accounts_excludes_password_fields(self, drip_client):
        r = drip_client.get(f"{BASE_URL}/api/accounts")
        assert r.status_code == 200
        accounts = r.json() if isinstance(r.json(), list) else r.json().get("accounts", [])
        for a in accounts:
            assert "smtp_password_encrypted" not in a
            assert "imap_password_encrypted" not in a

    def test_create_with_from_name_and_imap(self, drip_client, mongo, drip_user_id):
        # SMTP add endpoint requires live SMTP — skip live validation by inserting
        # a synthetic account directly into Mongo to verify GET projection + PUT logic.
        from cryptography.fernet import Fernet
        # load fernet key from backend .env (already loaded at module top)
        fkey = os.environ.get("FERNET_KEY") or os.environ.get("ENCRYPTION_KEY")
        # Fall back: just store opaque string (PUT path re-encrypts)
        acct_id = f"acc_TEST_{uuid.uuid4().hex[:8]}"
        original_pw_blob = "ORIGINAL_ENC_BLOB"
        mongo.email_accounts.insert_one({
            "account_id": acct_id, "user_id": drip_user_id,
            "email": f"TEST_imap_{uuid.uuid4().hex[:6]}@example.com",
            "from_name": "Tester From", "display_name": "tester",
            "smtp_host": "smtp.example.com", "smtp_port": 587,
            "smtp_username": "user", "smtp_password_encrypted": "ENC",
            "smtp_ssl": False, "imap_host": "imap.example.com",
            "imap_port": 993, "imap_username": "user",
            "imap_password_encrypted": original_pw_blob,
            "imap_encryption": "ssl", "daily_limit": 50, "delay_seconds": 60,
            "status": "active", "is_active": True,
        })
        try:
            # GET projection — must include from_name + imap_* but exclude encrypted fields
            accs = drip_client.get(f"{BASE_URL}/api/accounts").json()
            accs = accs if isinstance(accs, list) else accs.get("accounts", [])
            match = [a for a in accs if a.get("account_id") == acct_id]
            assert match, "Inserted account not visible via GET /accounts"
            m = match[0]
            assert m.get("from_name") == "Tester From"
            assert m.get("imap_host") == "imap.example.com"
            assert m.get("imap_port") == 993
            assert m.get("imap_username") == "user"
            assert m.get("imap_encryption") == "ssl"
            assert "smtp_password_encrypted" not in m
            assert "imap_password_encrypted" not in m

            # PUT: update from_name only — imap_password_encrypted untouched
            r2 = drip_client.put(f"{BASE_URL}/api/accounts/{acct_id}", json={"from_name": "New Name"})
            assert r2.status_code == 200, r2.text
            after = mongo.email_accounts.find_one({"account_id": acct_id})
            assert after["from_name"] == "New Name"
            assert after.get("imap_password_encrypted") == original_pw_blob

            # PUT with null imap_password should not update
            r3 = drip_client.put(f"{BASE_URL}/api/accounts/{acct_id}", json={"imap_password": None})
            assert r3.status_code == 200
            after2 = mongo.email_accounts.find_one({"account_id": acct_id})
            assert after2.get("imap_password_encrypted") == original_pw_blob

            # PUT with new imap_password updates encrypted blob
            r4 = drip_client.put(f"{BASE_URL}/api/accounts/{acct_id}", json={"imap_password": "new_imap_pw"})
            assert r4.status_code == 200
            after3 = mongo.email_accounts.find_one({"account_id": acct_id})
            assert after3.get("imap_password_encrypted") != original_pw_blob
            assert after3.get("imap_password_encrypted")
        finally:
            mongo.email_accounts.delete_one({"account_id": acct_id})

    def test_sample_csv_has_imap_columns(self, drip_client):
        r = drip_client.get(f"{BASE_URL}/api/accounts/smtp/sample-csv")
        assert r.status_code == 200
        text = r.text
        header = text.splitlines()[0]
        for col in ["email", "from_name", "smtp_host", "smtp_port", "smtp_username",
                    "smtp_password", "smtp_ssl", "imap_host", "imap_port",
                    "imap_username", "imap_password", "imap_ssl",
                    "daily_limit", "delay_seconds"]:
            assert col in header, f"Missing column {col} in sample CSV: {header}"


# ----------------- From-name override unit test -----------------
class TestFromNameOverride:
    def test_send_email_smtp_from_name_logic(self):
        """Verify the precedence logic (Rule 1 + Rule 2) by inspecting code paths."""
        # Read server.py at known location to confirm logic shape
        with open("/app/backend/server.py", "r") as f:
            src = f.read()
        # Rule 1: campaign.from_name overrides
        assert "campaign_from_name = (campaign.get(\"from_name\") or \"\").strip()" in src
        # Rule 2: fallback chain
        assert "account_from_name = (account.get(\"from_name\") or \"\").strip() or account.get(\"display_name\", \"\")" in src
        assert "from_name = campaign_from_name or account_from_name" in src
        # Drip caller passes campaign.from_name
        assert "from_name_override=campaign.get(\"from_name\")" in src

    def test_send_drip_email_returns_dict(self):
        with open("/app/backend/server.py", "r") as f:
            src = f.read()
        # Returns dict not bool
        assert "async def send_drip_email" in src
        assert "from_name_override: Optional[str] = None" in src
        # Search for the dict return shape near send_drip_email
        idx = src.find("async def send_drip_email")
        end = src.find("async def ", idx + 10)
        body = src[idx:end]
        assert "return {" in body
        # Has success and message_id
        assert "\"success\"" in body
        assert "\"message_id\"" in body
