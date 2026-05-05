"""
Iteration 29 — Backend test coverage:
1. Public Blog endpoints + Super-admin Blog CRUD
2. Standard campaign send_range slicing
3. Drip campaign send_range enrollment
4. GET /api/accounts/{id}/credential (decrypted SMTP password)
5. Daily limit validation (min=1, no max)
"""
import os
import asyncio
import uuid
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

def _read_frontend_env(key: str) -> str:
    try:
        with open('/app/frontend/.env') as f:
            for line in f:
                if line.startswith(key + '='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ''

BASE_URL = (os.environ.get('REACT_APP_BACKEND_URL') or _read_frontend_env('REACT_APP_BACKEND_URL')).rstrip('/')
assert BASE_URL, "REACT_APP_BACKEND_URL not set"
API = f"{BASE_URL}/api"
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

DRIP_USER_EMAIL = "drip.tester@example.com"
DRIP_USER_PASS = "DripTest123!"


# ---------- shared fixtures ----------

@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": DRIP_USER_EMAIL, "password": DRIP_USER_PASS})
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def me(session):
    r = session.get(f"{API}/auth/me")
    assert r.status_code == 200
    return r.json()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def db(event_loop):
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


# ---------- helpers ----------

async def _set_role(db, user_id: str, role: str):
    await db.users.update_one({"user_id": user_id}, {"$set": {"role": role}})


def _make_list_with_n(session, n: int, prefix: str):
    """Create an email list with n contacts directly via /api/lists."""
    name = f"TEST_iter29_{prefix}_{uuid.uuid4().hex[:6]}"
    emails = [{"email": f"iter29_{prefix}_{i}@example.com"} for i in range(1, n + 1)]
    r = session.post(f"{API}/lists", json={
        "name": name,
        "original_filename": f"{name}.csv",
        "column_headers": ["email"],
        "emails": emails,
    })
    assert r.status_code in (200, 201), r.text
    return r.json()["list_id"]


# ============================================================
# 1) BLOG ENDPOINTS
# ============================================================

class TestBlogEndpoints:

    def test_public_list_blogs_no_auth(self):
        r = requests.get(f"{API}/blogs/public")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_list_requires_super_admin(self, session):
        r = session.get(f"{API}/admin/blogs")
        assert r.status_code == 403, f"Non-admin should be 403, got {r.status_code}"

    def test_admin_create_blocked_for_regular_user(self, session):
        r = session.post(f"{API}/admin/blogs", json={
            "title": "Should fail", "content": "x", "status": "draft"
        })
        assert r.status_code == 403

    def test_admin_crud_full_cycle(self, session, me, db, event_loop):
        """Promote to super_admin, create→get→update→publish→list public→delete→404."""
        uid = me["user_id"]
        original_role = me.get("role", "user")
        try:
            event_loop.run_until_complete(_set_role(db, uid, "super_admin"))

            payload = {
                "title": f"TEST_iter29 Blog {uuid.uuid4().hex[:6]}",
                "excerpt": "Excerpt",
                "content": "<p>Hello world</p>",
                "author": "QA",
                "status": "draft",
            }
            r = session.post(f"{API}/admin/blogs", json=payload)
            assert r.status_code == 200, r.text
            blog = r.json()
            assert blog["title"] == payload["title"]
            assert blog["status"] == "draft"
            assert blog["slug"]
            blog_id, slug = blog["blog_id"], blog["slug"]

            # GET admin
            r = session.get(f"{API}/admin/blogs/{blog_id}")
            assert r.status_code == 200
            assert r.json()["blog_id"] == blog_id

            # While draft → not on public listing
            r = requests.get(f"{API}/blogs/public/{slug}")
            assert r.status_code == 404

            # Publish
            r = session.put(f"{API}/admin/blogs/{blog_id}", json={"status": "published"})
            assert r.status_code == 200
            assert r.json()["status"] == "published"
            assert r.json().get("published_at")

            # Public detail
            r = requests.get(f"{API}/blogs/public/{slug}")
            assert r.status_code == 200
            assert r.json()["title"] == payload["title"]

            # Public list contains it
            r = requests.get(f"{API}/blogs/public")
            assert r.status_code == 200
            assert any(b["blog_id"] == blog_id for b in r.json())

            # Delete
            r = session.delete(f"{API}/admin/blogs/{blog_id}")
            assert r.status_code == 200

            # 404 after delete
            r = requests.get(f"{API}/blogs/public/{slug}")
            assert r.status_code == 404
        finally:
            event_loop.run_until_complete(_set_role(db, uid, original_role))


# ============================================================
# 2) STANDARD CAMPAIGN SEND_RANGE
# ============================================================

class TestStandardCampaignSendRange:

    def _make_account(self, session):
        r = session.post(f"{API}/accounts/smtp", json={
            "email": f"iter29_acc_{uuid.uuid4().hex[:6]}@example.com",
            "smtp_host": "smtp.example.com", "smtp_port": 587,
            "smtp_username": "user", "smtp_password": "pwd",
            "smtp_encryption": "tls", "from_name": "QA", "daily_limit": 50
        })
        # Test account creation may fail SMTP test → fall back to direct DB seed via /accounts/manual or skip
        if r.status_code not in (200, 201):
            pytest.skip(f"Could not create SMTP test account: {r.status_code} {r.text[:120]}")
        return r.json().get("account_id") or r.json().get("id")

    def test_send_range_mode_range_persists(self, session):
        list_id = _make_list_with_n(session, 5, "rangepersist")
        try:
            r = session.post(f"{API}/campaigns", json={
                "name": "TEST_iter29_range",
                "subject": "Hi", "body": "<p>x</p>",
                "list_id": list_id,
                "account_ids": [],
                "send_range_mode": "range",
                "send_range_start": 2,
                "send_range_end": 4,
            })
            assert r.status_code in (200, 201), r.text
            cid = r.json().get("campaign_id") or r.json().get("id")

            # Read back
            r = session.get(f"{API}/campaigns/{cid}")
            assert r.status_code == 200
            c = r.json()
            assert c["send_range_mode"] == "range"
            assert c["send_range_start"] == 2
            assert c["send_range_end"] == 4
        finally:
            session.delete(f"{API}/lists/{list_id}")

    def test_send_range_all_persists(self, session):
        list_id = _make_list_with_n(session, 3, "allpersist")
        try:
            r = session.post(f"{API}/campaigns", json={
                "name": "TEST_iter29_all",
                "subject": "Hi", "body": "<p>x</p>",
                "list_id": list_id,
                "account_ids": [],
                "send_range_mode": "all",
            })
            assert r.status_code in (200, 201), r.text
            cid = r.json().get("campaign_id") or r.json().get("id")
            r = session.get(f"{API}/campaigns/{cid}")
            assert r.status_code == 200
            assert r.json()["send_range_mode"] == "all"
        finally:
            session.delete(f"{API}/lists/{list_id}")


# ============================================================
# 3) DRIP CAMPAIGN SEND_RANGE
# ============================================================

class TestDripSendRange:

    def _make_drip(self, session):
        r = session.post(f"{API}/drip-campaigns", json={
            "name": f"TEST_iter29_drip_{uuid.uuid4().hex[:6]}",
            "account_ids": [],
            "steps": [{"step_number": 1, "subject": "S1", "body": "<p>1</p>",
                       "delay_days": 0, "delay_hours": 0}]
        })
        assert r.status_code in (200, 201), r.text
        return r.json().get("drip_id") or r.json().get("id")

    def test_drip_range_enrolls_only_slice(self, session):
        list_id = _make_list_with_n(session, 5, "driprange")
        drip_id = self._make_drip(session)
        try:
            r = session.post(f"{API}/drip-campaigns/{drip_id}/contacts", json={
                "list_id": list_id,
                "send_range_mode": "range",
                "send_range_start": 2,
                "send_range_end": 4,
            })
            assert r.status_code in (200, 201), r.text
            assert r.json()["added"] == 3, r.json()

            r = session.get(f"{API}/drip-campaigns/{drip_id}/contacts")
            assert r.status_code == 200
            data = r.json()
            contacts = data.get("contacts") if isinstance(data, dict) else data
            emails = sorted([c["email"] for c in contacts])
            assert emails == [
                "iter29_driprange_2@example.com",
                "iter29_driprange_3@example.com",
                "iter29_driprange_4@example.com",
            ]
        finally:
            session.delete(f"{API}/drip-campaigns/{drip_id}")
            session.delete(f"{API}/lists/{list_id}")

    def test_drip_all_enrolls_everyone(self, session):
        list_id = _make_list_with_n(session, 4, "dripall")
        drip_id = self._make_drip(session)
        try:
            r = session.post(f"{API}/drip-campaigns/{drip_id}/contacts", json={
                "list_id": list_id, "send_range_mode": "all"
            })
            assert r.status_code in (200, 201), r.text
            assert r.json()["added"] == 4
        finally:
            session.delete(f"{API}/drip-campaigns/{drip_id}")
            session.delete(f"{API}/lists/{list_id}")

    def test_drip_missing_send_range_defaults_to_all(self, session):
        list_id = _make_list_with_n(session, 3, "dripdef")
        drip_id = self._make_drip(session)
        try:
            r = session.post(f"{API}/drip-campaigns/{drip_id}/contacts",
                             json={"list_id": list_id})
            assert r.status_code in (200, 201), r.text
            assert r.json()["added"] == 3
        finally:
            session.delete(f"{API}/drip-campaigns/{drip_id}")
            session.delete(f"{API}/lists/{list_id}")


# ============================================================
# 4) ACCOUNT CREDENTIAL RETRIEVAL
# ============================================================

class TestAccountCredential:
    """The implemented endpoint is /api/accounts/{id}/credential (review request said /password)."""

    def test_credential_returns_decrypted_password(self, session, db, event_loop, me):
        # Seed an account directly into Mongo so we don't need real SMTP
        from cryptography.fernet import Fernet
        # use the same fernet as backend if available
        try:
            import sys
            sys.path.insert(0, '/app/backend')
            from server import fernet  # type: ignore
        except Exception:
            pytest.skip("Cannot import backend fernet for seeding")
        uid = me["user_id"]
        acct_id = f"acc_TEST_iter29_{uuid.uuid4().hex[:6]}"
        plain = "S3cretP@ss!"
        enc = fernet.encrypt(plain.encode()).decode()

        async def _seed():
            await db.email_accounts.insert_one({
                "account_id": acct_id, "user_id": uid, "type": "smtp",
                "email": f"{acct_id}@example.com",
                "smtp_host": "smtp.example.com", "smtp_port": 587,
                "smtp_username": "u", "smtp_password_encrypted": enc,
                "smtp_encryption": "tls", "daily_limit": 50,
            })
        async def _cleanup():
            await db.email_accounts.delete_one({"account_id": acct_id})

        event_loop.run_until_complete(_seed())
        try:
            r = session.get(f"{API}/accounts/{acct_id}/credential")
            assert r.status_code == 200, r.text
            assert r.json().get("smtp_password") == plain

            # Unknown account → 404
            r = session.get(f"{API}/accounts/acc_does_not_exist/credential")
            assert r.status_code == 404
        finally:
            event_loop.run_until_complete(_cleanup())

    def test_credential_unauth(self):
        r = requests.get(f"{API}/accounts/acc_anything/credential")
        assert r.status_code in (401, 403)


# ============================================================
# 5) DAILY LIMIT VALIDATION (min=1, no max)
# ============================================================

class TestDailyLimit:

    def test_daily_limit_high_value_accepted(self, session, db, event_loop, me):
        # Direct seed → PUT → read back
        uid = me["user_id"]
        acct_id = f"acc_TEST_iter29dl_{uuid.uuid4().hex[:6]}"

        async def _seed():
            await db.email_accounts.insert_one({
                "account_id": acct_id, "user_id": uid, "type": "smtp",
                "email": f"{acct_id}@example.com",
                "smtp_host": "smtp.example.com", "smtp_port": 587,
                "smtp_username": "u", "smtp_password_encrypted": "x",
                "smtp_encryption": "tls", "daily_limit": 50,
            })
        async def _cleanup():
            await db.email_accounts.delete_one({"account_id": acct_id})

        event_loop.run_until_complete(_seed())
        try:
            # very large value OK
            r = session.put(f"{API}/accounts/{acct_id}", json={"daily_limit": 99999})
            assert r.status_code == 200, r.text

            # Read back
            r = session.get(f"{API}/accounts/{acct_id}")
            assert r.status_code == 200
            assert r.json()["daily_limit"] == 99999

            r = session.put(f"{API}/accounts/{acct_id}", json={"daily_limit": 1})
            assert r.status_code == 200
            r = session.get(f"{API}/accounts/{acct_id}")
            assert r.json()["daily_limit"] == 1

            # 0 / negative → backend normalizes to 1 (per iter28 contract)
            r = session.put(f"{API}/accounts/{acct_id}", json={"daily_limit": 0})
            assert r.status_code in (200, 400)
            if r.status_code == 200:
                r = session.get(f"{API}/accounts/{acct_id}")
                assert r.json()["daily_limit"] == 1
        finally:
            event_loop.run_until_complete(_cleanup())
