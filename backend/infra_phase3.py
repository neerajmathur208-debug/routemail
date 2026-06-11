"""Auto-Allocation + Capacity Planner — Phase 3 of the Infrastructure module.

Both endpoints reuse the data the Phase-2 projection engine already computes
(`_load_inboxes` + `build_projection`) so the numbers users see in the
recommendation match the dashboard exactly.

Two endpoints:
    POST /api/infrastructure/allocate  — diversification-aware inbox picker
    POST /api/infrastructure/planner   — leads/steps/duration → required inboxes
"""

from collections import defaultdict
from math import ceil
from statistics import median
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


# ---------- request schemas -------------------------------------------------

class AllocateRequest(BaseModel):
    required: int = Field(..., ge=1, le=10000, description="How many inboxes the campaign needs")
    ownership: Optional[str] = None
    min_remaining_per_inbox: int = Field(10, ge=0, le=10000,
        description="Skip inboxes with less remaining capacity TODAY than this floor")
    domain_capacity_floor: int = Field(10, ge=0, le=10000,
        description="Skip a whole domain when its remaining capacity today drops below this")


class PlannerRequest(BaseModel):
    leads: int = Field(..., ge=1, le=10_000_000)
    steps: int = Field(..., ge=1, le=20)
    duration_days: int = Field(..., ge=1, le=365)
    sending_days_per_week: int = Field(5, ge=1, le=7)


# ---------- helpers --------------------------------------------------------

def _allocate(
    inboxes: List[Dict[str, Any]],
    projection: Dict[str, Dict[str, int]],
    required: int,
    min_remaining_per_inbox: int,
    domain_capacity_floor: int,
) -> Dict[str, Any]:
    """Diversification-aware allocator.

    Priority order:
      1. Use **one inbox per domain** before reusing any domain.
      2. Among same-priority inboxes, prefer the one with the highest
         `remaining_capacity` today (= least loaded).
      3. Skip domains whose aggregate remaining capacity today is below
         `domain_capacity_floor` (protects domains close to exhaustion).
      4. Skip inboxes whose individual `remaining_capacity` is below
         `min_remaining_per_inbox` or whose status is Warming Up / Paused /
         Risky / Fully Reserved.
    """
    SKIP_STATUSES = {"Warming Up", "Paused", "Risky", "Fully Reserved"}

    # Group inboxes by domain
    by_domain: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in inboxes:
        if r["status"] in SKIP_STATUSES:
            continue
        if r["remaining_capacity"] < min_remaining_per_inbox:
            continue
        if not r.get("domain"):
            continue
        by_domain[r["domain"]].append(r)

    # Drop domains whose aggregate today-remaining is below the floor.
    eligible_domains: Dict[str, List[Dict[str, Any]]] = {}
    skipped_for_capacity: List[str] = []
    for dom, rows in by_domain.items():
        dom_remaining = sum(x["remaining_capacity"] for x in rows)
        if dom_remaining < domain_capacity_floor:
            skipped_for_capacity.append(dom)
            continue
        # Sort within each domain by remaining capacity desc (then lowest
        # projected_window_total to bias toward least-loaded long-term).
        rows.sort(
            key=lambda x: (
                -x["remaining_capacity"],
                int((projection.get(x["account_id"]) or {}).get("__total__", 0)) or
                sum((projection.get(x["account_id"]) or {}).values()),
            )
        )
        eligible_domains[dom] = rows

    # Round-robin across domains
    picked: List[Dict[str, Any]] = []
    cursors: Dict[str, int] = {d: 0 for d in eligible_domains}
    # Sort domains so that those with the most depth (largest pool) come first
    # — this slightly improves coverage when the user asks for more inboxes
    # than there are domains, by ensuring we always have a fallback inbox.
    domain_order = sorted(eligible_domains.keys(), key=lambda d: -len(eligible_domains[d]))

    while len(picked) < required and any(
        cursors[d] < len(eligible_domains[d]) for d in domain_order
    ):
        progress = False
        for d in domain_order:
            if len(picked) >= required:
                break
            if cursors[d] < len(eligible_domains[d]):
                picked.append(eligible_domains[d][cursors[d]])
                cursors[d] += 1
                progress = True
        if not progress:
            break  # safety — no domain advanced this pass

    domains_used = sorted({r["domain"] for r in picked})
    avg = round(len(picked) / len(domains_used), 2) if domains_used else 0.0
    eligible_total = sum(len(v) for v in eligible_domains.values())

    warnings: List[str] = []
    if len(picked) < required:
        warnings.append(
            f"Insufficient eligible capacity — only {len(picked)} inboxes allocatable "
            f"out of {required} requested ({eligible_total} eligible after filters)."
        )
    if len(domains_used) > 0 and len(picked) / max(len(domains_used), 1) >= 5:
        warnings.append(
            f"Low domain diversification — {len(picked)} inboxes spread across only "
            f"{len(domains_used)} domains (~{avg} per domain). Spread risk concentrates."
        )
    if skipped_for_capacity:
        warnings.append(
            f"Skipped {len(skipped_for_capacity)} domain(s) near exhaustion today: "
            + ", ".join(sorted(skipped_for_capacity)[:5])
            + ("…" if len(skipped_for_capacity) > 5 else "")
        )

    return {
        "requested": required,
        "allocated": len(picked),
        "eligible_count": eligible_total,
        "inboxes": [
            {
                "account_id": p["account_id"],
                "email": p["email"],
                "domain": p["domain"],
                "ownership": p["ownership"],
                "daily_limit": p["daily_limit"],
                "remaining_capacity": p["remaining_capacity"],
                "status": p["status"],
            }
            for p in picked
        ],
        "domains_used": domains_used,
        "avg_inboxes_per_domain": avg,
        "warnings": warnings,
        "skipped_domains_near_exhaustion": skipped_for_capacity,
    }


def _plan(
    inboxes: List[Dict[str, Any]],
    capacity: Dict[str, int],
    req: PlannerRequest,
) -> Dict[str, Any]:
    """Capacity Planner math.

    Returns enough numbers for the UI to clearly say either "Ready" or
    "Insufficient Capacity — need N more inboxes" along with a few extra
    diagnostic warnings.
    """
    total_emails = req.leads * req.steps
    sending_days_in_window = int(round(req.duration_days * (req.sending_days_per_week / 7.0)))
    sending_days_in_window = max(sending_days_in_window, 1)
    required_daily_volume = ceil(total_emails / sending_days_in_window)

    # Use the **median** daily_limit across eligible (non-warming, non-paused)
    # inboxes — robust to a couple of outlier inboxes with very high limits.
    eligible = [
        r for r in inboxes
        if r["status"] not in {"Warming Up", "Paused", "Risky"}
    ]
    if eligible:
        med_limit = max(int(median(r["daily_limit"] for r in eligible)), 1)
    else:
        med_limit = 50  # sane fallback if there are no usable inboxes at all

    required_inboxes = ceil(required_daily_volume / med_limit)
    available_inboxes = len(eligible)
    additional_needed = max(0, required_inboxes - available_inboxes)

    today = capacity.get("today", 0)
    window = capacity.get("window", capacity.get("month_30", 0))

    # Did the user buy themselves enough total capacity across the window?
    enough_window = (window or 0) >= total_emails
    enough_inboxes = required_inboxes <= available_inboxes
    ready = enough_window and enough_inboxes

    # Estimated completion = ceil(total_emails / per-day-capacity-of-allocated)
    per_day_capacity = required_inboxes * med_limit if required_inboxes > 0 else med_limit
    actual_sending_days = ceil(total_emails / max(per_day_capacity, 1))
    # Calendar days = actual_sending_days × 7 / sending_days_per_week
    estimated_completion_days = ceil(actual_sending_days * 7 / req.sending_days_per_week)

    warnings: List[str] = []
    if additional_needed > 0:
        warnings.append(
            f"Need {required_inboxes} inboxes; available {available_inboxes}. "
            f"Add {additional_needed} more to fit the schedule."
        )
    if not enough_window:
        shortfall = total_emails - (window or 0)
        warnings.append(
            f"Window capacity short by {shortfall:,} emails over {req.duration_days} days."
        )
    # Domain diversification warning — if all eligible inboxes live on ≤ 4 domains
    domain_count = len({r["domain"] for r in eligible if r.get("domain")})
    if available_inboxes > 0 and domain_count <= 4:
        warnings.append(
            f"Low domain diversification — only {domain_count} domain(s) across "
            f"{available_inboxes} eligible inboxes. Spread risk concentrates."
        )

    return {
        "inputs": {
            "leads": req.leads,
            "steps": req.steps,
            "duration_days": req.duration_days,
            "sending_days_per_week": req.sending_days_per_week,
        },
        "outputs": {
            "total_emails": total_emails,
            "sending_days_in_window": sending_days_in_window,
            "required_daily_volume": required_daily_volume,
            "required_inboxes": required_inboxes,
            "available_inboxes": available_inboxes,
            "additional_inboxes_required": additional_needed,
            "median_daily_limit": med_limit,
            "available_capacity_today": today,
            "available_capacity_window": window,
            "estimated_completion_days": estimated_completion_days,
            "domain_diversity": domain_count,
        },
        "status": "Ready" if ready else "Insufficient Capacity",
        "warnings": warnings,
    }


# ---------- router builder -------------------------------------------------

def attach_phase3_routes(router: APIRouter, db, get_infra_user, load_inboxes_fn, build_projection_fn, aggregate_capacity_fn):
    """Bolt the Phase-3 endpoints onto the existing /infrastructure router.

    Why we pass the helpers in rather than importing them directly: the
    Phase-2 helpers live inside `infrastructure_routes.build_infrastructure_router`
    (closure access to `db`). Passing them as args avoids a circular import.
    """

    @router.post("/allocate")
    async def allocate(req: AllocateRequest, user=Depends(get_infra_user)):
        rows = await load_inboxes_fn(db, user)
        projection = await build_projection_fn(db, user, window_days=120)
        # enrich rows with projection rollup (matches /inboxes output shape)
        for r in rows:
            r["projected_window_total"] = sum((projection.get(r["account_id"]) or {}).values())
        return _allocate(rows, projection, req.required, req.min_remaining_per_inbox, req.domain_capacity_floor)

    @router.post("/planner")
    async def planner(req: PlannerRequest, user=Depends(get_infra_user)):
        rows = await load_inboxes_fn(db, user)
        projection = await build_projection_fn(db, user, window_days=120)
        capacity = aggregate_capacity_fn(rows, projection, 120)
        return _plan(rows, capacity, req)
