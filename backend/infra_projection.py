"""Projection engine for the Infrastructure module — Phase 2.

Walks every active `drip_contact` + scheduled regular campaign forward up to
`window_days` (default 120) and produces a `{account_id: {YYYY-MM-DD: count}}`
dictionary of projected sends per inbox per local date.

Phase-1 simplifications that are intentionally retained:
- Each drip's `account_ids` pool is treated as round-robin across pending
  steps (one of the inboxes will be used for any given send). We don't try
  to predict which exact inbox the send worker will pick — instead the
  projected load for the step is **distributed evenly** across the pool. This
  matches what the send worker actually does in aggregate over many sends.
- Regular `scheduled` campaigns are projected as a single spike on their
  `scheduled_at` local date, distributing `(total_emails - sent_count)` over
  their `account_ids`. If a campaign is `running` *and* mid-burst, those
  pending items also land on today.

Public API:
    projection = await build_projection(db, user_doc, window_days=120)
    # projection["acc_xxx"]["2026-06-15"] -> 7   (projected sends)
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone, date as _date_cls
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo


def _safe_tz(name: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _advance_to_sending_day(d: _date_cls, sending_days: List[int]) -> _date_cls:
    """Roll `d` forward to the next allowed weekday. weekday() is 0=Mon..6=Sun
    which matches the schema. If sending_days is empty, treat every day as
    allowed (defensive)."""
    if not sending_days:
        return d
    allowed = set(sending_days)
    # Cap at 14 forward steps; a sane schedule always has at least one valid
    # day in a week so 7 is the real upper bound. 14 is just paranoia against
    # malformed sending_days values.
    for _ in range(14):
        if d.weekday() in allowed:
            return d
        d = d + timedelta(days=1)
    return d


def _local_date(dt_iso: str, tz: ZoneInfo) -> Optional[_date_cls]:
    """Convert an ISO timestamp (UTC or naive treated as UTC) to a local date
    in `tz`. Returns None if unparseable."""
    if not dt_iso:
        return None
    try:
        dt = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz).date()
    except Exception:
        return None


async def build_projection(
    db,
    user_doc: Dict[str, Any],
    window_days: int = 120,
) -> Dict[str, Dict[str, int]]:
    """Compute the per-account projection. See module docstring for shape.

    Visibility scoping matches the rest of the Infrastructure module — super
    admins see everything, infra-permitted users see only their own accounts /
    campaigns / drip campaigns. We never project for accounts the requester
    can't see.
    """
    is_admin = user_doc.get("role") == "super_admin"
    user_id = user_doc["user_id"]

    today_utc = datetime.now(timezone.utc)
    horizon = today_utc + timedelta(days=window_days)

    projection: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # ---------- 1. Drip projections ----------------------------------------
    drip_query: Dict[str, Any] = {"status": {"$in": ["running", "scheduled", "paused"]}}
    if not is_admin:
        drip_query["user_id"] = user_id

    drips = await db.drip_campaigns.find(
        drip_query,
        {
            "_id": 0,
            "drip_id": 1,
            "status": 1,
            "user_id": 1,
            "account_ids": 1,
            "steps": 1,
            "schedule": 1,
        },
    ).to_list(10000)

    if drips:
        drip_ids = [d["drip_id"] for d in drips]
        # Pull all active contacts in one round trip rather than per-drip.
        # We deliberately ignore status='completed' / 'replied' / 'bounced' /
        # 'unsubscribed' here — those contacts won't generate future sends.
        contacts = await db.drip_contacts.find(
            {"drip_id": {"$in": drip_ids}, "status": "active"},
            {
                "_id": 0,
                "drip_id": 1,
                "current_step": 1,
                "next_send_at": 1,
            },
        ).to_list(200000)

        contacts_by_drip: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for c in contacts:
            contacts_by_drip[c["drip_id"]].append(c)

        for drip in drips:
            account_ids: List[str] = list(drip.get("account_ids") or [])
            if not account_ids:
                continue  # nothing to project to
            steps: List[Dict[str, Any]] = list(drip.get("steps") or [])
            if not steps:
                continue

            schedule = drip.get("schedule") or {}
            tz = _safe_tz(schedule.get("timezone"))
            sending_days = schedule.get("sending_days") or [0, 1, 2, 3, 4]

            # `start_date` floor — drip's own start gate. The send worker also
            # honours this, so projection must too.
            start_date_str = schedule.get("start_date") or ""
            try:
                start_floor = _date_cls.fromisoformat(start_date_str) if start_date_str else None
            except Exception:
                start_floor = None

            # If the drip is `scheduled` and `start_date` is set, any contacts
            # without next_send_at default to firing on start_date.
            fallback_first_send = None
            if drip.get("status") == "scheduled":
                # First send = start_date (or today if missing) at start_time
                base_date = start_floor or today_utc.astimezone(tz).date()
                base_date = _advance_to_sending_day(base_date, sending_days)
                fallback_first_send = datetime.combine(
                    base_date,
                    datetime.strptime(schedule.get("start_time", "09:00"), "%H:%M").time(),
                    tzinfo=tz,
                )

            rr_cursor = 0  # round-robin pointer across this drip's inbox pool
            for contact in contacts_by_drip.get(drip["drip_id"], []):
                next_send_iso = contact.get("next_send_at")
                cur_step = int(contact.get("current_step") or 0)

                # Determine the next firing UTC datetime
                if next_send_iso:
                    try:
                        next_dt = datetime.fromisoformat(next_send_iso.replace("Z", "+00:00"))
                        if not next_dt.tzinfo:
                            next_dt = next_dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        continue
                elif fallback_first_send is not None:
                    next_dt = fallback_first_send
                else:
                    continue

                # Walk remaining steps forward
                step_idx = cur_step
                while step_idx < len(steps) and next_dt < horizon:
                    # Floor against drip start_date
                    local_dt = next_dt.astimezone(tz)
                    if start_floor and local_dt.date() < start_floor:
                        local_dt = local_dt.replace(
                            year=start_floor.year,
                            month=start_floor.month,
                            day=start_floor.day,
                        )

                    # Adjust to nearest valid sending_day forward
                    local_date = _advance_to_sending_day(local_dt.date(), sending_days)
                    if local_date >= horizon.astimezone(tz).date():
                        break

                    iso = local_date.isoformat()
                    aid = account_ids[rr_cursor % len(account_ids)]
                    rr_cursor += 1
                    projection[aid][iso] += 1

                    # Schedule the NEXT step
                    next_step_idx = step_idx + 1
                    if next_step_idx >= len(steps):
                        break
                    s = steps[next_step_idx] or {}
                    delta = timedelta(
                        days=int(s.get("delay_days", 0) or 0),
                        hours=int(s.get("delay_hours", 0) or 0),
                    )
                    if delta.total_seconds() <= 0:
                        delta = timedelta(days=1)  # safety floor
                    next_dt = datetime.combine(
                        local_date, local_dt.time(), tzinfo=tz
                    ) + delta
                    step_idx = next_step_idx

    # ---------- 2. Scheduled / running regular campaigns -------------------
    camp_query: Dict[str, Any] = {"status": {"$in": ["scheduled", "running"]}}
    if not is_admin:
        camp_query["user_id"] = user_id

    camps = await db.campaigns.find(
        camp_query,
        {
            "_id": 0,
            "campaign_id": 1,
            "user_id": 1,
            "account_ids": 1,
            "scheduled_at": 1,
            "started_at": 1,
            "total_emails": 1,
            "sent_count": 1,
            "timezone": 1,
        },
    ).to_list(10000)

    for c in camps:
        accs: List[str] = list(c.get("account_ids") or [])
        if not accs:
            continue
        pending = int(c.get("total_emails") or 0) - int(c.get("sent_count") or 0)
        if pending <= 0:
            continue
        tz = _safe_tz(c.get("timezone"))

        # Date of the projected burst — scheduled campaigns use `scheduled_at`,
        # already-running ones use `started_at` (or today as a final fallback).
        spike_date = (
            _local_date(c.get("scheduled_at"), tz)
            or _local_date(c.get("started_at"), tz)
            or today_utc.astimezone(tz).date()
        )
        if spike_date < today_utc.astimezone(tz).date():
            spike_date = today_utc.astimezone(tz).date()
        if spike_date >= horizon.astimezone(tz).date():
            continue

        per_account = max(1, pending // len(accs))
        remainder = pending - (per_account * len(accs))
        iso = spike_date.isoformat()
        for i, aid in enumerate(accs):
            extra = 1 if i < remainder else 0
            projection[aid][iso] += per_account + extra

    # Convert defaultdicts to plain dicts for serialisation friendliness
    return {acc: dict(days) for acc, days in projection.items()}


def aggregate_capacity(
    accounts: List[Dict[str, Any]],
    projection: Dict[str, Dict[str, int]],
    window_days: int,
) -> Dict[str, int]:
    """Returns `{today, week, month_30, window}` aggregate remaining-capacity
    numbers across all accounts. `today` uses the on-disk counters (matches
    the live send-worker view). `week / month_30 / window` subtract the
    projection from `daily_limit × N` for each account-day pair within range.
    """
    horizons = {"week": 7, "month_30": 30, "window": window_days}
    totals = {"today": 0, "week": 0, "month_30": 0, "window": 0}

    today_date = datetime.now(timezone.utc).date()
    for acc in accounts:
        limit = int(acc.get("daily_limit") or 50)
        sent_today = int(acc.get("emails_sent_today") or 0)
        totals["today"] += max(limit - sent_today, 0)

        per_acc = projection.get(acc["account_id"], {})
        for label, days in horizons.items():
            cap = 0
            for n in range(days):
                d = (today_date + timedelta(days=n)).isoformat()
                if n == 0:
                    used = sent_today + int(per_acc.get(d, 0))
                else:
                    used = int(per_acc.get(d, 0))
                cap += max(limit - used, 0)
            totals[label] += cap

    return totals


def calendar_for_account(
    account: Dict[str, Any],
    projection_for_account: Dict[str, int],
    window_days: int,
) -> List[Dict[str, Any]]:
    """Generate the `window_days`-row per-day calendar for one inbox.

    Each row is independently classified into Available / Partial / Reserved.
    Day-zero uses the live `emails_sent_today` counter so today's row matches
    the rest of the dashboard exactly; future days only see projected sends.
    """
    limit = int(account.get("daily_limit") or 50)
    sent_today = int(account.get("emails_sent_today") or 0)
    out: List[Dict[str, Any]] = []
    today = datetime.now(timezone.utc).date()
    for n in range(window_days):
        d = today + timedelta(days=n)
        iso = d.isoformat()
        projected = int(projection_for_account.get(iso, 0))
        used = (sent_today + projected) if n == 0 else projected
        remaining = max(limit - used, 0)
        if remaining <= 0:
            status = "Reserved"
        elif used > 0:
            status = "Partial"
        else:
            status = "Available"
        out.append({
            "date": iso,
            "weekday": d.weekday(),  # 0=Mon
            "limit": limit,
            "projected": projected,
            "used": used,
            "remaining": remaining,
            "status": status,
        })
    return out
