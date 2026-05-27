"""
Backup & Restore routes for RouteMail.

Adds export/import endpoints for individual modules and a full-account ZIP
backup. All endpoints are scoped to the authenticated user (no cross-user
access). Email-account credentials are stripped by default; the caller may
opt-in to include encrypted credentials (never plain text).

Mounted by server.py:
    from backup_routes import build_backup_router
    api_router.include_router(build_backup_router(db, get_current_user))
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

BACKUP_SCHEMA_VERSION = 1
ROUTEMAIL_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONFLICT_MODES = {"skip", "replace", "copy"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_internal_ids(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc.pop("_id", None)
    return doc


def _sanitize_account(acc: Dict[str, Any], include_credentials: bool) -> Dict[str, Any]:
    out = {k: v for k, v in acc.items() if k != "_id"}
    if not include_credentials:
        out.pop("smtp_password_encrypted", None)
        out.pop("imap_password_encrypted", None)
    # Never export plain text password fields if any sneaked in
    out.pop("smtp_password", None)
    out.pop("imap_password", None)
    out.pop("password", None)
    # Reset live counters on export — restored accounts start clean
    out.pop("daily_send_count", None)
    out.pop("last_send_date", None)
    out.pop("last_reset_at", None)
    out.pop("imap_last_sync_at", None)
    out.pop("imap_last_error", None)
    out.pop("imap_last_uid", None)
    return out


def _emails_list_to_csv(records: List[Dict[str, Any]], headers: List[str]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    for r in records:
        writer.writerow(r)
    return buf.getvalue()


def _stream_json(payload: Any, filename: str) -> StreamingResponse:
    data = json.dumps(payload, indent=2, default=str)
    return StreamingResponse(
        iter([data]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _stream_csv(text: str, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([text]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class ImportPayload(BaseModel):
    items: List[Dict[str, Any]] = []
    conflict: str = "copy"  # skip | replace | copy


# ---------------------------------------------------------------------------
# Core import logic (reused by individual + full restore)
# ---------------------------------------------------------------------------

def _normalize_conflict(mode: Optional[str]) -> str:
    mode = (mode or "copy").lower()
    if mode not in CONFLICT_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid conflict mode. Allowed: {sorted(CONFLICT_MODES)}",
        )
    return mode


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def build_backup_router(db, get_current_user):  # noqa: C901 — single feature module
    router = APIRouter(prefix="/backup", tags=["backup"])

    # =====================================================================
    # EXPORT — individual modules
    # =====================================================================

    @router.get("/export/campaigns")
    async def export_campaigns(user=Depends(get_current_user)):
        items = await db.campaigns.find(
            {"user_id": user.user_id}, {"_id": 0}
        ).to_list(10000)
        # Strip live state fields — only static config exported
        for c in items:
            for k in (
                "sent_count", "failed_count", "current_account_index",
                "is_locked", "started_at", "completed_at",
            ):
                c.pop(k, None)
        return _stream_json(
            {
                "schema_version": BACKUP_SCHEMA_VERSION,
                "exported_at": _now(),
                "user_email": user.email,
                "count": len(items),
                "items": items,
            },
            f"routemail-campaigns-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json",
        )

    @router.get("/export/drip-campaigns")
    async def export_drip_campaigns(user=Depends(get_current_user)):
        items = await db.drip_campaigns.find(
            {"user_id": user.user_id}, {"_id": 0}
        ).to_list(10000)
        for c in items:
            for k in ("total_sent", "total_contacts", "started_at", "completed_at"):
                c.pop(k, None)
        return _stream_json(
            {
                "schema_version": BACKUP_SCHEMA_VERSION,
                "exported_at": _now(),
                "user_email": user.email,
                "count": len(items),
                "items": items,
            },
            f"routemail-drip-campaigns-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json",
        )

    @router.get("/export/email-accounts")
    async def export_email_accounts(
        include_credentials: bool = Query(False),
        user=Depends(get_current_user),
    ):
        items = await db.email_accounts.find(
            {"user_id": user.user_id}, {"_id": 0}
        ).to_list(10000)
        items = [_sanitize_account(a, include_credentials) for a in items]
        return _stream_json(
            {
                "schema_version": BACKUP_SCHEMA_VERSION,
                "exported_at": _now(),
                "user_email": user.email,
                "include_credentials": include_credentials,
                "count": len(items),
                "items": items,
            },
            f"routemail-email-accounts-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json",
        )

    @router.get("/export/email-lists")
    async def export_email_lists(
        format: str = Query("json"),
        list_id: Optional[str] = Query(None),
        user=Depends(get_current_user),
    ):
        query: Dict[str, Any] = {"user_id": user.user_id}
        if list_id:
            query["list_id"] = list_id
        items = await db.email_lists.find(query, {"_id": 0}).to_list(10000)
        if format.lower() == "csv":
            if not items:
                return _stream_csv("", "routemail-email-lists.csv")
            # CSV mode flattens to one CSV: list_name, then all record columns
            rows = []
            headers_set = {"_list_name"}
            for lst in items:
                for rec in lst.get("emails", []):
                    row = {"_list_name": lst.get("name", "")}
                    row.update(rec)
                    headers_set.update(rec.keys())
                    rows.append(row)
            headers = ["_list_name"] + sorted(h for h in headers_set if h != "_list_name")
            return _stream_csv(
                _emails_list_to_csv(rows, headers),
                f"routemail-email-lists-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv",
            )
        return _stream_json(
            {
                "schema_version": BACKUP_SCHEMA_VERSION,
                "exported_at": _now(),
                "user_email": user.email,
                "count": len(items),
                "items": items,
            },
            f"routemail-email-lists-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json",
        )

    @router.get("/export/dne-lists")
    async def export_dne_lists(
        format: str = Query("json"),
        user=Depends(get_current_user),
    ):
        lists = await db.dne_lists.find(
            {"user_id": user.user_id}, {"_id": 0}
        ).to_list(1000)
        # Attach emails to each list
        for lst in lists:
            emails = await db.dne_emails.find(
                {"list_id": lst["list_id"], "user_id": user.user_id},
                {"_id": 0},
            ).to_list(100000)
            lst["emails"] = emails
        if format.lower() == "csv":
            rows = []
            headers = ["list_name", "email", "source", "added_at"]
            for lst in lists:
                for e in lst.get("emails", []):
                    rows.append(
                        {
                            "list_name": lst.get("name", ""),
                            "email": e.get("email", ""),
                            "source": e.get("source", "manual"),
                            "added_at": e.get("added_at", ""),
                        }
                    )
            return _stream_csv(
                _emails_list_to_csv(rows, headers),
                f"routemail-dne-lists-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv",
            )
        return _stream_json(
            {
                "schema_version": BACKUP_SCHEMA_VERSION,
                "exported_at": _now(),
                "user_email": user.email,
                "count": len(lists),
                "items": lists,
            },
            f"routemail-dne-lists-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json",
        )

    # Spec alias: "Do Not Email Lists" — same payload as /export/dne-lists
    @router.get("/export/do-not-email-lists")
    async def export_do_not_email_lists(
        format: str = Query("json"),
        user=Depends(get_current_user),
    ):
        return await export_dne_lists(format=format, user=user)

    @router.get("/export/responses-leads")
    async def export_responses_leads(user=Depends(get_current_user)):
        folders = await db.lead_folders.find(
            {"user_id": user.user_id}, {"_id": 0}
        ).to_list(2000)
        leads = await db.leads.find(
            {"user_id": user.user_id}, {"_id": 0}
        ).to_list(20000)
        return _stream_json(
            {
                "schema_version": BACKUP_SCHEMA_VERSION,
                "exported_at": _now(),
                "user_email": user.email,
                "folder_count": len(folders),
                "lead_count": len(leads),
                "folders": folders,
                "leads": leads,
            },
            f"routemail-responses-leads-{datetime.now(timezone.utc).strftime('%Y%m%d')}.json",
        )

    # =====================================================================
    # EXPORT — full ZIP backup
    # =====================================================================

    @router.get("/export/full")
    async def export_full_backup(
        include_credentials: bool = Query(False),
        user=Depends(get_current_user),
    ):
        campaigns = await db.campaigns.find(
            {"user_id": user.user_id}, {"_id": 0}
        ).to_list(10000)
        drips = await db.drip_campaigns.find(
            {"user_id": user.user_id}, {"_id": 0}
        ).to_list(10000)
        accounts = [
            _sanitize_account(a, include_credentials)
            for a in await db.email_accounts.find(
                {"user_id": user.user_id}, {"_id": 0}
            ).to_list(10000)
        ]
        lists = await db.email_lists.find(
            {"user_id": user.user_id}, {"_id": 0}
        ).to_list(10000)
        dne_lists = await db.dne_lists.find(
            {"user_id": user.user_id}, {"_id": 0}
        ).to_list(1000)
        for lst in dne_lists:
            lst["emails"] = await db.dne_emails.find(
                {"list_id": lst["list_id"], "user_id": user.user_id},
                {"_id": 0},
            ).to_list(100000)

        # Responses / Leads — folders + leads
        lead_folders = await db.lead_folders.find(
            {"user_id": user.user_id}, {"_id": 0}
        ).to_list(2000)
        leads_all = await db.leads.find(
            {"user_id": user.user_id}, {"_id": 0}
        ).to_list(20000)
        responses_leads = {"folders": lead_folders, "leads": leads_all}

        metadata = {
            "schema_version": BACKUP_SCHEMA_VERSION,
            "routemail_version": ROUTEMAIL_VERSION,
            "user_email": user.email,
            "exported_at": _now(),
            "include_credentials": include_credentials,
            "counts": {
                "campaigns": len(campaigns),
                "drip_campaigns": len(drips),
                "email_accounts": len(accounts),
                "email_lists": len(lists),
                "do_not_email_lists": len(dne_lists),
                "responses_leads_folders": len(lead_folders),
                "responses_leads_items": len(leads_all),
                # backward-compat alias
                "unsubscribe_lists": len(dne_lists),
            },
        }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("metadata.json", json.dumps(metadata, indent=2, default=str))
            zf.writestr("campaigns.json", json.dumps(campaigns, indent=2, default=str))
            zf.writestr("drip_campaigns.json", json.dumps(drips, indent=2, default=str))
            zf.writestr("email_accounts.json", json.dumps(accounts, indent=2, default=str))
            zf.writestr("email_lists.json", json.dumps(lists, indent=2, default=str))
            # Canonical filename per spec + legacy alias kept for older readers
            zf.writestr("do_not_email_lists.json", json.dumps(dne_lists, indent=2, default=str))
            zf.writestr("unsubscribe_lists.json", json.dumps(dne_lists, indent=2, default=str))
            zf.writestr("responses_leads.json", json.dumps(responses_leads, indent=2, default=str))
        buf.seek(0)
        fname = f"routemail-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
        return StreamingResponse(
            iter([buf.read()]),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    # =====================================================================
    # IMPORT — helpers per entity
    # =====================================================================

    async def _import_campaigns(items: List[Dict[str, Any]], conflict: str, user) -> Dict[str, int]:
        stats = {"imported": 0, "skipped": 0, "replaced": 0}
        for item in items:
            name = (item.get("name") or "").strip() or "Imported Campaign"
            existing = await db.campaigns.find_one(
                {"user_id": user.user_id, "name": name}, {"_id": 0}
            )
            doc = {k: v for k, v in item.items() if k != "_id"}
            doc["user_id"] = user.user_id
            # Always restored as draft, never locked, counters zeroed
            doc["status"] = "draft"
            doc["is_locked"] = False
            doc["sent_count"] = 0
            doc["failed_count"] = 0
            doc["current_account_index"] = 0
            doc["started_at"] = None
            doc["completed_at"] = None
            doc["scheduled_at"] = None
            doc["updated_at"] = _now()
            doc.setdefault("created_at", _now())
            if existing:
                if conflict == "skip":
                    stats["skipped"] += 1
                    continue
                if conflict == "replace":
                    doc["campaign_id"] = existing["campaign_id"]
                    await db.campaigns.replace_one(
                        {"campaign_id": existing["campaign_id"], "user_id": user.user_id}, doc
                    )
                    stats["replaced"] += 1
                    continue
                # copy
                doc["name"] = f"{name} (Imported)"
            doc["campaign_id"] = _new_id("camp")
            await db.campaigns.insert_one(doc)
            stats["imported"] += 1
        return stats

    async def _import_drips(items: List[Dict[str, Any]], conflict: str, user) -> Dict[str, int]:
        stats = {"imported": 0, "skipped": 0, "replaced": 0}
        for item in items:
            name = (item.get("name") or "").strip() or "Imported Drip"
            existing = await db.drip_campaigns.find_one(
                {"user_id": user.user_id, "name": name}, {"_id": 0}
            )
            doc = {k: v for k, v in item.items() if k != "_id"}
            doc["user_id"] = user.user_id
            doc["status"] = "draft"
            doc["total_sent"] = 0
            doc["total_contacts"] = 0
            doc["updated_at"] = _now()
            doc.setdefault("created_at", _now())
            if existing:
                if conflict == "skip":
                    stats["skipped"] += 1
                    continue
                if conflict == "replace":
                    doc["drip_id"] = existing["drip_id"]
                    await db.drip_campaigns.replace_one(
                        {"drip_id": existing["drip_id"], "user_id": user.user_id}, doc
                    )
                    stats["replaced"] += 1
                    continue
                doc["name"] = f"{name} (Imported)"
            doc["drip_id"] = _new_id("drip")
            await db.drip_campaigns.insert_one(doc)
            stats["imported"] += 1
        return stats

    async def _import_email_accounts(items: List[Dict[str, Any]], conflict: str, user) -> Dict[str, int]:
        stats = {"imported": 0, "skipped": 0, "replaced": 0}
        for item in items:
            email = (item.get("email") or "").strip().lower()
            if not email:
                continue
            existing = await db.email_accounts.find_one(
                {"user_id": user.user_id, "email": email}, {"_id": 0}
            )
            doc = {k: v for k, v in item.items() if k != "_id"}
            doc["user_id"] = user.user_id
            doc["email"] = email
            # Restored accounts are inactive until verified; warmup paused
            doc["status"] = "pending_verification"
            doc["last_error"] = None
            doc["daily_send_count"] = 0
            doc.pop("last_send_date", None)
            if doc.get("warmup_enabled"):
                doc["warmup_status"] = "paused"
            doc.setdefault("created_at", _now())
            if existing:
                if conflict == "skip":
                    stats["skipped"] += 1
                    continue
                if conflict == "replace":
                    doc["account_id"] = existing["account_id"]
                    await db.email_accounts.replace_one(
                        {"account_id": existing["account_id"], "user_id": user.user_id}, doc
                    )
                    stats["replaced"] += 1
                    continue
                # copy → mutate email to avoid unique conflict
                base, _, dom = email.rpartition("@")
                doc["email"] = f"{base}+imported-{uuid.uuid4().hex[:4]}@{dom}" if dom else f"{email}-imported"
                doc["display_name"] = f"{doc.get('display_name', email)} (Imported)"
            doc["account_id"] = _new_id("acc")
            await db.email_accounts.insert_one(doc)
            stats["imported"] += 1
        return stats

    async def _import_email_lists(items: List[Dict[str, Any]], conflict: str, user) -> Dict[str, int]:
        stats = {"imported": 0, "skipped": 0, "replaced": 0}
        for item in items:
            name = (item.get("name") or "").strip() or "Imported List"
            existing = await db.email_lists.find_one(
                {"user_id": user.user_id, "name": name}, {"_id": 0}
            )
            doc = {k: v for k, v in item.items() if k != "_id"}
            doc["user_id"] = user.user_id
            doc.setdefault("created_at", _now())
            # Recompute totals from emails array
            emails = doc.get("emails") or []
            doc["total_rows"] = len(emails)
            doc["valid_emails"] = sum(1 for e in emails if e.get("email"))
            if existing:
                if conflict == "skip":
                    stats["skipped"] += 1
                    continue
                if conflict == "replace":
                    doc["list_id"] = existing["list_id"]
                    await db.email_lists.replace_one(
                        {"list_id": existing["list_id"], "user_id": user.user_id}, doc
                    )
                    stats["replaced"] += 1
                    continue
                doc["name"] = f"{name} (Imported)"
            doc["list_id"] = _new_id("list")
            await db.email_lists.insert_one(doc)
            stats["imported"] += 1
        return stats

    async def _import_dne_lists(items: List[Dict[str, Any]], conflict: str, user) -> Dict[str, int]:
        stats = {"imported": 0, "skipped": 0, "replaced": 0, "emails_added": 0}
        for item in items:
            name = (item.get("name") or "").strip() or "Imported DNE"
            emails = item.get("emails") or []
            is_global = bool(item.get("is_global"))
            # Global DNE in the source maps to the user's existing global list (regardless of name)
            if is_global:
                existing = await db.dne_lists.find_one(
                    {"user_id": user.user_id, "is_global": True}, {"_id": 0}
                )
            else:
                existing = await db.dne_lists.find_one(
                    {"user_id": user.user_id, "name": name, "is_global": False}, {"_id": 0}
                )
            target_list_id: Optional[str] = None
            target_is_global = False
            if existing:
                if conflict == "skip":
                    stats["skipped"] += 1
                    continue
                if conflict == "replace":
                    target_list_id = existing["list_id"]
                    target_is_global = bool(existing.get("is_global"))
                    await db.dne_emails.delete_many(
                        {"list_id": target_list_id, "user_id": user.user_id}
                    )
                    await db.dne_lists.update_one(
                        {"list_id": target_list_id, "user_id": user.user_id},
                        {"$set": {"name": existing.get("name") if target_is_global else name, "email_count": 0}},
                    )
                    stats["replaced"] += 1
                else:
                    # copy: merge into existing if global (never duplicate the global list),
                    # otherwise create a new list with " (Imported)" suffix
                    if is_global:
                        target_list_id = existing["list_id"]
                        target_is_global = True
                        # fall through — emails will be inserted with dedupe
                    else:
                        name = f"{name} (Imported)"
            if target_list_id is None:
                target_list_id = _new_id("dne")
                # Honor "is_global" only when the user doesn't already have a global list
                make_global = bool(is_global and not existing)
                target_is_global = make_global
                await db.dne_lists.insert_one(
                    {
                        "list_id": target_list_id,
                        "user_id": user.user_id,
                        "name": name if not make_global else "Global Do Not Email",
                        "is_global": make_global,
                        "email_count": 0,
                        "created_at": _now(),
                    }
                )
                stats["imported"] += 1
            # Insert emails — skip duplicates by (list_id,email) lookup
            inserted = 0
            for e in emails:
                addr = (e.get("email") if isinstance(e, dict) else str(e) or "").strip().lower()
                if not addr:
                    continue
                exists = await db.dne_emails.find_one(
                    {"list_id": target_list_id, "user_id": user.user_id, "email": addr},
                    {"_id": 0, "email": 1},
                )
                if exists:
                    continue
                source = (e.get("source") if isinstance(e, dict) else None) or "imported"
                added_at = (e.get("added_at") if isinstance(e, dict) else None) or _now()
                notes = (e.get("notes") if isinstance(e, dict) else None)
                doc = {
                    "list_id": target_list_id,
                    "user_id": user.user_id,
                    "email": addr,
                    "source": source,
                    "added_at": added_at,
                }
                if notes:
                    doc["notes"] = notes
                await db.dne_emails.insert_one(doc)
                inserted += 1
            stats["emails_added"] += inserted
            count = await db.dne_emails.count_documents({"list_id": target_list_id})
            await db.dne_lists.update_one(
                {"list_id": target_list_id, "user_id": user.user_id},
                {"$set": {"email_count": count}},
            )
        # Return only the standard keys for consistency (extra: emails_added)
        return stats

    async def _import_responses_leads(payload: Dict[str, Any], conflict: str, user) -> Dict[str, int]:
        """Restore Responses/Leads folders + saved leads.

        payload may be either {folders:[], leads:[]} OR a flat list of folders with embedded leads.
        Conflict modes:
            skip    — keep existing folder, do not insert ITS leads
            replace — overwrite existing folder name + delete-and-reinsert its leads
            copy    — create a new folder with " (Imported)" suffix (default)
        """
        if isinstance(payload, list):
            folders = payload
            leads = []
        else:
            folders = payload.get("folders") or []
            leads = payload.get("leads") or []
        stats = {"folders_imported": 0, "folders_skipped": 0, "folders_replaced": 0, "leads_imported": 0}

        # Map old_folder_id -> new_folder_id so leads can be re-linked
        folder_id_map: Dict[str, str] = {}

        for f in folders:
            name = (f.get("name") or "").strip() or "Imported Folder"
            old_id = f.get("folder_id")
            existing = await db.lead_folders.find_one(
                {"user_id": user.user_id, "name": name}, {"_id": 0}
            )
            new_folder_id: Optional[str] = None
            skip_this_folder_leads = False
            if existing:
                if conflict == "skip":
                    stats["folders_skipped"] += 1
                    new_folder_id = existing["folder_id"]
                    skip_this_folder_leads = True
                elif conflict == "replace":
                    new_folder_id = existing["folder_id"]
                    await db.lead_folders.update_one(
                        {"folder_id": new_folder_id, "user_id": user.user_id},
                        {"$set": {"name": name}},
                    )
                    # Wipe existing leads in this folder
                    await db.leads.delete_many(
                        {"user_id": user.user_id, "folder_id": new_folder_id}
                    )
                    stats["folders_replaced"] += 1
                else:
                    # copy
                    name = f"{name} (Imported)"
                    new_folder_id = _new_id("foldr")
                    await db.lead_folders.insert_one(
                        {
                            "folder_id": new_folder_id,
                            "user_id": user.user_id,
                            "name": name,
                            "created_at": f.get("created_at") or _now(),
                        }
                    )
                    stats["folders_imported"] += 1
            else:
                new_folder_id = _new_id("foldr")
                await db.lead_folders.insert_one(
                    {
                        "folder_id": new_folder_id,
                        "user_id": user.user_id,
                        "name": name,
                        "created_at": f.get("created_at") or _now(),
                    }
                )
                stats["folders_imported"] += 1
            if old_id:
                folder_id_map[old_id] = new_folder_id
            # Inline leads support (if folder has embedded leads array)
            inline_leads = f.get("leads") or []
            if inline_leads and not skip_this_folder_leads:
                for lead in inline_leads:
                    doc = {k: v for k, v in lead.items() if k != "_id"}
                    doc["lead_id"] = _new_id("lead")
                    doc["user_id"] = user.user_id
                    doc["folder_id"] = new_folder_id
                    doc.setdefault("saved_at", _now())
                    await db.leads.insert_one(doc)
                    stats["leads_imported"] += 1

        # Now process standalone leads (with folder_id references)
        for lead in leads:
            old_folder_id = lead.get("folder_id")
            new_folder_id = folder_id_map.get(old_folder_id)
            if not new_folder_id:
                # Folder wasn't in the backup — drop into a fallback "Imported Leads" folder
                fallback = await db.lead_folders.find_one(
                    {"user_id": user.user_id, "name": "Imported Leads"}, {"_id": 0}
                )
                if fallback:
                    new_folder_id = fallback["folder_id"]
                else:
                    new_folder_id = _new_id("foldr")
                    await db.lead_folders.insert_one(
                        {
                            "folder_id": new_folder_id,
                            "user_id": user.user_id,
                            "name": "Imported Leads",
                            "created_at": _now(),
                        }
                    )
                    stats["folders_imported"] += 1
                    folder_id_map[old_folder_id or "_orphan"] = new_folder_id
            doc = {k: v for k, v in lead.items() if k != "_id"}
            doc["lead_id"] = _new_id("lead")
            doc["user_id"] = user.user_id
            doc["folder_id"] = new_folder_id
            doc.setdefault("saved_at", _now())
            await db.leads.insert_one(doc)
            stats["leads_imported"] += 1
        return stats

    # =====================================================================
    # IMPORT — individual JSON endpoints
    # =====================================================================

    @router.post("/import/campaigns")
    async def import_campaigns_route(payload: ImportPayload, user=Depends(get_current_user)):
        conflict = _normalize_conflict(payload.conflict)
        return await _import_campaigns(payload.items, conflict, user)

    @router.post("/import/drip-campaigns")
    async def import_drips_route(payload: ImportPayload, user=Depends(get_current_user)):
        conflict = _normalize_conflict(payload.conflict)
        return await _import_drips(payload.items, conflict, user)

    @router.post("/import/email-accounts")
    async def import_accounts_route(payload: ImportPayload, user=Depends(get_current_user)):
        conflict = _normalize_conflict(payload.conflict)
        return await _import_email_accounts(payload.items, conflict, user)

    @router.post("/import/email-lists")
    async def import_lists_route(payload: ImportPayload, user=Depends(get_current_user)):
        conflict = _normalize_conflict(payload.conflict)
        return await _import_email_lists(payload.items, conflict, user)

    @router.post("/import/dne-lists")
    async def import_dne_route(payload: ImportPayload, user=Depends(get_current_user)):
        conflict = _normalize_conflict(payload.conflict)
        return await _import_dne_lists(payload.items, conflict, user)

    # Spec alias: do-not-email-lists
    @router.post("/import/do-not-email-lists")
    async def import_do_not_email_lists_route(payload: ImportPayload, user=Depends(get_current_user)):
        conflict = _normalize_conflict(payload.conflict)
        return await _import_dne_lists(payload.items, conflict, user)

    @router.post("/import/responses-leads")
    async def import_responses_leads_route(payload: ImportPayload, user=Depends(get_current_user)):
        """Restore Responses/Leads folders + leads.

        Accepts payload.items as either:
        - A folders array (with optional embedded leads on each folder)
        - The single object {folders:[], leads:[]} wrapped in items[0]
        """
        conflict = _normalize_conflict(payload.conflict)
        if not payload.items:
            return {"folders_imported": 0, "folders_skipped": 0, "folders_replaced": 0, "leads_imported": 0}
        first = payload.items[0]
        if isinstance(first, dict) and ("folders" in first or "leads" in first):
            return await _import_responses_leads(first, conflict, user)
        # treat items as folders directly
        return await _import_responses_leads({"folders": payload.items, "leads": []}, conflict, user)

    # =====================================================================
    # IMPORT — full ZIP upload + preview
    # =====================================================================

    def _parse_zip(content: bytes) -> Dict[str, Any]:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = set(zf.namelist())
                if "metadata.json" not in names:
                    raise HTTPException(status_code=400, detail="ZIP missing metadata.json")
                metadata = json.loads(zf.read("metadata.json"))
                version = metadata.get("schema_version", 0)
                if version > BACKUP_SCHEMA_VERSION:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Backup schema version {version} is newer than supported "
                            f"({BACKUP_SCHEMA_VERSION}). Please update RouteMail."
                        ),
                    )

                def _read_list(name: str) -> List[Dict[str, Any]]:
                    if name not in names:
                        return []
                    raw = zf.read(name)
                    if not raw:
                        return []
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise HTTPException(status_code=400, detail=f"Invalid JSON in {name}: {exc}")
                    return data if isinstance(data, list) else data.get("items", [])

                def _read_obj(name: str) -> Dict[str, Any]:
                    if name not in names:
                        return {}
                    raw = zf.read(name)
                    if not raw:
                        return {}
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise HTTPException(status_code=400, detail=f"Invalid JSON in {name}: {exc}")
                    return data if isinstance(data, dict) else {"items": data}

                # Prefer canonical names; fall back to legacy alias for DNE lists
                dne = _read_list("do_not_email_lists.json")
                if not dne:
                    dne = _read_list("unsubscribe_lists.json")
                responses_leads = _read_obj("responses_leads.json")
                return {
                    "metadata": metadata,
                    "campaigns": _read_list("campaigns.json"),
                    "drip_campaigns": _read_list("drip_campaigns.json"),
                    "email_accounts": _read_list("email_accounts.json"),
                    "email_lists": _read_list("email_lists.json"),
                    "do_not_email_lists": dne,
                    # legacy alias kept for callers/UI that still use the old key
                    "unsubscribe_lists": dne,
                    "responses_leads": responses_leads,
                }
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid ZIP archive")

    @router.post("/import/full/preview")
    async def import_full_preview(file: UploadFile = File(...), user=Depends(get_current_user)):  # noqa: ARG001
        content = await file.read()
        parsed = _parse_zip(content)
        rl = parsed.get("responses_leads") or {}
        return {
            "metadata": parsed["metadata"],
            "summary": {
                "campaigns": len(parsed["campaigns"]),
                "drip_campaigns": len(parsed["drip_campaigns"]),
                "email_accounts": len(parsed["email_accounts"]),
                "email_lists": len(parsed["email_lists"]),
                "do_not_email_lists": len(parsed["do_not_email_lists"]),
                "responses_leads_folders": len(rl.get("folders", [])),
                "responses_leads_items": len(rl.get("leads", [])),
                # backward-compat alias
                "unsubscribe_lists": len(parsed["unsubscribe_lists"]),
            },
        }

    @router.post("/import/full")
    async def import_full(
        file: UploadFile = File(...),
        conflict: str = Query("copy"),
        user=Depends(get_current_user),
    ):
        conflict = _normalize_conflict(conflict)
        content = await file.read()
        parsed = _parse_zip(content)
        results = {
            "campaigns": await _import_campaigns(parsed["campaigns"], conflict, user),
            "drip_campaigns": await _import_drips(parsed["drip_campaigns"], conflict, user),
            "email_accounts": await _import_email_accounts(parsed["email_accounts"], conflict, user),
            "email_lists": await _import_email_lists(parsed["email_lists"], conflict, user),
            "do_not_email_lists": await _import_dne_lists(parsed["do_not_email_lists"], conflict, user),
            "responses_leads": await _import_responses_leads(parsed.get("responses_leads") or {}, conflict, user),
        }
        # Backward-compat alias for older UI keys
        results["unsubscribe_lists"] = results["do_not_email_lists"]
        return {
            "success": True,
            "metadata": parsed["metadata"],
            "results": results,
        }

    # =====================================================================
    # IMPORT — CSV upload helpers (email lists + DNE lists)
    # =====================================================================

    @router.post("/import/email-lists/csv")
    async def import_email_list_csv(
        file: UploadFile = File(...),
        list_name: str = Query(...),
        conflict: str = Query("copy"),
        user=Depends(get_current_user),
    ):
        conflict = _normalize_conflict(conflict)
        try:
            text = (await file.read()).decode("utf-8", errors="ignore")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Cannot read CSV: {exc}")
        reader = csv.DictReader(io.StringIO(text))
        rows = [dict(r) for r in reader]
        headers = reader.fieldnames or []
        item = {
            "name": list_name.strip() or "Imported List",
            "original_filename": file.filename or "imported.csv",
            "column_headers": headers,
            "emails": rows,
        }
        return await _import_email_lists([item], conflict, user)

    @router.post("/import/dne-lists/csv")
    async def import_dne_csv(
        file: UploadFile = File(...),
        list_name: str = Query(...),
        conflict: str = Query("copy"),
        user=Depends(get_current_user),
    ):
        conflict = _normalize_conflict(conflict)
        text = (await file.read()).decode("utf-8", errors="ignore")
        reader = csv.DictReader(io.StringIO(text))
        emails: List[Dict[str, Any]] = []
        # Accept either a single "email" column or rows where the only column is the email
        for row in reader:
            email = (row.get("email") or row.get("Email") or "").strip().lower()
            if not email and len(row) == 1:
                email = list(row.values())[0].strip().lower()
            if email and re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                emails.append({"email": email, "source": (row.get("source") or "imported")})
        item = {"name": list_name.strip() or "Imported DNE", "emails": emails}
        return await _import_dne_lists([item], conflict, user)

    return router
