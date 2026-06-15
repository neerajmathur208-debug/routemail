"""Sent Email Viewer + Search (Phase 2 Batch C).

Backs the "View Email" button in Campaign Logs / Drip Logs and the dedicated
sent-email search page. Reads from the `sent_emails` collection populated by
``unibox_routes.register_sent_email`` — which from Iteration 59 onwards stores
the rendered ``body_html`` / ``body_text`` / ``from_name`` / ``folder_id``.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query


def build_sent_email_router(db, get_current_user):
    router = APIRouter(tags=["sent-emails"])

    @router.get("/sent-emails")
    async def list_sent_emails(
        q: Optional[str] = Query(None, description="Search recipient / subject / from_name / campaign / drip"),
        campaign_id: Optional[str] = Query(None),
        drip_id: Optional[str] = Query(None),
        account_id: Optional[str] = Query(None),
        folder_id: Optional[str] = Query(None),
        date_from: Optional[str] = Query(None),
        date_to: Optional[str] = Query(None),
        sort_by: str = Query("sent_at"),
        sort_dir: str = Query("desc"),
        limit: int = Query(50, ge=1, le=500),
        skip: int = Query(0, ge=0),
        user=Depends(get_current_user),
    ):
        mongo_q: Dict[str, Any] = {"user_id": user.user_id}
        if campaign_id:
            mongo_q["campaign_id"] = campaign_id
        if drip_id:
            mongo_q["drip_campaign_id"] = drip_id
        if account_id:
            mongo_q["account_id"] = account_id
        if folder_id:
            mongo_q["folder_id"] = folder_id
        if date_from or date_to:
            d: Dict[str, Any] = {}
            if date_from:
                d["$gte"] = date_from
            if date_to:
                d["$lte"] = date_to
            mongo_q["sent_at"] = d
        if q:
            esc = q.strip()
            # Match against recipient, subject, from_name, campaign_name, drip_campaign_name
            mongo_q["$or"] = [
                {"recipient_email": {"$regex": esc, "$options": "i"}},
                {"subject": {"$regex": esc, "$options": "i"}},
                {"from_name": {"$regex": esc, "$options": "i"}},
                {"campaign_name": {"$regex": esc, "$options": "i"}},
                {"drip_campaign_name": {"$regex": esc, "$options": "i"}},
            ]

        direction = -1 if sort_dir.lower() == "desc" else 1
        # Only allow safe sort columns
        if sort_by not in ("sent_at", "recipient_email", "subject", "campaign_name"):
            sort_by = "sent_at"

        total = await db.sent_emails.count_documents(mongo_q)
        cursor = (
            db.sent_emails.find(
                mongo_q,
                # Drop body_html on list to keep payload small — full body is
                # only fetched from the single-record endpoint.
                {"_id": 0, "body_html": 0, "body_text": 0},
            )
            .sort(sort_by, direction)
            .skip(skip)
            .limit(limit)
        )
        items = await cursor.to_list(limit)
        return {"items": items, "total": total, "limit": limit, "skip": skip}

    @router.get("/sent-emails/by-recipient")
    async def latest_by_recipient(
        recipient_email: str = Query(...),
        campaign_id: Optional[str] = Query(None),
        drip_id: Optional[str] = Query(None),
        user=Depends(get_current_user),
    ):
        """Lookup the most recent sent_email matching a recipient — used by
        the 'View Email' button on Campaign Logs which only knows the
        recipient + campaign_id."""
        mongo_q: Dict[str, Any] = {
            "user_id": user.user_id,
            "recipient_email": (recipient_email or "").lower(),
        }
        if campaign_id:
            mongo_q["campaign_id"] = campaign_id
        if drip_id:
            mongo_q["drip_campaign_id"] = drip_id
        doc = await db.sent_emails.find_one(mongo_q, {"_id": 0}, sort=[("sent_at", -1)])
        if not doc:
            raise HTTPException(status_code=404, detail="No sent email matches that recipient")
        return doc

    @router.get("/sent-emails/{sent_id}")
    async def get_sent_email(sent_id: str, user=Depends(get_current_user)):
        doc = await db.sent_emails.find_one(
            {"sent_id": sent_id, "user_id": user.user_id},
            {"_id": 0},
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Sent email not found")
        return doc

    return router
