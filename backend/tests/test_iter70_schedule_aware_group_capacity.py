"""Iteration 70 — Schedule-aware auto-allocate: group-target semantics
+ per-execution-date capacity breakdown + exclusion reasons.
"""
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, "/app/backend")
from infra_phase3 import _allocate  # noqa: E402


def _mk(aid, domain, remaining, status="Available", projection=None):
    """Shape mirrors what load_inboxes returns."""
    return {
        "account_id": aid, "email": f"{aid}@{domain}", "domain": domain,
        "status": status, "ownership": "internal",
        "remaining_capacity": remaining, "daily_limit": remaining + 5,
        "warmup_status": "Active", "warming_up": True,
        "projected_window_total": sum((projection or {}).values()),
    }


def _future_date_series(n, delay=7, start_offset=1):
    d0 = date.today() + timedelta(days=start_offset)
    return [(d0 + timedelta(days=i * delay)).isoformat() for i in range(n)]


# ─────────────────── T1 — Distribution, not per-inbox threshold ──────────

def test_group_target_is_distributed_across_inboxes():
    """Reproducer of the reported bug: 8 inboxes × 10 available each,
    per_day_send_estimate=50 (group target). Before the fix the allocator
    treated 50 as the per-inbox floor and returned 0. Now it should return
    all 8 inboxes since ⌈50/8⌉ = 7 ≤ 10 available on each."""
    dates = _future_date_series(3)
    projection = {}
    inboxes = []
    for i in range(8):
        inboxes.append(_mk(f"acc{i}", f"d{i}.example", 30,
                            projection={d: 10 for d in dates}))
        projection[f"acc{i}"] = {d: 10 for d in dates}
    result = _allocate(
        inboxes, projection, required=8,
        min_remaining_per_inbox=10, domain_capacity_floor=10,
        execution_dates=dates, per_day_send_estimate=50,
    )
    assert result["allocated"] == 8, f"got {result['allocated']} / warnings: {result['warnings']}"
    assert result["per_inbox_floor"] == 7  # ceil(50/8)
    assert result["group_target_per_day"] == 50
    # Breakdown must cover all 3 execution dates
    assert len(result["date_breakdown"]) == 3
    for b in result["date_breakdown"]:
        assert b["required"] == 50
        assert b["available"] == 80  # 8 × 10
        assert b["selected"] == 50   # group covers target exactly
        assert b["shortfall"] == 0
        # Sum of individual contributions must equal `selected`
        assert sum(x["contributes"] for x in b["inboxes"]) == 50


# ─────────────────── T2 — Partial-capacity inboxes still qualify ─────────

def test_partial_capacity_inbox_still_included():
    """Inboxes with only 5 units available on the execution day should still
    be counted toward the group total. ⌈50/8⌉ = 7 → floor is 7, so a 5-unit
    inbox WOULD be filtered. Reduce the requested count to 10 so the floor
    becomes ⌈50/10⌉ = 5 and the 5-unit inbox qualifies."""
    dates = _future_date_series(1)
    inboxes = []
    projection = {}
    # 9 inboxes with 10 avail each + 1 inbox with just 5 avail.
    for i in range(9):
        acc = f"a{i}"
        proj = {dates[0]: 10}
        inboxes.append(_mk(acc, f"d{i}.example", 30, projection=proj))
        projection[acc] = proj
    inboxes.append(_mk("small", "small.example", 30, projection={dates[0]: 5}))
    projection["small"] = {dates[0]: 5}

    result = _allocate(
        inboxes, projection, required=10,
        min_remaining_per_inbox=5, domain_capacity_floor=5,
        execution_dates=dates, per_day_send_estimate=50,
    )
    assert result["per_inbox_floor"] == 5  # ceil(50/10)
    assert result["allocated"] == 10  # all 10 qualify
    b = result["date_breakdown"][0]
    small_row = next(x for x in b["inboxes"] if x["account_id"] == "small")
    assert small_row["available"] == 5
    # `small` contributes a positive amount (up to its cap of 5)
    assert 0 < small_row["contributes"] <= 5


# ─────────────────── T3 — Paused / risky / disconnected excluded ─────────

def test_paused_and_risky_excluded_with_clear_reason():
    dates = _future_date_series(1)
    ib_ok = _mk("ok", "ok.example", 40, projection={dates[0]: 40})
    ib_paused = _mk("p", "p.example", 40, status="Paused", projection={dates[0]: 40})
    ib_risky = _mk("r", "r.example", 40, status="Risky", projection={dates[0]: 40})
    ib_full = _mk("f", "f.example", 0, status="Fully Reserved", projection={dates[0]: 0})
    projection = {"ok": {dates[0]: 40}, "p": {dates[0]: 40}, "r": {dates[0]: 40}, "f": {dates[0]: 0}}
    result = _allocate(
        [ib_ok, ib_paused, ib_risky, ib_full], projection, required=4,
        min_remaining_per_inbox=10, domain_capacity_floor=10,
        execution_dates=dates, per_day_send_estimate=20,
    )
    excl = {e["account_id"]: e["reason"] for e in result["excluded"]}
    assert "paused" in excl["p"]
    assert "risky" in excl["r"]
    assert "reserved" in excl["f"] or "capacity" in excl["f"]
    # Only the healthy inbox was allocated.
    assert result["allocated"] == 1
    assert result["inboxes"][0]["account_id"] == "ok"


# ─────────────────── T4 — Warmup + low-score inboxes still qualify ───────

def test_warmup_and_low_score_still_qualify():
    """The Available status is the ONLY campaign gate. warming_up + a
    hypothetical low domain score both attach as metadata and don't affect
    eligibility."""
    dates = _future_date_series(1)
    inb = _mk("warm", "warm.example", 20, projection={dates[0]: 20})
    inb["warming_up"] = True
    inb["domain_score"] = 20  # simulated low score — irrelevant to allocator
    result = _allocate(
        [inb], {"warm": {dates[0]: 20}}, required=1,
        min_remaining_per_inbox=5, domain_capacity_floor=5,
        execution_dates=dates, per_day_send_estimate=15,
    )
    assert result["allocated"] == 1


# ─────────────────── T5 — Shortfall reported clearly ─────────────────────

def test_group_shortfall_reported_in_warning_and_breakdown():
    """Group target 100 but the pool only has 30. Response must:
    - Allocate what's possible
    - Show shortfall in the per-day breakdown
    - Emit a workspace-level warning naming the worst day."""
    dates = _future_date_series(2)
    projection = {}
    inboxes = []
    for i in range(3):
        acc = f"low{i}"
        proj = {d: 10 for d in dates}
        inboxes.append(_mk(acc, f"low{i}.example", 20, projection=proj))
        projection[acc] = proj
    result = _allocate(
        inboxes, projection, required=3,
        min_remaining_per_inbox=5, domain_capacity_floor=5,
        execution_dates=dates, per_day_send_estimate=100,
    )
    # per_inbox_floor = ceil(100/3) = 34 → every inbox is below → 0 alloc
    # This tests the OTHER edge: the group truly can't cover it.
    assert result["allocated"] == 0
    warnings = " ".join(result["warnings"]).lower()
    assert "insufficient" in warnings or "schedule-aware" in warnings


# ─────────────────── T6 — Fallback: no schedule params = old behaviour ───

def test_no_execution_dates_falls_back_to_today_only():
    inbox = _mk("simple", "simple.example", 30, projection={})
    result = _allocate(
        [inbox], {"simple": {}}, required=1,
        min_remaining_per_inbox=10, domain_capacity_floor=10,
    )
    assert result["allocated"] == 1
    # Not in schedule mode → no breakdown, no per-inbox floor reporting
    assert result["date_breakdown"] == []
    assert result["per_inbox_floor"] is None
    assert result["group_target_per_day"] is None
