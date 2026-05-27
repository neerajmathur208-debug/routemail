"""
Unibox + Responses/Leads + IMAP receiving routes for RouteMail.

This module owns:
- Real IMAP background worker that polls each account every ~10 min
- Reply ingestion + campaign mapping (Message-ID / In-Reply-To / References + fallback)
- Auto-stop drip steps when contact replies
- Unibox listing / filtering / mark-read / bulk DNE / bulk-save-to-lead-folder
- Responses/Leads folder system + saved lead CRUD
- Outbound Message-ID tracking helper (called from existing send paths)

Mounted by server.py:
    from unibox_routes import build_unibox_router, run_imap_worker, register_sent_email
    api_router.include_router(build_unibox_router(db, get_current_user, fernet))

Background task is started in server.py at startup.
"""
from __future__ import annotations

import asyncio
import email
import imaplib
import logging
import re
import uuid
from datetime import datetime, timezone
from email.utils import getaddresses, parseaddr, parsedate_to_datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

IMAP_SYNC_INTERVAL_SECONDS = 600  # 10 minutes (user choice)
IMAP_SYNC_BATCH_LIMIT = 50  # max new messages fetched per account per cycle

# ---------------------------------------------------------------------------
# Outbound Message-ID tracking (called from existing send functions)
# ---------------------------------------------------------------------------

async def register_sent_email(
    db,
    *,
    user_id: str,
    account_id: str,
    sender_email: str,
    recipient_email: str,
    subject: str,
    message_id: Optional[str],
    campaign_id: Optional[str] = None,
    campaign_name: Optional[str] = None,
    drip_campaign_id: Optional[str] = None,
    drip_campaign_name: Optional[str] = None,
    drip_step_number: Optional[int] = None,
) -> None:
    """Persist outbound message metadata so we can match incoming replies later."""
    try:
        doc = {
            "sent_id": f"sent_{uuid.uuid4().hex[:12]}",
            "user_id": user_id,
            "account_id": account_id,
            "sender_email": sender_email,
            "recipient_email": (recipient_email or "").lower(),
            "subject": (subject or "").strip(),
            "message_id": (message_id or "").strip().strip("<>"),
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "drip_campaign_id": drip_campaign_id,
            "drip_campaign_name": drip_campaign_name,
            "drip_step_number": drip_step_number,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.sent_emails.insert_one(doc)
    except Exception as exc:
        logger.warning(f"[UNIBOX] register_sent_email failed: {exc}")


# ---------------------------------------------------------------------------
# IMAP worker
# ---------------------------------------------------------------------------

def _decrypt(fernet, blob: Optional[str]) -> Optional[str]:
    if not blob:
        return None
    try:
        return fernet.decrypt(blob.encode()).decode()
    except Exception:
        return None


def _normalize_msgid(value: Optional[str]) -> str:
    if not value:
        return ""
    return value.strip().strip("<>").lower()


def _ids_from_header(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [_normalize_msgid(m) for m in re.findall(r"<([^>]+)>", value)]


def _safe_decode(payload: Optional[bytes]) -> str:
    if not payload:
        return ""
    if isinstance(payload, str):
        return payload
    for enc in ("utf-8", "latin-1"):
        try:
            return payload.decode(enc, errors="ignore")
        except Exception:
            continue
    return ""


def _extract_body(msg: "email.message.Message") -> str:
    """Extract a usable plain-text body from an email Message."""
    if msg.is_multipart():
        # Prefer text/plain over text/html
        for part in msg.walk():
            ctype = part.get_content_type()
            cdisp = part.get("Content-Disposition", "")
            if "attachment" in str(cdisp):
                continue
            if ctype == "text/plain":
                return _safe_decode(part.get_payload(decode=True)).strip()
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html = _safe_decode(part.get_payload(decode=True))
                # crude HTML strip
                return re.sub(r"<[^>]+>", " ", html).strip()
        return ""
    return _safe_decode(msg.get_payload(decode=True)).strip()


async def _process_imap_account(db, fernet, account: Dict[str, Any]) -> None:
    """Fetch new UIDs from one account's IMAP INBOX and store them as replies."""
    host = account.get("imap_host")
    port = int(account.get("imap_port") or 993)
    username = account.get("imap_username") or account.get("email")
    password = _decrypt(fernet, account.get("imap_password_encrypted"))
    encryption = (account.get("imap_encryption") or "ssl").lower()
    account_id = account.get("account_id")
    user_id = account.get("user_id")

    if not host or not password:
        return  # skipped — not configured

    last_uid = int(account.get("imap_last_uid") or 0)

    try:
        # Connect (blocking) inside the event loop's default executor
        def _imap_fetch() -> List[Dict[str, Any]]:
            if encryption == "ssl":
                conn = imaplib.IMAP4_SSL(host, port, timeout=20)
            else:
                conn = imaplib.IMAP4(host, port, timeout=20)
                try:
                    conn.starttls()
                except Exception:
                    pass
            conn.login(username, password)
            conn.select("INBOX", readonly=True)
            # UID search: everything newer than last_uid
            search_q = f"UID {last_uid + 1}:*" if last_uid else "ALL"
            typ, data = conn.uid("search", None, search_q)
            if typ != "OK" or not data or not data[0]:
                conn.logout()
                return []
            uids = data[0].split()
            uids = uids[-IMAP_SYNC_BATCH_LIMIT:]  # cap per cycle
            messages: List[Dict[str, Any]] = []
            for uid in uids:
                uid_int = int(uid)
                typ, fdata = conn.uid("fetch", uid, "(RFC822)")
                if typ != "OK" or not fdata or not fdata[0]:
                    continue
                raw = fdata[0][1]
                msg = email.message_from_bytes(raw)
                from_addr = parseaddr(msg.get("From", ""))[1].lower()
                to_addrs = [a[1].lower() for a in getaddresses([msg.get("To", "")]) if a[1]]
                subject_raw = msg.get("Subject", "") or ""
                # Decode subject if MIME-encoded
                try:
                    parts = email.header.decode_header(subject_raw)
                    subject = "".join(
                        (p.decode(enc or "utf-8", errors="ignore") if isinstance(p, bytes) else p)
                        for p, enc in parts
                    )
                except Exception:
                    subject = subject_raw
                date_hdr = msg.get("Date", "")
                try:
                    received_dt = parsedate_to_datetime(date_hdr) if date_hdr else datetime.now(timezone.utc)
                except Exception:
                    received_dt = datetime.now(timezone.utc)
                if received_dt and received_dt.tzinfo is None:
                    received_dt = received_dt.replace(tzinfo=timezone.utc)
                messages.append(
                    {
                        "uid": uid_int,
                        "from_email": from_addr,
                        "to_emails": to_addrs,
                        "subject": subject,
                        "message_id": _normalize_msgid(msg.get("Message-ID")),
                        "in_reply_to": _normalize_msgid(msg.get("In-Reply-To")),
                        "references": _ids_from_header(msg.get("References")),
                        "received_at": received_dt.isoformat(),
                        "body": _extract_body(msg)[:20000],  # cap body 20KB
                    }
                )
            try:
                conn.logout()
            except Exception:
                pass
            return messages

        messages = await asyncio.to_thread(_imap_fetch)

        max_uid_seen = last_uid
        for m in messages:
            max_uid_seen = max(max_uid_seen, m["uid"])

            # De-dupe by Message-ID per user
            if m["message_id"]:
                existing = await db.replies.find_one(
                    {"user_id": user_id, "message_id": m["message_id"]},
                    {"_id": 0, "reply_id": 1},
                )
                if existing:
                    continue

            # Skip RouteMail's own warmup traffic
            if "(RTM)" in m["subject"]:
                continue

            # Match this reply to an outbound send
            matched = None
            candidates = m["references"] + ([m["in_reply_to"]] if m["in_reply_to"] else [])
            if candidates:
                matched = await db.sent_emails.find_one(
                    {"user_id": user_id, "message_id": {"$in": candidates}},
                    {"_id": 0},
                )
            if not matched:
                # Fallback: same recipient+account+subject (Re: trimmed)
                clean_subject = re.sub(r"^\s*(re|fwd?):\s*", "", m["subject"], flags=re.I).strip()
                matched = await db.sent_emails.find_one(
                    {
                        "user_id": user_id,
                        "account_id": account_id,
                        "recipient_email": m["from_email"],
                        "subject": {"$regex": f"^(?:re:\\s*)*{re.escape(clean_subject)}$", "$options": "i"},
                    },
                    {"_id": 0},
                    sort=[("sent_at", -1)],
                )

            reply_doc = {
                "reply_id": f"rep_{uuid.uuid4().hex[:12]}",
                "user_id": user_id,
                "account_id": account_id,
                "received_on_email": account.get("email"),
                "from_email": m["from_email"],
                "subject": m["subject"],
                "body": m["body"],
                "message_id": m["message_id"],
                "in_reply_to": m["in_reply_to"],
                "references": m["references"],
                "received_at": m["received_at"],
                "read": False,
                "campaign_id": matched.get("campaign_id") if matched else None,
                "campaign_name": matched.get("campaign_name") if matched else None,
                "drip_campaign_id": matched.get("drip_campaign_id") if matched else None,
                "drip_campaign_name": matched.get("drip_campaign_name") if matched else None,
                "drip_step_number": matched.get("drip_step_number") if matched else None,
                "sent_id": matched.get("sent_id") if matched else None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.replies.insert_one(reply_doc)
            logger.info(
                f"[UNIBOX] New reply for user {user_id} on {account.get('email')} from {m['from_email']} "
                f"(matched_campaign={reply_doc['campaign_id'] or reply_doc['drip_campaign_id']})"
            )

            # Auto-stop drip for replied contact
            if reply_doc.get("drip_campaign_id"):
                try:
                    await db.drip_contacts.update_many(
                        {
                            "drip_id": reply_doc["drip_campaign_id"],
                            "contact_email": m["from_email"],
                            "status": {"$nin": ["replied", "completed", "stopped"]},
                        },
                        {
                            "$set": {
                                "status": "replied",
                                "stopped_at": datetime.now(timezone.utc).isoformat(),
                                "stopped_reason": "reply_received",
                            }
                        },
                    )
                except Exception as exc:
                    logger.warning(f"[UNIBOX] failed to auto-stop drip: {exc}")

        # Persist sync state
        await db.email_accounts.update_one(
            {"account_id": account_id, "user_id": user_id},
            {
                "$set": {
                    "imap_last_sync_at": datetime.now(timezone.utc).isoformat(),
                    "imap_last_uid": max_uid_seen,
                    "imap_last_error": None,
                }
            },
        )
    except Exception as exc:
        msg = str(exc)[:300]
        logger.warning(f"[UNIBOX] IMAP sync failed for {account.get('email')}: {msg}")
        await db.email_accounts.update_one(
            {"account_id": account_id, "user_id": user_id},
            {"$set": {"imap_last_error": msg, "imap_last_sync_at": datetime.now(timezone.utc).isoformat()}},
        )


async def run_imap_worker(db, fernet) -> None:
    """Background loop — polls IMAP-configured accounts every IMAP_SYNC_INTERVAL_SECONDS."""
    logger.info("[UNIBOX] IMAP worker started")
    while True:
        try:
            accounts = await db.email_accounts.find(
                {"imap_host": {"$nin": [None, ""]}, "imap_password_encrypted": {"$nin": [None, ""]}},
                {"_id": 0},
            ).to_list(1000)
            for acc in accounts:
                try:
                    await _process_imap_account(db, fernet, acc)
                except Exception as exc:
                    logger.error(f"[UNIBOX] account loop error: {exc}")
        except Exception as exc:
            logger.error(f"[UNIBOX] worker loop error: {exc}")
        await asyncio.sleep(IMAP_SYNC_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class MarkRepliesRequest(BaseModel):
    reply_ids: List[str]
    read: bool = True


class BulkDNERequest(BaseModel):
    reply_ids: List[str]


class CreateFolderRequest(BaseModel):
    name: str


class RenameFolderRequest(BaseModel):
    name: str


class SaveLeadRequest(BaseModel):
    reply_ids: List[str]
    folder_id: str
    new_folder_name: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def build_unibox_router(db, get_current_user, fernet):  # noqa: C901
    router = APIRouter(tags=["unibox"])

    # =================== UNIBOX ===================

    @router.get("/unibox/replies")
    async def list_replies(
        unread_only: bool = Query(False),
        campaign_id: Optional[str] = Query(None),
        drip_id: Optional[str] = Query(None),
        account_id: Optional[str] = Query(None),
        date_from: Optional[str] = Query(None),
        date_to: Optional[str] = Query(None),
        limit: int = Query(100),
        skip: int = Query(0),
        user=Depends(get_current_user),
    ):
        q: Dict[str, Any] = {"user_id": user.user_id}
        if unread_only:
            q["read"] = False
        if campaign_id:
            q["campaign_id"] = campaign_id
        if drip_id:
            q["drip_campaign_id"] = drip_id
        if account_id:
            q["account_id"] = account_id
        if date_from or date_to:
            d: Dict[str, Any] = {}
            if date_from:
                d["$gte"] = date_from
            if date_to:
                d["$lte"] = date_to
            q["received_at"] = d
        total = await db.replies.count_documents(q)
        unread_count = await db.replies.count_documents({"user_id": user.user_id, "read": False})
        items = (
            await db.replies.find(q, {"_id": 0})
            .sort("received_at", -1)
            .skip(skip)
            .limit(limit)
            .to_list(limit)
        )
        return {
            "items": items,
            "total": total,
            "unread_count": unread_count,
            "skip": skip,
            "limit": limit,
        }

    @router.post("/unibox/replies/mark")
    async def mark_replies(req: MarkRepliesRequest, user=Depends(get_current_user)):
        if not req.reply_ids:
            raise HTTPException(status_code=400, detail="No replies selected")
        res = await db.replies.update_many(
            {"user_id": user.user_id, "reply_id": {"$in": req.reply_ids}},
            {"$set": {"read": bool(req.read)}},
        )
        return {"matched": res.matched_count, "modified": res.modified_count}

    @router.post("/unibox/replies/add-to-dne")
    async def add_replies_to_dne(req: BulkDNERequest, user=Depends(get_current_user)):
        if not req.reply_ids:
            raise HTTPException(status_code=400, detail="No replies selected")
        replies = await db.replies.find(
            {"user_id": user.user_id, "reply_id": {"$in": req.reply_ids}},
            {"_id": 0, "from_email": 1},
        ).to_list(1000)
        # Find / lazy-create global DNE
        dne = await db.dne_lists.find_one(
            {"user_id": user.user_id, "is_global": True}, {"_id": 0}
        )
        if not dne:
            dne = {
                "list_id": f"dne_{uuid.uuid4().hex[:12]}",
                "user_id": user.user_id,
                "name": "Global Do Not Email",
                "is_global": True,
                "email_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.dne_lists.insert_one(dne)
        added = 0
        for r in replies:
            email_addr = (r.get("from_email") or "").strip().lower()
            if not email_addr:
                continue
            existing = await db.dne_emails.find_one(
                {"list_id": dne["list_id"], "user_id": user.user_id, "email": email_addr},
                {"_id": 0},
            )
            if existing:
                continue
            await db.dne_emails.insert_one(
                {
                    "list_id": dne["list_id"],
                    "user_id": user.user_id,
                    "email": email_addr,
                    "source": "unibox",
                    "added_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            added += 1
        if added:
            await db.dne_lists.update_one(
                {"list_id": dne["list_id"]},
                {"$inc": {"email_count": added}},
            )
        return {"added": added, "list_id": dne["list_id"]}

    @router.get("/unibox/status")
    async def unibox_status(user=Depends(get_current_user)):
        """Per-account sending/receiving status + last sync."""
        accounts = await db.email_accounts.find(
            {"user_id": user.user_id},
            {"_id": 0, "smtp_password_encrypted": 0, "imap_password_encrypted": 0},
        ).to_list(1000)
        out = []
        for a in accounts:
            out.append(
                {
                    "account_id": a.get("account_id"),
                    "email": a.get("email"),
                    "from_name": a.get("from_name") or a.get("display_name"),
                    "sending_configured": bool(a.get("smtp_host")),
                    "receiving_configured": bool(a.get("imap_host")),
                    "imap_last_sync_at": a.get("imap_last_sync_at"),
                    "imap_last_error": a.get("imap_last_error"),
                }
            )
        return {"accounts": out, "sync_interval_seconds": IMAP_SYNC_INTERVAL_SECONDS}

    # =================== RESPONSES / LEADS ===================

    @router.get("/leads/folders")
    async def list_folders(user=Depends(get_current_user)):
        folders = await db.lead_folders.find(
            {"user_id": user.user_id}, {"_id": 0}
        ).sort("created_at", -1).to_list(500)
        # attach counts
        for f in folders:
            f["lead_count"] = await db.leads.count_documents(
                {"user_id": user.user_id, "folder_id": f["folder_id"]}
            )
        return {"folders": folders}

    @router.post("/leads/folders")
    async def create_folder(req: CreateFolderRequest, user=Depends(get_current_user)):
        name = (req.name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Folder name is required")
        doc = {
            "folder_id": f"foldr_{uuid.uuid4().hex[:10]}",
            "user_id": user.user_id,
            "name": name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.lead_folders.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/leads/folders/{folder_id}")
    async def rename_folder(folder_id: str, req: RenameFolderRequest, user=Depends(get_current_user)):
        name = (req.name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Folder name is required")
        res = await db.lead_folders.update_one(
            {"folder_id": folder_id, "user_id": user.user_id},
            {"$set": {"name": name}},
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Folder not found")
        return {"success": True}

    @router.delete("/leads/folders/{folder_id}")
    async def delete_folder(folder_id: str, user=Depends(get_current_user)):
        res = await db.lead_folders.delete_one(
            {"folder_id": folder_id, "user_id": user.user_id}
        )
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Folder not found")
        await db.leads.delete_many({"user_id": user.user_id, "folder_id": folder_id})
        return {"success": True}

    @router.get("/leads")
    async def list_leads(
        folder_id: Optional[str] = Query(None),
        user=Depends(get_current_user),
    ):
        q: Dict[str, Any] = {"user_id": user.user_id}
        if folder_id:
            q["folder_id"] = folder_id
        leads = (
            await db.leads.find(q, {"_id": 0})
            .sort("saved_at", -1)
            .to_list(2000)
        )
        return {"items": leads}

    @router.post("/leads/save")
    async def save_leads(req: SaveLeadRequest, user=Depends(get_current_user)):
        if not req.reply_ids:
            raise HTTPException(status_code=400, detail="No replies selected")
        # Resolve folder: either an existing one or create new
        folder_id = req.folder_id
        if folder_id == "__new__":
            name = (req.new_folder_name or "").strip()
            if not name:
                raise HTTPException(status_code=400, detail="new_folder_name is required when folder_id='__new__'")
            new_folder = {
                "folder_id": f"foldr_{uuid.uuid4().hex[:10]}",
                "user_id": user.user_id,
                "name": name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.lead_folders.insert_one(new_folder)
            folder_id = new_folder["folder_id"]
        else:
            f = await db.lead_folders.find_one(
                {"folder_id": folder_id, "user_id": user.user_id}, {"_id": 0}
            )
            if not f:
                raise HTTPException(status_code=404, detail="Folder not found")

        replies = await db.replies.find(
            {"user_id": user.user_id, "reply_id": {"$in": req.reply_ids}}, {"_id": 0}
        ).to_list(2000)
        saved = 0
        for r in replies:
            doc = {
                "lead_id": f"lead_{uuid.uuid4().hex[:10]}",
                "user_id": user.user_id,
                "folder_id": folder_id,
                "reply_id": r.get("reply_id"),
                "contact_email": r.get("from_email"),
                "contact_name": None,
                "subject": r.get("subject"),
                "body": r.get("body"),
                "campaign_name": r.get("campaign_name") or r.get("drip_campaign_name"),
                "drip_step_number": r.get("drip_step_number"),
                "received_on_email": r.get("received_on_email"),
                "received_at": r.get("received_at"),
                "notes": (req.notes or "").strip() or None,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.leads.insert_one(doc)
            saved += 1
        return {"saved": saved, "folder_id": folder_id}

    return router
