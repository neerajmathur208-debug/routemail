"""
Bulk warmup endpoint tests for RouteMail.
Covers:
  - /api/accounts/warmup/bulk-enable | bulk-pause | bulk-resume | bulk-disable | bulk-settings
  - GET /api/accounts: warmup_emails_sent_today / warmup_replies_today fields
  - Cross-user isolation
  - 400 on empty account_ids, 401 on no auth
  - Clamping of warmup_settings
  - build_warmup_body() varied conversational output
  - WARMUP_SUBJECTS all contain '(RTM)'
"""
import os
import sys
import pytest
import requests

# Load REACT_APP_BACKEND_URL from /app/frontend/.env if not in environment
def _load_backend_url():
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if url:
        return url.rstrip("/")
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except FileNotFoundError:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")

BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

DRIP_USER = {"email": "drip.tester@example.com", "password": "DripTest123!"}
OTHER_USER = {"email": "dhruvmathur208@gmail.com", "password": "Perfect2026#"}


# ==================== Module: build_warmup_body & WARMUP_SUBJECTS (in-process import) ====================

def _import_server():
    sys.path.insert(0, "/app/backend")
    import server  # noqa
    return server


def test_warmup_subjects_all_have_rtm_marker():
    server = _import_server()
    assert len(server.WARMUP_SUBJECTS) >= 20, "WARMUP_SUBJECTS should be expanded"
    for subj in server.WARMUP_SUBJECTS:
        assert "(RTM)" in subj, f"Missing (RTM) in subject: {subj}"


def test_build_warmup_body_is_varied_and_2_to_5_lines():
    server = _import_server()
    samples = [server.build_warmup_body() for _ in range(30)]
    # No two identical
    unique = set(samples)
    assert len(unique) >= 25, f"Expected high variation, got {len(unique)} unique out of 30"
    greetings_seen, openers_seen, closers_seen = set(), set(), set()
    for body in samples:
        non_blank = [ln for ln in body.split("\n") if ln.strip()]
        assert 2 <= len(non_blank) <= 5, f"Body must be 2–5 non-blank lines, got {len(non_blank)}: {body!r}"
        # First line is greeting (with comma), last line is closer
        greetings_seen.add(non_blank[0])
        closers_seen.add(non_blank[-1])
        openers_seen.add(non_blank[1] if len(non_blank) >= 2 else "")
    assert len(greetings_seen) >= 4, f"Expected varied greetings, got {greetings_seen}"
    assert len(openers_seen) >= 4, f"Expected varied openers, got {openers_seen}"
    assert len(closers_seen) >= 3, f"Expected varied closers, got {closers_seen}"


# ==================== Module: Auth + bulk endpoints ====================

@pytest.fixture(scope="module")
def drip_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=DRIP_USER, timeout=20)
    assert r.status_code == 200, f"Drip login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def other_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json=OTHER_USER, timeout=20)
    assert r.status_code == 200, f"Other-user login failed: {r.status_code} {r.text}"
    return s


def _accounts_list(drip_session):
    r = drip_session.get(f"{API}/accounts", timeout=20)
    assert r.status_code == 200, f"GET /accounts failed: {r.text}"
    body = r.json()
    if isinstance(body, dict) and "accounts" in body:
        return body["accounts"]
    return body


@pytest.fixture(scope="module")
def bulk_account_ids(drip_session):
    accounts = _accounts_list(drip_session)
    bulk_accs = [a for a in accounts if a.get("email", "").startswith("bulk.test.")]
    assert len(bulk_accs) >= 3, f"Expected >=3 bulk.test seed accounts, got {len(bulk_accs)}: emails={[a.get('email') for a in accounts]}"
    return [a["account_id"] for a in bulk_accs[:3]]


# ---- New fields on GET /api/accounts ----
def test_get_accounts_includes_new_warmup_today_fields(drip_session):
    accounts = _accounts_list(drip_session)
    assert len(accounts) > 0
    for a in accounts:
        assert "warmup_emails_sent_today" in a, "Missing warmup_emails_sent_today"
        assert "warmup_replies_today" in a, "Missing warmup_replies_today"
        assert isinstance(a["warmup_emails_sent_today"], int)
        assert isinstance(a["warmup_replies_today"], int)


# ---- 401 for unauthenticated ----
@pytest.mark.parametrize("method,path,body", [
    ("post", "/accounts/warmup/bulk-enable", {"account_ids": ["x"], "starting_emails_per_day": 5,
                                              "max_emails_per_day": 50, "daily_increment": 5, "reply_rate": 40}),
    ("post", "/accounts/warmup/bulk-pause", {"account_ids": ["x"]}),
    ("post", "/accounts/warmup/bulk-resume", {"account_ids": ["x"]}),
    ("post", "/accounts/warmup/bulk-disable", {"account_ids": ["x"]}),
    ("put",  "/accounts/warmup/bulk-settings", {"account_ids": ["x"], "starting_emails_per_day": 5,
                                                "max_emails_per_day": 50, "daily_increment": 5, "reply_rate": 40}),
])
def test_bulk_endpoints_require_auth(method, path, body):
    r = requests.request(method, f"{API}{path}", json=body, timeout=20)
    assert r.status_code == 401, f"{method.upper()} {path} should be 401 unauth, got {r.status_code}: {r.text}"


# ---- 400 on empty account_ids ----
@pytest.mark.parametrize("method,path,body", [
    ("post", "/accounts/warmup/bulk-enable", {"account_ids": [], "starting_emails_per_day": 5,
                                              "max_emails_per_day": 50, "daily_increment": 5, "reply_rate": 40}),
    ("post", "/accounts/warmup/bulk-pause", {"account_ids": []}),
    ("post", "/accounts/warmup/bulk-resume", {"account_ids": []}),
    ("post", "/accounts/warmup/bulk-disable", {"account_ids": []}),
    ("put",  "/accounts/warmup/bulk-settings", {"account_ids": [], "starting_emails_per_day": 5,
                                                "max_emails_per_day": 50, "daily_increment": 5, "reply_rate": 40}),
])
def test_bulk_endpoints_reject_empty(method, path, body, drip_session):
    r = drip_session.request(method, f"{API}{path}", json=body, timeout=20)
    assert r.status_code == 400, f"{method.upper()} {path} empty list should be 400, got {r.status_code}: {r.text}"


# ---- bulk-enable applies settings (clamping) and sets active state ----
def test_bulk_enable_with_clamping_and_state(drip_session, bulk_account_ids):
    # Provide out-of-range values to verify clamping
    payload = {
        "account_ids": bulk_account_ids,
        "starting_emails_per_day": 100,  # → clamp to 20
        "max_emails_per_day": 5,         # → clamp to 10
        "daily_increment": 50,           # → clamp to 10
        "reply_rate": 10,                # → clamp to 30
    }
    r = drip_session.post(f"{API}/accounts/warmup/bulk-enable", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["success"] is True
    assert data["matched"] == 3
    assert data["modified"] >= 0
    assert data["settings"] == {
        "starting_emails_per_day": 20,
        "max_emails_per_day": 10,
        "daily_increment": 10,
        "reply_rate": 30,
    }

    # Verify state via GET /accounts
    accounts = _accounts_list(drip_session)
    affected = [a for a in accounts if a["account_id"] in bulk_account_ids]
    assert len(affected) == 3
    for a in affected:
        assert a["warmup_enabled"] is True
        assert a["warmup_status"] == "active"
        assert a.get("warmup_day") == 1
        assert a["warmup_settings"]["starting_emails_per_day"] == 20
        assert a["warmup_settings"]["max_emails_per_day"] == 10
        assert a["warmup_settings"]["daily_increment"] == 10
        assert a["warmup_settings"]["reply_rate"] == 30


# ---- bulk-pause sets paused only when enabled ----
def test_bulk_pause(drip_session, bulk_account_ids):
    r = drip_session.post(f"{API}/accounts/warmup/bulk-pause",
                          json={"account_ids": bulk_account_ids}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["matched"] == 3
    accounts = _accounts_list(drip_session)
    for a in [x for x in accounts if x["account_id"] in bulk_account_ids]:
        assert a["warmup_status"] == "paused"
        assert a["warmup_enabled"] is True


# ---- bulk-resume sets active only when enabled ----
def test_bulk_resume(drip_session, bulk_account_ids):
    r = drip_session.post(f"{API}/accounts/warmup/bulk-resume",
                          json={"account_ids": bulk_account_ids}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["matched"] == 3
    accounts = _accounts_list(drip_session)
    for a in [x for x in accounts if x["account_id"] in bulk_account_ids]:
        assert a["warmup_status"] == "active"


# ---- bulk-settings clamps & does not change status ----
def test_bulk_settings_clamps_without_changing_status(drip_session, bulk_account_ids):
    accounts_before = _accounts_list(drip_session)
    statuses_before = {a["account_id"]: a["warmup_status"]
                       for a in accounts_before if a["account_id"] in bulk_account_ids}

    payload = {
        "account_ids": bulk_account_ids,
        "starting_emails_per_day": 0,    # → 1
        "max_emails_per_day": 999,       # → 100
        "daily_increment": 0,            # → 1
        "reply_rate": 99,                # → 50
    }
    r = drip_session.put(f"{API}/accounts/warmup/bulk-settings", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["settings"] == {
        "starting_emails_per_day": 1,
        "max_emails_per_day": 100,
        "daily_increment": 1,
        "reply_rate": 50,
    }
    accounts_after = _accounts_list(drip_session)
    for a in [x for x in accounts_after if x["account_id"] in bulk_account_ids]:
        assert a["warmup_settings"]["starting_emails_per_day"] == 1
        assert a["warmup_settings"]["max_emails_per_day"] == 100
        assert a["warmup_settings"]["daily_increment"] == 1
        assert a["warmup_settings"]["reply_rate"] == 50
        # Status preserved
        assert a["warmup_status"] == statuses_before[a["account_id"]]


# ---- Cross-user isolation: other user cannot modify drip's accounts ----
def test_bulk_endpoints_cross_user_isolation(other_session, drip_session, bulk_account_ids):
    payload = {"account_ids": bulk_account_ids,
               "starting_emails_per_day": 5, "max_emails_per_day": 50,
               "daily_increment": 5, "reply_rate": 40}
    # Snapshot drip view
    before = _accounts_list(drip_session)
    before_map = {a["account_id"]: a for a in before if a["account_id"] in bulk_account_ids}

    r = other_session.post(f"{API}/accounts/warmup/bulk-enable", json=payload, timeout=20)
    # The endpoint should accept the call but match 0 accounts owned by 'other'
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["matched"] == 0, f"Other user should not match drip accounts: {data}"
    assert data["modified"] == 0

    # Pause/resume/disable too
    for path in ["/accounts/warmup/bulk-pause", "/accounts/warmup/bulk-resume",
                 "/accounts/warmup/bulk-disable"]:
        rr = other_session.post(f"{API}{path}", json={"account_ids": bulk_account_ids}, timeout=20)
        assert rr.status_code == 200, rr.text
        assert rr.json()["matched"] == 0

    rr = other_session.put(f"{API}/accounts/warmup/bulk-settings", json=payload, timeout=20)
    assert rr.status_code == 200, rr.text
    assert rr.json()["matched"] == 0

    # Verify drip's accounts were not touched
    after = _accounts_list(drip_session)
    after_map = {a["account_id"]: a for a in after if a["account_id"] in bulk_account_ids}
    for aid in bulk_account_ids:
        assert before_map[aid]["warmup_status"] == after_map[aid]["warmup_status"]
        assert before_map[aid]["warmup_enabled"] == after_map[aid]["warmup_enabled"]
        assert before_map[aid]["warmup_settings"] == after_map[aid]["warmup_settings"]


# ---- bulk-disable sets disabled & enabled=false ----
def test_bulk_disable(drip_session, bulk_account_ids):
    r = drip_session.post(f"{API}/accounts/warmup/bulk-disable",
                          json={"account_ids": bulk_account_ids}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["matched"] == 3
    accounts = _accounts_list(drip_session)
    for a in [x for x in accounts if x["account_id"] in bulk_account_ids]:
        assert a["warmup_enabled"] is False
        assert a["warmup_status"] == "disabled"


# ---- After disable, bulk-pause / bulk-resume should NOT match (warmup_enabled=False filter) ----
def test_pause_resume_skips_disabled_accounts(drip_session, bulk_account_ids):
    rp = drip_session.post(f"{API}/accounts/warmup/bulk-pause",
                           json={"account_ids": bulk_account_ids}, timeout=20)
    assert rp.status_code == 200
    assert rp.json()["matched"] == 0, "pause should skip warmup_enabled=False"

    rr = drip_session.post(f"{API}/accounts/warmup/bulk-resume",
                           json={"account_ids": bulk_account_ids}, timeout=20)
    assert rr.status_code == 200
    assert rr.json()["matched"] == 0, "resume should skip warmup_enabled=False"


# ---- Single-account legacy endpoints still work ----
def test_single_account_warmup_endpoints_still_work(drip_session, bulk_account_ids):
    aid = bulk_account_ids[0]

    # enable (single)
    r = drip_session.post(f"{API}/accounts/{aid}/warmup/enable",
                          json={"starting_emails_per_day": 5, "max_emails_per_day": 50,
                                "daily_increment": 5, "reply_rate": 40}, timeout=20)
    assert r.status_code == 200, r.text

    # stats
    r = drip_session.get(f"{API}/accounts/{aid}/warmup/stats", timeout=20)
    assert r.status_code == 200, r.text

    # pause
    r = drip_session.post(f"{API}/accounts/{aid}/warmup/pause", timeout=20)
    assert r.status_code == 200, r.text

    # resume
    r = drip_session.post(f"{API}/accounts/{aid}/warmup/resume", timeout=20)
    assert r.status_code == 200, r.text

    # settings
    r = drip_session.put(f"{API}/accounts/{aid}/warmup/settings",
                         json={"starting_emails_per_day": 4, "max_emails_per_day": 40,
                               "daily_increment": 3, "reply_rate": 35}, timeout=20)
    assert r.status_code == 200, r.text

    # logs
    r = drip_session.get(f"{API}/accounts/{aid}/warmup/logs", timeout=20)
    assert r.status_code == 200, r.text

    # disable
    r = drip_session.post(f"{API}/accounts/{aid}/warmup/disable", timeout=20)
    assert r.status_code == 200, r.text


# ---- Cleanup: leave bulk accounts in disabled state for next iteration ----
@pytest.fixture(scope="module", autouse=True)
def _cleanup(drip_session, bulk_account_ids):
    yield
    try:
        drip_session.post(f"{API}/accounts/warmup/bulk-disable",
                          json={"account_ids": bulk_account_ids}, timeout=20)
    except Exception:
        pass
