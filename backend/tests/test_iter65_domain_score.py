"""Iteration 65 — Domain Score new 5-component weighting.

Pure-math unit tests for `_score_from_counts` to lock in the new
deliverability-weighted model:
    Deliverability 50%, Reply 25%, Engagement 10%,
    Technical Health 10%, Sending Behaviour 5%.
"""
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app/backend")

import infra_phase_c as ipc  # noqa: E402


def _acc(days_old=90, warmup_enabled=True, warmup_status="active"):
    return {
        "email": "x@example.com",
        "created_at": (datetime.now(timezone.utc) - timedelta(days=days_old)).isoformat(),
        "warmup_enabled": warmup_enabled,
        "warmup_status": warmup_status,
    }


def test_weights_sum_to_one_and_have_5_keys():
    assert set(ipc.WEIGHTS.keys()) == {
        "deliverability", "reply", "engagement", "technical_health", "sending_behaviour"
    }
    assert ipc.WEIGHTS["deliverability"] == 0.50
    assert ipc.WEIGHTS["reply"] == 0.25
    assert ipc.WEIGHTS["engagement"] == 0.10
    assert ipc.WEIGHTS["technical_health"] == 0.10
    assert ipc.WEIGHTS["sending_behaviour"] == 0.05
    assert abs(sum(ipc.WEIGHTS.values()) - 1.0) < 1e-9


def test_perfect_inbox_scores_100():
    """0 bounces, 0 errors, 0 unsubs, 5% reply rate (clamps to 100),
    90+ days old, warmup complete → 100."""
    counts = {"sends": 1000, "replies": 50, "bounces": 0, "errors": 0, "unsubscribes": 0}
    r = ipc._score_from_counts(counts, _acc(days_old=120))
    assert r["score"] == 100.0
    c = r["components"]
    assert c["deliverability"] == 100.0
    assert c["reply"] == 100.0
    assert c["engagement"] == 100.0
    assert c["technical_health"] == 100.0
    assert c["sending_behaviour"] == 100.0


def test_high_bounce_dominates_score():
    """5% bounce rate alone should drag the overall well below 50."""
    counts = {"sends": 1000, "replies": 50, "bounces": 50, "errors": 0, "unsubscribes": 0}
    r = ipc._score_from_counts(counts, _acc(days_old=120))
    # Deliverability ≈ 0 → 50% of total → so overall ≤ 50
    assert r["components"]["deliverability"] == 0.0
    assert r["score"] <= 50.0
    # Reply still full
    assert r["components"]["reply"] == 100.0


def test_no_reply_drops_25_points_but_not_more():
    counts = {"sends": 1000, "replies": 0, "bounces": 0, "errors": 0, "unsubscribes": 0}
    r = ipc._score_from_counts(counts, _acc(days_old=120))
    # Reply = 0 → contributes 0; other four contribute 100. Overall = 75.
    assert r["components"]["reply"] == 0.0
    assert r["score"] == 75.0


def test_age_drives_technical_health_linearly():
    counts = {"sends": 1000, "replies": 50, "bounces": 0, "errors": 0, "unsubscribes": 0}
    r45 = ipc._score_from_counts(counts, _acc(days_old=45))
    r90 = ipc._score_from_counts(counts, _acc(days_old=90))
    assert r45["components"]["technical_health"] == 50.0
    assert r90["components"]["technical_health"] == 100.0


def test_warmup_status_maps_to_sending_behaviour():
    counts = {"sends": 100, "replies": 0, "bounces": 0, "errors": 0, "unsubscribes": 0}
    active = ipc._score_from_counts(counts, _acc(warmup_enabled=True, warmup_status="active"))
    warming = ipc._score_from_counts(counts, _acc(warmup_enabled=True, warmup_status="warming"))
    off_mature = ipc._score_from_counts(counts, _acc(warmup_enabled=False))
    assert active["components"]["sending_behaviour"] == 100.0
    assert warming["components"]["sending_behaviour"] == 50.0
    assert off_mature["components"]["sending_behaviour"] == 60.0


def test_unsubscribe_drives_engagement_only():
    counts = {"sends": 1000, "replies": 50, "bounces": 0, "errors": 0, "unsubscribes": 50}  # 5%
    r = ipc._score_from_counts(counts, _acc(days_old=120))
    # 5% unsub → engagement 0 → contributes 0 to total
    assert r["components"]["engagement"] == 0.0
    # Other 4 components are 100 → weighted total = 0.5*100 + 0.25*100 + 0.10*100 + 0.05*100 = 90
    assert r["score"] == 90.0


def test_error_rate_partially_penalises_deliverability():
    """5% error rate alone → -50 on deliverability (errors are weighted half
    as harshly as bounces because they're often transient/retryable)."""
    counts = {"sends": 1000, "replies": 50, "bounces": 0, "errors": 50, "unsubscribes": 0}
    r = ipc._score_from_counts(counts, _acc(days_old=120))
    assert r["components"]["deliverability"] == 50.0
