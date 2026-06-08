"""Iteration 49 — Blog Permission Management + Blog Backup/Restore.

Covers:
  • PUT /api/admin/users/{id}/blog-permission (grant/revoke, super-admin only)
  • /api/admin/blogs* gated by get_blog_manager_user (super_admin OR can_manage_blogs)
  • /api/auth/me + /api/admin/users include can_manage_blogs flag
  • /api/admin/backup/blogs/export (GET + POST), import (skip/merge/replace/copy)
  • /api/admin/backup/export/users include_blogs flag
  • /api/admin/backup/export/full + /api/admin/backup/import regression
  • Generic regression on existing protected endpoints
"""
import io
import json
import os
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

SUPER_ADMIN_ID = "user_b3e333b0f467"  # dhruvmathur208@gmail.com
NORMAL_USER_ID = "user_35cc629e1385"  # drip.tester@example.com


# ------------------------------------------------------------------
# Fixtures — inject session_token rows directly to bypass Turnstile
# ------------------------------------------------------------------
@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


def _make_session(db, user_id):
    token = f"TEST_iter49_{uuid.uuid4().hex}"
    db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=2),
    })
    return token


def _client(token):
    s = requests.Session()
    s.cookies.set("session_token", token)
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def admin_token(mongo):
    tok = _make_session(mongo, SUPER_ADMIN_ID)
    yield tok
    mongo.user_sessions.delete_one({"session_token": tok})


@pytest.fixture(scope="module")
def user_token(mongo):
    tok = _make_session(mongo, NORMAL_USER_ID)
    yield tok
    mongo.user_sessions.delete_one({"session_token": tok})


@pytest.fixture(scope="module")
def admin(admin_token):
    return _client(admin_token)


@pytest.fixture(scope="module")
def user(user_token):
    return _client(user_token)


@pytest.fixture(autouse=True, scope="module")
def reset_perm(mongo):
    """Ensure normal user starts WITHOUT blog permission; revoke at end."""
    mongo.users.update_one({"user_id": NORMAL_USER_ID}, {"$set": {"can_manage_blogs": False}})
    yield
    mongo.users.update_one({"user_id": NORMAL_USER_ID}, {"$set": {"can_manage_blogs": False}})
    # cleanup any TEST_ blogs leaked
    mongo.blogs.delete_many({"title": {"$regex": "^TEST_iter49"}})


# ------------------------------------------------------------------
# 1. Permission grant / revoke endpoint
# ------------------------------------------------------------------
class TestBlogPermission:
    def test_revoked_user_blocked_from_admin_blogs(self, user, mongo):
        mongo.users.update_one({"user_id": NORMAL_USER_ID}, {"$set": {"can_manage_blogs": False}})
        r = user.get(f"{BASE_URL}/api/admin/blogs", timeout=15)
        assert r.status_code == 403, r.text

    def test_non_admin_cannot_grant(self, user):
        r = user.put(
            f"{BASE_URL}/api/admin/users/{NORMAL_USER_ID}/blog-permission",
            json={"can_manage_blogs": True}, timeout=15,
        )
        assert r.status_code == 403, r.text

    def test_admin_grants_permission(self, admin, mongo):
        r = admin.put(
            f"{BASE_URL}/api/admin/users/{NORMAL_USER_ID}/blog-permission",
            json={"can_manage_blogs": True}, timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("can_manage_blogs") is True
        # verify in mongo
        doc = mongo.users.find_one({"user_id": NORMAL_USER_ID}, {"_id": 0, "can_manage_blogs": 1})
        assert doc.get("can_manage_blogs") is True

    def test_auth_me_returns_flag_for_normal_user(self, user):
        r = user.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200, r.text
        assert "can_manage_blogs" in r.json()
        assert r.json()["can_manage_blogs"] is True

    def test_auth_me_returns_flag_for_super_admin(self, admin):
        r = admin.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 200, r.text
        assert "can_manage_blogs" in r.json()

    def test_admin_users_list_includes_flag(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/users", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        users = data if isinstance(data, list) else data.get("users", [])
        assert users, "empty users list"
        target = next((u for u in users if u.get("user_id") == NORMAL_USER_ID), None)
        assert target is not None
        assert "can_manage_blogs" in target

    def test_admin_revokes_permission(self, admin, mongo):
        r = admin.put(
            f"{BASE_URL}/api/admin/users/{NORMAL_USER_ID}/blog-permission",
            json={"can_manage_blogs": False}, timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("can_manage_blogs") is False
        doc = mongo.users.find_one({"user_id": NORMAL_USER_ID}, {"_id": 0, "can_manage_blogs": 1})
        assert doc.get("can_manage_blogs") is False


# ------------------------------------------------------------------
# 2. Delegated user (can_manage_blogs=true) CRUD on /admin/blogs
# ------------------------------------------------------------------
class TestDelegatedBlogCRUD:
    @pytest.fixture(scope="class", autouse=True)
    def grant_perm(self, mongo):
        mongo.users.update_one({"user_id": NORMAL_USER_ID}, {"$set": {"can_manage_blogs": True}})
        yield
        mongo.users.update_one({"user_id": NORMAL_USER_ID}, {"$set": {"can_manage_blogs": False}})

    def test_list_ok(self, user):
        r = user.get(f"{BASE_URL}/api/admin/blogs", timeout=15)
        assert r.status_code == 200, r.text

    def test_full_crud(self, user, mongo):
        slug = f"test-iter49-{uuid.uuid4().hex[:8]}"
        payload = {
            "title": f"TEST_iter49 Delegated Post {uuid.uuid4().hex[:6]}",
            "slug": slug,
            "content": "<p>hello</p>",
            "excerpt": "x",
            "status": "draft",
        }
        # CREATE
        r = user.post(f"{BASE_URL}/api/admin/blogs", json=payload, timeout=15)
        assert r.status_code in (200, 201), r.text
        body = r.json()
        blog_id = body.get("blog_id") or body.get("id") or body.get("blog", {}).get("blog_id")
        assert blog_id, f"no blog_id in {body}"

        try:
            # READ
            r = user.get(f"{BASE_URL}/api/admin/blogs/{blog_id}", timeout=15)
            assert r.status_code == 200, r.text
            assert r.json().get("title") == payload["title"] or r.json().get("blog", {}).get("title") == payload["title"]

            # UPDATE
            new_title = payload["title"] + " (upd)"
            r = user.put(
                f"{BASE_URL}/api/admin/blogs/{blog_id}",
                json={"title": new_title, "slug": slug, "content": "<p>u</p>", "excerpt": "u", "status": "draft"},
                timeout=15,
            )
            assert r.status_code == 200, r.text

            # persisted?
            doc = mongo.blogs.find_one({"blog_id": blog_id}, {"_id": 0})
            assert doc and doc.get("title") == new_title
        finally:
            r = user.delete(f"{BASE_URL}/api/admin/blogs/{blog_id}", timeout=15)
            assert r.status_code in (200, 204), r.text
            assert mongo.blogs.find_one({"blog_id": blog_id}) is None

    def test_upload_image(self, user):
        # 1x1 png
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff"
            b"\xff?\x03\x00\x06\xfc\x02\xfe\xa7\x6b\xc3@\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        files = {"file": ("a.png", png, "image/png")}
        # remove json content-type for multipart
        s = requests.Session()
        s.cookies.update(user.cookies)
        s.headers.update({"Authorization": user.headers["Authorization"]})
        r = s.post(f"{BASE_URL}/api/admin/blogs/upload-image", files=files, timeout=20)
        assert r.status_code in (200, 201), r.text


# ------------------------------------------------------------------
# 3. Blog Backup / Restore endpoints (super-admin only)
# ------------------------------------------------------------------
class TestBlogBackup:
    @pytest.fixture(scope="class")
    def seed_blog(self, mongo):
        """Create one persistent test blog used by export+import tests."""
        slug = f"iter49-seed-{uuid.uuid4().hex[:6]}"
        blog = {
            "blog_id": f"blog_{uuid.uuid4().hex[:12]}",
            "title": "TEST_iter49 Seed Blog",
            "slug": slug,
            "content": "<p>seed</p>",
            "excerpt": "seed",
            "status": "published",
            "featured_image_url": "data:image/png;base64,iVBORw0KGgo=",
        }
        mongo.blogs.insert_one(dict(blog))
        yield blog
        mongo.blogs.delete_many({"slug": {"$regex": f"^{slug}"}})
        mongo.blogs.delete_many({"blog_id": blog["blog_id"]})

    def test_export_all_blogs_super_admin(self, admin, seed_blog):
        r = admin.get(f"{BASE_URL}/api/admin/backup/blogs/export", timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert r.headers.get("content-type", "").startswith("application/zip")
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(zf.namelist())
        assert {"metadata.json", "blogs.json"}.issubset(names)
        blogs = json.loads(zf.read("blogs.json"))
        assert isinstance(blogs, list)
        ids = {b.get("blog_id") for b in blogs}
        assert seed_blog["blog_id"] in ids
        target = next(b for b in blogs if b.get("blog_id") == seed_blog["blog_id"])
        assert target.get("featured_image_url", "").startswith("data:image/png;base64,")

    def test_export_selected_blogs(self, admin, seed_blog):
        r = admin.post(
            f"{BASE_URL}/api/admin/backup/blogs/export",
            json={"blog_ids": [seed_blog["blog_id"]]}, timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        blogs = json.loads(zf.read("blogs.json"))
        assert [b["blog_id"] for b in blogs] == [seed_blog["blog_id"]]

    def test_export_blogs_forbidden_for_non_admin(self, user, mongo):
        # even with can_manage_blogs=true, export must remain super-admin only
        mongo.users.update_one({"user_id": NORMAL_USER_ID}, {"$set": {"can_manage_blogs": True}})
        try:
            r1 = user.get(f"{BASE_URL}/api/admin/backup/blogs/export", timeout=15)
            r2 = user.post(f"{BASE_URL}/api/admin/backup/blogs/export", json={"blog_ids": ["x"]}, timeout=15)
            r3 = user.post(f"{BASE_URL}/api/admin/backup/blogs/import", files={"file": ("a.zip", b"x", "application/zip")}, timeout=15)
            assert r1.status_code == 403, r1.text[:200]
            assert r2.status_code == 403, r2.text[:200]
            assert r3.status_code == 403, r3.text[:200]
        finally:
            mongo.users.update_one({"user_id": NORMAL_USER_ID}, {"$set": {"can_manage_blogs": False}})

    # ---- helper to build a blogs-only zip from a blog doc ----
    @staticmethod
    def _make_zip(blogs_payload):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("metadata.json", json.dumps({"backup_type": "blogs_all"}))
            zf.writestr("blogs.json", json.dumps(blogs_payload))
        buf.seek(0)
        return buf.read()

    def test_import_invalid_file_400(self, admin):
        # non-zip
        r = admin.post(
            f"{BASE_URL}/api/admin/backup/blogs/import",
            files={"file": ("a.zip", b"not a zip", "application/zip")},
            timeout=15,
        )
        assert r.status_code == 400, r.text[:300]
        # zip without blogs.json
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("other.json", "{}")
        buf.seek(0)
        r2 = admin.post(
            f"{BASE_URL}/api/admin/backup/blogs/import",
            files={"file": ("b.zip", buf.read(), "application/zip")},
            timeout=15,
        )
        assert r2.status_code == 400, r2.text[:300]

    def test_import_copy_creates_imported_variant(self, admin, mongo, seed_blog):
        payload = [dict(seed_blog)]
        zbytes = self._make_zip(payload)
        r = admin.post(
            f"{BASE_URL}/api/admin/backup/blogs/import?conflict=copy",
            files={"file": ("c.zip", zbytes, "application/zip")}, timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("copied", 0) >= 1
        # verify a new doc with -imported slug & (Imported) title exists
        copy_doc = mongo.blogs.find_one({"slug": f"{seed_blog['slug']}-imported"}, {"_id": 0})
        assert copy_doc is not None
        assert "(Imported)" in copy_doc.get("title", "")
        assert copy_doc["blog_id"] != seed_blog["blog_id"]
        # source intact
        assert mongo.blogs.find_one({"blog_id": seed_blog["blog_id"]}) is not None
        # cleanup
        mongo.blogs.delete_one({"blog_id": copy_doc["blog_id"]})

    def test_import_skip_keeps_existing(self, admin, mongo, seed_blog):
        # modify the seed blog so we can detect any unwanted overwrite
        mongo.blogs.update_one({"blog_id": seed_blog["blog_id"]}, {"$set": {"excerpt": "original-skip"}})
        modified = dict(seed_blog)
        modified["excerpt"] = "from-import"
        zbytes = self._make_zip([modified])
        r = admin.post(
            f"{BASE_URL}/api/admin/backup/blogs/import?conflict=skip",
            files={"file": ("s.zip", zbytes, "application/zip")}, timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("skipped", 0) >= 1
        doc = mongo.blogs.find_one({"blog_id": seed_blog["blog_id"]}, {"_id": 0})
        assert doc.get("excerpt") == "original-skip"

    def test_import_merge_updates_in_place(self, admin, mongo, seed_blog):
        modified = dict(seed_blog)
        modified["excerpt"] = "merged-excerpt"
        modified["title"] = "TEST_iter49 Merge Title"
        zbytes = self._make_zip([modified])
        r = admin.post(
            f"{BASE_URL}/api/admin/backup/blogs/import?conflict=merge",
            files={"file": ("m.zip", zbytes, "application/zip")}, timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("merged", 0) >= 1
        doc = mongo.blogs.find_one({"blog_id": seed_blog["blog_id"]}, {"_id": 0})
        assert doc.get("excerpt") == "merged-excerpt"
        assert doc.get("title") == "TEST_iter49 Merge Title"
        assert doc.get("slug") == seed_blog["slug"]  # slug preserved
        assert doc.get("blog_id") == seed_blog["blog_id"]

    def test_import_replace_in_place(self, admin, mongo, seed_blog):
        modified = dict(seed_blog)
        modified["title"] = "TEST_iter49 Replaced Title"
        modified["content"] = "<p>replaced</p>"
        zbytes = self._make_zip([modified])
        r = admin.post(
            f"{BASE_URL}/api/admin/backup/blogs/import?conflict=replace",
            files={"file": ("r.zip", zbytes, "application/zip")}, timeout=20,
        )
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("replaced", 0) >= 1
        doc = mongo.blogs.find_one({"blog_id": seed_blog["blog_id"]}, {"_id": 0})
        assert doc.get("title") == "TEST_iter49 Replaced Title"
        assert doc.get("blog_id") == seed_blog["blog_id"]
        assert doc.get("slug") == seed_blog["slug"]


# ------------------------------------------------------------------
# 4. Users-export with include_blogs flag
# ------------------------------------------------------------------
class TestUsersExportIncludeBlogs:
    def test_users_export_without_blogs(self, admin):
        r = admin.post(
            f"{BASE_URL}/api/admin/backup/export/users",
            json={"user_ids": [SUPER_ADMIN_ID], "include_credentials": True, "include_blogs": False},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(zf.namelist())
        assert "blogs.json" not in names, f"unexpected blogs.json present: {names}"

    def test_users_export_with_blogs(self, admin):
        r = admin.post(
            f"{BASE_URL}/api/admin/backup/export/users",
            json={"user_ids": [SUPER_ADMIN_ID], "include_credentials": True, "include_blogs": True},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(zf.namelist())
        assert "blogs.json" in names

    def test_full_export_includes_blogs(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/backup/export/full", timeout=60)
        assert r.status_code == 200, r.text[:300]
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        assert "blogs.json" in set(zf.namelist())


# ------------------------------------------------------------------
# 5. Full-platform import regression (upsert by slug)
# ------------------------------------------------------------------
def test_full_platform_import_still_supports_blogs(admin, mongo):
    slug = f"iter49-full-{uuid.uuid4().hex[:6]}"
    blogs_payload = [{
        "blog_id": f"blog_{uuid.uuid4().hex[:12]}",
        "title": "TEST_iter49 Full Import",
        "slug": slug,
        "content": "<p>x</p>", "excerpt": "x", "status": "draft",
    }]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("metadata.json", json.dumps({"backup_type": "full_platform"}))
        zf.writestr("blogs.json", json.dumps(blogs_payload))
        zf.writestr("users.json", "[]")
        zf.writestr("plans.json", "[]")
        zf.writestr("system_settings.json", "[]")
    buf.seek(0)
    try:
        r = admin.post(
            f"{BASE_URL}/api/admin/backup/import",
            files={"file": ("full.zip", buf.read(), "application/zip")}, timeout=30,
        )
        assert r.status_code == 200, r.text[:400]
        assert mongo.blogs.find_one({"slug": slug}) is not None
    finally:
        mongo.blogs.delete_many({"slug": slug})


# ------------------------------------------------------------------
# 6. Generic regression on existing protected endpoints
# ------------------------------------------------------------------
@pytest.mark.parametrize("path", [
    "/api/campaigns", "/api/drip-campaigns", "/api/accounts",
    "/api/dne-lists", "/api/unibox/replies", "/api/auth/me",
])
def test_existing_endpoints_regression(admin, path):
    r = admin.get(f"{BASE_URL}{path}", timeout=20)
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"
