"""Infrastructure Phase B — Automatic Infrastructure Replacement.

Replaces paused / risky / errored inboxes with healthy ones in running
campaigns and drips. Rules:
  • Replacement candidates MUST NOT already be assigned to any
    running / scheduled / paused campaign or drip (must be free).
  • Cross-domain first — prefer a domain different from the one being
    replaced (diversification).
  • Higher remaining capacity wins on ties.
  • In-app toast only — no email side effects from the backend.

History lives in `tracked_replacements`.
"""
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


class ExecuteReplacementBody(BaseModel):
    replacement_account_id: Optional[str] = None
    reason: Optional[str] = Field(None, max_length=300)
    manual: bool = True


REPLACEABLE_STATUSES = {"Paused", "Risky"}
ACTIVE_CAMPAIGN_STATUSES = ["running", "scheduled", "paused", "paused_daily_limit"]
ACTIVE_DRIP_STATUSES = ["running", "scheduled", "paused"]


def attach_phase_b_routes(router: APIRouter, db, get_infra_user, load_inboxes_fn):
    """Mounts the Phase B endpoints onto the existing /infrastructure router."""

    async def _busy_account_ids(user_doc: Dict[str, Any]) -> set:
        """Return the set of account_ids currently assigned to ANY running /
        scheduled / paused campaign or drip the user can see."""
        is_admin = user_doc.get("role") == "super_admin"
        cq: Dict[str, Any] = {"status": {"$in": ACTIVE_CAMPAIGN_STATUSES}}
        dq: Dict[str, Any] = {"status": {"$in": ACTIVE_DRIP_STATUSES}}
        if not is_admin:
            cq["user_id"] = user_doc["user_id"]
            dq["user_id"] = user_doc["user_id"]

        busy: set = set()
        async for c in db.campaigns.find(cq, {"_id": 0, "account_ids": 1}):
            for aid in c.get("account_ids") or []:
                busy.add(aid)
        async for d in db.drip_campaigns.find(dq, {"_id": 0, "account_ids": 1}):
            for aid in d.get("account_ids") or []:
                busy.add(aid)
        return busy

    async def _affected_campaigns(user_doc: Dict[str, Any], account_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Return campaigns + drips that currently contain the given account_id."""
        is_admin = user_doc.get("role") == "super_admin"
        cq: Dict[str, Any] = {"account_ids": account_id, "status": {"$in": ACTIVE_CAMPAIGN_STATUSES}}
        dq: Dict[str, Any] = {"account_ids": account_id, "status": {"$in": ACTIVE_DRIP_STATUSES}}
        if not is_admin:
            cq["user_id"] = user_doc["user_id"]
            dq["user_id"] = user_doc["user_id"]
        camps = await db.campaigns.find(cq, {"_id": 0, "campaign_id": 1, "name": 1, "status": 1}).to_list(2000)
        drips = await db.drip_campaigns.find(dq, {"_id": 0, "drip_id": 1, "name": 1, "status": 1}).to_list(2000)
        return {"campaigns": camps, "drips": drips}

    async def _pick_replacement(
        user_doc: Dict[str, Any],
        replaced_row: Dict[str, Any],
        override_account_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Find the best replacement inbox honouring user-confirmed rules."""
        rows = await load_inboxes_fn(db, user_doc)
        busy = await _busy_account_ids(user_doc)

        if override_account_id:
            cand = next((r for r in rows if r["account_id"] == override_account_id), None)
            if not cand:
                raise HTTPException(status_code=404, detail="Override candidate not found")
            if cand["account_id"] in busy:
                raise HTTPException(status_code=400, detail="Override candidate is already in use by a campaign or drip")
            if cand["status"] in REPLACEABLE_STATUSES:
                raise HTTPException(status_code=400, detail=f"Override candidate is {cand['status']}")
            return cand

        replaced_domain = replaced_row.get("domain") or ""
        # Healthy + free + has capacity. Warmup is a parallel process —
        # a warming inbox still qualifies as a replacement candidate.
        pool = [
            r for r in rows
            if r["account_id"] != replaced_row["account_id"]
            and r["account_id"] not in busy
            and r["status"] not in REPLACEABLE_STATUSES
            and r["remaining_capacity"] > 0
        ]
        if not pool:
            return None
        # cross-domain first, then highest remaining capacity, then daily_limit
        pool.sort(key=lambda r: (
            0 if r["domain"] != replaced_domain else 1,
            -int(r["remaining_capacity"]),
            -int(r["daily_limit"]),
        ))
        return pool[0]

    async def _swap_in_collections(user_doc: Dict[str, Any], old_id: str, new_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Replace old_id with new_id inside campaign + drip `account_ids` arrays."""
        is_admin = user_doc.get("role") == "super_admin"
        cq: Dict[str, Any] = {"account_ids": old_id, "status": {"$in": ACTIVE_CAMPAIGN_STATUSES}}
        dq: Dict[str, Any] = {"account_ids": old_id, "status": {"$in": ACTIVE_DRIP_STATUSES}}
        if not is_admin:
            cq["user_id"] = user_doc["user_id"]
            dq["user_id"] = user_doc["user_id"]

        camps = await db.campaigns.find(cq, {"_id": 0, "campaign_id": 1, "name": 1, "status": 1, "account_ids": 1}).to_list(2000)
        drips = await db.drip_campaigns.find(dq, {"_id": 0, "drip_id": 1, "name": 1, "status": 1, "account_ids": 1}).to_list(2000)

        swapped_camps: List[Dict[str, Any]] = []
        for c in camps:
            ids = [new_id if a == old_id else a for a in (c.get("account_ids") or [])]
            # Avoid creating duplicates if the replacement was somehow already in the list
            seen: List[str] = []
            for a in ids:
                if a not in seen:
                    seen.append(a)
            await db.campaigns.update_one({"campaign_id": c["campaign_id"]}, {"$set": {"account_ids": seen}})
            swapped_camps.append({"campaign_id": c["campaign_id"], "name": c.get("name"), "kind": "campaign", "status": c.get("status")})
        swapped_drips: List[Dict[str, Any]] = []
        for d in drips:
            ids = [new_id if a == old_id else a for a in (d.get("account_ids") or [])]
            seen = []
            for a in ids:
                if a not in seen:
                    seen.append(a)
            await db.drip_campaigns.update_one({"drip_id": d["drip_id"]}, {"$set": {"account_ids": seen}})
            swapped_drips.append({"campaign_id": d["drip_id"], "name": d.get("name"), "kind": "drip", "status": d.get("status")})
        return {"campaigns": swapped_camps, "drips": swapped_drips}

    async def _log_replacement(doc: Dict[str, Any]) -> Dict[str, Any]:
        doc.setdefault("replacement_id", f"rep_{uuid.uuid4().hex[:12]}")
        doc.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        await db.tracked_replacements.insert_one(doc.copy())
        doc.pop("_id", None)
        return doc

    # ───────────── 1. PREVIEW REPLACEMENT ─────────────
    @router.get("/replacements/candidate/{account_id}")
    async def candidate(account_id: str, user=Depends(get_infra_user)):
        rows = await load_inboxes_fn(db, user)
        replaced = next((r for r in rows if r["account_id"] == account_id), None)
        if not replaced:
            raise HTTPException(status_code=404, detail="Inbox not found or not visible")
        candidate_row = await _pick_replacement(user, replaced)
        affected = await _affected_campaigns(user, account_id)
        return {
            "replaced": {
                "account_id": replaced["account_id"],
                "email": replaced["email"],
                "domain": replaced["domain"],
                "status": replaced["status"],
                "remaining_capacity": replaced["remaining_capacity"],
            },
            "candidate": (
                {
                    "account_id": candidate_row["account_id"],
                    "email": candidate_row["email"],
                    "domain": candidate_row["domain"],
                    "status": candidate_row["status"],
                    "remaining_capacity": candidate_row["remaining_capacity"],
                    "daily_limit": candidate_row["daily_limit"],
                    "cross_domain": candidate_row["domain"] != replaced["domain"],
                }
                if candidate_row else None
            ),
            "affected": affected,
            "no_candidate_reason": (
                None if candidate_row else
                "No free healthy inbox available — every healthy inbox is already assigned to a running campaign or drip."
            ),
        }

    # ───────────── 2. EXECUTE REPLACEMENT ─────────────
    @router.post("/replacements/execute/{account_id}")
    async def execute(account_id: str, body: ExecuteReplacementBody, user=Depends(get_infra_user)):
        rows = await load_inboxes_fn(db, user)
        replaced = next((r for r in rows if r["account_id"] == account_id), None)
        if not replaced:
            raise HTTPException(status_code=404, detail="Inbox not found or not visible")

        candidate_row = await _pick_replacement(user, replaced, override_account_id=body.replacement_account_id)
        if not candidate_row:
            # Log no-candidate event so the history still reflects the attempt
            log = await _log_replacement({
                "user_id": user["user_id"],
                "replaced_account_id": replaced["account_id"],
                "replaced_email": replaced["email"],
                "replaced_domain": replaced["domain"],
                "replaced_status": replaced["status"],
                "replacement_account_id": None,
                "replacement_email": None,
                "replacement_domain": None,
                "reason": body.reason or replaced["status"],
                "triggered_by": "manual" if body.manual else "auto",
                "status": "no_candidate",
                "campaigns_swapped": [],
                "drips_swapped": [],
            })
            raise HTTPException(status_code=409, detail={
                "message": "No free healthy inbox available for replacement",
                "log": {**log, "_id": None},
            })

        swapped = await _swap_in_collections(user, replaced["account_id"], candidate_row["account_id"])

        log = await _log_replacement({
            "user_id": user["user_id"],
            "replaced_account_id": replaced["account_id"],
            "replaced_email": replaced["email"],
            "replaced_domain": replaced["domain"],
            "replaced_status": replaced["status"],
            "replacement_account_id": candidate_row["account_id"],
            "replacement_email": candidate_row["email"],
            "replacement_domain": candidate_row["domain"],
            "cross_domain": candidate_row["domain"] != replaced["domain"],
            "reason": body.reason or replaced["status"],
            "triggered_by": "manual" if body.manual else "auto",
            "status": "completed",
            "campaigns_swapped": swapped["campaigns"],
            "drips_swapped": swapped["drips"],
        })
        log.pop("_id", None)
        return {
            "message": "Replacement completed",
            "log": log,
            "swap_counts": {"campaigns": len(swapped["campaigns"]), "drips": len(swapped["drips"])},
        }

    # ───────────── 3. AUTO SCAN (replace all at-risk) ─────────────
    @router.post("/replacements/auto-scan")
    async def auto_scan(user=Depends(get_infra_user)):
        rows = await load_inboxes_fn(db, user)
        targets = [r for r in rows if r["status"] in REPLACEABLE_STATUSES and r["active_campaign_count"] > 0]
        results = {"scanned": len(rows), "candidates": len(targets), "completed": [], "no_candidate": []}

        for target in targets:
            cand = await _pick_replacement(user, target)
            if not cand:
                log = await _log_replacement({
                    "user_id": user["user_id"],
                    "replaced_account_id": target["account_id"],
                    "replaced_email": target["email"],
                    "replaced_domain": target["domain"],
                    "replaced_status": target["status"],
                    "replacement_account_id": None,
                    "replacement_email": None,
                    "replacement_domain": None,
                    "reason": target["status"],
                    "triggered_by": "auto",
                    "status": "no_candidate",
                    "campaigns_swapped": [],
                    "drips_swapped": [],
                })
                log.pop("_id", None)
                results["no_candidate"].append(log)
                continue

            swapped = await _swap_in_collections(user, target["account_id"], cand["account_id"])
            log = await _log_replacement({
                "user_id": user["user_id"],
                "replaced_account_id": target["account_id"],
                "replaced_email": target["email"],
                "replaced_domain": target["domain"],
                "replaced_status": target["status"],
                "replacement_account_id": cand["account_id"],
                "replacement_email": cand["email"],
                "replacement_domain": cand["domain"],
                "cross_domain": cand["domain"] != target["domain"],
                "reason": target["status"],
                "triggered_by": "auto",
                "status": "completed",
                "campaigns_swapped": swapped["campaigns"],
                "drips_swapped": swapped["drips"],
            })
            log.pop("_id", None)
            results["completed"].append(log)
        return results

    # ───────────── 4. HISTORY ─────────────
    @router.get("/replacements")
    async def history(limit: int = 200, status: Optional[str] = None,
                      triggered_by: Optional[str] = None, user=Depends(get_infra_user)):
        is_admin = user.get("role") == "super_admin"
        q: Dict[str, Any] = {} if is_admin else {"user_id": user["user_id"]}
        if status:
            q["status"] = status
        if triggered_by:
            q["triggered_by"] = triggered_by
        docs = await db.tracked_replacements.find(q, {"_id": 0}).sort("created_at", -1).to_list(min(max(limit, 1), 1000))

        counts: Dict[str, int] = defaultdict(int)
        for d in docs:
            counts[d.get("status") or "unknown"] += 1
            counts[f"by_{d.get('triggered_by') or 'unknown'}"] += 1
        return {"items": docs, "counts": dict(counts), "total": len(docs)}
