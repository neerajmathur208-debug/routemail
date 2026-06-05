"""
Super Admin platform-wide backup & restore for RouteMail.

Visible ONLY to super_admin role. Provides:
- Export ENTIRE platform (all users + all data) as a ZIP
- Export selected user(s) as a ZIP
- Import a platform backup (full or partial) with skip/merge/replace per user
- Backup history (logs every export with file size + type)

Security:
- Strips active sessions, password reset tokens, verification tokens, CAPTCHA secrets
- SMTP / IMAP / passwords remain in their existing encrypted form (Fernet-encrypted blobs)
- Plain `password` / `smtp_password` / `imap_password` fields are scrubbed
- API/Stripe secret keys are NEVER exported (those live in .env, never in DB)

Mounted by server.py:
    from admin_backup_routes import build_admin_backup_router
    api_router.include_router(build_admin_backup_router(db, get_super_admin_user))
"""
from __future__ import annotations

import io
import json
import logging
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

PLATFORM_SCHEMA_VERSION = 1
ROUTEMAIL_VERSION = "1.0.0"

# Fields stripped from EVERY exported user document
SENSITIVE_USER_FIELDS = {
    "password_hash",
    "password",
    "verification_token",
    "verification_expires",
    "reset_token",
    "reset_expires",
    "stripe_webhook_secret",
    "captcha_secret",
    "captcha_token",
    "session_token",
}

# Fields stripped from every email account document (encrypted blobs stay, plain text scrubbed)
SENSITIVE_ACCOUNT_FIELDS = {
    "smtp_password",
    "imap_password",
    "password",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scrub_user(u: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in u.items() if k not in SENSITIVE_USER_FIELDS and k != "_id"}
    return out


def _scrub_account(a: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in a.items() if k not in SENSITIVE_ACCOUNT_FIELDS and k != "_id"}
    # Reset live-counter fields so restored accounts start clean
    for k in ("daily_send_count", "last_send_date", "last_reset_at",
              "imap_last_sync_at", "imap_last_error", "imap_last_uid"):
        out.pop(k, None)
    return out


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


async def _gather_user_payload(db, user_id: str) -> Dict[str, Any]:
    """Collect every per-user collection scoped to user_id."""
    return {
        "campaigns": [
            {k: v for k, v in c.items() if k != "_id"}
            for c in await db.campaigns.find({"user_id": user_id}, {"_id": 0}).to_list(50000)
        ],
        "drip_campaigns": [
            {k: v for k, v in c.items() if k != "_id"}
            for c in await db.drip_campaigns.find({"user_id": user_id}, {"_id": 0}).to_list(50000)
        ],
        "email_accounts": [
            _scrub_account(a)
            for a in await db.email_accounts.find({"user_id": user_id}, {"_id": 0}).to_list(50000)
        ],
        "email_lists": [
            {k: v for k, v in lst_doc.items() if k != "_id"}
            for lst_doc in await db.email_lists.find({"user_id": user_id}, {"_id": 0}).to_list(50000)
        ],
        "dne_lists": [
            dict(
                {k: v for k, v in lst.items() if k != "_id"},
                emails=await db.dne_emails.find(
                    {"list_id": lst["list_id"], "user_id": user_id}, {"_id": 0}
                ).to_list(500000),
            )
            for lst in await db.dne_lists.find({"user_id": user_id}, {"_id": 0}).to_list(2000)
        ],
        "lead_folders": [
            {k: v for k, v in f.items() if k != "_id"}
            for f in await db.lead_folders.find({"user_id": user_id}, {"_id": 0}).to_list(5000)
        ],
        "leads": [
            {k: v for k, v in lead.items() if k != "_id"}
            for lead in await db.leads.find({"user_id": user_id}, {"_id": 0}).to_list(200000)
        ],
        "warmup_settings": [
            {k: v for k, v in w.items() if k != "_id"}
            for w in await db.warmup_settings.find({"user_id": user_id}, {"_id": 0}).to_list(5000)
        ] if "warmup_settings" in await db.list_collection_names() else [],
    }


async def _record_backup_history(
    db,
    admin_user_id: str,
    backup_type: str,
    file_size: int,
    note: Optional[str] = None,
    user_count: int = 0,
) -> str:
    backup_id = f"bkp_{uuid.uuid4().hex[:12]}"
    await db.admin_backup_history.insert_one({
        "backup_id": backup_id,
        "admin_user_id": admin_user_id,
        "backup_type": backup_type,
        "file_size": int(file_size),
        "user_count": int(user_count),
        "note": note,
        "created_at": _now_iso(),
    })
    return backup_id


class SelectedUsersExportRequest(BaseModel):
    user_ids: List[str]
    include_credentials: bool = True  # encrypted blobs only — never plain text


class PlatformImportOptions(BaseModel):
    conflict: str = "merge"  # skip | merge | replace


def build_admin_backup_router(db, get_super_admin_user):  # noqa: C901
    router = APIRouter(prefix="/admin/backup", tags=["admin-backup"])

    # ============================================================
    # EXPORT — full platform
    # ============================================================
    @router.get("/export/full")
    async def export_full_platform(admin=Depends(get_super_admin_user)):
        users = await db.users.find({}, {"_id": 0}).to_list(100000)
        scrubbed_users = [_scrub_user(u) for u in users]

        # Per-user data
        per_user_blocks: List[Dict[str, Any]] = []
        all_campaigns: List[Dict[str, Any]] = []
        all_drips: List[Dict[str, Any]] = []
        all_accounts: List[Dict[str, Any]] = []
        all_lists: List[Dict[str, Any]] = []
        all_dne: List[Dict[str, Any]] = []
        all_folders: List[Dict[str, Any]] = []
        all_leads: List[Dict[str, Any]] = []
        for u in scrubbed_users:
            uid = u.get("user_id")
            if not uid:
                continue
            payload = await _gather_user_payload(db, uid)
            per_user_blocks.append({
                "user_id": uid,
                "email": u.get("email"),
                **payload,
            })
            all_campaigns.extend(payload["campaigns"])
            all_drips.extend(payload["drip_campaigns"])
            all_accounts.extend(payload["email_accounts"])
            all_lists.extend(payload["email_lists"])
            all_dne.extend(payload["dne_lists"])
            all_folders.extend(payload["lead_folders"])
            all_leads.extend(payload["leads"])

        # Platform-level collections
        async def _all(coll_name: str) -> List[Dict[str, Any]]:
            try:
                if coll_name in await db.list_collection_names():
                    return [
                        {k: v for k, v in d.items() if k != "_id"}
                        for d in await db[coll_name].find({}, {"_id": 0}).to_list(100000)
                    ]
            except Exception as exc:
                logger.warning(f"[ADMIN_BACKUP] failed reading {coll_name}: {exc}")
            return []

        plans = await _all("plans")
        blogs = await _all("blogs")
        system_settings = await _all("system_settings")
        subscriptions = [
            {
                "user_id": u.get("user_id"),
                "stripe_customer_id": u.get("stripe_customer_id"),
                "stripe_subscription_id": u.get("stripe_subscription_id"),
                "subscription_status": u.get("subscription_status"),
                "plan_type": u.get("plan_type"),
                "billing_cycle_start": u.get("billing_cycle_start"),
                "billing_cycle_end": u.get("billing_cycle_end"),
                "admin_override_active": u.get("admin_override_active"),
                "admin_override_plan": u.get("admin_override_plan"),
                "admin_max_contacts": u.get("admin_max_contacts"),
                "admin_max_accounts": u.get("admin_max_accounts"),
            }
            for u in scrubbed_users
        ]

        metadata = {
            "schema_version": PLATFORM_SCHEMA_VERSION,
            "routemail_version": ROUTEMAIL_VERSION,
            "backup_type": "platform_full",
            "exported_at": _now_iso(),
            "exported_by": admin.get("email") if isinstance(admin, dict) else getattr(admin, "email", None),
            "counts": {
                "users": len(scrubbed_users),
                "campaigns": len(all_campaigns),
                "drip_campaigns": len(all_drips),
                "email_accounts": len(all_accounts),
                "email_lists": len(all_lists),
                "do_not_email_lists": len(all_dne),
                "responses_leads_folders": len(all_folders),
                "responses_leads_items": len(all_leads),
                "plans": len(plans),
                "blogs": len(blogs),
                "system_settings": len(system_settings),
            },
            "note": "Sensitive fields (passwords, tokens, sessions, secrets) are NOT exported. SMTP/IMAP credentials remain in their Fernet-encrypted form.",
        }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("metadata.json", json.dumps(metadata, indent=2, default=str))
            zf.writestr("users.json", json.dumps(scrubbed_users, indent=2, default=str))
            zf.writestr("campaigns.json", json.dumps(all_campaigns, indent=2, default=str))
            zf.writestr("drip_campaigns.json", json.dumps(all_drips, indent=2, default=str))
            zf.writestr("email_accounts.json", json.dumps(all_accounts, indent=2, default=str))
            zf.writestr("email_lists.json", json.dumps(all_lists, indent=2, default=str))
            zf.writestr("do_not_email_lists.json", json.dumps(all_dne, indent=2, default=str))
            zf.writestr("responses_leads.json", json.dumps({"folders": all_folders, "leads": all_leads}, indent=2, default=str))
            zf.writestr("subscriptions.json", json.dumps(subscriptions, indent=2, default=str))
            zf.writestr("plans.json", json.dumps(plans, indent=2, default=str))
            zf.writestr("blogs.json", json.dumps(blogs, indent=2, default=str))
            zf.writestr("system_settings.json", json.dumps(system_settings, indent=2, default=str))
            zf.writestr("per_user_data.json", json.dumps(per_user_blocks, indent=2, default=str))
        buf.seek(0)
        content = buf.read()

        await _record_backup_history(
            db,
            admin_user_id=getattr(admin, "user_id", None) or (admin.get("user_id") if isinstance(admin, dict) else "admin"),
            backup_type="platform_full",
            file_size=len(content),
            user_count=len(scrubbed_users),
        )

        fname = f"routemail-platform-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
        return StreamingResponse(
            iter([content]),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    # ============================================================
    # EXPORT — selected users
    # ============================================================
    @router.post("/export/users")
    async def export_selected_users(req: SelectedUsersExportRequest, admin=Depends(get_super_admin_user)):
        if not req.user_ids:
            raise HTTPException(status_code=400, detail="At least one user_id required")
        users = await db.users.find({"user_id": {"$in": req.user_ids}}, {"_id": 0}).to_list(100000)
        if not users:
            raise HTTPException(status_code=404, detail="No matching users found")
        scrubbed_users = [_scrub_user(u) for u in users]

        per_user_blocks: List[Dict[str, Any]] = []
        for u in scrubbed_users:
            uid = u.get("user_id")
            if not uid:
                continue
            payload = await _gather_user_payload(db, uid)
            per_user_blocks.append({
                "user_id": uid,
                "email": u.get("email"),
                **payload,
            })

        metadata = {
            "schema_version": PLATFORM_SCHEMA_VERSION,
            "routemail_version": ROUTEMAIL_VERSION,
            "backup_type": "selected_users",
            "exported_at": _now_iso(),
            "user_count": len(scrubbed_users),
        }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("metadata.json", json.dumps(metadata, indent=2, default=str))
            zf.writestr("users.json", json.dumps(scrubbed_users, indent=2, default=str))
            zf.writestr("per_user_data.json", json.dumps(per_user_blocks, indent=2, default=str))
        buf.seek(0)
        content = buf.read()

        await _record_backup_history(
            db,
            admin_user_id=getattr(admin, "user_id", None) or (admin.get("user_id") if isinstance(admin, dict) else "admin"),
            backup_type="selected_users",
            file_size=len(content),
            user_count=len(scrubbed_users),
        )

        fname = f"routemail-users-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
        return StreamingResponse(
            iter([content]),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    # ============================================================
    # IMPORT — full platform / selected users (auto-detected)
    # ============================================================
    def _parse_zip(content: bytes) -> Dict[str, Any]:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = set(zf.namelist())
                if "metadata.json" not in names:
                    raise HTTPException(status_code=400, detail="ZIP missing metadata.json")
                meta = json.loads(zf.read("metadata.json"))
                version = meta.get("schema_version", 0)
                if version > PLATFORM_SCHEMA_VERSION:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Backup schema version {version} is newer than supported "
                            f"({PLATFORM_SCHEMA_VERSION}). Please update RouteMail."
                        ),
                    )

                def _read(name: str) -> Any:
                    if name not in names:
                        return None
                    return json.loads(zf.read(name) or b"null")

                return {
                    "metadata": meta,
                    "users": _read("users.json") or [],
                    "per_user_data": _read("per_user_data.json") or [],
                    "plans": _read("plans.json") or [],
                    "blogs": _read("blogs.json") or [],
                    "system_settings": _read("system_settings.json") or [],
                }
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid ZIP archive")

    @router.post("/import/preview")
    async def import_preview(file: UploadFile = File(...), admin=Depends(get_super_admin_user)):  # noqa: ARG001
        parsed = _parse_zip(await file.read())
        return {
            "metadata": parsed["metadata"],
            "summary": {
                "users": len(parsed["users"]),
                "per_user_blocks": len(parsed["per_user_data"]),
                "plans": len(parsed["plans"]),
                "blogs": len(parsed["blogs"]),
                "system_settings": len(parsed["system_settings"]),
            },
        }

    async def _restore_user(user_doc: Dict[str, Any], user_payload: Dict[str, Any], conflict: str) -> Dict[str, Any]:
        result = {"action": "imported", "user_id": user_doc.get("user_id"), "email": user_doc.get("email")}
        existing = None
        if user_doc.get("email"):
            existing = await db.users.find_one({"email": user_doc["email"]}, {"_id": 0})

        target_uid = user_doc.get("user_id") or f"user_{uuid.uuid4().hex[:12]}"

        if existing:
            if conflict == "skip":
                return {**result, "action": "skipped"}
            target_uid = existing["user_id"]
            if conflict == "replace":
                # Wipe per-user data BEFORE re-inserting
                for coll in ("campaigns", "drip_campaigns", "email_accounts", "email_lists",
                             "dne_lists", "dne_emails", "lead_folders", "leads"):
                    await db[coll].delete_many({"user_id": target_uid})
                # Replace user doc preserving password_hash (don't overwrite credentials)
                merged = {**user_doc, "user_id": target_uid, "password_hash": existing.get("password_hash")}
                await db.users.replace_one({"user_id": target_uid}, merged)
                result["action"] = "replaced"
            else:
                # merge — leave existing user doc alone (keep credentials), import only NEW per-user data
                result["action"] = "merged"
        else:
            # New user — insert (with no password_hash; super admin must reset)
            await db.users.insert_one({**user_doc, "user_id": target_uid})

        # Per-user collections
        for coll_key, coll_name in (
            ("campaigns", "campaigns"),
            ("drip_campaigns", "drip_campaigns"),
            ("email_accounts", "email_accounts"),
            ("email_lists", "email_lists"),
            ("lead_folders", "lead_folders"),
            ("leads", "leads"),
        ):
            for doc in user_payload.get(coll_key, []):
                doc = {k: v for k, v in doc.items() if k != "_id"}
                doc["user_id"] = target_uid
                if conflict == "merge":
                    # For merge — give a fresh ID to avoid colliding with existing user data
                    id_field = {
                        "campaigns": "campaign_id",
                        "drip_campaigns": "drip_id",
                        "email_accounts": "account_id",
                        "email_lists": "list_id",
                        "lead_folders": "folder_id",
                        "leads": "lead_id",
                    }[coll_key]
                    if id_field in doc:
                        doc[id_field] = _new_id(id_field.split("_")[0])
                await db[coll_name].insert_one(doc)

        # DNE: list + emails (preserve list_id from payload)
        for lst in user_payload.get("dne_lists", []):
            emails = lst.get("emails", []) or []
            lst_doc = {k: v for k, v in lst.items() if k not in ("_id", "emails")}
            lst_doc["user_id"] = target_uid
            if conflict == "merge":
                lst_doc["list_id"] = _new_id("dne")
            await db.dne_lists.update_one(
                {"list_id": lst_doc["list_id"]},
                {"$set": lst_doc},
                upsert=True,
            )
            for e in emails:
                e_doc = {k: v for k, v in e.items() if k != "_id"}
                e_doc["user_id"] = target_uid
                e_doc["list_id"] = lst_doc["list_id"]
                await db.dne_emails.update_one(
                    {"list_id": lst_doc["list_id"], "user_id": target_uid, "email": e_doc.get("email")},
                    {"$set": e_doc},
                    upsert=True,
                )

        return result

    @router.post("/import")
    async def import_platform(
        file: UploadFile = File(...),
        conflict: str = Query("merge"),
        admin=Depends(get_super_admin_user),
    ):
        conflict = (conflict or "merge").lower()
        if conflict not in ("skip", "merge", "replace"):
            raise HTTPException(status_code=400, detail="conflict must be skip|merge|replace")
        parsed = _parse_zip(await file.read())

        # Index per-user blocks by user_id
        payload_by_uid: Dict[str, Dict[str, Any]] = {
            block.get("user_id"): block for block in parsed.get("per_user_data", []) if block.get("user_id")
        }

        results: List[Dict[str, Any]] = []
        for u in parsed["users"]:
            uid = u.get("user_id")
            payload = payload_by_uid.get(uid, {})
            res = await _restore_user(u, payload, conflict)
            results.append(res)

        # Restore platform-level data (blogs, plans, system_settings) — upsert by id where possible
        for blog in parsed["blogs"]:
            blog = {k: v for k, v in blog.items() if k != "_id"}
            slug = blog.get("slug")
            if slug:
                await db.blogs.update_one({"slug": slug}, {"$set": blog}, upsert=True)
            else:
                await db.blogs.insert_one(blog)

        for plan in parsed["plans"]:
            plan = {k: v for k, v in plan.items() if k != "_id"}
            key = plan.get("plan_id") or plan.get("slug")
            if key:
                await db.plans.update_one({"$or": [{"plan_id": key}, {"slug": key}]}, {"$set": plan}, upsert=True)
            else:
                await db.plans.insert_one(plan)

        for s in parsed["system_settings"]:
            s = {k: v for k, v in s.items() if k != "_id"}
            key = s.get("key") or s.get("name")
            if key:
                await db.system_settings.update_one({"$or": [{"key": key}, {"name": key}]}, {"$set": s}, upsert=True)
            else:
                await db.system_settings.insert_one(s)

        return {
            "success": True,
            "metadata": parsed["metadata"],
            "conflict": conflict,
            "user_results": results,
            "platform": {
                "blogs": len(parsed["blogs"]),
                "plans": len(parsed["plans"]),
                "system_settings": len(parsed["system_settings"]),
            },
        }

    # ============================================================
    # BACKUP HISTORY
    # ============================================================
    @router.get("/history")
    async def list_history(admin=Depends(get_super_admin_user)):  # noqa: ARG001
        items = (
            await db.admin_backup_history.find({}, {"_id": 0})
            .sort("created_at", -1)
            .to_list(500)
        )
        return {"items": items}

    return router
