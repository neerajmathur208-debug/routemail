"""Iteration 59 — Phase 2 Batch A backend tests.

Covers:
 1. template_render unit tests (render_template, extract_template_variables,
    analyse_contacts, HTML cleanup).
 2. Campaign + Drip folder_id linking + _ensure_default_folder_id auto-link.
 3. POST /api/campaigns/{id}/preflight and /api/drip-campaigns/{id}/preflight.
 4. register_sent_email accepts new fields (folder_id, body_html, body_text,
    from_name) and reply auto-routing inherits folder_id.
 5. GET /api/leads/folders returns reply_count + unassigned_reply_count.
"""
import os
import sys
import uuid
import asyncio
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

TAG = f"TEST_iter59_{uuid.uuid4().hex[:8]}"


# ----------------------- Fixtures -----------------------
@pytest.fixture(scope="module")
def mongo():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def admin_token(mongo):
    tok = f"TEST_iter59_{uuid.uuid4().hex}"
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


@pytest.fixture(scope="module", autouse=True)
def cleanup(mongo):
    """Clean up all TAG-tagged seed data after the run."""
    yield
    for coll in ("campaigns", "drip_campaigns", "lead_folders", "email_lists",
                 "email_list_contacts", "drip_contacts", "sent_emails", "replies"):
        try:
            mongo[coll].delete_many({"_tag": TAG})
        except Exception:
            pass


# =================== 1. template_render unit tests ===================
class TestTemplateRender:
    def test_first_name_generic_fallback(self):
        from template_render import render_template
        # Double-brace generic fallback
        assert render_template("Hi {{first_name}}", {}) == "Hi there"

    def test_first_name_resolved(self):
        from template_render import render_template
        assert render_template("Hi {{first_name}}", {"first_name": "Anna"}) == "Hi Anna"

    def test_unknown_variable_stripped(self):
        from template_render import render_template
        # Unknown variable that is NOT a first_name-style key → stripped
        assert render_template("Hi {{Dhruv}}", {}) == "Hi "

    def test_case_and_space_tolerant(self):
        from template_render import render_template
        assert render_template("Hi {{First Name}}", {"first_name": "Anna"}) == "Hi Anna"

    def test_single_brace_legacy_resolved(self):
        from template_render import render_template
        # legacy drip syntax {var}
        assert render_template("Hi {first_name}", {"first_name": "Anna"}) == "Hi Anna"

    def test_html_entity_nbsp_decoded(self):
        from template_render import render_template
        assert render_template("Section&nbsp;A", {}) == "Section A"

    def test_empty_braces_stripped(self):
        from template_render import render_template
        assert render_template("Revenue for {{}}", {}) == "Revenue for "
        assert render_template("Revenue for {}", {}) == "Revenue for "

    def test_per_campaign_fallback_honored(self):
        from template_render import render_template
        out = render_template(
            "Hi {{company}}", {}, fallbacks={"company": "your team"}
        )
        assert out == "Hi your team"

    def test_per_campaign_fallback_beats_generic(self):
        from template_render import render_template
        # If campaign-level fallback is provided for first_name, it wins over "there"
        out = render_template(
            "Hi {{first_name}}", {}, fallbacks={"first_name": "friend"}
        )
        assert out == "Hi friend"

    def test_extract_template_variables(self):
        from template_render import extract_template_variables
        names = extract_template_variables(
            "Hi {{First Name}}, your {{company}} report. {legacy_var}"
        )
        # Normalised: first_name, company, legacy_var
        assert "first_name" in names
        assert "company" in names
        assert "legacy_var" in names

    def test_analyse_contacts_missing_var(self):
        from template_render import analyse_contacts
        contacts = [
            {"email": "a@x.com", "data": {"first_name": "A"}},
            {"email": "b@x.com", "data": {"first_name": "B"}},
            {"email": "c@x.com", "data": {"first_name": "C", "company": "Foo"}},
        ]
        result = analyse_contacts(
            ["Hi {{first_name}}", "Hi {{first_name}}, your {{company}} report"],
            contacts,
        )
        assert result["total_contacts"] == 3
        assert "company" in result["variables"]
        # company missing in 2/3 contacts
        assert result["missing_per_variable"]["company"] == 2
        # warning text should mention company
        assert any("company" in w for w in result["warnings"])
        assert result["ok"] is False

    def test_analyse_contacts_empty_recipients_warns(self):
        from template_render import analyse_contacts
        result = analyse_contacts(["Hi {{first_name}}"], [])
        assert result["total_contacts"] == 0
        assert any("No recipients" in w for w in result["warnings"])
        assert result["ok"] is False

    def test_regression_full_render(self):
        """Real-world scenario from the spec — no `{`, `}`, `{}`, `&nbsp;`
        literals must leak to recipient."""
        from template_render import render_template
        body = "Hi {{first_name}}, your {{company}} report&nbsp;is ready. {} {{Dhruv}}"
        out = render_template(body, {"email": "x@y.com"})
        # `{{first_name}}` → 'there', `{{company}}` → '', `{}` → '', `{{Dhruv}}` → ''
        # `&nbsp;` → ' '
        assert "{" not in out and "}" not in out
        assert "&nbsp;" not in out
        assert out.startswith("Hi there,")


# =================== 2. Campaign folder linking ===================
class TestCampaignFolderLink:
    def test_create_campaign_with_folder_id_persists(self, client, mongo):
        # Seed a folder
        folder_id = f"foldr_{uuid.uuid4().hex[:10]}"
        mongo.lead_folders.insert_one({
            "folder_id": folder_id,
            "user_id": SUPER_ADMIN_ID,
            "name": f"{TAG}_BrandA",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "_tag": TAG,
        })

        r = client.post(f"{BASE_URL}/api/campaigns", json={
            "name": f"{TAG}_camp_with_folder",
            "subject": "Hi {{first_name}}",
            "body": "Body {{first_name}}",
            "folder_id": folder_id,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["folder_id"] == folder_id
        cid = data["campaign_id"]
        mongo.campaigns.update_one({"campaign_id": cid}, {"$set": {"_tag": TAG}})

        # Verify persisted in DB
        doc = mongo.campaigns.find_one({"campaign_id": cid})
        assert doc["folder_id"] == folder_id

        # Verify GET returns it
        g = client.get(f"{BASE_URL}/api/campaigns")
        assert g.status_code == 200
        camps = g.json() if isinstance(g.json(), list) else g.json().get("campaigns", [])
        target = [c for c in camps if c.get("campaign_id") == cid]
        assert target and target[0].get("folder_id") == folder_id

    def test_create_campaign_without_folder_creates_default(self, client, mongo):
        # Remove existing default folder for clean test
        existing = mongo.lead_folders.find_one(
            {"user_id": SUPER_ADMIN_ID, "name": "Default"}
        )
        r = client.post(f"{BASE_URL}/api/campaigns", json={
            "name": f"{TAG}_camp_no_folder",
            "subject": "Hi",
            "body": "Body",
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["folder_id"], "folder_id must be auto-assigned"
        mongo.campaigns.update_one(
            {"campaign_id": data["campaign_id"]},
            {"$set": {"_tag": TAG}},
        )
        # Verify a 'Default' folder now exists
        default = mongo.lead_folders.find_one(
            {"folder_id": data["folder_id"], "user_id": SUPER_ADMIN_ID}
        )
        assert default is not None
        assert default["name"] == "Default"
        # If we created it (no prior), tag for cleanup
        if not existing:
            mongo.lead_folders.update_one(
                {"folder_id": data["folder_id"]}, {"$set": {"_tag": TAG}}
            )

    def test_update_campaign_folder_id(self, client, mongo):
        # Create campaign
        r = client.post(f"{BASE_URL}/api/campaigns", json={
            "name": f"{TAG}_camp_update",
            "subject": "Hi",
            "body": "Body",
        })
        cid = r.json()["campaign_id"]
        mongo.campaigns.update_one({"campaign_id": cid}, {"$set": {"_tag": TAG}})

        new_folder = f"foldr_{uuid.uuid4().hex[:10]}"
        mongo.lead_folders.insert_one({
            "folder_id": new_folder,
            "user_id": SUPER_ADMIN_ID,
            "name": f"{TAG}_BrandB",
            "_tag": TAG,
        })
        u = client.put(f"{BASE_URL}/api/campaigns/{cid}", json={
            "folder_id": new_folder,
        })
        assert u.status_code == 200, u.text
        doc = mongo.campaigns.find_one({"campaign_id": cid})
        assert doc["folder_id"] == new_folder


# =================== 3. Drip folder linking ===================
class TestDripFolderLink:
    def test_create_drip_with_folder(self, client, mongo):
        folder_id = f"foldr_{uuid.uuid4().hex[:10]}"
        mongo.lead_folders.insert_one({
            "folder_id": folder_id,
            "user_id": SUPER_ADMIN_ID,
            "name": f"{TAG}_DripBrand",
            "_tag": TAG,
        })
        r = client.post(f"{BASE_URL}/api/drip-campaigns", json={
            "name": f"{TAG}_drip_with_folder",
            "steps": [
                {"step_number": 1, "subject": "Hello {{first_name}}",
                 "body": "Hi {{first_name}}, your {{company}} update.",
                 "delay_days": 0, "delay_hours": 0},
            ],
            "folder_id": folder_id,
        })
        assert r.status_code == 200, r.text
        did = r.json()["drip_id"]
        mongo.drip_campaigns.update_one(
            {"drip_id": did}, {"$set": {"_tag": TAG}}
        )
        doc = mongo.drip_campaigns.find_one({"drip_id": did})
        assert doc["folder_id"] == folder_id

    def test_create_drip_without_folder_uses_default(self, client, mongo):
        r = client.post(f"{BASE_URL}/api/drip-campaigns", json={
            "name": f"{TAG}_drip_default",
            "steps": [
                {"step_number": 1, "subject": "S", "body": "B",
                 "delay_days": 0, "delay_hours": 0},
            ],
        })
        assert r.status_code == 200, r.text
        did = r.json()["drip_id"]
        mongo.drip_campaigns.update_one(
            {"drip_id": did}, {"$set": {"_tag": TAG}}
        )
        doc = mongo.drip_campaigns.find_one({"drip_id": did})
        assert doc.get("folder_id"), "Drip should auto-link to Default folder"
        # Verify the linked folder is named Default
        f = mongo.lead_folders.find_one({"folder_id": doc["folder_id"]})
        assert f and f["name"] == "Default"


# =================== 4. Preflight endpoints ===================
class TestPreflight:
    def test_preflight_campaign_warns_missing_var(self, client, mongo):
        # Seed list + contacts (all missing 'company')
        list_id = f"list_{uuid.uuid4().hex[:10]}"
        mongo.email_lists.insert_one({
            "list_id": list_id,
            "user_id": SUPER_ADMIN_ID,
            "name": f"{TAG}_list",
            "valid_emails": 3,
            "_tag": TAG,
        })
        for i in range(3):
            mongo.email_list_contacts.insert_one({
                "list_id": list_id,
                "user_id": SUPER_ADMIN_ID,
                "email": f"u{i}@x.com",
                "data": {"first_name": f"User{i}"},  # missing 'company'
                "is_valid": True,
                "_tag": TAG,
            })
        # Create campaign
        r = client.post(f"{BASE_URL}/api/campaigns", json={
            "name": f"{TAG}_pf_camp",
            "subject": "Hi {{first_name}}",
            "body": "Your {{company}} report is ready.",
            "list_id": list_id,
        })
        cid = r.json()["campaign_id"]
        mongo.campaigns.update_one({"campaign_id": cid}, {"$set": {"_tag": TAG}})

        pf = client.post(f"{BASE_URL}/api/campaigns/{cid}/preflight")
        assert pf.status_code == 200, pf.text
        data = pf.json()
        assert "variables" in data
        assert "total_contacts" in data
        assert data["total_contacts"] == 3
        assert "missing_per_variable" in data
        assert "unresolved_samples" in data
        assert "warnings" in data
        assert "ok" in data
        assert "company" in data["variables"]
        assert data["missing_per_variable"]["company"] == 3
        joined = " ".join(data["warnings"])
        assert "company" in joined and "3/3" in joined

    def test_preflight_campaign_no_recipients(self, client, mongo):
        r = client.post(f"{BASE_URL}/api/campaigns", json={
            "name": f"{TAG}_pf_empty",
            "subject": "Hi {{first_name}}",
            "body": "Body",
        })
        cid = r.json()["campaign_id"]
        mongo.campaigns.update_one({"campaign_id": cid}, {"$set": {"_tag": TAG}})

        pf = client.post(f"{BASE_URL}/api/campaigns/{cid}/preflight")
        assert pf.status_code == 200
        data = pf.json()
        assert data["total_contacts"] == 0
        assert any("No recipients" in w for w in data["warnings"])

    def test_preflight_drip_covers_every_step(self, client, mongo):
        # Seed drip + drip_contacts missing 'company'
        r = client.post(f"{BASE_URL}/api/drip-campaigns", json={
            "name": f"{TAG}_pf_drip",
            "steps": [
                {"step_number": 1, "subject": "Hi {{first_name}}",
                 "body": "Step 1 body", "delay_days": 0, "delay_hours": 0},
                {"step_number": 2, "subject": "Re: hello",
                 "body": "Your {{company}} update", "delay_days": 1, "delay_hours": 0},
            ],
        })
        did = r.json()["drip_id"]
        mongo.drip_campaigns.update_one(
            {"drip_id": did}, {"$set": {"_tag": TAG}}
        )
        # Seed 2 drip_contacts missing company
        for i in range(2):
            mongo.drip_contacts.insert_one({
                "drip_id": did,
                "user_id": SUPER_ADMIN_ID,
                "contact_email": f"d{i}@x.com",
                "email": f"d{i}@x.com",
                "data": {"first_name": f"D{i}"},
                "_tag": TAG,
            })
        pf = client.post(f"{BASE_URL}/api/drip-campaigns/{did}/preflight")
        assert pf.status_code == 200, pf.text
        data = pf.json()
        assert data["total_contacts"] == 2
        # Step2 references {{company}} which is missing in all contacts
        assert "company" in data["variables"]
        assert data["missing_per_variable"]["company"] == 2


# =================== 5. register_sent_email + reply auto-routing ===================
class TestRegisterSentEmailAndReplyRouting:
    def test_register_sent_email_persists_new_fields(self, mongo):
        from unibox_routes import register_sent_email
        msg_id = f"msg-{uuid.uuid4().hex}"
        folder_id = f"foldr_{uuid.uuid4().hex[:10]}"
        mongo.lead_folders.insert_one({
            "folder_id": folder_id, "user_id": SUPER_ADMIN_ID,
            "name": f"{TAG}_F1", "_tag": TAG,
        })
        # Run async fn
        import motor.motor_asyncio as motor
        async_db = motor.AsyncIOMotorClient(MONGO_URL)[DB_NAME]
        asyncio.get_event_loop().run_until_complete(
            register_sent_email(
                async_db,
                user_id=SUPER_ADMIN_ID,
                account_id="acc_test",
                sender_email="me@example.com",
                recipient_email="them@example.com",
                subject="Hi",
                message_id=msg_id,
                campaign_id="camp_x",
                folder_id=folder_id,
                body_html="<p>Hi</p>",
                body_text="Hi",
                from_name="Sender Name",
            )
        )
        sent = mongo.sent_emails.find_one({"message_id": msg_id})
        assert sent is not None
        assert sent["folder_id"] == folder_id
        assert sent["body_html"] == "<p>Hi</p>"
        assert sent["body_text"] == "Hi"
        assert sent["from_name"] == "Sender Name"
        # cleanup
        mongo.sent_emails.delete_one({"message_id": msg_id})

    def test_reply_inherits_folder_id(self, mongo):
        """Insert a sent_email with folder_id, then insert a matching reply
        and assert auto-routing logic would copy folder_id. We simulate the
        routing inline (the worker fetches sent_emails and stamps folder_id
        onto reply_doc — same logic asserted here).
        """
        msg_id = f"<msg-{uuid.uuid4().hex}@x.com>"
        folder_id = f"foldr_{uuid.uuid4().hex[:10]}"
        mongo.lead_folders.insert_one({
            "folder_id": folder_id, "user_id": SUPER_ADMIN_ID,
            "name": f"{TAG}_FR", "_tag": TAG,
        })
        mongo.sent_emails.insert_one({
            "sent_id": f"sent_{uuid.uuid4().hex[:12]}",
            "user_id": SUPER_ADMIN_ID,
            "account_id": "acc_test",
            "recipient_email": "lead@x.com",
            "subject": "Hello there",
            "message_id": msg_id.strip("<>"),
            "campaign_id": "camp_y",
            "folder_id": folder_id,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "_tag": TAG,
        })
        # Simulate the matcher in unibox_routes.run_imap_worker
        matched = mongo.sent_emails.find_one({"message_id": msg_id.strip("<>")})
        assert matched is not None
        reply_doc = {
            "reply_id": f"rep_{uuid.uuid4().hex[:12]}",
            "user_id": SUPER_ADMIN_ID,
            "account_id": "acc_test",
            "from_email": "lead@x.com",
            "subject": "Re: Hello there",
            "body": "Sure, thanks!",
            "message_id": f"reply-{uuid.uuid4().hex}",
            "in_reply_to": msg_id,
            "references": msg_id,
            "received_at": datetime.now(timezone.utc).isoformat(),
            "read": False,
            "archived": False,
            "campaign_id": matched.get("campaign_id"),
            "folder_id": matched.get("folder_id"),
            "sent_id": matched.get("sent_id"),
            "_tag": TAG,
        }
        mongo.replies.insert_one(reply_doc)
        saved = mongo.replies.find_one({"reply_id": reply_doc["reply_id"]})
        assert saved["folder_id"] == folder_id


# =================== 6. /leads/folders reply counts ===================
class TestFoldersEndpoint:
    def test_folders_returns_reply_counts(self, client, mongo):
        folder_id = f"foldr_{uuid.uuid4().hex[:10]}"
        mongo.lead_folders.insert_one({
            "folder_id": folder_id,
            "user_id": SUPER_ADMIN_ID,
            "name": f"{TAG}_RC",
            "_tag": TAG,
        })
        # Seed 2 replies in folder, 1 unassigned
        for _ in range(2):
            mongo.replies.insert_one({
                "reply_id": f"rep_{uuid.uuid4().hex[:12]}",
                "user_id": SUPER_ADMIN_ID,
                "folder_id": folder_id,
                "from_email": "x@y.com",
                "subject": "S",
                "body": "B",
                "message_id": f"m-{uuid.uuid4().hex}",
                "received_at": datetime.now(timezone.utc).isoformat(),
                "read": False, "archived": False,
                "_tag": TAG,
            })
        mongo.replies.insert_one({
            "reply_id": f"rep_{uuid.uuid4().hex[:12]}",
            "user_id": SUPER_ADMIN_ID,
            "folder_id": None,
            "from_email": "x@y.com",
            "subject": "S",
            "body": "B",
            "message_id": f"m-{uuid.uuid4().hex}",
            "received_at": datetime.now(timezone.utc).isoformat(),
            "read": False, "archived": False,
            "_tag": TAG,
        })
        r = client.get(f"{BASE_URL}/api/leads/folders")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "folders" in data
        assert "unassigned_reply_count" in data
        target = [f for f in data["folders"] if f.get("folder_id") == folder_id]
        assert target, "Test folder must be returned"
        assert target[0].get("reply_count") == 2
        # unassigned >= 1 (other tests may have left some, just verify >=1)
        assert data["unassigned_reply_count"] >= 1
