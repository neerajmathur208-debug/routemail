"""
Backup & Restore endpoint tests for RouteMail (/api/backup/*).

Covers:
  - 5 export endpoints schema/shape
  - email-accounts credential opt-in/out
  - CSV exports & ZIP full export
  - Full restore preview + apply
  - Conflict modes (copy/skip/replace)
  - Cross-user isolation
  - Auth required (401)
  - Bad ZIP / missing metadata / schema version mismatch
  - CSV imports for email-lists and dne-lists
  - Bad conflict value (400)
"""
import io
import json
import os
import zipfile

import pytest
import requests


def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if url:
        return url.rstrip("/")
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

DRIP_USER = {"email": "drip.tester@example.com", "password": "DripTest123!"}
OTHER_USER = {"email": "dhruvmathur208@gmail.com", "password": "Perfect2026#"}


# ==================== fixtures ====================

@pytest.fixture(scope="module")
def drip_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=DRIP_USER, timeout=20)
    assert r.status_code == 200, f"Drip login failed: {r.text}"
    return s


@pytest.fixture(scope="module")
def other_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=OTHER_USER, timeout=20)
    assert r.status_code == 200, f"Other login failed: {r.text}"
    return s


@pytest.fixture(scope="module")
def full_backup_zip(drip_session):
    """Download a full backup ZIP and return bytes."""
    r = drip_session.get(f"{API}/backup/export/full", timeout=30)
    assert r.status_code == 200, r.text
    return r.content


# ==================== EXPORT — shape checks ====================

@pytest.mark.parametrize("path", [
    "/backup/export/campaigns",
    "/backup/export/drip-campaigns",
    "/backup/export/email-accounts",
    "/backup/export/email-lists",
    "/backup/export/dne-lists",
])
def test_export_shape(drip_session, path):
    r = drip_session.get(f"{API}{path}", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["schema_version"] == 1
    assert "exported_at" in data
    assert data["user_email"] == DRIP_USER["email"]
    assert isinstance(data["count"], int)
    assert isinstance(data["items"], list)
    assert data["count"] == len(data["items"])
    # Content-Disposition header for download
    assert "attachment" in r.headers.get("content-disposition", "").lower()


# ==================== email-accounts credential gating ====================

def test_email_accounts_no_credentials_by_default(drip_session):
    r = drip_session.get(f"{API}/backup/export/email-accounts", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data["include_credentials"] is False
    assert data["count"] > 0
    for acc in data["items"]:
        assert "smtp_password_encrypted" not in acc
        assert "smtp_password" not in acc
        assert "password" not in acc


def test_email_accounts_with_credentials_opt_in(drip_session):
    r = drip_session.get(
        f"{API}/backup/export/email-accounts?include_credentials=true",
        timeout=30,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["include_credentials"] is True
    has_enc = False
    for acc in data["items"]:
        # plain text NEVER present
        assert "smtp_password" not in acc
        assert "password" not in acc
        if "smtp_password_encrypted" in acc:
            has_enc = True
    # At least one of the SMTP accounts should expose the encrypted blob
    assert has_enc, "No smtp_password_encrypted found despite opt-in"


# ==================== CSV exports ====================

def test_export_email_lists_csv(drip_session):
    r = drip_session.get(f"{API}/backup/export/email-lists?format=csv", timeout=30)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    text = r.text
    # _list_name as first column
    first_line = text.splitlines()[0] if text else ""
    assert first_line.startswith("_list_name"), f"Header: {first_line!r}"


def test_export_dne_lists_csv(drip_session):
    r = drip_session.get(f"{API}/backup/export/dne-lists?format=csv", timeout=30)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    headers = r.text.splitlines()[0].split(",")
    assert headers == ["list_name", "email", "source", "added_at"]


# ==================== Full ZIP export ====================

def test_export_full_zip_structure(full_backup_zip):
    zf = zipfile.ZipFile(io.BytesIO(full_backup_zip))
    expected = {
        "metadata.json", "campaigns.json", "drip_campaigns.json",
        "email_accounts.json", "email_lists.json", "unsubscribe_lists.json",
    }
    assert set(zf.namelist()) == expected
    metadata = json.loads(zf.read("metadata.json"))
    assert metadata["schema_version"] == 1
    assert metadata["user_email"] == DRIP_USER["email"]
    # counts match files
    for key, fname in [
        ("campaigns", "campaigns.json"),
        ("drip_campaigns", "drip_campaigns.json"),
        ("email_accounts", "email_accounts.json"),
        ("email_lists", "email_lists.json"),
        ("unsubscribe_lists", "unsubscribe_lists.json"),
    ]:
        items = json.loads(zf.read(fname))
        assert len(items) == metadata["counts"][key], (
            f"Count mismatch for {key}: meta={metadata['counts'][key]} actual={len(items)}"
        )


# ==================== Full import preview ====================

def test_import_full_preview(drip_session, full_backup_zip):
    files = {"file": ("backup.zip", full_backup_zip, "application/zip")}
    r = drip_session.post(f"{API}/backup/import/full/preview", files=files, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "metadata" in body
    s = body["summary"]
    assert set(s.keys()) == {"campaigns", "drip_campaigns", "email_accounts",
                             "email_lists", "unsubscribe_lists"}
    # numbers match metadata counts
    assert s == body["metadata"]["counts"]


# ==================== Auth required ====================

@pytest.mark.parametrize("path", [
    "/backup/export/campaigns",
    "/backup/export/drip-campaigns",
    "/backup/export/email-accounts",
    "/backup/export/email-lists",
    "/backup/export/dne-lists",
    "/backup/export/full",
])
def test_export_requires_auth(path):
    r = requests.get(f"{API}{path}", timeout=20)
    assert r.status_code == 401, f"{path} expected 401, got {r.status_code}"


def test_import_requires_auth():
    r = requests.post(f"{API}/backup/import/campaigns",
                      json={"items": [], "conflict": "copy"}, timeout=20)
    assert r.status_code == 401


# ==================== Bad ZIP / missing metadata / schema mismatch ====================

def test_import_full_bad_zip(drip_session):
    files = {"file": ("notzip.zip", b"this is not a zip", "application/zip")}
    r = drip_session.post(f"{API}/backup/import/full", files=files, timeout=20)
    assert r.status_code == 400
    assert "ZIP" in r.json().get("detail", "")


def test_import_full_missing_metadata(drip_session):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("campaigns.json", "[]")
    buf.seek(0)
    files = {"file": ("bad.zip", buf.read(), "application/zip")}
    r = drip_session.post(f"{API}/backup/import/full", files=files, timeout=20)
    assert r.status_code == 400
    assert "metadata.json" in r.json().get("detail", "")


def test_import_full_schema_too_new(drip_session):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("metadata.json", json.dumps({"schema_version": 99}))
        for f in ("campaigns.json", "drip_campaigns.json", "email_accounts.json",
                  "email_lists.json", "unsubscribe_lists.json"):
            zf.writestr(f, "[]")
    buf.seek(0)
    files = {"file": ("future.zip", buf.read(), "application/zip")}
    r = drip_session.post(f"{API}/backup/import/full", files=files, timeout=20)
    assert r.status_code == 400
    assert "newer" in r.json().get("detail", "").lower()


def test_bad_conflict_value(drip_session):
    r = drip_session.post(
        f"{API}/backup/import/campaigns",
        json={"items": [], "conflict": "merge"},
        timeout=20,
    )
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert "skip" in detail and "replace" in detail and "copy" in detail


# ==================== Cross-user isolation ====================

def test_cross_user_export_empty(other_session):
    """User dhruv has no campaigns/drips/accounts of drip.tester (different user_id)."""
    # exported lists should only contain dhruv's own data, not drip.tester's
    for path in [
        "/backup/export/campaigns",
        "/backup/export/drip-campaigns",
    ]:
        r = other_session.get(f"{API}{path}", timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["user_email"] == OTHER_USER["email"]
        # All items must belong to dhruv (no drip.tester names)
        for it in d["items"]:
            assert it.get("user_id") != "user_35cc629e1385", \
                f"Cross-user leak: drip.tester item in dhruv's export: {it}"


# ==================== Conflict modes (copy/skip/replace) ====================

@pytest.fixture(scope="module")
def imported_camp_ids(drip_session, full_backup_zip):
    """Apply full restore in copy mode and capture imported campaign IDs for cleanup."""
    files = {"file": ("backup.zip", full_backup_zip, "application/zip")}
    r = drip_session.post(
        f"{API}/backup/import/full?conflict=copy", files=files, timeout=60
    )
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    yield results
    # cleanup: find and delete (Imported) suffixed entities
    # campaigns
    rc = drip_session.get(f"{API}/campaigns", timeout=20).json()
    camps = rc.get("campaigns", rc) if isinstance(rc, dict) else rc
    for c in camps:
        if c.get("name", "").endswith("(Imported)"):
            try:
                drip_session.delete(f"{API}/campaigns/{c['campaign_id']}", timeout=20)
            except Exception:
                pass
    # drips
    rd = drip_session.get(f"{API}/drip-campaigns", timeout=20).json()
    drips = rd.get("drip_campaigns", rd) if isinstance(rd, dict) else rd
    for d in drips:
        if d.get("name", "").endswith("(Imported)"):
            try:
                drip_session.delete(f"{API}/drip-campaigns/{d['drip_id']}", timeout=20)
            except Exception:
                pass
    # email accounts (imported ones have plus-addressing +imported-XXXX)
    ra = drip_session.get(f"{API}/accounts", timeout=20).json()
    accs = ra.get("accounts", ra) if isinstance(ra, dict) else ra
    for a in accs:
        if "+imported-" in a.get("email", "") or a.get("display_name", "").endswith("(Imported)"):
            try:
                drip_session.delete(f"{API}/accounts/{a['account_id']}", timeout=20)
            except Exception:
                pass
    # email lists
    rl = drip_session.get(f"{API}/lists", timeout=20).json()
    lists = rl.get("lists", rl.get("email_lists", rl)) if isinstance(rl, dict) else rl
    lists = [x for x in lists if isinstance(x, dict)]
    for lst in lists:
        if lst.get("name", "").endswith("(Imported)"):
            try:
                drip_session.delete(f"{API}/lists/{lst['list_id']}", timeout=20)
            except Exception:
                pass
    # dne lists
    rdne = drip_session.get(f"{API}/dne-lists", timeout=20).json()
    dne = rdne.get("dne_lists", rdne.get("lists", rdne)) if isinstance(rdne, dict) else rdne
    dne = [x for x in dne if isinstance(x, dict)]
    for d in dne:
        if d.get("name", "").endswith("(Imported)"):
            try:
                drip_session.delete(f"{API}/dne-lists/{d['list_id']}", timeout=20)
            except Exception:
                pass


def test_full_restore_copy_mode(drip_session, imported_camp_ids):
    """After copy restore: campaigns/drips drafts; accounts pending_verification."""
    results = imported_camp_ids
    assert results["campaigns"]["imported"] >= 1
    assert results["drip_campaigns"]["imported"] >= 1

    # Verify campaigns
    rc = drip_session.get(f"{API}/campaigns", timeout=20).json()
    camps = rc.get("campaigns", rc) if isinstance(rc, dict) else rc
    imported = [c for c in camps if c.get("name", "").endswith("(Imported)")]
    assert len(imported) >= 1
    for c in imported:
        assert c["status"] == "draft"

    # Verify drips
    rd = drip_session.get(f"{API}/drip-campaigns", timeout=20).json()
    drips = rd.get("drip_campaigns", rd) if isinstance(rd, dict) else rd
    imported_d = [d for d in drips if d.get("name", "").endswith("(Imported)")]
    assert len(imported_d) >= 1
    for d in imported_d:
        assert d["status"] == "draft"

    # Verify email accounts
    ra = drip_session.get(f"{API}/accounts", timeout=20).json()
    accs = ra.get("accounts", ra) if isinstance(ra, dict) else ra
    imported_a = [a for a in accs if "+imported-" in a.get("email", "")]
    assert len(imported_a) >= 1
    for a in imported_a:
        assert a["status"] == "pending_verification"


def test_individual_skip_mode(drip_session, full_backup_zip):
    """Skip mode: nothing imported when all names exist."""
    zf = zipfile.ZipFile(io.BytesIO(full_backup_zip))
    camps = json.loads(zf.read("campaigns.json"))
    r = drip_session.post(
        f"{API}/backup/import/campaigns",
        json={"items": camps, "conflict": "skip"},
        timeout=30,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["imported"] == 0
    assert d["skipped"] == len(camps)


def test_individual_replace_mode(drip_session, full_backup_zip):
    """Replace mode: existing campaigns replaced in place."""
    zf = zipfile.ZipFile(io.BytesIO(full_backup_zip))
    camps = json.loads(zf.read("campaigns.json"))
    if not camps:
        pytest.skip("No campaigns to test replace")
    r = drip_session.post(
        f"{API}/backup/import/campaigns",
        json={"items": camps, "conflict": "replace"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["replaced"] == len(camps)
    assert d["imported"] == 0

    # All campaigns must still be draft post-replace
    rc = drip_session.get(f"{API}/campaigns", timeout=20).json()
    out = rc.get("campaigns", rc) if isinstance(rc, dict) else rc
    for c in out:
        if not c.get("name", "").endswith("(Imported)"):
            assert c["status"] == "draft"


# ==================== CSV imports ====================

def test_import_email_lists_csv(drip_session):
    csv_text = "email,first_name\nTEST_csv1@example.com,Alice\nTEST_csv2@example.com,Bob\n"
    files = {"file": ("leads.csv", csv_text, "text/csv")}
    r = drip_session.post(
        f"{API}/backup/import/email-lists/csv?list_name=TEST_csv_list&conflict=copy",
        files=files,
        timeout=20,
    )
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 1
    # Verify list exists with column_headers + emails
    rl = drip_session.get(f"{API}/lists", timeout=20).json()
    lists = rl.get("lists", rl.get("email_lists", rl)) if isinstance(rl, dict) else rl
    lists = [x for x in lists if isinstance(x, dict)]
    matched = [lst for lst in lists if lst.get("name") == "TEST_csv_list"]
    assert len(matched) == 1
    lst = matched[0]
    assert lst.get("column_headers") == ["email", "first_name"]
    # Cleanup
    try:
        drip_session.delete(f"{API}/lists/{lst['list_id']}", timeout=10)
    except Exception:
        pass


def test_import_dne_lists_csv(drip_session):
    csv_text = "email\nTEST_dne1@example.com\nTEST_dne2@example.com\nTEST_dne1@example.com\n"
    files = {"file": ("dne.csv", csv_text, "text/csv")}
    r = drip_session.post(
        f"{API}/backup/import/dne-lists/csv?list_name=TEST_dne_list&conflict=copy",
        files=files,
        timeout=20,
    )
    assert r.status_code == 200, r.text
    # Verify list created and is_global False
    rdne = drip_session.get(f"{API}/dne-lists", timeout=20).json()
    dne = rdne.get("dne_lists", rdne.get("lists", rdne)) if isinstance(rdne, dict) else rdne
    dne = [x for x in dne if isinstance(x, dict)]
    matched = [d for d in dne if d.get("name") == "TEST_dne_list"]
    assert len(matched) == 1
    assert matched[0].get("is_global") is False
    # Cleanup
    try:
        drip_session.delete(f"{API}/dne-lists/{matched[0]['list_id']}", timeout=10)
    except Exception:
        pass
