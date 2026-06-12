"""Infrastructure Phase C — Domain Reputation Monitoring + Issues Dashboard.

Reputation score (0-100) — user-confirmed weights:
    Positive: reply_rate 50%, inbox_age 10%, warmup_status 10%
    Negative: bounce_rate 20%, unsubscribe_rate 5%, error_rate 5%

Lookback windows: 7 days (recent) + 30 days (trailing) — both surfaced.

Cache: `domain_reputation` collection, computed once per 24h via lazy
background recompute (no new worker process needed). `POST /recompute`
forces a synchronous recompute.

Issues dashboard: lists Paused / Risky / Errored inboxes and supports
bulk `resume | pause | replace | delete`.
"""
import asyncio
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

# Reuse Phase B helpers via a soft import path — kept independent if Phase B
# is removed.
from infra_phase_b import attach_phase_b_routes  # noqa: F401 (sibling module)


WEIGHTS = {
    "reply": 0.50,
    "age": 0.10,
    "warmup": 0.10,
    "bounce": 0.20,
    "unsubscribe": 0.05,
    "error": 0.05,
}

CACHE_TTL_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _parse_dt(s: Any) -> Optional[datetime]:
    if not s:
        return None
    if isinstance(s, datetime):
        return s
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _age_days(account: Dict[str, Any]) -> float:
    dt = _parse_dt(account.get("created_at") or account.get("added_at"))
    if not dt:
        return 0.0
    return max(0.0, (_now() - dt).total_seconds() / 86400.0)


def _warmup_component(account: Dict[str, Any]) -> float:
    if not account.get("warmup_enabled"):
        # If warmup is OFF but the account is otherwise stable + aged, treat
        # as neutral (50) — penalising every non-warmup inbox would be unfair
        # to mature long-running mailboxes.
        return 60.0
    status = (account.get("warmup_status") or "").lower()
    if status in ("complete", "completed", "active"):
        return 100.0
    if status in ("warming", "in_progress", "running"):
        return 50.0
    return 30.0


async def _gather_window_counts(db, user_doc: Dict[str, Any], account: Dict[str, Any],
                                 since: datetime) -> Dict[str, int]:
    """Return {sends, bounces, errors, replies, unsubscribes} for an account in [since, now]."""
    acc_id = account["account_id"]
    email_lower = (account.get("email") or "").lower()
    since_iso = since.isoformat()

    # Standard campaign sends — `email_queue.sent_from_account` matches the account_id
    sends_q = await db.email_queue.count_documents({
        "sent_from_account": acc_id,
        "status": "sent",
        "sent_at": {"$gte": since_iso},
    })
    bounces_q = await db.email_queue.count_documents({
        "sent_from_account": acc_id,
        "status": "bounced",
        "sent_at": {"$gte": since_iso},
    })
    failed_q = await db.email_queue.count_documents({
        "sent_from_account": acc_id,
        "status": "failed",
        "sent_at": {"$gte": since_iso},
    })

    # Drip sends — `drip_logs.account_email` is the account email (drip_logs
    # doesn't store account_id today). Both case-insensitive.
    drip_match: Dict[str, Any] = {"sent_at": {"$gte": since_iso}}
    if email_lower:
        drip_match["account_email"] = {"$regex": f"^{email_lower}$", "$options": "i"}
    sends_d = await db.drip_logs.count_documents({**drip_match, "status": "sent"})
    bounces_d = await db.drip_logs.count_documents({**drip_match, "status": "bounced"})
    failed_d = await db.drip_logs.count_documents({**drip_match, "status": "failed"})

    # Replies routed to this account
    replies = await db.replies.count_documents({
        "account_id": acc_id,
        "received_at": {"$gte": since_iso},
    })

    # Unsubscribes — approximate by `drip_contacts` flipped to status=unsubscribed
    # within the window, scoped to the account's user.
    unsubs = await db.drip_contacts.count_documents({
        "user_id": account.get("user_id"),
        "status": "unsubscribed",
        "unsubscribed_at": {"$gte": since_iso},
    })

    return {
        "sends": int(sends_q + sends_d),
        "bounces": int(bounces_q + bounces_d),
        "errors": int(failed_q + failed_d),
        "replies": int(replies),
        "unsubscribes": int(unsubs),
    }


def _score_from_counts(counts: Dict[str, int], account: Dict[str, Any]) -> Dict[str, Any]:
    sends = max(counts["sends"], 1)  # avoid div-by-zero; rates use real numerator
    real_sends = counts["sends"]

    reply_rate = (counts["replies"] / sends) if real_sends else 0.0
    bounce_rate = (counts["bounces"] / sends) if real_sends else 0.0
    error_rate = (counts["errors"] / sends) if real_sends else 0.0
    # Unsubscribes are scoped to user — treat the workspace-level rate as the
    # account's rate (acceptable approximation since unsub events don't carry
    # account attribution in the current schema).
    unsub_rate = (counts["unsubscribes"] / sends) if real_sends else 0.0

    reply_score = _clamp(reply_rate * 2000)            # 5% → 100
    age_score = _clamp(_age_days(account) / 90.0 * 100.0)
    warmup_score = _warmup_component(account)
    bounce_score = _clamp(100.0 - bounce_rate * 1000)  # 10% → 0
    unsub_score = _clamp(100.0 - unsub_rate * 2000)    # 5% → 0
    error_score = _clamp(100.0 - error_rate * 1000)    # 10% → 0

    score = (
        WEIGHTS["reply"] * reply_score
        + WEIGHTS["age"] * age_score
        + WEIGHTS["warmup"] * warmup_score
        + WEIGHTS["bounce"] * bounce_score
        + WEIGHTS["unsubscribe"] * unsub_score
        + WEIGHTS["error"] * error_score
    )

    return {
        "score": round(score, 1),
        "sends": real_sends,
        "replies": counts["replies"],
        "bounces": counts["bounces"],
        "errors": counts["errors"],
        "unsubscribes": counts["unsubscribes"],
        "reply_rate": round(reply_rate * 100, 2),
        "bounce_rate": round(bounce_rate * 100, 2),
        "error_rate": round(error_rate * 100, 2),
        "unsubscribe_rate": round(unsub_rate * 100, 2),
        "components": {
            "reply": round(reply_score, 1),
            "age": round(age_score, 1),
            "warmup": round(warmup_score, 1),
            "bounce": round(bounce_score, 1),
            "unsubscribe": round(unsub_score, 1),
            "error": round(error_score, 1),
        },
    }


async def _compute_reputation_for_user(db, user_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Compute (and upsert into `domain_reputation`) one document per (user, domain)."""
    is_admin = user_doc.get("role") == "super_admin"
    q: Dict[str, Any] = {} if is_admin else {"user_id": user_doc["user_id"]}
    accounts = await db.email_accounts.find(q, {"_id": 0}).to_list(10000)

    now = _now()
    since_30 = now - timedelta(days=30)
    since_7 = now - timedelta(days=7)

    by_domain: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for a in accounts:
        email = (a.get("email") or "").lower()
        if "@" not in email:
            continue
        domain = email.rsplit("@", 1)[1]
        c30 = await _gather_window_counts(db, user_doc, a, since_30)
        c7 = await _gather_window_counts(db, user_doc, a, since_7)
        sc30 = _score_from_counts(c30, a)
        sc7 = _score_from_counts(c7, a)
        by_domain[domain].append({
            "account_id": a["account_id"],
            "email": a.get("email"),
            "user_id": a.get("user_id"),
            "domain": domain,
            "window_30d": sc30,
            "window_7d": sc7,
        })

    # Write one doc per (user, domain) — for super_admin scans, scope to the
    # owner of the inboxes within that domain so reads stay role-correct.
    output: List[Dict[str, Any]] = []
    for domain, inboxes in by_domain.items():
        # Group inboxes by user_id within this domain so each user gets their own row
        per_user: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for ib in inboxes:
            per_user[ib["user_id"]].append(ib)

        for uid, ibs in per_user.items():
            avg30 = round(sum(i["window_30d"]["score"] for i in ibs) / len(ibs), 1)
            avg7 = round(sum(i["window_7d"]["score"] for i in ibs) / len(ibs), 1)
            doc = {
                "user_id": uid,
                "domain": domain,
                "score_30d": avg30,
                "score_7d": avg7,
                "inbox_count": len(ibs),
                "inboxes": ibs,
                "computed_at": now.isoformat(),
            }
            await db.domain_reputation.update_one(
                {"user_id": uid, "domain": domain},
                {"$set": doc},
                upsert=True,
            )
            output.append(doc)

    return output


async def _read_reputation_cache(db, user_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    is_admin = user_doc.get("role") == "super_admin"
    q: Dict[str, Any] = {} if is_admin else {"user_id": user_doc["user_id"]}
    return await db.domain_reputation.find(q, {"_id": 0}).sort("score_30d", 1).to_list(10000)


def _bucket_score(s: float) -> str:
    if s >= 80:
        return "excellent"
    if s >= 60:
        return "good"
    if s >= 40:
        return "fair"
    if s >= 20:
        return "poor"
    return "critical"


class BulkIssueAction(BaseModel):
    action: str = Field(..., description="resume | pause | replace | delete")
    account_ids: List[str] = Field(..., min_length=1, max_length=500)
    reason: Optional[str] = Field(None, max_length=300)


def attach_phase_c_routes(router: APIRouter, db, get_infra_user, load_inboxes_fn):

    # ───────────── 1. REPUTATION (cached + lazy recompute) ─────────────
    @router.get("/reputation")
    async def reputation(user=Depends(get_infra_user)):
        cache = await _read_reputation_cache(db, user)
        stale = False
        if not cache:
            stale = True
        else:
            oldest = min(
                _parse_dt(d.get("computed_at")) or _now() - timedelta(days=999)
                for d in cache
            )
            if (_now() - oldest) > timedelta(hours=CACHE_TTL_HOURS):
                stale = True

        if stale:
            # Schedule background recompute, return whatever cache has now
            asyncio.create_task(_compute_reputation_for_user(db, user))

        # Build summary
        buckets = defaultdict(int)
        for d in cache:
            buckets[_bucket_score(d.get("score_30d", 0))] += 1

        avg30 = round(sum(d.get("score_30d", 0) for d in cache) / len(cache), 1) if cache else 0
        avg7 = round(sum(d.get("score_7d", 0) for d in cache) / len(cache), 1) if cache else 0

        # Sort worst-3 / best-3 by 30-day score
        ranked = sorted(cache, key=lambda d: d.get("score_30d", 0))
        worst = [{"domain": d["domain"], "score_30d": d["score_30d"], "score_7d": d["score_7d"]} for d in ranked[:3]]
        best = [{"domain": d["domain"], "score_30d": d["score_30d"], "score_7d": d["score_7d"]} for d in reversed(ranked[-3:])]

        return {
            "domains": [
                {
                    "domain": d["domain"],
                    "score_30d": d.get("score_30d", 0),
                    "score_7d": d.get("score_7d", 0),
                    "bucket_30d": _bucket_score(d.get("score_30d", 0)),
                    "bucket_7d": _bucket_score(d.get("score_7d", 0)),
                    "inbox_count": d.get("inbox_count", 0),
                    "computed_at": d.get("computed_at"),
                    "inboxes": d.get("inboxes", []),
                }
                for d in cache
            ],
            "summary": {
                "avg_score_30d": avg30,
                "avg_score_7d": avg7,
                "total_domains": len(cache),
                "buckets": dict(buckets),
                "worst": worst,
                "best": best,
            },
            "stale": stale,
            "cache_ttl_hours": CACHE_TTL_HOURS,
        }

    @router.post("/reputation/recompute")
    async def recompute(user=Depends(get_infra_user)):
        results = await _compute_reputation_for_user(db, user)
        return {"message": "Recomputed", "domain_count": len(results)}

    # ───────────── 2. ISSUES DASHBOARD ─────────────
    @router.get("/issues")
    async def issues(user=Depends(get_infra_user)):
        rows = await load_inboxes_fn(db, user)
        paused = [r for r in rows if r["status"] == "Paused"]
        risky = [r for r in rows if r["status"] == "Risky"]
        # An "errored" inbox is one with a recent last_error or status disconnected
        errored = []
        for r in rows:
            if r.get("account_status") == "disconnected":
                errored.append(r)
        return {
            "counts": {
                "paused": len(paused),
                "risky": len(risky),
                "errored": len(errored),
                "total": len(paused) + len(risky) + len(errored),
            },
            "paused": paused,
            "risky": risky,
            "errored": errored,
        }

    @router.post("/issues/bulk")
    async def bulk_action(payload: BulkIssueAction, user=Depends(get_infra_user)):
        action = payload.action.lower().strip()
        if action not in ("resume", "pause", "replace", "delete"):
            raise HTTPException(status_code=400, detail="action must be resume|pause|replace|delete")

        is_admin = user.get("role") == "super_admin"
        # Verify ownership for non-admin users
        scope: Dict[str, Any] = {"account_id": {"$in": payload.account_ids}}
        if not is_admin:
            scope["user_id"] = user["user_id"]
        targets = await db.email_accounts.find(scope, {"_id": 0}).to_list(1000)
        if not targets:
            raise HTTPException(status_code=404, detail="No matching inboxes")

        results = {"action": action, "succeeded": [], "failed": []}

        if action == "resume":
            for t in targets:
                try:
                    await db.email_accounts.update_one(
                        {"account_id": t["account_id"]},
                        {"$set": {"status": "connected", "paused": False, "last_error": None}},
                    )
                    results["succeeded"].append(t["account_id"])
                except Exception as e:
                    results["failed"].append({"account_id": t["account_id"], "error": str(e)})

        elif action == "pause":
            for t in targets:
                try:
                    await db.email_accounts.update_one(
                        {"account_id": t["account_id"]},
                        {"$set": {"status": "paused", "paused": True}},
                    )
                    results["succeeded"].append(t["account_id"])
                except Exception as e:
                    results["failed"].append({"account_id": t["account_id"], "error": str(e)})

        elif action == "delete":
            for t in targets:
                try:
                    # Remove this account from any campaign / drip account_ids array
                    await db.campaigns.update_many(
                        {"account_ids": t["account_id"]},
                        {"$pull": {"account_ids": t["account_id"]}},
                    )
                    await db.drip_campaigns.update_many(
                        {"account_ids": t["account_id"]},
                        {"$pull": {"account_ids": t["account_id"]}},
                    )
                    await db.email_accounts.delete_one({"account_id": t["account_id"]})
                    results["succeeded"].append(t["account_id"])
                except Exception as e:
                    results["failed"].append({"account_id": t["account_id"], "error": str(e)})

        elif action == "replace":
            # Delegate to the Phase B execute helper via direct collection
            # operations to keep this module independent.
            from infra_phase_b import attach_phase_b_routes as _phb  # noqa
            # Build the candidate pool ourselves to avoid circular imports.
            rows = await load_inboxes_fn(db, user)
            # busy = all accounts currently in any running campaign/drip
            cq: Dict[str, Any] = {"status": {"$in": ["running", "scheduled", "paused", "paused_daily_limit"]}}
            dq: Dict[str, Any] = {"status": {"$in": ["running", "scheduled", "paused"]}}
            if not is_admin:
                cq["user_id"] = user["user_id"]
                dq["user_id"] = user["user_id"]
            busy: set = set()
            async for c in db.campaigns.find(cq, {"_id": 0, "account_ids": 1}):
                for a in c.get("account_ids") or []:
                    busy.add(a)
            async for d in db.drip_campaigns.find(dq, {"_id": 0, "account_ids": 1}):
                for a in d.get("account_ids") or []:
                    busy.add(a)

            for t in targets:
                replaced_row = next((r for r in rows if r["account_id"] == t["account_id"]), None)
                if not replaced_row:
                    results["failed"].append({"account_id": t["account_id"], "error": "Not visible"})
                    continue
                pool = [
                    r for r in rows
                    if r["account_id"] != replaced_row["account_id"]
                    and r["account_id"] not in busy
                    and r["status"] not in ("Paused", "Risky", "Warming Up")
                    and r["remaining_capacity"] > 0
                ]
                if not pool:
                    await db.tracked_replacements.insert_one({
                        "replacement_id": f"rep_{uuid.uuid4().hex[:12]}",
                        "user_id": user["user_id"],
                        "replaced_account_id": replaced_row["account_id"],
                        "replaced_email": replaced_row["email"],
                        "replaced_domain": replaced_row["domain"],
                        "replaced_status": replaced_row["status"],
                        "replacement_account_id": None,
                        "replacement_email": None,
                        "replacement_domain": None,
                        "reason": payload.reason or f"bulk:{replaced_row['status']}",
                        "triggered_by": "manual",
                        "status": "no_candidate",
                        "campaigns_swapped": [],
                        "drips_swapped": [],
                        "created_at": _now().isoformat(),
                    })
                    results["failed"].append({"account_id": t["account_id"], "error": "No free replacement candidate"})
                    continue

                pool.sort(key=lambda r: (
                    0 if r["domain"] != replaced_row["domain"] else 1,
                    -int(r["remaining_capacity"]),
                    -int(r["daily_limit"]),
                ))
                cand = pool[0]
                # Swap in collections
                swapped_camps = []
                async for c in db.campaigns.find(
                    {**cq, "account_ids": replaced_row["account_id"]},
                    {"_id": 0, "campaign_id": 1, "name": 1, "status": 1, "account_ids": 1},
                ):
                    ids = [cand["account_id"] if a == replaced_row["account_id"] else a for a in c.get("account_ids") or []]
                    seen: List[str] = []
                    for a in ids:
                        if a not in seen:
                            seen.append(a)
                    await db.campaigns.update_one({"campaign_id": c["campaign_id"]}, {"$set": {"account_ids": seen}})
                    swapped_camps.append({"campaign_id": c["campaign_id"], "name": c.get("name"), "kind": "campaign", "status": c.get("status")})
                swapped_drips = []
                async for d in db.drip_campaigns.find(
                    {**dq, "account_ids": replaced_row["account_id"]},
                    {"_id": 0, "drip_id": 1, "name": 1, "status": 1, "account_ids": 1},
                ):
                    ids = [cand["account_id"] if a == replaced_row["account_id"] else a for a in d.get("account_ids") or []]
                    seen = []
                    for a in ids:
                        if a not in seen:
                            seen.append(a)
                    await db.drip_campaigns.update_one({"drip_id": d["drip_id"]}, {"$set": {"account_ids": seen}})
                    swapped_drips.append({"campaign_id": d["drip_id"], "name": d.get("name"), "kind": "drip", "status": d.get("status")})

                await db.tracked_replacements.insert_one({
                    "replacement_id": f"rep_{uuid.uuid4().hex[:12]}",
                    "user_id": user["user_id"],
                    "replaced_account_id": replaced_row["account_id"],
                    "replaced_email": replaced_row["email"],
                    "replaced_domain": replaced_row["domain"],
                    "replaced_status": replaced_row["status"],
                    "replacement_account_id": cand["account_id"],
                    "replacement_email": cand["email"],
                    "replacement_domain": cand["domain"],
                    "cross_domain": cand["domain"] != replaced_row["domain"],
                    "reason": payload.reason or f"bulk:{replaced_row['status']}",
                    "triggered_by": "manual",
                    "status": "completed",
                    "campaigns_swapped": swapped_camps,
                    "drips_swapped": swapped_drips,
                    "created_at": _now().isoformat(),
                })
                busy.add(cand["account_id"])  # candidate is now busy for the next iteration
                results["succeeded"].append(t["account_id"])

        return results
