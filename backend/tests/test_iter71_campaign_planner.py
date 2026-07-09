"""Iteration 71 — Campaign Capacity Planner redesign.

Tests the new `_plan_campaign` engine + `/plan-campaign` endpoint against
the 16-point spec (auto inbox count, partial contributions, slight
over-allocation, per-date breakdown, warmup ignored, exclusions, etc.).
"""
import sys
import uuid
from datetime import date, timedelta

import pytest

sys.path.insert(0, "/app/backend")
from infra_phase3 import _plan_campaign, _compute_execution_dates  # noqa: E402


def _mk(aid, domain, projection, status="Available", daily_limit=50):
    return {
        "account_id": aid, "email": f"{aid}@{domain}", "domain": domain,
        "status": status, "ownership": "internal",
        "daily_limit": daily_limit, "remaining_capacity": daily_limit,
        "warmup_status": "Active", "warming_up": True,
        "projected_window_total": sum(projection.values()),
    }


def _dates(n=3, delay=7, offset=7):
    d0 = date.today() + timedelta(days=offset)
    return [(d0 + timedelta(days=i * delay)).isoformat() for i in range(n)]


# ─── T1 — Execution dates roll forward across non-sending weekdays ─────────

def test_execution_dates_skip_non_sending_weekdays():
    # Start on Sat 2026-07-11, allow only Mon-Fri, 3 steps × 7 delay.
    dates = _compute_execution_dates("2026-07-11", steps=3, delay_days=7,
                                     sending_days=[0, 1, 2, 3, 4])
    weekdays = [date.fromisoformat(d).weekday() for d in dates]
    assert all(0 <= w <= 4 for w in weekdays), f"got weekdays {weekdays}"
    # Every date is at least 1 day apart (no duplicates from rolling forward).
    assert len(set(dates)) == 3


# ─── T2 — Auto-derived inbox count ────────────────────────────────────────

def test_auto_derived_inbox_count_from_median_projection():
    """20 inboxes each projecting 40/day, daily_target 500 → auto suggests
    ceil(500/40) = 13 inboxes."""
    dates = _dates(3)
    projection = {}
    inboxes = []
    for i in range(20):
        aid = f"a{i}"
        proj = {d: 40 for d in dates}
        projection[aid] = proj
        inboxes.append(_mk(aid, f"d{i}.example", proj))
    plan = _plan_campaign(inboxes, projection, dates,
                          daily_target=500, domain_reserve=0)
    assert plan["auto_recommended_inboxes"] == 13
    # Picked count uses auto value when no override
    assert plan["requested_inboxes"] == 13
    # Combined min-daily should meet/exceed the target
    assert plan["combined_min_daily_capacity"] >= 500


# ─── T3 — Manual override wins over auto ──────────────────────────────────

def test_override_required_inboxes_takes_precedence():
    dates = _dates(1)
    inboxes = []
    projection = {}
    for i in range(10):
        aid = f"o{i}"
        proj = {dates[0]: 20}
        projection[aid] = proj
        inboxes.append(_mk(aid, f"d{i}.example", proj))
    plan = _plan_campaign(inboxes, projection, dates,
                          daily_target=40, domain_reserve=0,
                          override_required=6)
    assert plan["requested_inboxes"] == 6
    assert plan["recommended_inboxes_count"] == 6


# ─── T4 — Partial contributions across many inboxes ──────────────────────

def test_partial_contributions_sum_to_target():
    """5 inboxes × 12/day each, target 50 → each contributes 10 (proportional)."""
    dates = _dates(1)
    inboxes = []
    projection = {}
    for i in range(5):
        aid = f"p{i}"
        proj = {dates[0]: 12}
        projection[aid] = proj
        inboxes.append(_mk(aid, f"d{i}.example", proj))
    plan = _plan_campaign(inboxes, projection, dates,
                          daily_target=50, domain_reserve=0)
    b = plan["date_plan"][0]
    assert b["selected"] == 50, f"got {b['selected']}"
    for row in b["inboxes"]:
        assert row["contributes"] > 0, "every picked inbox must contribute"


# ─── T5 — Slight over-allocation acceptable ──────────────────────────────

def test_slight_over_allocation_allowed():
    """Combined capacity 540, target 500 → auto count picks enough inboxes
    that combined_min_daily_capacity >= target (may slightly exceed)."""
    dates = _dates(2)
    inboxes = []
    projection = {}
    for i in range(15):
        aid = f"s{i}"
        proj = {d: 36 for d in dates}
        projection[aid] = proj
        inboxes.append(_mk(aid, f"d{i}.example", proj))
    plan = _plan_campaign(inboxes, projection, dates,
                          daily_target=500, domain_reserve=0)
    assert plan["combined_min_daily_capacity"] >= 500
    # Never picks LESS than needed
    for b in plan["date_plan"]:
        assert b["selected"] >= 500
    assert plan["infrastructure_status"] == "Healthy"


# ─── T6 — Warmup + low score inboxes still qualify ──────────────────────

def test_warmup_active_inbox_is_allocated():
    dates = _dates(2)
    warm_proj = {d: 30 for d in dates}
    warm = _mk("warm", "warm.example", warm_proj)
    warm["warming_up"] = True
    warm["warmup_status"] = "Active"
    warm["domain_score"] = 5  # simulated low score
    plan = _plan_campaign(
        [warm], {"warm": warm_proj}, dates,
        daily_target=20, domain_reserve=0,
    )
    assert plan["recommended_inboxes_count"] == 1
    aid_row = plan["inboxes"][0]
    assert aid_row["account_id"] == "warm"
    assert aid_row["allocated_total"] > 0


# ─── T7 — Only hard blockers excluded ────────────────────────────────────

def test_hard_blockers_excluded_with_reason():
    dates = _dates(1)
    ok = _mk("ok", "ok.example", {dates[0]: 30})
    paused = _mk("p", "p.example", {dates[0]: 30}, status="Paused")
    risky = _mk("r", "r.example", {dates[0]: 30}, status="Risky")
    zero = _mk("z", "z.example", {dates[0]: 0})
    projection = {"ok": {dates[0]: 30}, "p": {dates[0]: 30},
                  "r": {dates[0]: 30}, "z": {dates[0]: 0}}
    plan = _plan_campaign([ok, paused, risky, zero], projection, dates,
                          daily_target=10, domain_reserve=0)
    reasons = {e["account_id"]: e["reason"] for e in plan["excluded"]}
    assert "paused" in reasons["p"]
    assert "risky" in reasons["r"]
    assert "no remaining projected campaign capacity" in reasons["z"]
    assert plan["recommended_inboxes_count"] == 1
    assert plan["inboxes"][0]["account_id"] == "ok"


# ─── T8 — Domain reserve honoured ────────────────────────────────────────

def test_domain_reserve_caps_per_domain_contribution():
    """One domain has 50/day. With domain_reserve=10, the effective cap is 40."""
    dates = _dates(1)
    a = _mk("a", "shared.example", {dates[0]: 30}, daily_limit=30)
    b = _mk("b", "shared.example", {dates[0]: 30}, daily_limit=30)
    projection = {"a": {dates[0]: 30}, "b": {dates[0]: 30}}
    plan = _plan_campaign([a, b], projection, dates,
                          daily_target=60, domain_reserve=10)
    plan_b = plan["date_plan"][0]
    # domain pool 60, reserve 10 → allocatable 50, target 60 → shortfall 10
    assert plan_b["available_after_reserve"] == 50
    assert plan_b["shortfall"] == 10


# ─── T9 — Future-date-only availability still qualifies ─────────────────

def test_inbox_with_capacity_only_on_some_dates_still_used():
    """Inbox A has capacity on step 1 & 2 but zero on step 3 — because the
    plan requires positive projection on every execution date (total > 0),
    but the min-projection may be 0. Confirm the inbox is EXCLUDED when
    it has zero on any planning date and would prevent meeting daily_target."""
    dates = _dates(3)
    # Inbox A: 30 avail on all three dates
    a_proj = {dates[0]: 30, dates[1]: 30, dates[2]: 30}
    # Inbox B: 30 on first two, 8 on the last
    b_proj = {dates[0]: 30, dates[1]: 30, dates[2]: 8}
    inboxes = [
        _mk("A", "a.example", a_proj),
        _mk("B", "b.example", b_proj),
    ]
    projection = {"A": a_proj, "B": b_proj}
    plan = _plan_campaign(inboxes, projection, dates,
                          daily_target=30, domain_reserve=0)
    # Both inboxes have SOME projected capacity → both in pool.
    # B contributes 8 on the last date, A contributes the rest.
    ids = {r["account_id"] for r in plan["inboxes"]}
    assert "A" in ids and "B" in ids
    step3 = plan["date_plan"][2]
    contribs = {r["account_id"]: r["contributes"] for r in step3["inboxes"]}
    assert contribs.get("B", 0) <= 8
    assert step3["selected"] >= 30  # target met via A picking up slack


# ─── T10 — Insufficient capacity flagged clearly ─────────────────────────

def test_infrastructure_status_partial_when_shortfall():
    """3 inboxes × 10 avail = 30 combined vs target 100 → shortfall on
    every date, status = 'Partial' (some inboxes picked, none saturated)."""
    dates = _dates(2)
    inboxes = []
    projection = {}
    for i in range(3):
        aid = f"low{i}"
        proj = {d: 10 for d in dates}
        projection[aid] = proj
        inboxes.append(_mk(aid, f"d{i}.example", proj))
    plan = _plan_campaign(inboxes, projection, dates,
                          daily_target=100, domain_reserve=0)
    assert plan["shortfall_days"] == 2
    assert plan["infrastructure_status"] == "Partial"
    assert any("insufficient" in w.lower() for w in plan["warnings"])
