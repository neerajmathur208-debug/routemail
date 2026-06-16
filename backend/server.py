from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, UploadFile, File, BackgroundTasks, Depends, Query, Header, Body
from fastapi.responses import RedirectResponse, StreamingResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import asyncio
import random
import csv
import io
import json
import re
from cryptography.fernet import Fernet
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import bcrypt
import stripe
import resend
import secrets

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Encryption key for credentials
ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    
fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)

# Stripe configuration
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

# Resend configuration for transactional emails
resend.api_key = os.environ.get('RESEND_API_KEY')
FROM_EMAIL = os.environ.get('FROM_EMAIL', 'support@routemail.co')
ADMIN_NOTIFICATION_EMAIL = 'support@routemail.co'
# Strip trailing slash from FRONTEND_URL to prevent double slashes in URLs
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://routemail.co').rstrip('/')
SUPER_ADMIN_EMAIL = os.environ.get('SUPER_ADMIN_EMAIL', '')

# Stripe Price IDs (from environment)
STRIPE_PRICES = {
    "starter_usd": os.environ.get('STRIPE_PRICE_STARTER_USD'),
    "growth_usd": os.environ.get('STRIPE_PRICE_GROWTH_USD'),
    "starter_inr": os.environ.get('STRIPE_PRICE_STARTER_INR'),
    "growth_inr": os.environ.get('STRIPE_PRICE_GROWTH_INR'),
    # Custom Plan slabs (USD, yearly)
    "custom_15k": os.environ.get('STRIPE_PRICE_CUSTOM_15K'),
    "custom_20k": os.environ.get('STRIPE_PRICE_CUSTOM_20K'),
    "custom_30k": os.environ.get('STRIPE_PRICE_CUSTOM_30K'),
    "custom_50k": os.environ.get('STRIPE_PRICE_CUSTOM_50K'),
    "custom_75k": os.environ.get('STRIPE_PRICE_CUSTOM_75K'),
    "custom_100k": os.environ.get('STRIPE_PRICE_CUSTOM_100K'),
}

# Custom Plan slab definitions: contacts/month → yearly USD price
CUSTOM_PLAN_SLABS = [
    {"slug": "custom_15k",  "contacts": 15000,  "price_usd": 199, "label": "15,000 contacts"},
    {"slug": "custom_20k",  "contacts": 20000,  "price_usd": 249, "label": "20,000 contacts"},
    {"slug": "custom_30k",  "contacts": 30000,  "price_usd": 349, "label": "30,000 contacts"},
    {"slug": "custom_50k",  "contacts": 50000,  "price_usd": 499, "label": "50,000 contacts"},
    {"slug": "custom_75k",  "contacts": 75000,  "price_usd": 699, "label": "75,000 contacts"},
    {"slug": "custom_100k", "contacts": 100000, "price_usd": 899, "label": "100,000 contacts"},
]

# Plan Limits Configuration
PLAN_LIMITS = {
    "free": {
        "max_accounts": 3,
        "max_contacts": 500,
        "max_monthly_recipients": 500,
    },
    "starter": {
        "max_accounts": 10,
        "max_contacts": 4000,
        "max_monthly_recipients": 4000,
    },
    "growth": {
        "max_accounts": 15,
        "max_contacts": 10000,
        "max_monthly_recipients": 10000,
    },
    # Custom plan slabs — accounts default to a generous 25, contacts/recipients per slab.
    **{
        s["slug"]: {
            "max_accounts": 25,
            "max_contacts": s["contacts"],
            "max_monthly_recipients": s["contacts"],
        }
        for s in CUSTOM_PLAN_SLABS
    },
}

# Permanently Assigned Plans (these accounts always have these plans regardless of Stripe)
# Read from environment variables for production flexibility
def _parse_permanent_plans():
    """Parse permanent plan assignments from environment variables"""
    assignments = {}
    starter_emails = os.environ.get('PERMANENT_PLAN_STARTER_EMAILS', '')
    growth_emails = os.environ.get('PERMANENT_PLAN_GROWTH_EMAILS', '')
    
    for email in starter_emails.split(','):
        email = email.strip().lower()
        if email:
            assignments[email] = "starter"
    
    for email in growth_emails.split(','):
        email = email.strip().lower()
        if email:
            assignments[email] = "growth"
    
    return assignments

PERMANENT_PLAN_ASSIGNMENTS = _parse_permanent_plans()

# Create the main app
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Log configuration at startup
logger.info(f"FRONTEND_URL configured as: {FRONTEND_URL}")
if 'preview.emergentagent.com' in FRONTEND_URL:
    logger.warning("WARNING: FRONTEND_URL is set to a preview domain. For production, ensure FRONTEND_URL=https://routemail.co")

# ==================== BACKGROUND SCHEDULER FOR SCHEDULED CAMPAIGNS ====================

scheduler_running = False
scheduler_task = None
warmup_task = None
warmup_running = False

# Warmup email subjects with (RTM) marker — varied, conversational
WARMUP_SUBJECTS = [
    "Quick question (RTM)",
    "Following up (RTM)",
    "Checking in on this (RTM)",
    "Project update (RTM)",
    "Re: Our discussion (RTM)",
    "Just wanted to share (RTM)",
    "Quick update for you (RTM)",
    "Thoughts on this? (RTM)",
    "Brief question (RTM)",
    "FYI - Update (RTM)",
    "Re: Next steps (RTM)",
    "Quick note (RTM)",
    "Circling back (RTM)",
    "Follow-up from earlier (RTM)",
    "Quick sync request (RTM)",
    "Update on progress (RTM)",
    "Just checking in (RTM)",
    "Brief update (RTM)",
    "Re: Action items (RTM)",
    "Quick feedback request (RTM)",
    "Hope you're doing well (RTM)",
    "Got a minute? (RTM)",
    "Following up from earlier today (RTM)",
    "Re: That thing we discussed (RTM)",
    "A quick favor (RTM)",
    "Wanted to share something (RTM)",
    "Quick heads up (RTM)",
    "Re: Yesterday's chat (RTM)",
    "Need your input (RTM)",
    "Touching base (RTM)",
    "Catching up (RTM)",
    "Re: Our thread (RTM)",
    "Looping back (RTM)",
    "When you get a chance (RTM)",
    "A small update (RTM)",
    "Just a thought (RTM)",
    "Wrapping up (RTM)",
    "Going over notes (RTM)",
    "Quick FYI (RTM)",
    "Re: Earlier conversation (RTM)",
]

# Warmup body building blocks for randomized, conversational content
WARMUP_GREETINGS = [
    "Hi", "Hey", "Hello", "Hi there", "Hey there", "Morning", "Good morning",
    "Hope all's well", "Hey friend", "Hi again", "Quick one",
]

WARMUP_OPENERS = [
    "Hope you're having a good week so far.",
    "Hope you're doing well.",
    "Hope this finds you well.",
    "Just wanted to follow up on this from earlier today.",
    "Thanks again for the update earlier.",
    "Quick one for you.",
    "Wanted to circle back on what we discussed.",
    "Following up on our last chat.",
    "Just checking in on this — no rush.",
    "Wanted to make sure this didn't get buried.",
    "Hope you had a good weekend.",
    "Thanks for getting back to me earlier.",
    "Just touching base on this.",
    "Picking up where we left off.",
    "Hope your week is going smoothly.",
]

WARMUP_BODY_LINES = [
    "Let me know your thoughts when you get a chance.",
    "I'll review this and get back to you shortly.",
    "Happy to jump on a quick call if that's easier.",
    "No rush at all — whenever it works for you.",
    "Just wanted to keep you in the loop.",
    "Curious what you think.",
    "Let me know if anything needs adjusting.",
    "I think we're on the same page, but want to confirm.",
    "Let me know if you'd like more detail.",
    "If anything looks off, ping me back.",
    "Happy to help with whatever you need on this.",
    "I'll wait to hear from you before moving forward.",
    "Just wanted to say thanks for the help yesterday.",
    "Will keep things moving on my end in the meantime.",
    "Drop a line whenever — no pressure.",
    "Quick gut check would be helpful when you can.",
    "Appreciate your time on this, as always.",
    "Wanted to make sure we're aligned before next steps.",
    "Let me know if I should hold off or proceed.",
    "Anything I'm missing here?",
]

WARMUP_CLOSERS = [
    "Thanks!", "Cheers,", "Best,", "Best regards,", "Talk soon,",
    "Appreciate it,", "Thanks again,", "All the best,", "Cheers!",
    "Catch you later,", "Have a good one,",
]

# Legacy templates kept for backwards compatibility (fallback only)
WARMUP_BODIES = [
    "Hi there,\n\nJust wanted to touch base on this. Let me know your thoughts when you get a chance.\n\nBest regards",
    "Hey,\n\nHope you're doing well. Wanted to follow up on our previous conversation. Any updates?\n\nThanks",
    "Hi,\n\nQuick question - have you had a chance to look at this? No rush, just checking in.\n\nCheers",
    "Hello,\n\nJust a brief note to see how things are going. Let me know if you need anything from my end.\n\nBest",
    "Hi there,\n\nWanted to share a quick update. Things are progressing well on our end. Will keep you posted.\n\nThanks",
]

# Warmup reply templates — varied, natural acknowledgements
WARMUP_REPLIES = [
    "Thanks for reaching out! I'll take a look and get back to you soon.",
    "Got it, thanks for the update. Will review and follow up.",
    "Appreciate you checking in. Everything looks good on my end.",
    "Thanks! Yes, I've been working on this. Will send an update shortly.",
    "Good to hear from you. Let me check on this and I'll respond in detail.",
    "Thanks for following up. I'm still working through this — will update you soon.",
    "Received, thank you! I'll review and get back to you.",
    "Thanks for the reminder. I'll prioritize this and respond soon.",
    "Hey! Thanks for the nudge. Looking at this now.",
    "All good on my side — appreciate the heads up.",
    "Got it, thanks. I'll loop back once I've reviewed.",
    "Thanks for circling back. Let me dig in and revert.",
    "Noted, thanks! Will get to this today if I can.",
    "Appreciate it — I'll have something for you by end of day.",
    "Thanks for keeping me posted. Sounds good on my end.",
    "Received, will reply with details shortly.",
    "Thanks again — I'll take it from here.",
    "Got your message. Confirming I'll handle this.",
    "Cheers, makes sense. I'll come back to you with thoughts.",
    "Thanks for the follow-up. All clear on my side.",
]


def build_warmup_body() -> str:
    """Build a conversational, varied warmup email body (2–5 lines)."""
    greeting = random.choice(WARMUP_GREETINGS)
    opener = random.choice(WARMUP_OPENERS)
    # 1-2 middle body lines
    middle_count = random.choice([1, 1, 2])
    middle = random.sample(WARMUP_BODY_LINES, k=middle_count)
    closer = random.choice(WARMUP_CLOSERS)
    parts = [f"{greeting},", "", opener]
    parts.extend(middle)
    parts.extend(["", closer])
    return "\n".join(parts)

async def run_warmup_worker():
    """Background worker for email warmup"""
    global warmup_running
    warmup_running = True
    logger.info("[WARMUP] Warmup worker started")
    
    while warmup_running:
        try:
            # Find accounts with warmup enabled
            warmup_accounts = await db.email_accounts.find({
                "warmup_enabled": True,
                "warmup_status": "active",
                "status": "connected"
            }, {"_id": 0}).to_list(1000)
            
            for account in warmup_accounts:
                try:
                    await process_warmup_for_account(account)
                except Exception as e:
                    logger.error(f"[WARMUP] Error processing warmup for {account.get('email')}: {e}")
            
            # Wait 5 minutes before next check
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"[WARMUP] Error in warmup worker: {e}")
            await asyncio.sleep(60)

async def process_warmup_for_account(account: dict):
    """Process warmup emails for a single account"""
    import random
    
    account_id = account.get("account_id")
    user_id = account.get("user_id")
    email = account.get("email")
    
    # Get warmup settings
    warmup_settings = account.get("warmup_settings", {})
    starting_emails = warmup_settings.get("starting_emails_per_day", 5)
    max_emails = warmup_settings.get("max_emails_per_day", 50)
    daily_increment = warmup_settings.get("daily_increment", 5)
    reply_rate = warmup_settings.get("reply_rate", 40) / 100  # Convert to decimal
    
    # Get current warmup stats
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    warmup_stats = await db.warmup_stats.find_one({
        "account_id": account_id,
        "date": today
    }, {"_id": 0})
    
    if not warmup_stats:
        # Initialize today's stats
        warmup_stats = {
            "account_id": account_id,
            "user_id": user_id,
            "date": today,
            "emails_sent": 0,
            "replies_sent": 0,
            "opens_tracked": 0,
            "warmup_day": account.get("warmup_day", 1),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.warmup_stats.insert_one(warmup_stats)
    
    # Calculate today's target based on warmup day
    warmup_day = warmup_stats.get("warmup_day", 1)
    todays_target = min(starting_emails + (warmup_day - 1) * daily_increment, max_emails)
    
    emails_sent_today = warmup_stats.get("emails_sent", 0)
    
    # Check if we've hit today's target
    if emails_sent_today >= todays_target:
        return
    
    # Find other accounts from the same user for warmup pool
    other_accounts = await db.email_accounts.find({
        "user_id": user_id,
        "account_id": {"$ne": account_id},
        "warmup_enabled": True,
        "status": "connected"
    }, {"_id": 0}).to_list(100)
    
    if not other_accounts:
        # No other accounts to warmup with - skip
        logger.info(f"[WARMUP] No warmup pool for {email} - need at least 2 accounts")
        return
    
    # Random delay before sending (30 seconds to 5 minutes)
    delay = random.randint(30, 300)
    await asyncio.sleep(delay)
    
    # Refresh campaign status check - make sure no active campaign is running
    active_campaign = await db.campaigns.find_one({
        "user_id": user_id,
        "status": "running",
        "account_ids": account_id
    })
    
    if active_campaign:
        # Don't send warmup during active campaigns
        return
    
    # Select random recipient from warmup pool
    recipient_account = random.choice(other_accounts)
    recipient_email = recipient_account.get("email")
    
    # Select random subject and build a fresh, varied conversational body
    subject = random.choice(WARMUP_SUBJECTS)
    body = build_warmup_body()
    
    try:
        # Send warmup email
        success = await send_warmup_email(account, recipient_email, subject, body)
        
        if success:
            # Update stats
            await db.warmup_stats.update_one(
                {"account_id": account_id, "date": today},
                {"$inc": {"emails_sent": 1, "opens_tracked": 1}}
            )
            
            # Log the warmup email
            warmup_log = {
                "log_id": f"wlog_{uuid.uuid4().hex[:12]}",
                "account_id": account_id,
                "user_id": user_id,
                "sender_email": email,
                "recipient_email": recipient_email,
                "subject": subject,
                "type": "sent",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.warmup_logs.insert_one(warmup_log)
            
            logger.info(f"[WARMUP] Sent warmup email from {email} to {recipient_email}")
            
            # Decide if we should simulate a reply
            if random.random() < reply_rate:
                # Schedule a reply (with delay)
                reply_delay = random.randint(60, 600)  # 1-10 minutes
                asyncio.create_task(send_warmup_reply(recipient_account, email, subject, reply_delay))
                
    except Exception as e:
        logger.error(f"[WARMUP] Failed to send warmup email from {email}: {e}")

async def send_warmup_email(account: dict, recipient: str, subject: str, body: str) -> bool:
    """Send a warmup email using SMTP"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        # Decrypt SMTP password
        encrypted_password = account.get("smtp_password_encrypted")
        if not encrypted_password:
            return False
        
        smtp_password = fernet.decrypt(encrypted_password.encode()).decode()
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"{account.get('display_name', '')} <{account.get('email')}>"
        msg['To'] = recipient
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send via SMTP
        smtp_host = account.get("smtp_host")
        smtp_port = account.get("smtp_port", 587)
        smtp_username = account.get("smtp_username") or account.get("email")
        encryption = account.get("smtp_encryption", "tls")
        
        if encryption == "ssl":
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
            if encryption == "tls":
                server.starttls()
        
        server.login(smtp_username, smtp_password)
        server.sendmail(account.get("email"), recipient, msg.as_string())
        server.quit()
        
        return True
        
    except Exception as e:
        logger.error(f"[WARMUP] SMTP error: {e}")
        return False

async def send_warmup_reply(account: dict, original_sender: str, original_subject: str, delay: int):
    """Send a warmup reply email after delay"""
    import random
    
    await asyncio.sleep(delay)
    
    reply_subject = f"Re: {original_subject}"
    reply_body = random.choice(WARMUP_REPLIES)
    
    try:
        success = await send_warmup_email(account, original_sender, reply_subject, reply_body)
        
        if success:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            
            # Update stats for the replying account
            await db.warmup_stats.update_one(
                {"account_id": account.get("account_id"), "date": today},
                {"$inc": {"replies_sent": 1}},
                upsert=True
            )
            
            # Log the reply
            warmup_log = {
                "log_id": f"wlog_{uuid.uuid4().hex[:12]}",
                "account_id": account.get("account_id"),
                "user_id": account.get("user_id"),
                "sender_email": account.get("email"),
                "recipient_email": original_sender,
                "subject": reply_subject,
                "type": "reply",
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.warmup_logs.insert_one(warmup_log)
            
            logger.info(f"[WARMUP] Sent reply from {account.get('email')} to {original_sender}")
            
    except Exception as e:
        logger.error(f"[WARMUP] Failed to send reply: {e}")

# ==================== DRIP CAMPAIGN WORKER ====================

drip_task = None
drip_running = False

async def run_drip_worker():
    """Background worker for drip campaign processing"""
    global drip_running
    drip_running = True
    logger.info("[DRIP] Drip campaign worker started")
    
    while drip_running:
        try:
            await process_drip_campaigns()
            # Check every minute
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"[DRIP] Error in drip worker: {e}")
            await asyncio.sleep(30)

async def process_drip_campaigns():
    """Process all active drip campaigns"""
    import random
    import pytz
    
    # Find all running drip campaigns
    drip_campaigns = await db.drip_campaigns.find({
        "status": "running"
    }, {"_id": 0}).to_list(1000)
    
    for campaign in drip_campaigns:
        try:
            await process_drip_campaign(campaign)
        except Exception as e:
            logger.error(f"[DRIP] Error processing campaign {campaign.get('drip_id')}: {e}")

async def process_drip_campaign(campaign: dict):
    """Process a single drip campaign - check and send due emails"""
    import random
    import pytz
    
    drip_id = campaign.get("drip_id")
    _user_id = campaign.get("user_id")  # noqa: F841 - reserved for future filtering
    
    # Get campaign schedule settings
    schedule = campaign.get("schedule", {})
    timezone_str = schedule.get("timezone", "UTC")
    sending_days = schedule.get("sending_days", [0, 1, 2, 3, 4])  # Mon-Fri default
    start_time = schedule.get("start_time", "09:00")
    end_time = schedule.get("end_time", "18:00")
    randomize_time = schedule.get("randomize_time", False)
    
    # Parse timezone
    try:
        tz = pytz.timezone(timezone_str)
    except Exception:
        tz = pytz.UTC
    
    # Get current time in campaign timezone
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)

    # Honour start_date — if set and the current local date is still before it,
    # the campaign hasn't started yet. The drip worker silently skips it; the
    # next worker tick will pick it up once the date has rolled over.
    start_date_str = schedule.get("start_date")
    if start_date_str:
        try:
            from datetime import date as _date_cls
            start_date_obj = _date_cls.fromisoformat(start_date_str)
            if now_local.date() < start_date_obj:
                return
        except Exception:
            # Malformed start_date — ignore the gate rather than block sending.
            pass

    # Check if current day is a sending day (0=Monday, 6=Sunday)
    current_day = now_local.weekday()
    if current_day not in sending_days:
        return
    
    # Parse start and end times
    try:
        start_hour, start_min = map(int, start_time.split(":"))
        end_hour, end_min = map(int, end_time.split(":"))
    except Exception:
        start_hour, start_min = 9, 0
        end_hour, end_min = 18, 0
    
    # Check if current time is within sending window
    current_minutes = now_local.hour * 60 + now_local.minute
    start_minutes = start_hour * 60 + start_min
    end_minutes = end_hour * 60 + end_min
    
    if current_minutes < start_minutes or current_minutes > end_minutes:
        return
    
    # Get steps
    steps = campaign.get("steps", [])
    if not steps:
        return

    # Get account IDs for rotation
    account_ids = campaign.get("account_ids", [])
    if not account_ids:
        return

    # Load accounts for sending (fresh from DB so daily_send_count is current)
    accounts = await db.email_accounts.find({
        "account_id": {"$in": account_ids},
        "status": "connected"
    }, {"_id": 0}).to_list(10000)

    if not accounts:
        return

    # ── PRE-RESET daily counters across ALL selected accounts ─────────────
    # Without this, accounts whose `last_reset_date` rolled over yesterday
    # carry stale `daily_send_count` values, and the per-contact rotation
    # check sees them as "at limit". We do a single bulk update + refresh
    # the in-memory copies so the rotation loop reasons over accurate state.
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stale_ids = [a["account_id"] for a in accounts if a.get("last_reset_date") != today_str]
    if stale_ids:
        await db.email_accounts.update_many(
            {"account_id": {"$in": stale_ids}},
            {"$set": {"daily_send_count": 0, "last_reset_date": today_str}},
        )
        for a in accounts:
            if a["account_id"] in stale_ids:
                a["daily_send_count"] = 0
                a["last_reset_date"] = today_str

    # ── FETCH ALL ELIGIBLE CONTACTS (no hidden batch cap) ─────────────────
    # Previously this used `.to_list(100)` which silently capped each worker
    # tick to 100 contacts, making large campaigns crawl. The new cap is a
    # safety ceiling, not a throughput limit.
    contacts = await db.drip_contacts.find({
        "drip_id": drip_id,
        "status": "active",
        "next_send_at": {"$lte": now_utc.isoformat()}
    }, {"_id": 0}).to_list(10000)

    # ── PROCESS WITH DIAGNOSTICS ──────────────────────────────────────────
    # We track per-run stats and the reason sending stopped so the UI /
    # admin diagnostics can show e.g. "Daily capacity reached".
    stats = {
        "campaign_id": drip_id,
        "campaign_name": campaign.get("name"),
        "total_contacts": await db.drip_contacts.count_documents({"drip_id": drip_id}),
        "eligible_contacts": len(contacts),
        "queued_contacts": len(contacts),
        "sent_contacts": 0,
        "skipped_contacts": 0,
        "suppressed_contacts": 0,
        "accounts_selected": len(account_ids),
        "accounts_connected": len(accounts),
        "accounts_used": {},  # account_id -> emails sent this run
        "stop_reason": None,
        "started_at": now_utc.isoformat(),
    }

    if not contacts:
        stats["stop_reason"] = "no_eligible_contacts"
    else:
        for contact in contacts:
            # Schedule-window close check (re-evaluated each contact so a
            # campaign that crosses its end_time stops cleanly mid-run).
            now_local_check = datetime.now(timezone.utc).astimezone(tz)
            cur_min = now_local_check.hour * 60 + now_local_check.minute
            if cur_min < start_minutes or cur_min > end_minutes:
                stats["stop_reason"] = "schedule_window_closed"
                break

            # All accounts at limit? Stop early — next tick (or tomorrow's
            # reset) will pick up the remaining contacts.
            if all(a.get("daily_send_count", 0) >= a.get("daily_limit", 50) for a in accounts):
                stats["stop_reason"] = "daily_capacity_reached"
                break

            try:
                result = await process_drip_contact(
                    campaign, contact, steps, accounts,
                    randomize_time, tz, start_minutes, end_minutes,
                )
                # `process_drip_contact` now returns a small dict describing
                # what it did so the parent can update counters.
                outcome = (result or {}).get("outcome")
                if outcome == "sent":
                    stats["sent_contacts"] += 1
                    used_id = result.get("account_id")
                    if used_id:
                        stats["accounts_used"][used_id] = stats["accounts_used"].get(used_id, 0) + 1
                elif outcome == "suppressed":
                    stats["suppressed_contacts"] += 1
                else:
                    stats["skipped_contacts"] += 1
            except Exception as e:
                logger.error(f"[DRIP] Error processing contact {contact.get('email')}: {e}")
                stats["skipped_contacts"] += 1
        else:
            # for-loop completed without `break` → we sent (or attempted) all
            # eligible contacts.
            stats["stop_reason"] = "all_eligible_sent"

    # Persist diagnostics on the campaign + emit a single structured log line.
    stats["finished_at"] = datetime.now(timezone.utc).isoformat()
    await db.drip_campaigns.update_one(
        {"drip_id": drip_id},
        {"$set": {"last_run_stats": stats, "last_run_stop_reason": stats["stop_reason"]}},
    )
    logger.info(
        f"[DRIP] run drip_id={drip_id} eligible={stats['eligible_contacts']} "
        f"sent={stats['sent_contacts']} skipped={stats['skipped_contacts']} "
        f"suppressed={stats['suppressed_contacts']} "
        f"accounts_used={len(stats['accounts_used'])}/{stats['accounts_connected']} "
        f"stop_reason={stats['stop_reason']}"
    )

async def process_drip_contact(campaign: dict, contact: dict, steps: list, accounts: list, randomize_time: bool, tz, start_minutes: int, end_minutes: int):
    """Process a single contact in a drip campaign"""
    import random
    
    drip_id = campaign.get("drip_id")
    contact_id = contact.get("contact_id")
    current_step = contact.get("current_step", 0)
    
    if current_step >= len(steps):
        # Contact completed all steps
        await db.drip_contacts.update_one(
            {"contact_id": contact_id},
            {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"outcome": "completed"}
    
    step = steps[current_step]
    
    # Check stop conditions
    stop_on_reply = campaign.get("stop_on_reply", True)
    stop_on_bounce = campaign.get("stop_on_bounce", True)
    
    if stop_on_reply and contact.get("replied"):
        await db.drip_contacts.update_one(
            {"contact_id": contact_id},
            {"$set": {"status": "replied"}}
        )
        return {"outcome": "replied"}
    
    if stop_on_bounce and contact.get("bounced"):
        await db.drip_contacts.update_one(
            {"contact_id": contact_id},
            {"$set": {"status": "bounced"}}
        )
        return {"outcome": "bounced"}
    
    # Real-time DNE / suppression check — runs before every step
    recipient_email_pre = contact.get("email", "")
    suppression_list_ids = campaign.get("suppression_list_ids", [])
    if await is_email_suppressed(campaign.get("user_id"), recipient_email_pre, suppression_list_ids):
        await db.drip_contacts.update_one(
            {"contact_id": contact_id},
            {"$set": {
                "status": "suppressed",
                "suppressed_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        await db.drip_logs.insert_one({
            "log_id": f"dlog_{uuid.uuid4().hex[:12]}",
            "drip_id": drip_id,
            "contact_id": contact_id,
            "contact_email": recipient_email_pre,
            "step": current_step,
            "subject": (steps[current_step] or {}).get("subject", ""),
            "account_email": None,
            "status": "suppressed",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"[DRIP] Skipped suppressed contact {recipient_email_pre} for campaign {drip_id}")
        return {"outcome": "suppressed"}
    
    # ── ACCOUNT SELECTION — fair least-loaded ────────────────────────────
    # Previously this pinned each contact to one account via
    # `hash(contact_id) % len(accounts)` — meaning contacts pinned to a
    # saturated account would be skipped even if other accounts had spare
    # capacity. We now pick the account with the MOST remaining daily
    # capacity, falling back to the next non-saturated one. This guarantees
    # the full 1080 emails/day (27 inboxes × 40) is actually used.
    account = None
    best_remaining = -1
    for cand in accounts:
        cand_limit = cand.get("daily_limit", 50)
        cand_sent = cand.get("daily_send_count", 0)
        remaining = cand_limit - cand_sent
        if remaining > best_remaining:
            best_remaining = remaining
            account = cand
    if account is None or best_remaining <= 0:
        # All selected accounts at limit — parent loop also checks this and
        # will record `stop_reason = daily_capacity_reached`.
        return {"outcome": "skipped_no_capacity"}
    
    # Prepare email content
    raw_subject = step.get("subject", "")
    body = step.get("body", "")

    # Use the unified renderer so {{var}}, {var}, missing variables and stray
    # HTML entities are all handled identically across campaigns and drips.
    from template_render import render_template as _render_tmpl
    contact_data = contact.get("data", {}) or {}
    # Merge top-level contact fields (email, first_name, last_name etc.) into
    # the data dict so they're addressable inside the template.
    merged_data = {**contact_data, **{k: v for k, v in contact.items() if k not in ("data", "_id")}}
    fallbacks = campaign.get("variable_fallbacks") or {}
    subject = _render_tmpl(raw_subject, merged_data, fallbacks=fallbacks)
    body = _render_tmpl(body, merged_data, fallbacks=fallbacks)

    # ── EMPTY-SUBJECT THREADING ───────────────────────────────────────────
    # When a follow-up step has an empty subject, RouteMail continues the
    # original conversation: actual subject becomes "Re: <first step subject>"
    # and proper In-Reply-To / References headers are set so the recipient's
    # mail client groups the messages into one thread.
    in_reply_to_id: Optional[str] = None
    references_ids: List[str] = []
    if not subject.strip() and current_step > 0:
        # Find the first non-empty step subject (rendered against this
        # contact). The first step is required to have a subject, so this
        # is virtually guaranteed to find one.
        anchor_subject = ""
        for prior in steps[:current_step]:
            cand = _render_tmpl(prior.get("subject", ""), merged_data, fallbacks=fallbacks).strip()
            if cand:
                anchor_subject = cand
                break
        # Avoid double "Re: " — match case-insensitively at the start.
        if anchor_subject:
            subject = anchor_subject if anchor_subject.lower().startswith("re:") else f"Re: {anchor_subject}"

        # Build the threading chain from the sent_emails collection. We grab
        # every prior message_id sent to this recipient under this drip and
        # use the newest as In-Reply-To plus the full ordered list as
        # References.
        prior_sends = await db.sent_emails.find(
            {
                "user_id": campaign.get("user_id", ""),
                "drip_campaign_id": campaign.get("drip_id"),
                "recipient_email": contact.get("email"),
                "message_id": {"$exists": True, "$nin": [None, ""]},
            },
            {"_id": 0, "message_id": 1, "sent_at": 1, "drip_step_number": 1},
        ).sort([("sent_at", 1)]).to_list(50)
        if prior_sends:
            references_ids = [
                (p["message_id"] if p["message_id"].startswith("<") else f"<{p['message_id']}>")
                for p in prior_sends
            ]
            in_reply_to_id = references_ids[-1]

    recipient_email = contact.get("email")
    
    # Resolve {{unsubscribe_url}} (per-recipient) so that an Unsubscribe link inserted
    # in the drip step body becomes a working URL. Uses a signed token (no internal IDs leaked).
    frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
    unsubscribe_token_str = make_unsubscribe_token(campaign.get('user_id', ''), recipient_email)
    unsubscribe_url = f"{frontend_url}/api/unsubscribe/u/{unsubscribe_token_str}"
    body = body.replace("{{unsubscribe_url}}", unsubscribe_url)
    subject = subject.replace("{{unsubscribe_url}}", unsubscribe_url)
    
    # Send email
    try:
        send_result = await send_drip_email(
            account,
            recipient_email,
            subject,
            body,
            from_name_override=campaign.get("from_name"),
            in_reply_to=in_reply_to_id,
            references=references_ids,
        )
        success = bool(send_result.get("success"))

        if success:
            # Track outbound for Unibox reply matching + Sent Email Viewer
            await register_sent_email(
                db,
                user_id=campaign.get("user_id", ""),
                account_id=account.get("account_id", ""),
                sender_email=account.get("email", ""),
                recipient_email=recipient_email,
                subject=subject,
                message_id=send_result.get("message_id"),
                drip_campaign_id=campaign.get("drip_id"),
                drip_campaign_name=campaign.get("name"),
                drip_step_number=current_step,
                folder_id=campaign.get("folder_id"),
                body_html=body,
                from_name=campaign.get("from_name"),
            )
            # Update account send count (DB + in-memory mirror so the parent
            # loop's "all accounts at limit?" check stays accurate within the
            # same tick).
            await db.email_accounts.update_one(
                {"account_id": account.get("account_id")},
                {"$inc": {"daily_send_count": 1}}
            )
            account["daily_send_count"] = account.get("daily_send_count", 0) + 1
            
            # Calculate next send time
            next_step = current_step + 1
            if next_step < len(steps):
                next_step_data = steps[next_step]
                delay_hours = next_step_data.get("delay_hours", 0)
                delay_days = next_step_data.get("delay_days", 0)
                total_delay_hours = delay_hours + (delay_days * 24)
                
                next_send_at = datetime.now(timezone.utc) + timedelta(hours=total_delay_hours)
                
                # Apply randomization if enabled
                if randomize_time:
                    # Add random minutes within the window
                    window_minutes = end_minutes - start_minutes
                    if window_minutes > 0:
                        random_offset = random.randint(0, min(60, window_minutes))
                        next_send_at += timedelta(minutes=random_offset)
            else:
                next_send_at = None
            
            # Update contact
            await db.drip_contacts.update_one(
                {"contact_id": contact_id},
                {"$set": {
                    "current_step": next_step,
                    "last_sent_at": datetime.now(timezone.utc).isoformat(),
                    "last_sent_step": current_step,
                    "next_send_at": next_send_at.isoformat() if next_send_at else None
                }}
            )
            
            # Log the send
            await db.drip_logs.insert_one({
                "log_id": f"dlog_{uuid.uuid4().hex[:12]}",
                "drip_id": drip_id,
                "contact_id": contact_id,
                "contact_email": recipient_email,
                "step": current_step,
                "subject": subject,
                "account_email": account.get("email"),
                "status": "sent",
                "sent_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Update campaign stats
            await db.drip_campaigns.update_one(
                {"drip_id": drip_id},
                {"$inc": {"total_sent": 1}}
            )
            
            logger.info(f"[DRIP] Sent step {current_step + 1} to {recipient_email} for campaign {drip_id}")
            
            # Apply per-email delay
            send_delay = account.get("send_delay", 5)
            await asyncio.sleep(send_delay)
            return {"outcome": "sent", "account_id": account.get("account_id")}
            
    except Exception as e:
        logger.error(f"[DRIP] Failed to send email to {recipient_email}: {e}")
        
        # Log the failure
        await db.drip_logs.insert_one({
            "log_id": f"dlog_{uuid.uuid4().hex[:12]}",
            "drip_id": drip_id,
            "contact_id": contact_id,
            "contact_email": recipient_email,
            "step": current_step,
            "subject": subject,
            "account_email": account.get("email"),
            "status": "failed",
            "error": str(e),
            "sent_at": datetime.now(timezone.utc).isoformat()
        })
        return {"outcome": "failed", "account_id": account.get("account_id")}
    # send_drip_email returned success=False without raising
    return {"outcome": "send_failed", "account_id": account.get("account_id")}

async def send_drip_email(
    account: dict,
    recipient: str,
    subject: str,
    body: str,
    from_name_override: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    references: Optional[List[str]] = None,
) -> bool:
    """Send a drip campaign email using SMTP.

    Optional ``in_reply_to`` / ``references`` apply RFC 5322 threading
    headers so follow-up drip steps with an empty subject continue the
    original conversation in the recipient's mailbox.
    """
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        # Decrypt SMTP password
        encrypted_password = account.get("smtp_password_encrypted")
        if not encrypted_password:
            return False
        
        smtp_password = fernet.decrypt(encrypted_password.encode()).decode()
        
        # Create message
        msg = MIMEMultipart("alternative")
        # Campaign/drip From Name override takes priority over account-level fields
        effective_from_name = (
            (from_name_override or "").strip()
            or (account.get("from_name") or "").strip()
            or account.get("display_name", "")
        )
        msg['From'] = f"{effective_from_name} <{account.get('email')}>" if effective_from_name else account.get('email')
        msg['To'] = recipient
        msg['Subject'] = subject
        # Stable Message-ID for IMAP reply matching
        from email.utils import make_msgid as _make_msgid
        msg_id = _make_msgid(domain="routemail.app")
        msg['Message-ID'] = msg_id

        # Threading headers — applied only when this is a follow-up step in
        # an existing conversation (empty-subject auto-thread). Both
        # In-Reply-To and References are required for reliable threading in
        # Gmail / Outlook / Apple Mail.
        if in_reply_to:
            msg['In-Reply-To'] = in_reply_to
        if references:
            msg['References'] = " ".join(references)
        
        # Add both plain text and HTML versions
        text_part = MIMEText(body.replace("<br>", "\n").replace("</p>", "\n"), 'plain')
        html_part = MIMEText(body, 'html')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Send via SMTP
        smtp_host = account.get("smtp_host")
        smtp_port = account.get("smtp_port", 587)
        smtp_username = account.get("smtp_username") or account.get("email")
        encryption = account.get("smtp_encryption", "tls")
        
        if encryption == "ssl":
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
            if encryption == "tls":
                server.starttls()
        
        server.login(smtp_username, smtp_password)
        server.sendmail(account.get("email"), recipient, msg.as_string())
        server.quit()
        
        return {"success": True, "message_id": msg_id}
        
    except Exception as e:
        logger.error(f"[DRIP] SMTP error: {e}")
        return {"success": False, "error": str(e)}

async def check_scheduled_campaigns():
    """Check for scheduled campaigns that need to be started, AND
    auto-resume campaigns that were paused due to daily limits whenever
    at least one assigned account has rolled over to a new day."""
    global scheduler_running
    
    while scheduler_running:
        try:
            now = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")
            
            # ---- 1) Start scheduled campaigns ----
            scheduled_campaigns = await db.campaigns.find({
                "status": "scheduled",
                "scheduled_at": {"$ne": None}
            }, {"_id": 0}).to_list(100)
            
            for campaign in scheduled_campaigns:
                try:
                    scheduled_at = campaign.get("scheduled_at")
                    if not scheduled_at:
                        continue
                    
                    if isinstance(scheduled_at, str):
                        scheduled_dt = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                    else:
                        scheduled_dt = scheduled_at
                    
                    if scheduled_dt.tzinfo is None:
                        scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
                    
                    if now >= scheduled_dt:
                        logger.info(f"Starting scheduled campaign: {campaign['campaign_id']} - scheduled for {scheduled_at}")
                        await start_scheduled_campaign(campaign)
                        
                except Exception as e:
                    logger.error(f"Error processing scheduled campaign {campaign.get('campaign_id')}: {e}")
            
            # ---- 2) Auto-resume campaigns paused due to daily limits ----
            paused_dl_campaigns = await db.campaigns.find({
                "status": "paused_daily_limit"
            }, {"_id": 0}).to_list(100)
            
            for campaign in paused_dl_campaigns:
                try:
                    user_id = campaign.get("user_id")
                    account_ids = campaign.get("account_ids", [])
                    query = {"user_id": user_id, "status": "connected"}
                    if account_ids:
                        query["account_id"] = {"$in": account_ids}
                    accounts = await db.email_accounts.find(query, {"_id": 0}).to_list(100)
                    if not accounts:
                        continue
                    # An account is "fresh" if its last_send_date is not today
                    # OR (same day) it still has remaining quota (e.g. user raised the limit).
                    has_capacity = False
                    for acc in accounts:
                        if acc.get("last_send_date") != today:
                            has_capacity = True
                            break
                        if acc.get("daily_send_count", 0) < acc.get("daily_limit", 50):
                            has_capacity = True
                            break
                    if not has_capacity:
                        continue
                    
                    logger.info(f"[AUTO-RESUME] Daily-limit-paused campaign {campaign['campaign_id']} has fresh capacity — resuming")
                    await db.campaigns.update_one(
                        {"campaign_id": campaign["campaign_id"]},
                        {"$set": {
                            "status": "running",
                            "is_locked": True,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                            "auto_resumed_at": datetime.now(timezone.utc).isoformat(),
                        }}
                    )
                    asyncio.create_task(process_campaign_queue(campaign["campaign_id"], user_id))
                except Exception as e:
                    logger.error(f"Error auto-resuming campaign {campaign.get('campaign_id')}: {e}")
            
        except Exception as e:
            logger.error(f"Error in scheduled campaign checker: {e}")
        
        # Wait 30 seconds before checking again
        await asyncio.sleep(30)

async def start_scheduled_campaign(campaign: dict):
    """Start a scheduled campaign (internal function)"""
    campaign_id = campaign["campaign_id"]
    user_id = campaign["user_id"]
    
    try:
        # Get email accounts
        account_ids = campaign.get("account_ids", [])
        if not account_ids:
            accounts = await db.email_accounts.find(
                {"user_id": user_id, "status": "connected"},
                {"_id": 0}
            ).to_list(100)
            account_ids = [a["account_id"] for a in accounts]
        else:
            accounts = await db.email_accounts.find(
                {"user_id": user_id, "account_id": {"$in": account_ids}, "status": "connected"},
                {"_id": 0}
            ).to_list(100)
            account_ids = [a["account_id"] for a in accounts]
        
        if not accounts:
            logger.error(f"Scheduled campaign {campaign_id}: No connected email accounts")
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {"$set": {"status": "failed", "error": "No connected email accounts", "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            return
        
        # Get email list
        email_list = await db.email_lists.find_one(
            {"list_id": campaign["list_id"], "user_id": user_id},
            {"_id": 0}
        )
        
        if not email_list:
            logger.error(f"Scheduled campaign {campaign_id}: Email list not found")
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {"$set": {"status": "failed", "error": "Email list not found", "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            return
        
        if not email_list.get("emails") or len(email_list["emails"]) == 0:
            logger.error(f"Scheduled campaign {campaign_id}: Email list is empty")
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {"$set": {"status": "failed", "error": "Email list is empty", "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            return
        
        # Check for existing queue (prevent duplicate creation)
        existing_queue = await db.email_queue.count_documents({"campaign_id": campaign_id})
        
        if existing_queue == 0:
            # Apply send-range filter
            all_emails = email_list["emails"]
            send_mode = campaign.get("send_range_mode", "all")
            if send_mode == "range":
                start = max(1, int(campaign.get("send_range_start") or 1))
                end = min(len(all_emails), int(campaign.get("send_range_end") or len(all_emails)))
                if start > end:
                    selected_emails = []
                else:
                    selected_emails = all_emails[start - 1:end]
            else:
                selected_emails = all_emails
            
            queue_items = []
            for email_data in selected_emails:
                item = {
                    "queue_id": f"q_{uuid.uuid4().hex[:12]}",
                    "campaign_id": campaign_id,
                    "user_id": user_id,
                    "recipient_email": email_data.get("email", ""),
                    "recipient_data": email_data,
                    "status": "pending",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                queue_items.append(item)
            
            if queue_items:
                await db.email_queue.insert_many(queue_items)
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {"$set": {"total_emails": len(queue_items)}}
            )
        
        # Update campaign status and lock it
        await db.campaigns.update_one(
            {"campaign_id": campaign_id},
            {"$set": {
                "status": "running",
                "is_locked": True,
                "account_ids": account_ids,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        logger.info(f"Scheduled campaign {campaign_id} started successfully")
        
        # Start the email queue processing in background
        asyncio.create_task(process_campaign_queue(campaign_id, user_id))
        
    except Exception as e:
        logger.error(f"Error starting scheduled campaign {campaign_id}: {e}")
        await db.campaigns.update_one(
            {"campaign_id": campaign_id},
            {"$set": {"status": "failed", "error": str(e), "updated_at": datetime.now(timezone.utc).isoformat()}}
        )

@app.on_event("startup")
async def startup_event():
    """Start the background scheduler on app startup"""
    global scheduler_running, scheduler_task, warmup_running, warmup_task, drip_running, drip_task
    scheduler_running = True
    scheduler_task = asyncio.create_task(check_scheduled_campaigns())
    logger.info("Background scheduler for scheduled campaigns started")
    
    # Start warmup worker
    warmup_running = True
    warmup_task = asyncio.create_task(run_warmup_worker())
    logger.info("Background warmup worker started")
    
    # Start drip campaign worker
    drip_running = True
    drip_task = asyncio.create_task(run_drip_worker())
    logger.info("Background drip campaign worker started")

    # Start IMAP receive worker (Unibox)
    imap_task = asyncio.create_task(run_imap_worker(db, fernet))  # noqa: F841
    logger.info("Background IMAP receive worker started")
    
    # Ensure DNE / suppression indexes exist for fast lookups
    try:
        await db.dne_emails.create_index(
            [("user_id", 1), ("email", 1)],
            name="user_email_idx"
        )
        await db.dne_emails.create_index(
            [("list_id", 1), ("email", 1)],
            name="list_email_idx",
            unique=True
        )
        await db.suppression_list.create_index(
            [("user_id", 1), ("email", 1)],
            name="user_email_idx"
        )
        logger.info("DNE / suppression indexes ensured")
    except Exception as e:
        logger.warning(f"Could not create DNE indexes: {e}")

@app.on_event("shutdown") 
async def shutdown_event():
    """Stop the background scheduler on app shutdown"""
    global scheduler_running, scheduler_task, warmup_running, warmup_task, drip_running, drip_task
    scheduler_running = False
    warmup_running = False
    drip_running = False
    
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
    
    if warmup_task:
        warmup_task.cancel()
        try:
            await warmup_task
        except asyncio.CancelledError:
            pass
    
    if drip_task:
        drip_task.cancel()
        try:
            await drip_task
        except asyncio.CancelledError:
            pass
    
    logger.info("Background scheduler, warmup worker, and drip worker stopped")

# ==================== ENCRYPTION HELPERS ====================

def encrypt_data(data: str) -> str:
    """Encrypt sensitive data"""
    return fernet.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    try:
        return fernet.decrypt(encrypted_data.encode()).decode()
    except Exception:
        return ""

# ==================== DO NOT EMAIL (DNE) HELPERS ====================

async def ensure_global_dne_list(user_id: str) -> str:
    """Ensure the user has a global DNE list; return its list_id."""
    existing = await db.dne_lists.find_one(
        {"user_id": user_id, "is_global": True},
        {"_id": 0, "list_id": 1}
    )
    if existing:
        return existing["list_id"]
    
    new_list = {
        "list_id": f"dne_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "name": "Global Do Not Email",
        "is_global": True,
        "email_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.dne_lists.insert_one(new_list)
    return new_list["list_id"]

# --- Domain-level suppression helpers -----------------------------------

_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
_DOMAIN_PATTERN = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$")


def extract_domain(email: str) -> str:
    """Return lowercase domain part of an email, '' if invalid."""
    if not email or "@" not in email:
        return ""
    return email.strip().lower().rsplit("@", 1)[-1].lstrip(".")


def classify_dne_entry(raw: str) -> Optional[Dict[str, str]]:
    """Classify a raw user input as either an email or a domain entry.
    Returns {'type': 'email'|'domain', 'value': normalized_value} or None if invalid.
    Accepts entries like 'john@example.com', 'example.com', '@example.com'.
    """
    if raw is None:
        return None
    val = str(raw).strip().lower()
    if not val:
        return None
    # Treat leading "@" as a domain shortcut
    if val.startswith("@"):
        val = val[1:]
    if "@" in val:
        if _EMAIL_PATTERN.match(val):
            return {"type": "email", "value": val}
        return None
    if _DOMAIN_PATTERN.match(val):
        return {"type": "domain", "value": val}
    return None


async def is_email_suppressed(user_id: str, email: str, suppression_list_ids: Optional[List[str]] = None) -> bool:
    """Check whether `email` should be blocked from sending.
    
    Checks (in order):
    - Legacy unsubscribe register (`suppression_list`) — ALWAYS applied for both
      the email itself AND its domain (if a domain entry exists).
    - The DNE lists explicitly attached to the campaign via `suppression_list_ids`.
      Both email-level and domain-level entries are matched.
    The Global DNE list is ONLY checked when the user has explicitly selected it.
    """
    if not email:
        return False
    email_norm = email.strip().lower()
    if not email_norm:
        return False
    domain = extract_domain(email_norm)

    # 1) Legacy unsubscribes — email OR domain match. Always applied.
    legacy_q: Dict[str, Any] = {"user_id": user_id, "$or": [{"email": email_norm}]}
    if domain:
        legacy_q["$or"].append({"email": domain, "type": "domain"})
    legacy = await db.suppression_list.find_one(legacy_q, {"email": 1})
    if legacy:
        return True
    
    # 2) Only the DNE lists explicitly selected on the campaign
    list_ids = list(suppression_list_ids or [])
    if not list_ids:
        return False
    
    or_clauses: List[Dict[str, Any]] = [{"email": email_norm}]
    if domain:
        or_clauses.append({"email": domain, "type": "domain"})
    hit = await db.dne_emails.find_one(
        {"user_id": user_id, "list_id": {"$in": list_ids}, "$or": or_clauses},
        {"email": 1}
    )
    return hit is not None

async def add_email_to_global_dne(user_id: str, email: str, *, entry_type: str = "email", source: str = "unsubscribe") -> bool:
    """Add a single email OR domain entry to the user's Global DNE list (idempotent).
    Returns True if a new entry was added, False if it already existed.
    """
    if not email:
        return False
    value = email.strip().lower().lstrip("@")
    if not value:
        return False
    global_id = await ensure_global_dne_list(user_id)
    existing = await db.dne_emails.find_one(
        {"user_id": user_id, "list_id": global_id, "email": value},
        {"email": 1}
    )
    if existing:
        return False
    await db.dne_emails.insert_one({
        "user_id": user_id,
        "list_id": global_id,
        "email": value,
        "type": entry_type if entry_type in ("email", "domain") else "email",
        "source": source,
        "added_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.dne_lists.update_one(
        {"list_id": global_id},
        {"$inc": {"email_count": 1}}
    )
    return True

def parse_scheduled_at_in_timezone(scheduled_at_str: str, tz_name: Optional[str]) -> datetime:
    """Parse a scheduled_at string, honouring the user-selected timezone.
    
    Rules:
    - If the string carries Z or +HH:MM offset, trust it (treat as absolute UTC/offset).
    - Else if it's a naive local string (e.g. '2026-05-04T09:00' or '2026-05-04T09:00:00')
      and a timezone name is provided, localise it in that timezone and return a
      timezone-aware UTC datetime.
    - Else (naive + no timezone), fall back to treating it as UTC.
    
    Raises ValueError on invalid input.
    """
    import pytz
    raw = (scheduled_at_str or "").strip()
    if not raw:
        raise ValueError("Empty scheduled_at")
    
    # Has an explicit tz offset? parse directly
    if raw.endswith("Z") or ("+" in raw[10:]) or ("-" in raw[10:]):
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    
    # Naive → treat as local time in the given tz
    naive = datetime.fromisoformat(raw)
    if naive.tzinfo is not None:
        return naive
    
    tz = None
    if tz_name:
        try:
            tz = pytz.timezone(tz_name)
        except Exception:
            tz = None
    if tz is None:
        return naive.replace(tzinfo=timezone.utc)
    
    localised = tz.localize(naive)
    return localised.astimezone(timezone.utc)

# ==================== EMAIL HELPERS (Resend) ====================

# Logo URL for system emails (publicly accessible)
ROUTEMAIL_LOGO_URL = "https://routemail.co/routemail-logo.png"

def get_email_logo_html() -> str:
    """Generate the logo header HTML for system emails"""
    return f"""
        <div style="text-align: center; margin-bottom: 20px;">
            <img src="{ROUTEMAIL_LOGO_URL}" alt="RouteMail" style="width: 160px; display: block; margin: 0 auto 20px auto; max-width: 100%; height: auto;">
        </div>
    """

async def send_email_async(to_email: str, subject: str, html_content: str):
    """Send email using Resend API (non-blocking)"""
    try:
        params = {
            "from": FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        }
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email sent to {to_email}: {result.get('id')}")
        return result
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return None

def get_verification_email_html(first_name: str, verification_link: str) -> str:
    """Generate verification email HTML with RouteMail branding"""
    logo_html = get_email_logo_html()
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f5; margin: 0; padding: 40px 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
            {logo_html}
            <div style="text-align: center; margin-bottom: 32px;">
                <h1 style="color: #18181b; font-size: 24px; margin: 0;">Verify Your RouteMail Account</h1>
            </div>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">Hi {first_name},</p>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">Welcome to RouteMail!</p>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 24px;">Please confirm your email address to activate your account.</p>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 24px;">Click the button below to verify your account:</p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{verification_link}" style="display: inline-block; background: linear-gradient(135deg, #8b5cf6 0%, #3b82f6 100%); color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 16px;">Verify My Email</a>
            </div>
            <p style="color: #71717a; font-size: 14px; line-height: 1.6; margin: 24px 0 0;">This link will expire in 2 hours.</p>
            <p style="color: #71717a; font-size: 14px; line-height: 1.6; margin: 16px 0 0;">If you did not create this account, you can safely ignore this email.</p>
            <hr style="border: none; border-top: 1px solid #e4e4e7; margin: 32px 0;">
            <p style="color: #a1a1aa; font-size: 13px; text-align: center; margin: 0;">— RouteMail Team<br>support@routemail.co</p>
        </div>
    </body>
    </html>
    """

def get_welcome_email_html(first_name: str, plan_type: str) -> tuple:
    """Generate welcome email subject and HTML based on plan type with RouteMail branding"""
    logo_html = get_email_logo_html()
    
    if plan_type == "growth":
        subject = "Welcome to RouteMail Growth 🚀"
        features = """
            <li style="margin-bottom: 8px;">Connect up to <strong>15 email accounts</strong></li>
            <li style="margin-bottom: 8px;">Send to <strong>10,000 contacts per month</strong></li>
            <li style="margin-bottom: 8px;">Send up to <strong>120,000 emails per year</strong></li>
            <li style="margin-bottom: 8px;"><strong>Unlimited emails</strong></li>
        """
        intro = "Your Growth Plan is now active."
        outro = "Time to maximize your outreach."
    elif plan_type == "starter":
        subject = "Welcome to RouteMail Starter 🎯"
        features = """
            <li style="margin-bottom: 8px;">Connect up to <strong>10 email accounts</strong></li>
            <li style="margin-bottom: 8px;">Send to <strong>4,000 contacts per month</strong></li>
            <li style="margin-bottom: 8px;">Send up to <strong>48,000 emails per year</strong></li>
            <li style="margin-bottom: 8px;"><strong>Unlimited emails</strong></li>
        """
        intro = "Your Starter Plan is now active."
        outro = "You're ready to scale your outreach efficiently."
    else:  # free
        subject = "Welcome to RouteMail – You're on the Free Plan"
        features = """
            <li style="margin-bottom: 8px;">Connect up to <strong>3 email accounts</strong></li>
            <li style="margin-bottom: 8px;">Store up to <strong>500 contacts</strong></li>
            <li style="margin-bottom: 8px;">Send emails to <strong>500 contacts per month</strong></li>
        """
        intro = "Your Free Plan is now active — free forever, no expiry."
        outro = "Upgrade anytime from your dashboard to unlock higher monthly contact limits.<br><br>Let's get your first campaign live!"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f5; margin: 0; padding: 40px 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
            {logo_html}
            <div style="text-align: center; margin-bottom: 32px;">
                <h1 style="color: #18181b; font-size: 24px; margin: 0;">{subject.replace(' 🚀', '').replace(' 🎯', '')}</h1>
            </div>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">Hi {first_name},</p>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 24px;">{intro}</p>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">You can:</p>
            <ul style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 24px; padding-left: 24px;">
                {features}
            </ul>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 24px;">{outro}</p>
            <hr style="border: none; border-top: 1px solid #e4e4e7; margin: 32px 0;">
            <p style="color: #a1a1aa; font-size: 13px; text-align: center; margin: 0;">— RouteMail Team</p>
        </div>
    </body>
    </html>
    """
    return subject, html

def get_password_reset_email_html(reset_link: str) -> str:
    """Generate password reset email HTML with RouteMail branding"""
    logo_html = get_email_logo_html()
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f5; margin: 0; padding: 40px 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
            {logo_html}
            <div style="text-align: center; margin-bottom: 32px;">
                <h1 style="color: #18181b; font-size: 24px; margin: 0;">Reset Your RouteMail Password</h1>
            </div>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">Hi,</p>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 24px;">We received a request to reset your password.</p>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 24px;">Click below to reset it:</p>
            <div style="text-align: center; margin: 32px 0;">
                <a href="{reset_link}" style="display: inline-block; background: linear-gradient(135deg, #8b5cf6 0%, #3b82f6 100%); color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 16px;">Reset Password</a>
            </div>
            <p style="color: #71717a; font-size: 14px; line-height: 1.6; margin: 24px 0 0;">This link expires in 30 minutes.</p>
            <p style="color: #71717a; font-size: 14px; line-height: 1.6; margin: 16px 0 0;">If you didn't request this, ignore this email.</p>
            <hr style="border: none; border-top: 1px solid #e4e4e7; margin: 32px 0;">
            <p style="color: #a1a1aa; font-size: 13px; text-align: center; margin: 0;">— RouteMail Team</p>
        </div>
    </body>
    </html>
    """

# ==================== ADMIN NOTIFICATION EMAILS ====================

async def send_admin_notification(subject: str, html_content: str):
    """Send admin notification email - non-blocking, logs errors"""
    try:
        if resend.api_key:
            resend.Emails.send({
                "from": FROM_EMAIL,
                "to": [ADMIN_NOTIFICATION_EMAIL],
                "subject": subject,
                "html": html_content
            })
            logger.info(f"Admin notification sent: {subject}")
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")
        # Don't raise - admin notifications should not interrupt user flow

def get_admin_signup_notification_html(user_email: str, signup_method: str, ip_address: str = "Unknown") -> str:
    """Generate admin notification for new user signup with RouteMail branding"""
    logo_html = get_email_logo_html()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f5; margin: 0; padding: 40px 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
            {logo_html}
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #18181b; font-size: 24px; margin: 0;">🎉 New User Signup</h1>
            </div>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 24px;">A new user has registered on RouteMail.</p>
            <div style="background: #f8fafc; border-radius: 8px; padding: 20px; margin-bottom: 24px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #64748b; font-size: 14px; padding: 8px 0;">User Email:</td>
                        <td style="color: #18181b; font-size: 14px; font-weight: 600; padding: 8px 0;">{user_email}</td>
                    </tr>
                    <tr>
                        <td style="color: #64748b; font-size: 14px; padding: 8px 0;">Signup Time:</td>
                        <td style="color: #18181b; font-size: 14px; padding: 8px 0;">{timestamp}</td>
                    </tr>
                    <tr>
                        <td style="color: #64748b; font-size: 14px; padding: 8px 0;">Signup Method:</td>
                        <td style="color: #18181b; font-size: 14px; padding: 8px 0;">{signup_method}</td>
                    </tr>
                    <tr>
                        <td style="color: #64748b; font-size: 14px; padding: 8px 0;">IP Address:</td>
                        <td style="color: #18181b; font-size: 14px; padding: 8px 0;">{ip_address}</td>
                    </tr>
                </table>
            </div>
            <p style="color: #3f3f46; font-size: 14px; line-height: 1.6; margin: 0 0 16px;">
                <strong>Plan:</strong> Free Plan (free forever).
            </p>
            <p style="color: #71717a; font-size: 13px; margin: 0;">
                You can view the user in the Super Admin dashboard.
            </p>
        </div>
    </body>
    </html>
    """

def get_admin_subscription_notification_html(
    user_email: str,
    plan: str,
    currency: str,
    amount: str,
    customer_id: str,
    subscription_id: str
) -> str:
    """Generate admin notification for new paid subscription with RouteMail branding"""
    logo_html = get_email_logo_html()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #f4f4f5; margin: 0; padding: 40px 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
            {logo_html}
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #18181b; font-size: 24px; margin: 0;">💰 New Paid Subscription</h1>
            </div>
            <p style="color: #3f3f46; font-size: 16px; line-height: 1.6; margin: 0 0 24px;">A user has upgraded their plan.</p>
            <div style="background: linear-gradient(135deg, #dbeafe 0%, #ede9fe 100%); border-radius: 8px; padding: 20px; margin-bottom: 24px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="color: #475569; font-size: 14px; padding: 8px 0;">User Email:</td>
                        <td style="color: #18181b; font-size: 14px; font-weight: 600; padding: 8px 0;">{user_email}</td>
                    </tr>
                    <tr>
                        <td style="color: #475569; font-size: 14px; padding: 8px 0;">Plan:</td>
                        <td style="color: #18181b; font-size: 14px; font-weight: 600; padding: 8px 0;">{plan.capitalize()}</td>
                    </tr>
                    <tr>
                        <td style="color: #475569; font-size: 14px; padding: 8px 0;">Currency:</td>
                        <td style="color: #18181b; font-size: 14px; padding: 8px 0;">{currency.upper()}</td>
                    </tr>
                    <tr>
                        <td style="color: #475569; font-size: 14px; padding: 8px 0;">Amount Paid:</td>
                        <td style="color: #059669; font-size: 14px; font-weight: 600; padding: 8px 0;">{amount}</td>
                    </tr>
                    <tr>
                        <td style="color: #475569; font-size: 14px; padding: 8px 0;">Stripe Customer ID:</td>
                        <td style="color: #18181b; font-size: 12px; font-family: monospace; padding: 8px 0;">{customer_id}</td>
                    </tr>
                    <tr>
                        <td style="color: #475569; font-size: 14px; padding: 8px 0;">Subscription ID:</td>
                        <td style="color: #18181b; font-size: 12px; font-family: monospace; padding: 8px 0;">{subscription_id}</td>
                    </tr>
                    <tr>
                        <td style="color: #475569; font-size: 14px; padding: 8px 0;">Date:</td>
                        <td style="color: #18181b; font-size: 14px; padding: 8px 0;">{timestamp}</td>
                    </tr>
                </table>
            </div>
        </div>
    </body>
    </html>
    """

# ==================== PLAN ENFORCEMENT HELPERS ====================

async def get_effective_user_plan(user_id: str) -> dict:
    """
    Get the effective plan for a user following priority:
    1. Admin override (if active)
    2. Stripe subscription (if exists)
    3. Free plan (default)
    """
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return {"plan": "free", "source": "free", "admin_override_active": False}
    
    # Priority 1: Admin override
    if user.get("admin_override_active"):
        override_plan = user.get("admin_override_plan", "free")
        return {
            "plan": override_plan,
            "source": "admin_override",
            "admin_override_active": True,
            "admin_override_plan": override_plan,
            "admin_override_updated_at": user.get("admin_override_updated_at")
        }
    
    # Priority 2: Stripe subscription
    stripe_sub_id = user.get("stripe_subscription_id")
    if stripe_sub_id:
        plan_type = user.get("plan_type", "free")
        return {
            "plan": plan_type,
            "source": "stripe",
            "admin_override_active": False,
            "stripe_subscription_id": stripe_sub_id
        }
    
    # Priority 3: Free plan (or assigned plan_type for backward compatibility)
    plan_type = user.get("plan_type", "free")
    return {
        "plan": plan_type,
        "source": "free",
        "admin_override_active": False
    }

async def get_user_plan_limits(user_id: str) -> dict:
    """Get the plan limits for a user (with admin override applied)"""
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return PLAN_LIMITS["free"]
    
    # Use effective plan resolution
    effective = await get_effective_user_plan(user_id)
    plan_type = effective.get("plan", "free")
    base = dict(PLAN_LIMITS.get(plan_type, PLAN_LIMITS["free"]))
    
    # Per-user admin overrides — take priority over plan when set.
    override_max_accounts = user.get("admin_override_max_accounts")
    override_max_contacts = user.get("admin_override_max_contacts")
    if isinstance(override_max_accounts, int) and override_max_accounts >= 0:
        base["max_accounts"] = override_max_accounts
    if isinstance(override_max_contacts, int) and override_max_contacts >= 0:
        base["max_contacts"] = override_max_contacts
        base["max_monthly_recipients"] = override_max_contacts
    return base

async def check_account_limit(user_id: str) -> dict:
    """Check if user can add more email accounts"""
    limits = await get_user_plan_limits(user_id)
    current_count = await db.email_accounts.count_documents({"user_id": user_id})
    
    return {
        "can_add": current_count < limits["max_accounts"],
        "current": current_count,
        "limit": limits["max_accounts"],
        "remaining": max(0, limits["max_accounts"] - current_count)
    }

async def check_contact_limit(user_id: str, new_contacts: int = 0) -> dict:
    """Check if user can store more contacts"""
    limits = await get_user_plan_limits(user_id)
    
    # Count total contacts across all lists
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": None, "total": {"$sum": "$valid_emails"}}}
    ]
    result = await db.email_lists.aggregate(pipeline).to_list(1)
    current_count = result[0]["total"] if result else 0
    
    return {
        "can_add": (current_count + new_contacts) <= limits["max_contacts"],
        "current": current_count,
        "limit": limits["max_contacts"],
        "remaining": max(0, limits["max_contacts"] - current_count)
    }

async def check_recipient_limit(user_id: str, new_recipients: int = 0) -> dict:
    """Check monthly unique recipient limit"""
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return {"can_send": False, "error": "User not found"}
    
    limits = await get_user_plan_limits(user_id)
    
    # Check and reset monthly counter if needed
    last_reset = user.get("last_recipient_reset_date")
    current_count = user.get("monthly_unique_recipient_count", 0)
    
    if last_reset:
        if isinstance(last_reset, str):
            last_reset = datetime.fromisoformat(last_reset.replace('Z', '+00:00'))
        if last_reset.tzinfo is None:
            last_reset = last_reset.replace(tzinfo=timezone.utc)
        
        # Reset if 30 days have passed
        if datetime.now(timezone.utc) > last_reset + timedelta(days=30):
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "monthly_unique_recipient_count": 0,
                    "last_recipient_reset_date": datetime.now(timezone.utc).isoformat()
                }}
            )
            current_count = 0
    else:
        # Initialize reset date
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"last_recipient_reset_date": datetime.now(timezone.utc).isoformat()}}
        )
    
    return {
        "can_send": (current_count + new_recipients) <= limits["max_monthly_recipients"],
        "current": current_count,
        "limit": limits["max_monthly_recipients"],
        "remaining": max(0, limits["max_monthly_recipients"] - current_count)
    }

async def check_subscription_active(user_id: str) -> dict:
    """Check if a user can send. Free Plan is a permanent (non-expiring) tier; paid plans
    use Stripe with the standard 7-day grace period before downgrade to Free.
    """
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return {"active": False, "reason": "User not found"}
    
    # Check admin override first
    if user.get("admin_override_active"):
        override_plan = user.get("admin_override_plan", "free")
        return {
            "active": True,
            "plan": override_plan,
            "status": "admin_override",
            "source": "admin_override"
        }
    
    plan_type = user.get("plan_type") or "free"
    status = user.get("subscription_status") or "active"
    
    # Check for paid plans (Stripe)
    if plan_type in ["starter", "growth"] or plan_type.startswith("custom_"):
        if status == "active":
            return {"active": True, "plan": plan_type, "status": status, "source": "stripe"}
        elif status == "past_due":
            # Check grace period (7 days)
            grace_end = user.get("grace_period_end")
            if grace_end:
                if isinstance(grace_end, str):
                    grace_end = datetime.fromisoformat(grace_end.replace('Z', '+00:00'))
                if grace_end.tzinfo is None:
                    grace_end = grace_end.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < grace_end:
                    return {"active": True, "plan": plan_type, "status": "grace_period", "grace_ends": grace_end.isoformat(), "source": "stripe"}
            # Grace period expired → automatic downgrade to Free Plan
            await _downgrade_to_free_plan(user_id, reason="grace_expired")
            return {"active": True, "plan": "free", "status": "active", "downgraded_from": plan_type, "source": "free"}
        elif status == "canceled":
            # Check if still in billing period
            cycle_end = user.get("billing_cycle_end")
            if cycle_end:
                if isinstance(cycle_end, str):
                    cycle_end = datetime.fromisoformat(cycle_end.replace('Z', '+00:00'))
                if cycle_end.tzinfo is None:
                    cycle_end = cycle_end.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < cycle_end:
                    return {"active": True, "plan": plan_type, "status": "canceled_active", "ends": cycle_end.isoformat(), "source": "stripe"}
            # Past cycle end with canceled status → downgrade
            await _downgrade_to_free_plan(user_id, reason="canceled_cycle_ended")
            return {"active": True, "plan": "free", "status": "active", "downgraded_from": plan_type, "source": "free"}
    
    # Free Plan — no expiration. Migrate any legacy 'trialing' or 'expired' statuses on read.
    if status in ("trialing", "expired"):
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "subscription_status": "active",
                "plan_type": "free",
                "trial_ends_at": None,
            }},
        )
        status = "active"
        plan_type = "free"
    
    return {"active": True, "plan": plan_type, "status": "active", "source": "free"}


async def _downgrade_to_free_plan(user_id: str, reason: str = "expired") -> None:
    """Downgrade a paid user to the Free Plan. Preserves Stripe customer id for re-subscribing
    later, but clears the active subscription id + grace fields. Idempotent.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "plan_type": "free",
            "subscription_status": "active",
            "stripe_subscription_id": None,
            "grace_period_end": None,
            "downgraded_to_free_at": now_iso,
            "downgrade_reason": reason,
            "trial_ends_at": None,
        }},
    )

async def increment_recipient_count(user_id: str, count: int = 1):
    """Increment the monthly recipient counter"""
    await db.users.update_one(
        {"user_id": user_id},
        {"$inc": {"monthly_unique_recipient_count": count}}
    )

async def apply_permanent_plan_if_applicable(email: str, user_id: str = None) -> bool:
    """
    Check if a user has a permanently assigned plan and apply it.
    Returns True if a permanent plan was applied.
    
    These are special accounts that bypass Stripe and always have their assigned plan.
    """
    email_lower = email.lower()
    if email_lower in PERMANENT_PLAN_ASSIGNMENTS:
        assigned_plan = PERMANENT_PLAN_ASSIGNMENTS[email_lower]
        logger.info(f"Applying permanent plan '{assigned_plan}' to {email}")
        
        update_data = {
            "plan_type": assigned_plan,
            "subscription_status": "active",
            # Clear trial/grace fields since this is a permanent assignment
            "trial_ends_at": None,
            "grace_period_end": None,
        }
        
        if user_id:
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": update_data}
            )
        else:
            await db.users.update_one(
                {"email": email},
                {"$set": update_data}
            )
        return True
    return False

# ==================== MODELS ====================

class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    subscription_status: str = "active"
    subscription_expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserSession(BaseModel):
    user_id: str
    session_token: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class EmailAccount(BaseModel):
    account_id: str = Field(default_factory=lambda: f"acc_{uuid.uuid4().hex[:12]}")
    user_id: str
    account_type: str = "smtp"
    email: str
    display_name: str
    from_name: Optional[str] = None  # Default From Name for this account
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password_encrypted: Optional[str] = None
    smtp_encryption: Optional[str] = None
    # IMAP (receiving) settings — optional, required for Unibox reply tracking
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    imap_password_encrypted: Optional[str] = None
    imap_encryption: Optional[str] = None  # "ssl" | "tls" | "none"
    imap_last_sync_at: Optional[str] = None
    imap_last_error: Optional[str] = None
    imap_last_uid: Optional[int] = None  # highest IMAP UID seen, for incremental sync
    status: str = "connected"
    last_error: Optional[str] = None
    daily_limit: int = 50  # User-configurable (10-200)
    send_delay: int = 30  # Delay between emails in seconds (10-300)
    daily_send_count: int = 0
    last_send_date: Optional[str] = None
    last_reset_at: Optional[datetime] = None
    # Infrastructure module — free-form ownership label (e.g. "Client A", "Perfect
    # Digitals", "Internal"). Defaults to empty; super_admin or owner can set it.
    ownership: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class EmailList(BaseModel):
    list_id: str = Field(default_factory=lambda: f"list_{uuid.uuid4().hex[:12]}")
    user_id: str
    name: str
    original_filename: str = ""
    column_headers: List[str] = []
    total_rows: int = 0
    valid_emails: int = 0
    emails: List[Dict[str, Any]] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Campaign(BaseModel):
    campaign_id: str = Field(default_factory=lambda: f"camp_{uuid.uuid4().hex[:12]}")
    user_id: str
    name: str
    subject: str
    body: str
    body_text: Optional[str] = None
    from_name: Optional[str] = None
    list_id: Optional[str] = None
    account_ids: List[str] = []
    status: str = "draft"  # draft, scheduled, running, paused, paused_daily_limit, completed, failed
    total_emails: int = 0
    sent_count: int = 0
    failed_count: int = 0
    current_account_index: int = 0
    is_locked: bool = False  # Prevents editing when running
    scheduled_at: Optional[datetime] = None  # For scheduled campaigns
    timezone: Optional[str] = None  # User-selected timezone for the schedule
    suppression_list_ids: List[str] = []  # DNE list IDs applied to this campaign
    send_range_mode: str = "all"  # 'all' | 'range'
    send_range_start: Optional[int] = None  # 1-based inclusive
    send_range_end: Optional[int] = None    # 1-based inclusive
    add_unsubscribe_footer: bool = False  # If True, append a default unsubscribe footer at send-time
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class EmailQueueItem(BaseModel):
    queue_id: str = Field(default_factory=lambda: f"q_{uuid.uuid4().hex[:12]}")
    campaign_id: str
    user_id: str
    recipient_email: str
    recipient_data: Dict[str, Any] = {}
    assigned_account_id: Optional[str] = None
    status: str = "pending"  # pending, sent, failed
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None

# ==================== REQUEST/RESPONSE MODELS ====================

class SessionRequest(BaseModel):
    session_id: str

class EmailRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    confirm_password: str
    turnstile_token: Optional[str] = None

class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str
    turnstile_token: Optional[str] = None


# Cloudflare Turnstile server-side verification ----------------------------
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_FAIL_MESSAGE = "Security verification failed. Please try again."

async def verify_turnstile_or_raise(token: Optional[str], http_request: Optional[Request] = None) -> None:
    """Validate a Cloudflare Turnstile token server-side. Raises 400 on failure.
    
    If TURNSTILE_SECRET_KEY is unset in the environment (e.g. local dev), verification
    is skipped — useful for tests and local bring-up. In production the key MUST be set.
    """
    secret = (os.environ.get("TURNSTILE_SECRET_KEY") or "").strip()
    if not secret:
        # Not configured → skip (dev / test mode)
        return
    if not token or not token.strip():
        raise HTTPException(status_code=400, detail=TURNSTILE_FAIL_MESSAGE)
    
    remote_ip = ""
    if http_request is not None:
        try:
            xff = http_request.headers.get("x-forwarded-for", "")
            remote_ip = (xff.split(",")[0].strip() if xff else "") or (
                http_request.client.host if http_request.client else ""
            )
        except Exception:
            remote_ip = ""

    payload = {"secret": secret, "response": token.strip()}
    if remote_ip:
        payload["remoteip"] = remote_ip
    
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(TURNSTILE_VERIFY_URL, data=payload)
        data = r.json() if r.status_code == 200 else {}
    except Exception as exc:
        logger.warning(f"[TURNSTILE] verification request failed: {exc}")
        raise HTTPException(status_code=400, detail=TURNSTILE_FAIL_MESSAGE)
    
    if not data.get("success"):
        codes = data.get("error-codes", [])
        logger.warning(f"[TURNSTILE] verification failed for {http_request and http_request.client.host}: {codes}")
        raise HTTPException(status_code=400, detail=TURNSTILE_FAIL_MESSAGE)

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    confirm_password: str

class SendTestEmailRequest(BaseModel):
    test_email: EmailStr
    subject: str
    body: str
    from_name: Optional[str] = None
    account_id: Optional[str] = None  # Optional: specific account to use
    recipient_data: Optional[Dict[str, Any]] = None  # Optional: contact row to merge into {{vars}}
    # When a drip step-2+ has an empty subject, the UI passes the rendered
    # first-step subject here so the test send shows the same "Re: …"
    # threading subject the real send will produce.
    prior_subject: Optional[str] = None


class TestEmailPreviewRequest(BaseModel):
    """Read-only preview of a test email: returns rendered subject + body
    without actually sending anything. Used by the Drip Test Email modal so
    the user can verify variable substitution before clicking Send."""
    subject: str
    body: str
    recipient_data: Optional[Dict[str, Any]] = None
    prior_subject: Optional[str] = None
    variable_fallbacks: Optional[Dict[str, str]] = None

class AddSMTPAccountRequest(BaseModel):
    email: str
    display_name: str
    from_name: Optional[str] = None
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_encryption: str = "tls"
    # IMAP (optional — required for reply tracking via Unibox)
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    imap_password: Optional[str] = None
    imap_encryption: Optional[str] = None
    daily_limit: int = 50
    send_delay: int = 30  # Delay between emails in seconds (10-300)

class UpdateAccountLimitRequest(BaseModel):
    daily_limit: int

class UpdateAccountDelayRequest(BaseModel):
    send_delay: int

class UpdateSMTPAccountRequest(BaseModel):
    """Patch an existing SMTP account. Password is optional — only updated if provided."""
    email: Optional[str] = None
    display_name: Optional[str] = None
    from_name: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None  # only set if user wants to rotate credentials
    smtp_encryption: Optional[str] = None
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_username: Optional[str] = None
    imap_password: Optional[str] = None
    imap_encryption: Optional[str] = None
    daily_limit: Optional[int] = None
    send_delay: Optional[int] = None

class TestSMTPRequest(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_encryption: str = "tls"

class CreateListRequest(BaseModel):
    name: str
    original_filename: str
    column_headers: List[str]
    emails: List[Dict[str, Any]]

class UpdateListRequest(BaseModel):
    name: str

class UpdateListRecordRequest(BaseModel):
    """Payload for editing a single contact/record inside an email list."""
    original_email: str  # the current email value (used to locate the row)
    data: Dict[str, Any]  # full new row, e.g. {"email":"...","name":"...","company":"..."}

class AddListRecordRequest(BaseModel):
    """Payload for adding a single new contact to an email list."""
    data: Dict[str, Any]  # at minimum must contain 'email'

class DeleteListRecordRequest(BaseModel):
    email: str

# ==================== BLOG MODELS ====================

class Blog(BaseModel):
    blog_id: str = Field(default_factory=lambda: f"blog_{uuid.uuid4().hex[:12]}")
    slug: str
    title: str
    excerpt: Optional[str] = ""
    content: str
    featured_image_url: Optional[str] = None
    author: str = "RouteMail Team"
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    status: str = "draft"  # draft | published
    published_at: Optional[datetime] = None
    created_by: str  # user_id of super_admin
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CreateBlogRequest(BaseModel):
    title: str
    slug: Optional[str] = None
    excerpt: Optional[str] = ""
    content: str
    featured_image_url: Optional[str] = None
    author: Optional[str] = "RouteMail Team"
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    status: str = "draft"

class UpdateBlogRequest(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    featured_image_url: Optional[str] = None
    author: Optional[str] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    status: Optional[str] = None

class CreateCampaignRequest(BaseModel):
    name: str
    subject: str
    body: str
    body_text: Optional[str] = None
    from_name: Optional[str] = None
    list_id: Optional[str] = None
    account_ids: List[str] = []
    scheduled_at: Optional[str] = None  # ISO datetime string for scheduled sends
    timezone: Optional[str] = None  # User's selected timezone
    suppression_list_ids: List[str] = []  # DNE list IDs to exclude
    send_range_mode: Optional[str] = "all"  # 'all' | 'range'
    send_range_start: Optional[int] = None
    send_range_end: Optional[int] = None
    add_unsubscribe_footer: Optional[bool] = False
    # Phase-2 additions
    folder_id: Optional[str] = None  # Brand / Responses folder this campaign belongs to
    variable_fallbacks: Optional[Dict[str, str]] = None

class UpdateCampaignRequest(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    body_text: Optional[str] = None
    from_name: Optional[str] = None
    list_id: Optional[str] = None
    account_ids: Optional[List[str]] = None
    scheduled_at: Optional[str] = None  # ISO datetime string for scheduled sends
    timezone: Optional[str] = None  # User's selected timezone
    suppression_list_ids: Optional[List[str]] = None
    send_range_mode: Optional[str] = None
    send_range_start: Optional[int] = None
    send_range_end: Optional[int] = None
    add_unsubscribe_footer: Optional[bool] = None
    folder_id: Optional[str] = None
    variable_fallbacks: Optional[Dict[str, str]] = None

class AddToSuppressionRequest(BaseModel):
    email: str

# ==================== DRIP CAMPAIGN MODELS ====================

class DripStep(BaseModel):
    """One step in a drip sequence"""
    step_number: int  # 1, 2, 3...
    subject: str
    body: str
    body_text: Optional[str] = None
    delay_days: int = 0  # days after previous step (0 for first step)
    delay_hours: int = 0  # hours after previous step

class DripScheduleSettings(BaseModel):
    timezone: str = "UTC"
    sending_days: List[int] = [0, 1, 2, 3, 4]  # 0=Monday, 6=Sunday
    start_time: str = "09:00"
    end_time: str = "18:00"
    randomize_time: bool = False
    # Optional one-shot calendar date when the campaign should *begin* (in `timezone`).
    # Stored as an ISO date string ("YYYY-MM-DD") or None. When set, the drip worker
    # will treat the campaign as not-yet-due until that local date arrives.
    start_date: Optional[str] = None

class CreateDripCampaignRequest(BaseModel):
    name: str
    from_name: Optional[str] = None
    account_ids: List[str] = []
    steps: List[DripStep] = []
    schedule: DripScheduleSettings = DripScheduleSettings()
    stop_on_reply: bool = True
    stop_on_bounce: bool = True
    suppression_list_ids: List[str] = []
    # Phase-2 additions
    folder_id: Optional[str] = None
    variable_fallbacks: Optional[Dict[str, str]] = None

class UpdateDripCampaignRequest(BaseModel):
    name: Optional[str] = None
    from_name: Optional[str] = None
    account_ids: Optional[List[str]] = None
    steps: Optional[List[DripStep]] = None
    schedule: Optional[DripScheduleSettings] = None
    stop_on_reply: Optional[bool] = None
    stop_on_bounce: Optional[bool] = None
    suppression_list_ids: Optional[List[str]] = None
    folder_id: Optional[str] = None
    variable_fallbacks: Optional[Dict[str, str]] = None

class AddDripContactsRequest(BaseModel):
    list_id: str
    send_range_mode: Optional[str] = "all"  # 'all' | 'range'
    send_range_start: Optional[int] = None  # 1-based inclusive
    send_range_end: Optional[int] = None    # 1-based inclusive

# ==================== DO NOT EMAIL (DNE / SUPPRESSION) MODELS ====================

class DNEList(BaseModel):
    list_id: str = Field(default_factory=lambda: f"dne_{uuid.uuid4().hex[:12]}")
    user_id: str
    name: str
    is_global: bool = False
    email_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CreateDNEListRequest(BaseModel):
    name: str

class AddDNEEmailsRequest(BaseModel):
    # Either a list of raw values (emails or domains, auto-detected)…
    emails: List[str] = []
    # …or a typed list of {type:'email'|'domain', value:'...'}
    entries: Optional[List[Dict[str, str]]] = None

class RemoveDNEEmailRequest(BaseModel):
    email: str  # holds either the email address or the bare domain to remove

# ==================== AUTH HELPERS ====================

async def get_current_user(request: Request) -> User:
    """Get current user from session token in cookie or header"""
    session_token = request.cookies.get("session_token")
    
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session_doc = await db.user_sessions.find_one(
        {"session_token": session_token},
        {"_id": 0}
    )
    
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    
    user_doc = await db.users.find_one(
        {"user_id": session_doc["user_id"]},
        {"_id": 0}
    )
    
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    
    return User(**user_doc)

# ==================== AUTH ENDPOINTS ====================

# Phase: Google OAuth removed (Batch 1). Historical `/auth/session` endpoint
# deleted; users on `provider=='google'` are flagged in /auth/me with
# `password_setup_required=True` and must POST to /auth/set-initial-password
# to convert to email/password before they can authenticate further.

@api_router.get("/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    # Get full user data including role and subscription
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    if user_doc:
        # Check subscription status
        sub_status = await check_subscription_active(user.user_id)
        
        return {
            "user_id": user_doc["user_id"],
            "email": user_doc["email"],
            "name": user_doc.get("name", ""),
            "picture": user_doc.get("picture"),
            "subscription_status": user_doc.get("subscription_status", "active"),
            "plan_type": user_doc.get("plan_type", "free"),
            "role": user_doc.get("role", "user"),
            "can_manage_blogs": bool(user_doc.get("can_manage_blogs", False)),
            "can_access_infrastructure": bool(user_doc.get("can_access_infrastructure", False)),
            "trial_ends_at": None,
            "billing_cycle_end": user_doc.get("billing_cycle_end"),
            "downgraded_to_free_at": user_doc.get("downgraded_to_free_at"),
            "downgrade_reason": user_doc.get("downgrade_reason"),
            "subscription_active": sub_status.get("active", False),
            "onboarding_completed": user_doc.get("onboarding_completed", False),
            # Phase Batch-1 — flag legacy Google users so the frontend can
            # surface the forced "set password" screen on their next login.
            "password_setup_required": (
                user_doc.get("provider") == "google" or not user_doc.get("password_hash")
            ),
        }
    return user.model_dump()

@api_router.post("/auth/set-initial-password")
async def set_initial_password(payload: Dict[str, Any] = Body(...), user: User = Depends(get_current_user)):
    """Forced password setup for legacy Google-OAuth users (Batch 1).

    Body: {password: str, confirm_password: str}
    On success the user becomes a standard email/password user and the
    `password_setup_required` flag flips off.
    """
    password = (payload.get("password") or "").strip()
    confirm = (payload.get("confirm_password") or "").strip()
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    if password != confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    # Only allow on accounts that don't already have a usable password
    if user_doc.get("password_hash") and user_doc.get("provider") != "google":
        raise HTTPException(status_code=400, detail="Password already set")
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    await db.users.update_one(
        {"user_id": user.user_id},
        {
            "$set": {
                "password_hash": hashed,
                "provider": "email",
                "password_set_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    return {"ok": True, "message": "Password set — you can now log in with email + password."}


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie(key="session_token", path="/", secure=True, samesite="none")
    return {"message": "Logged out"}

@api_router.post("/auth/onboarding-complete")
async def complete_onboarding(user: User = Depends(get_current_user)):
    """Mark user's onboarding as completed"""
    await db.users.update_one(
        {"user_id": user.user_id},
        {"$set": {"onboarding_completed": True}}
    )
    return {"message": "Onboarding completed", "onboarding_completed": True}

# ==================== EMAIL/PASSWORD AUTH ====================

@api_router.post("/auth/register")
async def register_email(request: EmailRegisterRequest, http_request: Request, background_tasks: BackgroundTasks):
    """Register a new user with email and password - requires email verification"""
    # Cloudflare Turnstile gate
    await verify_turnstile_or_raise(request.turnstile_token, http_request)

    # ========== STEP 1: Validate Input ==========
    logger.info(f"[REGISTRATION] Step 1: Validating input for email: {request.email}")
    
    if request.password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    # ========== STEP 2: Check Existing User ==========
    logger.info(f"[REGISTRATION] Step 2: Checking if user exists: {request.email}")
    
    existing_user = await db.users.find_one({"email": request.email}, {"_id": 0})
    if existing_user:
        if existing_user.get("provider") == "google":
            # Legacy Google-OAuth user — allow them to set a password during
            # registration (effectively "claim" the account).
            raise HTTPException(
                status_code=400,
                detail="This email exists from a previous Google login. Use 'Forgot Password' to set a new password.",
            )
        # Check if unverified account that expired (>2 hours old)
        if not existing_user.get("email_verified", False):
            created_at = existing_user.get("created_at")
            if created_at:
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > created_at + timedelta(hours=2):
                    # Delete expired unverified account
                    logger.info(f"[REGISTRATION] Deleting expired unverified account: {request.email}")
                    await db.users.delete_one({"email": request.email})
                else:
                    raise HTTPException(status_code=400, detail="Please check your email to verify your account. Check spam folder too.")
            else:
                raise HTTPException(status_code=400, detail="Email already registered")
        else:
            raise HTTPException(status_code=400, detail="Email already registered")
    
    # ========== STEP 3: Generate UUID Token ==========
    logger.info(f"[REGISTRATION] Step 3: Generating UUID verification token for: {request.email}")
    
    # Use UUID for consistent, URL-safe token format (no special chars at start)
    verification_token = str(uuid.uuid4())
    verification_expires = datetime.now(timezone.utc) + timedelta(hours=2)
    
    # Log full token (UUID format is safe to log)
    logger.info(f"[REGISTRATION] Generated UUID token: {verification_token}")
    logger.info("[REGISTRATION] Token format: UUID (36 chars with hyphens)")
    
    # ========== STEP 4: Prepare User Document ==========
    logger.info(f"[REGISTRATION] Step 4: Preparing user document for: {request.email}")
    
    password_hash = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    role = "super_admin" if request.email == SUPER_ADMIN_EMAIL else "user"

    user_doc = {
        "user_id": user_id,
        "email": request.email,
        "name": request.name,
        "picture": None,
        "password_hash": password_hash,
        "provider": "email",
        "role": role,
        # Email verification - token stored HERE
        "email_verified": False,
        "verification_token": verification_token,  # SAME token that will be emailed
        "verification_expires": verification_expires.isoformat(),
        # Subscription fields — Free Plan, no expiry
        "plan_type": "free",
        "subscription_status": "active",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "trial_ends_at": None,
        "billing_cycle_start": None,
        "billing_cycle_end": None,
        "grace_period_end": None,
        "monthly_unique_recipient_count": 0,
        "last_recipient_reset_date": datetime.now(timezone.utc).isoformat(),
        "onboarding_completed": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # ========== STEP 5: Save User to Database ==========
    logger.info(f"[REGISTRATION] Step 5: Saving user to database: {request.email}")
    
    try:
        await db.users.insert_one(user_doc)
        logger.info(f"[REGISTRATION] User saved successfully: {request.email}, user_id: {user_id}")
    except Exception as e:
        logger.error(f"[REGISTRATION] FAILED to save user {request.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create account. Please try again.")
    
    # ========== STEP 6: Verify Token Was Saved Correctly ==========
    logger.info(f"[REGISTRATION] Step 6: Verifying token was saved for: {request.email}")
    
    saved_user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "verification_token": 1})
    if saved_user:
        saved_token = saved_user.get("verification_token")
        if saved_token == verification_token:
            logger.info(f"[REGISTRATION] Token verified in DB matches generated token for: {request.email}")
        else:
            logger.error(f"[REGISTRATION] TOKEN MISMATCH! Generated: {verification_token[:20]}..., Saved: {saved_token[:20] if saved_token else 'None'}...")
    else:
        logger.error(f"[REGISTRATION] Could not verify saved user: {request.email}")
    
    # ========== STEP 7: Build Verification Link (using SAME token) ==========
    logger.info(f"[REGISTRATION] Step 7: Building verification link for: {request.email}")
    
    verification_link = f"{FRONTEND_URL}/verify-email?token={verification_token}"
    logger.info(f"[REGISTRATION] Verification link: {verification_link}")
    logger.info(f"[REGISTRATION] Token in link (first 20 chars): {verification_token[:20]}...")
    
    # ========== STEP 8: Queue Email (Background Task) ==========
    logger.info(f"[REGISTRATION] Step 8: Queueing verification email for: {request.email}")
    
    try:
        first_name = request.name.split()[0] if request.name else "there"
        html_content = get_verification_email_html(first_name, verification_link)
        
        # Add to background tasks - email will be sent after response is returned
        background_tasks.add_task(
            send_email_async,
            request.email,
            "Verify Your RouteMail Account",
            html_content
        )
        logger.info(f"[REGISTRATION] Verification email queued for: {request.email}")
    except Exception as e:
        logger.error(f"[REGISTRATION] Failed to queue verification email for {request.email}: {str(e)}")
        # Don't fail registration - user is already created
    
    # ========== STEP 9: Apply Permanent Plan (Optional, Non-blocking) ==========
    try:
        await apply_permanent_plan_if_applicable(request.email, user_id)
    except Exception as e:
        logger.error(f"[REGISTRATION] Failed to apply permanent plan for {request.email}: {str(e)}")
    
    # ========== STEP 10: Queue Admin Notification (Optional, Non-blocking) ==========
    try:
        admin_html = get_admin_signup_notification_html(request.email, "Email + Password")
        background_tasks.add_task(
            send_admin_notification,
            "New User Signup on RouteMail",
            admin_html
        )
    except Exception as e:
        logger.error(f"[REGISTRATION] Failed to queue admin notification for {request.email}: {str(e)}")
    
    # ========== STEP 11: Return Success Response ==========
    logger.info(f"[REGISTRATION] Step 11: Returning success response for: {request.email}")
    
    response_data = {
        "success": True,
        "message": "Registration successful! Please check your email to verify your account.",
        "email": request.email,
        "requires_verification": True
    }
    
    logger.info(f"[REGISTRATION] COMPLETE for {request.email}. Response: {response_data}")
    
    return JSONResponse(
        status_code=201,
        content=response_data
    )

@api_router.get("/auth/verify-email")
async def verify_email(token: str, response: Response, background_tasks: BackgroundTasks):
    """Verify email address with UUID token"""
    
    # ========== STEP 1: Log Received Token ==========
    logger.info("[VERIFICATION] Step 1: Token received")
    logger.info(f"[VERIFICATION] Token value: {token}")
    logger.info(f"[VERIFICATION] Token length: {len(token) if token else 0}")
    
    # ========== STEP 2: Validate Token Format ==========
    if not token or len(token) < 32:
        logger.warning("[VERIFICATION] Step 2: INVALID - Token too short or empty")
        raise HTTPException(status_code=400, detail="Invalid verification link.")
    
    # Clean token (strip whitespace, trailing slashes)
    clean_token = token.strip().rstrip('/').rstrip('?').rstrip('&')
    if clean_token != token:
        logger.info(f"[VERIFICATION] Token cleaned: '{token}' -> '{clean_token}'")
        token = clean_token
    
    logger.info("[VERIFICATION] Step 2: Token validated")
    
    # ========== STEP 3: Find User by Token (Direct Lookup) ==========
    logger.info(f"[VERIFICATION] Step 3: Searching for user with token: {token}")
    
    user = await db.users.find_one({"verification_token": token}, {"_id": 0})
    
    if not user:
        logger.warning(f"[VERIFICATION] Step 3: FAILED - No user found with token: {token}")
        
        # Debug: Count unverified users
        unverified_count = await db.users.count_documents({"email_verified": False, "provider": "email"})
        logger.info(f"[VERIFICATION] Debug: Total unverified email users: {unverified_count}")
        
        raise HTTPException(status_code=400, detail="Invalid verification link. The link may have already been used or expired.")
    
    logger.info(f"[VERIFICATION] Step 3: Found user: {user['email']}")
    logger.info(f"[VERIFICATION] User's stored token: {user.get('verification_token')}")
    
    # ========== STEP 4: Check If Already Verified ==========
    if user.get("email_verified", False):
        logger.info(f"[VERIFICATION] Step 4: User {user['email']} is already verified")
        
        # Clear any remaining token
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$unset": {"verification_token": "", "verification_expires": ""}}
        )
        
        return {
            "success": True,
            "message": "Email already verified!",
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user.get("name"),
            "plan_type": user.get("plan_type", "free"),
            "verified": True,
            "redirect_url": f"{FRONTEND_URL}/dashboard"
        }
    
    # ========== STEP 5: Check Token Expiration ==========
    logger.info("[VERIFICATION] Step 5: Checking token expiration...")
    
    expires = user.get("verification_expires")
    if expires:
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires.replace('Z', '+00:00'))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        
        now = datetime.now(timezone.utc)
        logger.info(f"[VERIFICATION] Token expires: {expires.isoformat()}")
        logger.info(f"[VERIFICATION] Current time: {now.isoformat()}")
        
        if now > expires:
            logger.warning(f"[VERIFICATION] Step 5: EXPIRED - Token expired for {user['email']}")
            
            # Delete expired user
            await db.users.delete_one({"user_id": user["user_id"]})
            logger.info(f"[VERIFICATION] Deleted expired unverified user: {user['email']}")
            
            raise HTTPException(status_code=400, detail="Verification link has expired. Please register again.")
    
    logger.info("[VERIFICATION] Step 5: Token is valid and not expired")
    
    # ========== STEP 6: Verify Email (Atomic Update) ==========
    logger.info(f"[VERIFICATION] Step 6: Marking email as verified for: {user['email']}")
    
    result = await db.users.update_one(
        {"user_id": user["user_id"], "verification_token": token},  # Ensure token still matches
        {
            "$set": {"email_verified": True},
            "$unset": {"verification_token": "", "verification_expires": ""}
        }
    )
    
    if result.modified_count == 0:
        logger.warning(f"[VERIFICATION] Step 6: FAILED - Token already consumed for {user['email']}")
        raise HTTPException(status_code=400, detail="Invalid verification link. The link may have already been used.")
    
    logger.info(f"[VERIFICATION] Step 6: SUCCESS - Email verified for: {user['email']}")
    
    # ========== STEP 7: Get Updated User Data ==========
    updated_user = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    plan_type = updated_user.get("plan_type", "free") if updated_user else "free"
    
    # ========== STEP 8: Send Welcome Email ==========
    logger.info(f"[VERIFICATION] Step 8: Queueing welcome email for: {user['email']}")
    
    try:
        first_name = user.get("name", "").split()[0] if user.get("name") else "there"
        subject, html_content = get_welcome_email_html(first_name, plan_type)
        
        background_tasks.add_task(
            send_email_async,
            user["email"],
            subject,
            html_content
        )
    except Exception as e:
        logger.error(f"[VERIFICATION] Failed to queue welcome email: {str(e)}")
    
    # ========== STEP 9: Create Session ==========
    logger.info(f"[VERIFICATION] Step 9: Creating session for: {user['email']}")
    
    session_token = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    session_doc = {
        "user_id": user["user_id"],
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    # Set cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60
    )
    
    # ========== STEP 10: Return Success ==========
    response_data = {
        "success": True,
        "message": "Email verified successfully!",
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name"),
        "plan_type": plan_type,
        "verified": True,
        "redirect_url": f"{FRONTEND_URL}/dashboard"
    }
    
    logger.info(f"[VERIFICATION] Step 10: COMPLETE for {user['email']}. Redirecting to dashboard.")
    
    return response_data

@api_router.post("/auth/resend-verification")
async def resend_verification(email: EmailStr, background_tasks: BackgroundTasks):
    """Resend verification email"""
    logger.info(f"[RESEND] Resend verification requested for: {email}")
    
    user = await db.users.find_one({"email": email}, {"_id": 0})
    
    if not user:
        logger.info(f"[RESEND] User not found: {email}")
        # Don't reveal if email exists
        return {"message": "If this email is registered, you will receive a verification link."}
    
    if user.get("email_verified", False):
        logger.info(f"[RESEND] User already verified: {email}")
        raise HTTPException(status_code=400, detail="Email is already verified")

    # (Google OAuth removed — Batch 1)

    # Generate new UUID verification token
    verification_token = str(uuid.uuid4())
    verification_expires = datetime.now(timezone.utc) + timedelta(hours=2)
    
    logger.info(f"[RESEND] Generated new UUID token for {email}: {verification_token}")
    
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "verification_token": verification_token,
                "verification_expires": verification_expires.isoformat()
            }
        }
    )
    
    logger.info(f"[RESEND] Token saved to DB for: {email}")
    
    # Send verification email
    first_name = user.get("name", "").split()[0] if user.get("name") else "there"
    verification_link = f"{FRONTEND_URL}/verify-email?token={verification_token}"
    logger.info(f"[RESEND] Verification link: {verification_link}")
    
    html_content = get_verification_email_html(first_name, verification_link)
    
    background_tasks.add_task(
        send_email_async,
        email,
        "Verify Your RouteMail Account",
        html_content
    )
    
    return {"message": "If this email is registered, you will receive a verification link."}

@api_router.post("/auth/login")
async def login_email(request: EmailLoginRequest, http_request: Request, response: Response):
    """Login with email and password"""
    # Cloudflare Turnstile gate
    await verify_turnstile_or_raise(request.turnstile_token, http_request)
    # Find user
    user_doc = await db.users.find_one({"email": request.email}, {"_id": 0})
    
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Check if user is a legacy Google user without a password yet — block
    # login until they convert via /auth/set-initial-password.
    if user_doc.get("provider") == "google" or not user_doc.get("password_hash"):
        raise HTTPException(
            status_code=401,
            detail="This account was migrated from Google sign-in. Use 'Forgot Password' to set a new password and continue.",
        )
    
    # Check if email is verified
    if not user_doc.get("email_verified", False):
        raise HTTPException(status_code=401, detail="Please verify your email before logging in. Check your inbox or spam folder.")
    
    # Verify password
    if not bcrypt.checkpw(request.password.encode('utf-8'), user_doc["password_hash"].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Apply permanent plan assignment if applicable (ensure plan is always correct)
    await apply_permanent_plan_if_applicable(request.email, user_doc["user_id"])
    
    # Create session
    session_token = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    session_doc = {
        "user_id": user_doc["user_id"],
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.user_sessions.insert_one(session_doc)
    
    # Set cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60
    )
    
    # Get updated user data (may have permanent plan applied)
    updated_user = await db.users.find_one({"user_id": user_doc["user_id"]}, {"_id": 0})
    
    return {
        "user_id": updated_user["user_id"],
        "email": updated_user["email"],
        "name": updated_user.get("name", ""),
        "picture": updated_user.get("picture"),
        "subscription_status": updated_user.get("subscription_status", "active"),
        "plan_type": updated_user.get("plan_type", "free"),
        "role": updated_user.get("role", "user")
    }

# ==================== FORGOT PASSWORD ====================

@api_router.post("/auth/forgot-password")
async def forgot_password(request: ForgotPasswordRequest, background_tasks: BackgroundTasks):
    """Request password reset - rate limited to 3 attempts per hour"""
    email = request.email.lower()
    
    # Check rate limit (3 attempts per hour)
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_attempts = await db.password_reset_attempts.count_documents({
        "email": email,
        "created_at": {"$gte": one_hour_ago.isoformat()}
    })
    
    if recent_attempts >= 3:
        # Don't reveal rate limit - just return success
        return {"message": "If this email exists, you will receive a password reset link."}
    
    # Log the attempt
    await db.password_reset_attempts.insert_one({
        "email": email,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Find user (don't reveal if email exists). Legacy Google users CAN use
    # forgot-password — that's exactly how they're expected to convert.
    user = await db.users.find_one({"email": email}, {"_id": 0})

    if not user:
        # Don't reveal if email doesn't exist
        return {"message": "If this email exists, you will receive a password reset link."}
    
    # Generate reset token
    reset_token = secrets.token_urlsafe(32)
    reset_expires = datetime.now(timezone.utc) + timedelta(minutes=30)
    
    # Store reset token
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "reset_token": reset_token,
                "reset_expires": reset_expires.isoformat()
            }
        }
    )
    
    # Send reset email in background
    reset_link = f"{FRONTEND_URL}/reset-password?token={reset_token}"
    logger.info(f"Password reset link for {email}: {reset_link}")
    html_content = get_password_reset_email_html(reset_link)
    
    background_tasks.add_task(
        send_email_async,
        email,
        "Reset Your RouteMail Password",
        html_content
    )
    
    return {"message": "If this email exists, you will receive a password reset link."}

@api_router.post("/auth/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """Reset password with token"""
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    # Find user with this token
    user = await db.users.find_one({"reset_token": request.token}, {"_id": 0})
    
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    
    # Check if token expired
    expires = user.get("reset_expires")
    if expires:
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires.replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > expires:
            raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")
    
    # Hash new password
    password_hash = bcrypt.hashpw(request.new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Update password and clear reset token
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {
            "$set": {"password_hash": password_hash},
            "$unset": {"reset_token": "", "reset_expires": ""}
        }
    )
    
    # Invalidate all existing sessions for security
    await db.user_sessions.delete_many({"user_id": user["user_id"]})
    
    return {"message": "Password reset successfully. Please login with your new password."}

# ==================== EMAIL ACCOUNT ENDPOINTS ====================

@api_router.get("/accounts")
async def get_email_accounts(user: User = Depends(get_current_user)):
    """Get all connected email accounts"""
    accounts = await db.email_accounts.find(
        {"user_id": user.user_id},
        {"_id": 0, "smtp_password_encrypted": 0, "imap_password_encrypted": 0}
    ).to_list(10000)
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # Bulk-fetch today's warmup stats so the UI can show combined totals
    account_ids = [acc.get("account_id") for acc in accounts]
    warmup_stats_today = {
        s["account_id"]: s
        async for s in db.warmup_stats.find(
            {"account_id": {"$in": account_ids}, "date": today},
            {"_id": 0, "account_id": 1, "emails_sent": 1, "replies_sent": 1},
        )
    }
    for acc in accounts:
        if acc.get("last_send_date") != today:
            acc["daily_send_count"] = 0
        ws = warmup_stats_today.get(acc.get("account_id"))
        acc["warmup_emails_sent_today"] = ws.get("emails_sent", 0) if ws else 0
        acc["warmup_replies_today"] = ws.get("replies_sent", 0) if ws else 0
    
    # Add limit info
    account_limit = await check_account_limit(user.user_id)
    
    return {
        "accounts": accounts,
        "limit_info": account_limit
    }

@api_router.post("/accounts/smtp")
async def add_smtp_account(request: AddSMTPAccountRequest, user: User = Depends(get_current_user)):
    """Add a new SMTP email account"""
    # Check subscription is active
    sub_status = await check_subscription_active(user.user_id)
    if not sub_status.get("active"):
        raise HTTPException(status_code=403, detail=f"Subscription required: {sub_status.get('reason', 'Inactive subscription')}")
    
    # Check account limit
    account_limit = await check_account_limit(user.user_id)
    if not account_limit["can_add"]:
        raise HTTPException(
            status_code=403, 
            detail=f"Account limit reached. Your plan allows {account_limit['limit']} accounts. Please upgrade to add more."
        )
    
    existing = await db.email_accounts.find_one(
        {"user_id": user.user_id, "email": request.email},
        {"_id": 0}
    )
    
    if existing:
        raise HTTPException(status_code=400, detail="Email account already connected")
    
    test_result = await test_smtp_connection(
        request.smtp_host, request.smtp_port, request.smtp_username,
        request.smtp_password, request.smtp_encryption
    )
    
    if not test_result["success"]:
        raise HTTPException(status_code=400, detail=f"SMTP connection failed: {test_result['error']}")
    
    # Validate daily limit (>=1, no upper cap so users can configure freely)
    try:
        daily_limit = max(1, int(request.daily_limit))
    except (TypeError, ValueError):
        daily_limit = 50
    
    # Validate send delay (10-300 seconds)
    send_delay = max(10, min(300, request.send_delay))
    
    encrypted_password = encrypt_data(request.smtp_password)
    encrypted_imap_password = encrypt_data(request.imap_password) if request.imap_password else None
    
    account = EmailAccount(
        user_id=user.user_id,
        account_type="smtp",
        email=request.email,
        display_name=request.display_name,
        from_name=(request.from_name or request.display_name),
        smtp_host=request.smtp_host,
        smtp_port=request.smtp_port,
        smtp_username=request.smtp_username,
        smtp_password_encrypted=encrypted_password,
        smtp_encryption=request.smtp_encryption,
        imap_host=request.imap_host,
        imap_port=request.imap_port,
        imap_username=request.imap_username,
        imap_password_encrypted=encrypted_imap_password,
        imap_encryption=request.imap_encryption,
        daily_limit=daily_limit,
        send_delay=send_delay,
        status="connected",
        last_reset_at=datetime.now(timezone.utc)
    )
    
    acc_dict = account.model_dump()
    acc_dict["created_at"] = acc_dict["created_at"].isoformat()
    acc_dict["last_reset_at"] = acc_dict["last_reset_at"].isoformat()
    await db.email_accounts.insert_one(acc_dict)

    # Batch-1 auto-detection — silently create / update the tracked domain.
    try:
        from infra_phase_a import ensure_domain_record
        await ensure_domain_record(db, user.user_id, account.email)
    except Exception as e:
        logger.warning(f"[DOMAIN_AUTO_DETECT] failed for {account.email}: {e}")

    return {
        "account_id": account.account_id, 
        "email": account.email, 
        "status": "connected",
        "daily_limit": daily_limit,
        "message": "SMTP account connected successfully"
    }

@api_router.put("/accounts/{account_id}/limit")
async def update_account_limit(account_id: str, request: UpdateAccountLimitRequest, user: User = Depends(get_current_user)):
    """Update daily sending limit for an account (>=1, no upper cap)"""
    try:
        daily_limit = max(1, int(request.daily_limit))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="daily_limit must be a positive integer")
    
    result = await db.email_accounts.update_one(
        {"account_id": account_id, "user_id": user.user_id},
        {"$set": {"daily_limit": daily_limit}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return {"message": "Daily limit updated", "daily_limit": daily_limit}

@api_router.put("/accounts/{account_id}/delay")
async def update_account_delay(account_id: str, request: UpdateAccountDelayRequest, user: User = Depends(get_current_user)):
    """Update sending delay between emails for an account"""
    # Validate delay (10-300 seconds)
    send_delay = max(10, min(300, request.send_delay))
    
    result = await db.email_accounts.update_one(
        {"account_id": account_id, "user_id": user.user_id},
        {"$set": {"send_delay": send_delay}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return {"message": "Sending delay updated", "send_delay": send_delay}


@api_router.put("/accounts/{account_id}/ownership")
async def update_account_ownership(
    account_id: str,
    payload: dict,
    user: User = Depends(get_current_user),
):
    """Tag an inbox with an "Ownership" label (e.g. Client A, Perfect Digitals,
    Internal). Used by the Infrastructure module to group/filter inboxes. Any
    authenticated user can label their own accounts; super_admin can label any.

    Body: { "ownership": "<label or empty string to clear>" }
    """
    ownership = payload.get("ownership")
    if ownership is not None and not isinstance(ownership, str):
        raise HTTPException(status_code=400, detail="ownership must be a string")
    ownership = (ownership or "").strip()[:120]

    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    query = {"account_id": account_id}
    if (user_doc or {}).get("role") != "super_admin":
        query["user_id"] = user.user_id

    result = await db.email_accounts.update_one(query, {"$set": {"ownership": ownership}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")

    return {"message": "Ownership updated", "ownership": ownership}

# ==================== WARMUP ENDPOINTS ====================

class WarmupSettingsRequest(BaseModel):
    starting_emails_per_day: int = 5
    max_emails_per_day: int = 50
    daily_increment: int = 5
    reply_rate: int = 40  # Percentage (30-50%)

@api_router.post("/accounts/{account_id}/warmup/enable")
async def enable_warmup(account_id: str, settings: WarmupSettingsRequest, user: User = Depends(get_current_user)):
    """Enable warmup for an email account"""
    # Validate settings
    starting = max(1, min(20, settings.starting_emails_per_day))
    max_emails = max(10, min(100, settings.max_emails_per_day))
    increment = max(1, min(10, settings.daily_increment))
    reply_rate = max(30, min(50, settings.reply_rate))
    
    # Check account exists
    account = await db.email_accounts.find_one(
        {"account_id": account_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Update account with warmup settings
    await db.email_accounts.update_one(
        {"account_id": account_id, "user_id": user.user_id},
        {"$set": {
            "warmup_enabled": True,
            "warmup_status": "active",
            "warmup_day": 1,
            "warmup_started_at": datetime.now(timezone.utc).isoformat(),
            "warmup_settings": {
                "starting_emails_per_day": starting,
                "max_emails_per_day": max_emails,
                "daily_increment": increment,
                "reply_rate": reply_rate
            }
        }}
    )
    
    logger.info(f"[WARMUP] Enabled warmup for account {account.get('email')} by user {user.email}")
    
    return {
        "success": True,
        "message": "Warmup enabled successfully",
        "warmup_status": "active",
        "settings": {
            "starting_emails_per_day": starting,
            "max_emails_per_day": max_emails,
            "daily_increment": increment,
            "reply_rate": reply_rate
        }
    }

@api_router.post("/accounts/{account_id}/warmup/disable")
async def disable_warmup(account_id: str, user: User = Depends(get_current_user)):
    """Disable warmup for an email account"""
    result = await db.email_accounts.update_one(
        {"account_id": account_id, "user_id": user.user_id},
        {"$set": {
            "warmup_enabled": False,
            "warmup_status": "disabled"
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")
    
    logger.info(f"[WARMUP] Disabled warmup for account {account_id} by user {user.email}")
    
    return {"success": True, "message": "Warmup disabled", "warmup_status": "disabled"}

@api_router.post("/accounts/{account_id}/warmup/pause")
async def pause_warmup(account_id: str, user: User = Depends(get_current_user)):
    """Pause warmup for an email account"""
    result = await db.email_accounts.update_one(
        {"account_id": account_id, "user_id": user.user_id, "warmup_enabled": True},
        {"$set": {"warmup_status": "paused"}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Account not found or warmup not enabled")
    
    return {"success": True, "message": "Warmup paused", "warmup_status": "paused"}

@api_router.post("/accounts/{account_id}/warmup/resume")
async def resume_warmup(account_id: str, user: User = Depends(get_current_user)):
    """Resume warmup for an email account"""
    result = await db.email_accounts.update_one(
        {"account_id": account_id, "user_id": user.user_id, "warmup_enabled": True},
        {"$set": {"warmup_status": "active"}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Account not found or warmup not enabled")
    
    return {"success": True, "message": "Warmup resumed", "warmup_status": "active"}

@api_router.put("/accounts/{account_id}/warmup/settings")
async def update_warmup_settings(account_id: str, settings: WarmupSettingsRequest, user: User = Depends(get_current_user)):
    """Update warmup settings for an email account"""
    # Validate settings
    starting = max(1, min(20, settings.starting_emails_per_day))
    max_emails = max(10, min(100, settings.max_emails_per_day))
    increment = max(1, min(10, settings.daily_increment))
    reply_rate = max(30, min(50, settings.reply_rate))
    
    result = await db.email_accounts.update_one(
        {"account_id": account_id, "user_id": user.user_id},
        {"$set": {
            "warmup_settings": {
                "starting_emails_per_day": starting,
                "max_emails_per_day": max_emails,
                "daily_increment": increment,
                "reply_rate": reply_rate
            }
        }}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return {
        "success": True,
        "message": "Warmup settings updated",
        "settings": {
            "starting_emails_per_day": starting,
            "max_emails_per_day": max_emails,
            "daily_increment": increment,
            "reply_rate": reply_rate
        }
    }

@api_router.get("/accounts/{account_id}/warmup/stats")
async def get_warmup_stats(account_id: str, user: User = Depends(get_current_user)):
    """Get warmup statistics for an email account"""
    # Verify account ownership
    account = await db.email_accounts.find_one(
        {"account_id": account_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Get today's stats
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_stats = await db.warmup_stats.find_one(
        {"account_id": account_id, "date": today},
        {"_id": 0}
    )
    
    # Get last 7 days stats
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    weekly_stats = await db.warmup_stats.find(
        {"account_id": account_id, "date": {"$gte": seven_days_ago}},
        {"_id": 0}
    ).sort("date", -1).to_list(7)
    
    # Calculate totals
    total_sent = sum(s.get("emails_sent", 0) for s in weekly_stats)
    total_replies = sum(s.get("replies_sent", 0) for s in weekly_stats)
    
    # Get warmup settings
    warmup_settings = account.get("warmup_settings", {
        "starting_emails_per_day": 5,
        "max_emails_per_day": 50,
        "daily_increment": 5,
        "reply_rate": 40
    })
    
    # Calculate current daily target
    warmup_day = account.get("warmup_day", 1)
    starting = warmup_settings.get("starting_emails_per_day", 5)
    increment = warmup_settings.get("daily_increment", 5)
    max_daily = warmup_settings.get("max_emails_per_day", 50)
    current_target = min(starting + (warmup_day - 1) * increment, max_daily)
    
    return {
        "warmup_enabled": account.get("warmup_enabled", False),
        "warmup_status": account.get("warmup_status", "disabled"),
        "warmup_day": warmup_day,
        "current_daily_target": current_target,
        "settings": warmup_settings,
        "today": {
            "emails_sent": today_stats.get("emails_sent", 0) if today_stats else 0,
            "replies_sent": today_stats.get("replies_sent", 0) if today_stats else 0,
            "opens_tracked": today_stats.get("opens_tracked", 0) if today_stats else 0
        },
        "weekly": {
            "total_sent": total_sent,
            "total_replies": total_replies,
            "days": weekly_stats
        }
    }

@api_router.get("/accounts/{account_id}/warmup/logs")
async def get_warmup_logs(account_id: str, limit: int = 50, user: User = Depends(get_current_user)):
    """Get warmup logs for an email account"""
    # Verify account ownership
    account = await db.email_accounts.find_one(
        {"account_id": account_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    logs = await db.warmup_logs.find(
        {"account_id": account_id},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return {"logs": logs}

@api_router.get("/warmup/dashboard")
async def get_warmup_dashboard(user: User = Depends(get_current_user)):
    """Get warmup dashboard data for all user accounts"""
    accounts = await db.email_accounts.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    dashboard_data = []
    for account in accounts:
        account_id = account.get("account_id")
        
        # Get today's stats
        today_stats = await db.warmup_stats.find_one(
            {"account_id": account_id, "date": today},
            {"_id": 0}
        )
        
        warmup_settings = account.get("warmup_settings", {
            "starting_emails_per_day": 5,
            "max_emails_per_day": 50,
            "daily_increment": 5,
            "reply_rate": 40
        })
        
        warmup_day = account.get("warmup_day", 1)
        starting = warmup_settings.get("starting_emails_per_day", 5)
        increment = warmup_settings.get("daily_increment", 5)
        max_daily = warmup_settings.get("max_emails_per_day", 50)
        current_target = min(starting + (warmup_day - 1) * increment, max_daily)
        
        dashboard_data.append({
            "account_id": account_id,
            "email": account.get("email"),
            "warmup_enabled": account.get("warmup_enabled", False),
            "warmup_status": account.get("warmup_status", "disabled"),
            "warmup_day": warmup_day,
            "current_daily_target": current_target,
            "emails_sent_today": today_stats.get("emails_sent", 0) if today_stats else 0,
            "replies_today": today_stats.get("replies_sent", 0) if today_stats else 0,
            "settings": warmup_settings
        })
    
    return {"accounts": dashboard_data}

# ==================== BULK WARMUP ENDPOINTS ====================

class BulkWarmupRequest(BaseModel):
    account_ids: list[str]

class BulkWarmupSettingsRequest(BaseModel):
    account_ids: list[str]
    starting_emails_per_day: int = 5
    max_emails_per_day: int = 50
    daily_increment: int = 5
    reply_rate: int = 40

def _validate_warmup_settings(s: WarmupSettingsRequest | BulkWarmupSettingsRequest) -> dict:
    return {
        "starting_emails_per_day": max(1, min(20, s.starting_emails_per_day)),
        "max_emails_per_day": max(10, min(100, s.max_emails_per_day)),
        "daily_increment": max(1, min(10, s.daily_increment)),
        "reply_rate": max(30, min(50, s.reply_rate)),
    }

@api_router.post("/accounts/warmup/bulk-enable")
async def bulk_enable_warmup(req: BulkWarmupSettingsRequest, user: User = Depends(get_current_user)):
    """Enable warmup for multiple accounts with shared settings."""
    if not req.account_ids:
        raise HTTPException(status_code=400, detail="No accounts selected")
    settings = _validate_warmup_settings(req)
    now_iso = datetime.now(timezone.utc).isoformat()
    result = await db.email_accounts.update_many(
        {"account_id": {"$in": req.account_ids}, "user_id": user.user_id},
        {"$set": {
            "warmup_enabled": True,
            "warmup_status": "active",
            "warmup_day": 1,
            "warmup_started_at": now_iso,
            "warmup_settings": settings,
        }},
    )
    logger.info(f"[WARMUP] Bulk enabled warmup for {result.modified_count} accounts by user {user.email}")
    return {
        "success": True,
        "matched": result.matched_count,
        "modified": result.modified_count,
        "settings": settings,
    }

@api_router.post("/accounts/warmup/bulk-pause")
async def bulk_pause_warmup(req: BulkWarmupRequest, user: User = Depends(get_current_user)):
    """Pause warmup for multiple accounts."""
    if not req.account_ids:
        raise HTTPException(status_code=400, detail="No accounts selected")
    result = await db.email_accounts.update_many(
        {"account_id": {"$in": req.account_ids}, "user_id": user.user_id, "warmup_enabled": True},
        {"$set": {"warmup_status": "paused"}},
    )
    return {"success": True, "matched": result.matched_count, "modified": result.modified_count}

@api_router.post("/accounts/warmup/bulk-resume")
async def bulk_resume_warmup(req: BulkWarmupRequest, user: User = Depends(get_current_user)):
    """Resume warmup for multiple accounts."""
    if not req.account_ids:
        raise HTTPException(status_code=400, detail="No accounts selected")
    result = await db.email_accounts.update_many(
        {"account_id": {"$in": req.account_ids}, "user_id": user.user_id, "warmup_enabled": True},
        {"$set": {"warmup_status": "active"}},
    )
    return {"success": True, "matched": result.matched_count, "modified": result.modified_count}

@api_router.post("/accounts/warmup/bulk-disable")
async def bulk_disable_warmup(req: BulkWarmupRequest, user: User = Depends(get_current_user)):
    """Disable warmup for multiple accounts."""
    if not req.account_ids:
        raise HTTPException(status_code=400, detail="No accounts selected")
    result = await db.email_accounts.update_many(
        {"account_id": {"$in": req.account_ids}, "user_id": user.user_id},
        {"$set": {"warmup_enabled": False, "warmup_status": "disabled"}},
    )
    return {"success": True, "matched": result.matched_count, "modified": result.modified_count}

@api_router.put("/accounts/warmup/bulk-settings")
async def bulk_update_warmup_settings(req: BulkWarmupSettingsRequest, user: User = Depends(get_current_user)):
    """Update warmup settings for multiple accounts at once (does not toggle status)."""
    if not req.account_ids:
        raise HTTPException(status_code=400, detail="No accounts selected")
    settings = _validate_warmup_settings(req)
    result = await db.email_accounts.update_many(
        {"account_id": {"$in": req.account_ids}, "user_id": user.user_id},
        {"$set": {"warmup_settings": settings}},
    )
    return {
        "success": True,
        "matched": result.matched_count,
        "modified": result.modified_count,
        "settings": settings,
    }


class BulkDeleteAccountsRequest(BaseModel):
    account_ids: list[str]
    force: bool = False


@api_router.post("/accounts/bulk-delete")
async def bulk_delete_accounts(req: BulkDeleteAccountsRequest, user: User = Depends(get_current_user)):
    """Delete multiple email accounts. Refuses by default if any selected account is part of a
    running campaign — caller can pass force=true to override after explicit user confirmation.

    Never deletes campaigns, campaign logs, email_queue, drip_contacts, or replies (Unibox).
    Only removes the email_account configuration row itself.
    """
    if not req.account_ids:
        raise HTTPException(status_code=400, detail="No accounts selected")

    owned = await db.email_accounts.find(
        {"account_id": {"$in": req.account_ids}, "user_id": user.user_id},
        {"_id": 0, "account_id": 1, "email": 1},
    ).to_list(1000)
    owned_ids = [a["account_id"] for a in owned]
    if not owned_ids:
        return {"deleted": 0, "blocked": 0, "blocked_accounts": [], "skipped": len(req.account_ids)}

    if not req.force:
        active_campaigns = await db.campaigns.find(
            {
                "user_id": user.user_id,
                "account_ids": {"$in": owned_ids},
                "status": {"$in": ["running", "scheduled", "sending"]},
            },
            {"_id": 0, "campaign_id": 1, "name": 1, "status": 1, "account_ids": 1},
        ).to_list(1000)
        active_drips = await db.drip_campaigns.find(
            {
                "user_id": user.user_id,
                "account_ids": {"$in": owned_ids},
                "status": {"$in": ["running", "scheduled"]},
            },
            {"_id": 0, "drip_id": 1, "name": 1, "status": 1, "account_ids": 1},
        ).to_list(1000)
        blocked_set = set()
        for c in active_campaigns:
            for aid in c.get("account_ids", []):
                if aid in owned_ids:
                    blocked_set.add(aid)
        for c in active_drips:
            for aid in c.get("account_ids", []):
                if aid in owned_ids:
                    blocked_set.add(aid)
        if blocked_set:
            blocked_accounts = [
                {"account_id": a["account_id"], "email": a["email"]}
                for a in owned if a["account_id"] in blocked_set
            ]
            return {
                "deleted": 0,
                "blocked": len(blocked_accounts),
                "blocked_accounts": blocked_accounts,
                "active_campaigns": [
                    {"campaign_id": c.get("campaign_id"), "name": c.get("name"), "status": c.get("status")}
                    for c in active_campaigns
                ],
                "active_drips": [
                    {"drip_id": c.get("drip_id"), "name": c.get("name"), "status": c.get("status")}
                    for c in active_drips
                ],
                "requires_force": True,
            }

    result = await db.email_accounts.delete_many(
        {"account_id": {"$in": owned_ids}, "user_id": user.user_id}
    )
    logger.info(
        f"[ACCOUNTS] User {user.email} bulk-deleted {result.deleted_count} account(s); force={req.force}"
    )
    return {
        "deleted": result.deleted_count,
        "blocked": 0,
        "blocked_accounts": [],
        "requires_force": False,
    }



@api_router.post("/accounts/test-smtp")
async def test_smtp_endpoint(request: TestSMTPRequest, user: User = Depends(get_current_user)):
    """Test SMTP connection without saving"""
    result = await test_smtp_connection(
        request.smtp_host, request.smtp_port, request.smtp_username,
        request.smtp_password, request.smtp_encryption
    )
    return result

async def test_smtp_connection(host: str, port: int, username: str, password: str, encryption: str) -> dict:
    """Test SMTP connection"""
    try:
        if encryption == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            if encryption == "tls":
                server.starttls()
        
        server.login(username, password)
        server.quit()
        return {"success": True, "message": "Connection successful"}
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "error": "Authentication failed. Check username and password."}
    except smtplib.SMTPConnectError:
        return {"success": False, "error": "Could not connect to SMTP server."}
    except Exception as e:
        return {"success": False, "error": str(e)}

@api_router.get("/accounts/{account_id}")
async def get_email_account(account_id: str, user: User = Depends(get_current_user)):
    """Return detailed settings for a single SMTP account (password is never returned)."""
    acc = await db.email_accounts.find_one(
        {"account_id": account_id, "user_id": user.user_id},
        {"_id": 0, "smtp_password_encrypted": 0}
    )
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    return acc

@api_router.get("/accounts/{account_id}/credential")
async def get_account_credential(account_id: str, user: User = Depends(get_current_user)):
    """Return the saved SMTP password to the account owner ONLY.
    Used by the in-app Edit dialog so the user can review/update existing credentials.
    """
    acc = await db.email_accounts.find_one(
        {"account_id": account_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    enc = acc.get("smtp_password_encrypted")
    plain = decrypt_data(enc) if enc else ""
    return {"smtp_password": plain or ""}

@api_router.put("/accounts/{account_id}")
async def update_smtp_account(
    account_id: str,
    request: UpdateSMTPAccountRequest,
    user: User = Depends(get_current_user),
):
    """Update SMTP account settings. Password is optional — only changed if provided.
    Tests the connection before persisting (when credentials/host change)."""
    existing = await db.email_accounts.find_one(
        {"account_id": account_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Email change → prevent clashing with another account owned by same user
    if request.email and request.email != existing.get("email"):
        conflict = await db.email_accounts.find_one(
            {"user_id": user.user_id, "email": request.email, "account_id": {"$ne": account_id}},
            {"_id": 0, "account_id": 1}
        )
        if conflict:
            raise HTTPException(status_code=400, detail="Another account with this email already exists")
    
    # Resolve the credentials we'll use for the connection test
    new_host = request.smtp_host if request.smtp_host is not None else existing.get("smtp_host")
    new_port = request.smtp_port if request.smtp_port is not None else existing.get("smtp_port")
    new_username = (request.smtp_username if request.smtp_username is not None
                    else existing.get("smtp_username") or existing.get("email"))
    new_encryption = (request.smtp_encryption if request.smtp_encryption is not None
                      else existing.get("smtp_encryption", "tls"))
    
    password_to_test = None
    if request.smtp_password:
        password_to_test = request.smtp_password
    else:
        # decrypt existing
        enc = existing.get("smtp_password_encrypted")
        password_to_test = decrypt_data(enc) if enc else None
    
    # Only re-test SMTP if credentials or connection settings actually changed,
    # otherwise a legacy/bogus encrypted blob could cause spurious 400s on pure metadata edits.
    creds_changed = (
        request.smtp_password is not None
        or (request.smtp_host is not None and request.smtp_host != existing.get("smtp_host"))
        or (request.smtp_port is not None and request.smtp_port != existing.get("smtp_port"))
        or (request.smtp_username is not None and request.smtp_username != existing.get("smtp_username"))
        or (request.smtp_encryption is not None and request.smtp_encryption != existing.get("smtp_encryption"))
    )
    if creds_changed and new_host and new_port and password_to_test:
        test_result = await test_smtp_connection(new_host, new_port, new_username, password_to_test, new_encryption)
        if not test_result.get("success"):
            raise HTTPException(status_code=400, detail=f"SMTP connection failed: {test_result.get('error')}")
    
    update_data = {}
    if request.email is not None:
        update_data["email"] = request.email
    if request.display_name is not None:
        update_data["display_name"] = request.display_name
    if request.smtp_host is not None:
        update_data["smtp_host"] = request.smtp_host
    if request.smtp_port is not None:
        update_data["smtp_port"] = request.smtp_port
    if request.smtp_username is not None:
        update_data["smtp_username"] = request.smtp_username
    if request.smtp_encryption is not None:
        update_data["smtp_encryption"] = request.smtp_encryption
    if request.daily_limit is not None:
        try:
            update_data["daily_limit"] = max(1, int(request.daily_limit))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="daily_limit must be a positive integer")
    if request.send_delay is not None:
        update_data["send_delay"] = max(10, min(300, request.send_delay))
    if request.smtp_password:
        update_data["smtp_password_encrypted"] = encrypt_data(request.smtp_password)
    # From Name (campaign-level override still wins at send-time)
    if request.from_name is not None:
        update_data["from_name"] = request.from_name
    # IMAP (receiving) fields — set whatever the user provides; password optional
    if request.imap_host is not None:
        update_data["imap_host"] = request.imap_host
    if request.imap_port is not None:
        update_data["imap_port"] = request.imap_port
    if request.imap_username is not None:
        update_data["imap_username"] = request.imap_username
    if request.imap_encryption is not None:
        update_data["imap_encryption"] = request.imap_encryption
    if request.imap_password:
        update_data["imap_password_encrypted"] = encrypt_data(request.imap_password)
    # Only mark 'connected' if we actually re-tested successfully above
    if creds_changed:
        update_data["status"] = "connected"
        update_data["last_error"] = None
    
    await db.email_accounts.update_one(
        {"account_id": account_id, "user_id": user.user_id},
        {"$set": update_data}
    )
    return {"message": "Account updated", "account_id": account_id}

@api_router.get("/accounts/smtp/sample-csv")
async def download_sample_accounts_csv(user: User = Depends(get_current_user)):
    """Return a sample CSV for bulk SMTP account import."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "email", "from_name", "smtp_host", "smtp_port", "smtp_username", "smtp_password", "smtp_ssl",
        "imap_host", "imap_port", "imap_username", "imap_password", "imap_ssl",
        "daily_limit", "delay_seconds"
    ])
    writer.writerow([
        "sales@example.com", "Sales Team", "smtp.gmail.com", "587", "sales@example.com", "your_app_password", "true",
        "imap.gmail.com", "993", "sales@example.com", "your_app_password", "true",
        "50", "30"
    ])
    writer.writerow([
        "outreach@example.com", "Outreach Team", "smtp.office365.com", "587", "outreach@example.com", "your_password", "true",
        "outlook.office365.com", "993", "outreach@example.com", "your_password", "true",
        "40", "30"
    ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="email_accounts_sample.csv"'}
    )

@api_router.post("/accounts/smtp/bulk-import")
async def bulk_import_smtp_accounts(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Bulk import SMTP accounts from a CSV file.
    Returns per-row success/error summary. Never halts on a single bad row.
    """
    # Subscription check
    sub_status = await check_subscription_active(user.user_id)
    if not sub_status.get("active"):
        raise HTTPException(status_code=403, detail=f"Subscription required: {sub_status.get('reason', 'Inactive subscription')}")
    
    filename = (file.filename or "").lower()
    if not filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are supported for account import")
    
    content = await file.read()
    if len(content) > 1 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 1MB limit")
    
    text = content.decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    required = {"email", "password", "smtp_host", "smtp_port"}
    missing = required - set(headers)
    if missing:
        raise HTTPException(status_code=400, detail=f"CSV is missing required columns: {', '.join(sorted(missing))}")
    
    MAX_IMPORT_ROWS = 200
    all_rows = list(reader)
    if len(all_rows) > MAX_IMPORT_ROWS:
        raise HTTPException(
            status_code=400,
            detail=f"Too many rows in one import (max {MAX_IMPORT_ROWS}). Please split the file."
        )
    
    # Build list of existing emails for this user (to skip duplicates without SMTP test)
    existing_accounts = await db.email_accounts.find(
        {"user_id": user.user_id},
        {"_id": 0, "email": 1}
    ).to_list(1000)
    existing_emails = {(a.get("email") or "").lower() for a in existing_accounts}
    
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    results = []  # {row, email, status: 'imported'|'skipped'|'failed', error?}
    imported = 0
    skipped = 0
    failed = 0
    
    row_num = 1  # header is row 1 in user-facing terms
    for raw in all_rows:
        row_num += 1
        normalized = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        email = normalized.get("email", "").strip().lower()
        # Support both legacy "password" column and new explicit smtp_password column
        password = (normalized.get("smtp_password") or normalized.get("password") or "").strip()
        smtp_host = normalized.get("smtp_host", "")
        smtp_port_raw = normalized.get("smtp_port", "")
        
        if not email or not password or not smtp_host or not smtp_port_raw:
            failed += 1
            results.append({"row": row_num, "email": email, "status": "failed",
                            "error": "Missing required fields (email/password/smtp_host/smtp_port)"})
            continue
        if not email_pattern.match(email):
            failed += 1
            results.append({"row": row_num, "email": email, "status": "failed",
                            "error": "Invalid email format"})
            continue
        
        # Check account limit each time we add
        limit_check = await check_account_limit(user.user_id)
        if not limit_check.get("can_add"):
            failed += 1
            results.append({"row": row_num, "email": email, "status": "failed",
                            "error": f"Account limit reached ({limit_check.get('limit')})"})
            continue
        
        if email.lower() in existing_emails:
            skipped += 1
            results.append({"row": row_num, "email": email, "status": "skipped",
                            "error": "Already connected"})
            continue
        
        try:
            smtp_port = int(smtp_port_raw)
        except ValueError:
            failed += 1
            results.append({"row": row_num, "email": email, "status": "failed",
                            "error": "smtp_port must be a number"})
            continue
        
        use_ssl_raw = normalized.get("use_ssl", "true").lower()
        encryption = "ssl" if use_ssl_raw in ("ssl", "true", "1", "yes") and smtp_port in (465,) else "tls"
        # If use_ssl is true but the port is typical STARTTLS, keep tls
        
        try:
            daily_limit = int(normalized.get("daily_limit") or 50)
        except ValueError:
            daily_limit = 50
        daily_limit = max(1, daily_limit)
        
        try:
            send_delay = int(normalized.get("delay_seconds") or 30)
        except ValueError:
            send_delay = 30
        send_delay = max(10, min(300, send_delay))
        
        # Test connection
        test_result = await test_smtp_connection(smtp_host, smtp_port, email, password, encryption)
        if not test_result.get("success"):
            failed += 1
            results.append({"row": row_num, "email": email, "status": "failed",
                            "error": f"SMTP test failed: {test_result.get('error')}"})
            continue
        
        account = EmailAccount(
            user_id=user.user_id,
            account_type="smtp",
            email=email,
            display_name=(normalized.get("from_name") or email.split("@")[0]),
            from_name=normalized.get("from_name") or None,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_username=(normalized.get("smtp_username") or email),
            smtp_password_encrypted=encrypt_data(password),
            smtp_encryption=encryption,
            imap_host=normalized.get("imap_host") or None,
            imap_port=int(normalized["imap_port"]) if normalized.get("imap_port", "").isdigit() else None,
            imap_username=normalized.get("imap_username") or (email if normalized.get("imap_host") else None),
            imap_password_encrypted=(
                encrypt_data(normalized.get("imap_password"))
                if normalized.get("imap_password")
                else (encrypt_data(password) if normalized.get("imap_host") else None)
            ),
            imap_encryption=(
                "ssl" if normalized.get("imap_ssl", "true").lower() in ("ssl", "true", "1", "yes") else "tls"
            ) if normalized.get("imap_host") else None,
            daily_limit=daily_limit,
            send_delay=send_delay,
            status="connected",
            last_reset_at=datetime.now(timezone.utc),
        )
        acc_dict = account.model_dump()
        acc_dict["created_at"] = acc_dict["created_at"].isoformat()
        acc_dict["last_reset_at"] = acc_dict["last_reset_at"].isoformat()
        await db.email_accounts.insert_one(acc_dict)
        # Batch-1 auto-detection — silently track the domain.
        try:
            from infra_phase_a import ensure_domain_record
            await ensure_domain_record(db, user.user_id, email)
        except Exception as e:
            logger.warning(f"[DOMAIN_AUTO_DETECT] bulk-import failed for {email}: {e}")
        existing_emails.add(email.lower())
        
        imported += 1
        results.append({"row": row_num, "email": email, "status": "imported"})
    
    return {
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "total_processed": imported + skipped + failed,
        "results": results,
    }

@api_router.delete("/accounts/{account_id}")
async def delete_email_account(account_id: str, user: User = Depends(get_current_user)):
    """Delete an email account"""
    result = await db.email_accounts.delete_one(
        {"account_id": account_id, "user_id": user.user_id}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")
    
    return {"message": "Account deleted"}

# ==================== EMAIL LIST ENDPOINTS ====================

@api_router.get("/lists")
async def get_email_lists(user: User = Depends(get_current_user)):
    """Get all email lists"""
    lists = await db.email_lists.find(
        {"user_id": user.user_id},
        {"_id": 0, "emails": 0}
    ).sort("created_at", -1).to_list(100)
    
    return lists

@api_router.get("/lists/{list_id}")
async def get_email_list(list_id: str, user: User = Depends(get_current_user)):
    """Get a specific email list with emails"""
    email_list = await db.email_lists.find_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not email_list:
        raise HTTPException(status_code=404, detail="List not found")
    
    return email_list

@api_router.post("/lists/upload")
async def upload_email_list(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user)
):
    """Upload and parse CSV or Excel file"""
    import pandas as pd
    
    filename = file.filename.lower()
    allowed_extensions = ['.csv', '.xlsx', '.xls']
    file_ext = None
    for ext in allowed_extensions:
        if filename.endswith(ext):
            file_ext = ext
            break
    
    if not file_ext:
        raise HTTPException(status_code=400, detail="Only CSV and Excel files (.csv, .xlsx, .xls) are allowed")
    
    # Read file content. The 2MB cap was removed — large CSV/XLSX uploads are now allowed.
    content = await file.read()
    
    try:
        # Helper: normalize a single header value
        def _normalize_header(h: str) -> str:
            s = str(h or "").strip().lower()
            # Replace any whitespace, dots, dashes with underscore
            s = re.sub(r"[\s.\-]+", "_", s)
            # Drop any other special characters (keep alphanumeric + underscore)
            s = re.sub(r"[^a-z0-9_]+", "", s)
            # Collapse runs of underscores and trim leading/trailing underscores
            s = re.sub(r"_+", "_", s).strip("_")
            return s

        # Helper: normalize and dedupe a list of headers
        def _normalize_headers(headers):
            seen = {}
            out = []
            for raw in headers:
                base = _normalize_header(raw) or "column"
                if base in seen:
                    seen[base] += 1
                    out.append(f"{base}_{seen[base]}")
                else:
                    seen[base] = 1
                    out.append(base)
            return out

        # Parse based on file type
        if file_ext == '.csv':
            text_content = content.decode('utf-8')
            reader = csv.DictReader(io.StringIO(text_content))
            raw_headers = reader.fieldnames or []
            column_headers = _normalize_headers(raw_headers)
            # Map original-trimmed -> normalized so we can rewrite each row's keys
            header_map = {raw_headers[i]: column_headers[i] for i in range(len(raw_headers))}

            rows = []
            for row in reader:
                normalized_row = {}
                for raw_key, val in row.items():
                    new_key = header_map.get(raw_key)
                    if not new_key:
                        continue
                    normalized_row[new_key] = (val.strip() if isinstance(val, str) else (str(val) if val is not None else "")) if val else ""
                rows.append(normalized_row)
        else:
            # Excel file (.xlsx or .xls)
            try:
                df = pd.read_excel(io.BytesIO(content), engine='openpyxl' if file_ext == '.xlsx' else 'xlrd')
            except Exception:
                # Fallback to openpyxl for both
                df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
            
            # Clean & dedupe column headers
            df.columns = _normalize_headers([str(col) for col in df.columns])
            column_headers = df.columns.tolist()
            
            # Convert to list of dicts
            df = df.fillna('')
            rows = df.to_dict('records')
            # Ensure all values are strings
            for row in rows:
                for key in row:
                    row[key] = str(row[key]).strip() if row[key] != '' else ''
        
        if 'email' not in column_headers:
            raise HTTPException(status_code=400, detail="File must contain an 'email' column")
        
        emails = []
        seen_emails = set()
        email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        
        for row in rows:
            email = row.get('email', '')
            
            if not email or not email_pattern.match(email):
                continue
            
            if email.lower() in seen_emails:
                continue
            
            seen_emails.add(email.lower())
            emails.append(row)
        
        if not emails:
            raise HTTPException(status_code=400, detail="No valid emails found in file")
        
        return {
            "original_filename": file.filename,
            "column_headers": column_headers,
            "total_rows": len(emails),
            "valid_emails": len(emails),
            "preview": emails[:10],
            "emails": emails
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing file: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

@api_router.post("/lists")
async def create_email_list(request: CreateListRequest, user: User = Depends(get_current_user)):
    """Save email list"""
    # Check subscription is active
    sub_status = await check_subscription_active(user.user_id)
    if not sub_status.get("active"):
        raise HTTPException(status_code=403, detail=f"Subscription required: {sub_status.get('reason', 'Inactive subscription')}")
    
    # Check contact limit
    contact_limit = await check_contact_limit(user.user_id, len(request.emails))
    if not contact_limit["can_add"]:
        raise HTTPException(
            status_code=403,
            detail=f"Contact limit exceeded. Your plan allows {contact_limit['limit']} contacts ({contact_limit['current']} used). Please upgrade to add more."
        )
    
    suppression = await db.suppression_list.find(
        {"user_id": user.user_id},
        {"_id": 0, "email": 1}
    ).to_list(10000)
    
    suppressed_emails = {s["email"].lower() for s in suppression}
    filtered_emails = [e for e in request.emails if e.get("email", "").lower() not in suppressed_emails]
    
    email_list = EmailList(
        user_id=user.user_id,
        name=request.name,
        original_filename=request.original_filename,
        column_headers=request.column_headers,
        total_rows=len(request.emails),
        valid_emails=len(filtered_emails),
        emails=filtered_emails
    )
    
    list_dict = email_list.model_dump()
    list_dict["created_at"] = list_dict["created_at"].isoformat()
    await db.email_lists.insert_one(list_dict)
    
    return {
        "list_id": email_list.list_id,
        "name": email_list.name,
        "column_headers": email_list.column_headers,
        "total_rows": email_list.total_rows,
        "valid_emails": email_list.valid_emails
    }

@api_router.put("/lists/{list_id}")
async def update_email_list(list_id: str, request: UpdateListRequest, user: User = Depends(get_current_user)):
    """Update email list name"""
    result = await db.email_lists.update_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"$set": {"name": request.name}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="List not found")
    
    return {"message": "List updated"}

@api_router.put("/lists/{list_id}/record")
async def update_list_record(list_id: str, request: UpdateListRecordRequest, user: User = Depends(get_current_user)):
    """Update a single contact row inside an email list (matched by original_email)."""
    email_list = await db.email_lists.find_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not email_list:
        raise HTTPException(status_code=404, detail="List not found")
    
    new_email = (request.data.get("email") or "").strip()
    if not new_email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if not email_pattern.match(new_email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    original_norm = (request.original_email or "").strip().lower()
    new_norm = new_email.lower()
    
    emails = email_list.get("emails", [])
    found_idx = None
    for i, row in enumerate(emails):
        if (row.get("email") or "").strip().lower() == original_norm:
            found_idx = i
            break
    if found_idx is None:
        raise HTTPException(status_code=404, detail="Contact not found in list")
    
    # Prevent collision with another existing contact if email changed
    if original_norm != new_norm:
        for i, row in enumerate(emails):
            if i == found_idx:
                continue
            if (row.get("email") or "").strip().lower() == new_norm:
                raise HTTPException(status_code=400, detail="Another contact with this email already exists in this list")
    
    # Merge: preserve unknown keys from the existing row, overlay with provided data
    merged = {**emails[found_idx], **request.data, "email": new_email}
    emails[found_idx] = merged
    
    # Recalculate counts (all valid since we validated above)
    valid_count = sum(1 for r in emails if email_pattern.match((r.get("email") or "").strip()))
    
    await db.email_lists.update_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"$set": {"emails": emails, "valid_emails": valid_count}}
    )
    return {"message": "Contact updated", "record": merged}

@api_router.post("/lists/{list_id}/records")
async def add_list_record(list_id: str, request: AddListRecordRequest, user: User = Depends(get_current_user)):
    """Manually add a single contact to an email list."""
    email_list = await db.email_lists.find_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not email_list:
        raise HTTPException(status_code=404, detail="List not found")
    
    raw_email = (request.data.get("email") or "").strip().lower()
    if not raw_email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    if not email_pattern.match(raw_email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    emails = email_list.get("emails", [])
    for row in emails:
        if (row.get("email") or "").strip().lower() == raw_email:
            raise HTTPException(status_code=400, detail="A contact with this email already exists in this list")
    
    # Normalise the new row: trim every value, force email lowercase
    new_row = {}
    headers = email_list.get("column_headers") or list(request.data.keys())
    for k in set(list(request.data.keys()) + headers):
        v = request.data.get(k, "")
        new_row[k] = (str(v).strip() if v is not None else "")
    new_row["email"] = raw_email
    
    if "email" not in (email_list.get("column_headers") or []):
        new_headers = ["email"] + [h for h in (email_list.get("column_headers") or []) if h != "email"]
    else:
        new_headers = email_list.get("column_headers")
    
    emails.append(new_row)
    valid_count = sum(1 for r in emails if email_pattern.match((r.get("email") or "").strip()))
    
    await db.email_lists.update_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"$set": {
            "emails": emails,
            "valid_emails": valid_count,
            "total_rows": len(emails),
            "column_headers": new_headers,
        }}
    )
    return {"message": "Contact added", "record": new_row, "valid_emails": valid_count}

@api_router.delete("/lists/{list_id}/records")
async def delete_list_record(list_id: str, request: DeleteListRecordRequest, user: User = Depends(get_current_user)):
    """Delete a single contact (by email) from an email list."""
    email_list = await db.email_lists.find_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not email_list:
        raise HTTPException(status_code=404, detail="List not found")
    
    target = (request.email or "").strip().lower()
    if not target:
        raise HTTPException(status_code=400, detail="Email is required")
    
    emails = email_list.get("emails", [])
    new_emails = [r for r in emails if (r.get("email") or "").strip().lower() != target]
    if len(new_emails) == len(emails):
        raise HTTPException(status_code=404, detail="Contact not found in this list")
    
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    valid_count = sum(1 for r in new_emails if email_pattern.match((r.get("email") or "").strip()))
    
    await db.email_lists.update_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"$set": {
            "emails": new_emails,
            "valid_emails": valid_count,
            "total_rows": len(new_emails),
        }}
    )
    return {"message": "Contact deleted", "valid_emails": valid_count}

@api_router.get("/lists/{list_id}/export")
async def export_email_list(list_id: str, user: User = Depends(get_current_user)):
    """Download the email list as a CSV (current values)."""
    email_list = await db.email_lists.find_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not email_list:
        raise HTTPException(status_code=404, detail="List not found")
    
    headers = email_list.get("column_headers") or ["email"]
    if "email" not in headers:
        headers = ["email"] + headers
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in email_list.get("emails", []):
        writer.writerow([row.get(h, "") for h in headers])
    output.seek(0)
    
    safe_name = re.sub(r'[^A-Za-z0-9_-]+', '_', email_list.get("name") or "list") or "list"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.csv"'}
    )

@api_router.delete("/lists/{list_id}")
async def delete_email_list(list_id: str, user: User = Depends(get_current_user)):
    """Delete an email list"""
    # Check if list is used in any active campaign
    active_campaign = await db.campaigns.find_one(
        {"user_id": user.user_id, "list_id": list_id, "status": {"$in": ["running", "paused", "paused_daily_limit"]}},
        {"_id": 0}
    )
    
    if active_campaign:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete list: it is used in an active campaign. Please complete or delete the campaign first."
        )
    
    result = await db.email_lists.delete_one(
        {"list_id": list_id, "user_id": user.user_id}
    )
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="List not found")
    
    return {"message": "List deleted"}

# ==================== CAMPAIGN ENDPOINTS ====================

@api_router.get("/campaigns")
async def get_campaigns(user: User = Depends(get_current_user)):
    """Get all campaigns with Phase-2 reporting enrichment (folder name, reply/lead counts)."""
    campaigns = await db.campaigns.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    if campaigns:
        folder_ids = {c.get("folder_id") for c in campaigns if c.get("folder_id")}
        folder_name_by_id: Dict[str, str] = {}
        if folder_ids:
            async for f in db.lead_folders.find(
                {"user_id": user.user_id, "folder_id": {"$in": list(folder_ids)}},
                {"_id": 0, "folder_id": 1, "name": 1},
            ):
                folder_name_by_id[f["folder_id"]] = f["name"]
        for c in campaigns:
            cid = c.get("campaign_id")
            c["folder_name"] = folder_name_by_id.get(c.get("folder_id") or "")
            c["reply_count"] = await db.replies.count_documents(
                {"user_id": user.user_id, "campaign_id": cid}
            )
            c["lead_count"] = await db.leads.count_documents(
                {"user_id": user.user_id, "source_campaign_id": cid}
            )
    return campaigns

@api_router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, user: User = Depends(get_current_user)):
    """Get campaign details with stats"""
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    pending = await db.email_queue.count_documents({"campaign_id": campaign_id, "status": "pending"})
    sent = await db.email_queue.count_documents({"campaign_id": campaign_id, "status": "sent"})
    failed = await db.email_queue.count_documents({"campaign_id": campaign_id, "status": "failed"})
    suppressed = await db.email_queue.count_documents({"campaign_id": campaign_id, "status": "suppressed"})
    
    campaign["pending_count"] = pending
    campaign["sent_count"] = sent
    campaign["failed_count"] = failed
    campaign["suppressed_count"] = suppressed
    
    return campaign

@api_router.get("/campaigns/{campaign_id}/logs")
async def get_campaign_logs(
    campaign_id: str, 
    user: User = Depends(get_current_user),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0),
    limit: int = Query(50)
):
    """Get campaign sending logs"""
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Build query
    query = {"campaign_id": campaign_id}
    if status:
        query["status"] = status
    if search:
        query["recipient_email"] = {"$regex": search, "$options": "i"}
    
    # Get logs
    logs = await db.email_queue.find(
        query,
        {"_id": 0}
    ).sort("sent_at", -1).skip(skip).limit(limit).to_list(limit)
    
    # Get total count
    total = await db.email_queue.count_documents(query)
    
    # Get account emails for display
    account_ids = list(set([log.get("assigned_account_id") for log in logs if log.get("assigned_account_id")]))
    accounts = await db.email_accounts.find(
        {"account_id": {"$in": account_ids}},
        {"_id": 0, "account_id": 1, "email": 1}
    ).to_list(100)
    account_map = {a["account_id"]: a["email"] for a in accounts}
    
    # Add account email to logs
    for log in logs:
        if log.get("assigned_account_id"):
            log["account_email"] = account_map.get(log["assigned_account_id"], "Unknown")
    
    return {
        "logs": logs,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@api_router.get("/campaigns/{campaign_id}/logs/export")
async def export_campaign_logs(campaign_id: str, user: User = Depends(get_current_user)):
    """Export campaign logs as CSV"""
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get all logs
    logs = await db.email_queue.find(
        {"campaign_id": campaign_id},
        {"_id": 0}
    ).sort("sent_at", -1).to_list(10000)
    
    # Get account emails
    account_ids = list(set([log.get("assigned_account_id") for log in logs if log.get("assigned_account_id")]))
    accounts = await db.email_accounts.find(
        {"account_id": {"$in": account_ids}},
        {"_id": 0, "account_id": 1, "email": 1}
    ).to_list(100)
    account_map = {a["account_id"]: a["email"] for a in accounts}
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Recipient Email", "Status", "Sent From", "Sent At", "Error Message"])
    
    for log in logs:
        writer.writerow([
            log.get("recipient_email", ""),
            log.get("status", ""),
            account_map.get(log.get("assigned_account_id"), ""),
            log.get("sent_at", ""),
            log.get("error_message", "")
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=campaign_{campaign_id}_logs.csv"}
    )

# Phase-2 helper — keep this above the routes that use it.
async def _ensure_default_folder_id(user_id: str, requested: Optional[str]) -> str:
    """Resolve a folder_id for a campaign/drip.

    * If the caller provided a real folder_id and it exists for the user, return it.
    * Otherwise, find-or-create the per-user "Default" folder so every campaign
      always has a brand/folder linkage.
    """
    if requested:
        existing = await db.lead_folders.find_one(
            {"folder_id": requested, "user_id": user_id}, {"_id": 0, "folder_id": 1}
        )
        if existing:
            return existing["folder_id"]
    default = await db.lead_folders.find_one(
        {"user_id": user_id, "name": "Default"}, {"_id": 0, "folder_id": 1}
    )
    if default:
        return default["folder_id"]
    fid = f"foldr_{uuid.uuid4().hex[:10]}"
    await db.lead_folders.insert_one({
        "folder_id": fid,
        "user_id": user_id,
        "name": "Default",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return fid


@api_router.post("/campaigns")
async def create_campaign(request: CreateCampaignRequest, user: User = Depends(get_current_user)):
    """Create a new campaign"""
    total_emails = 0
    if request.list_id:
        email_list = await db.email_lists.find_one(
            {"list_id": request.list_id, "user_id": user.user_id},
            {"_id": 0}
        )
        if email_list:
            total_emails = email_list.get("valid_emails", 0)
    
    # Determine status based on scheduling
    status = "draft"
    scheduled_at = None
    if request.scheduled_at:
        try:
            scheduled_at = parse_scheduled_at_in_timezone(request.scheduled_at, request.timezone)
            status = "scheduled"
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid scheduled_at datetime format")
    
    campaign = Campaign(
        user_id=user.user_id,
        name=request.name,
        subject=request.subject,
        body=request.body,
        body_text=request.body_text,
        from_name=request.from_name,
        list_id=request.list_id,
        account_ids=request.account_ids,
        total_emails=total_emails,
        status=status,
        scheduled_at=scheduled_at,
        timezone=request.timezone,
        suppression_list_ids=request.suppression_list_ids,
        send_range_mode=request.send_range_mode or "all",
        send_range_start=request.send_range_start,
        send_range_end=request.send_range_end,
        add_unsubscribe_footer=bool(request.add_unsubscribe_footer),
    )
    
    camp_dict = campaign.model_dump()
    camp_dict["created_at"] = camp_dict["created_at"].isoformat()
    camp_dict["updated_at"] = camp_dict["updated_at"].isoformat()
    if camp_dict.get("scheduled_at"):
        camp_dict["scheduled_at"] = camp_dict["scheduled_at"].isoformat()
    
    await db.campaigns.insert_one(camp_dict)

    # Phase-2: persist folder linkage + fallback config (added after .model_dump
    # so we don't have to touch the Campaign model schema).
    folder_id = await _ensure_default_folder_id(user.user_id, request.folder_id)
    await db.campaigns.update_one(
        {"campaign_id": campaign.campaign_id},
        {"$set": {
            "folder_id": folder_id,
            "variable_fallbacks": request.variable_fallbacks or {},
        }},
    )

    return {"campaign_id": campaign.campaign_id, "status": campaign.status, "scheduled_at": request.scheduled_at, "folder_id": folder_id}

@api_router.put("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: str, request: UpdateCampaignRequest, user: User = Depends(get_current_user)):
    """Update a campaign"""
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.get("is_locked") or campaign["status"] in ["running"]:
        raise HTTPException(status_code=400, detail="Cannot edit a running campaign. Pause it first.")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    if request.name is not None:
        update_data["name"] = request.name
    if request.subject is not None:
        update_data["subject"] = request.subject
    if request.body is not None:
        update_data["body"] = request.body
    if request.body_text is not None:
        update_data["body_text"] = request.body_text
    if request.from_name is not None:
        update_data["from_name"] = request.from_name
    if request.list_id is not None:
        update_data["list_id"] = request.list_id
        email_list = await db.email_lists.find_one(
            {"list_id": request.list_id, "user_id": user.user_id},
            {"_id": 0}
        )
        if email_list:
            update_data["total_emails"] = email_list.get("valid_emails", 0)
    if request.account_ids is not None:
        update_data["account_ids"] = request.account_ids
    if request.suppression_list_ids is not None:
        update_data["suppression_list_ids"] = request.suppression_list_ids
    if request.scheduled_at is not None:
        if request.scheduled_at == "":
            update_data["scheduled_at"] = None
            if campaign["status"] == "scheduled":
                update_data["status"] = "draft"
        else:
            try:
                scheduled_dt = parse_scheduled_at_in_timezone(request.scheduled_at, request.timezone)
                update_data["scheduled_at"] = scheduled_dt.isoformat()
                update_data["status"] = "scheduled"
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid scheduled_at datetime format")
    if request.timezone is not None:
        update_data["timezone"] = request.timezone
    if request.send_range_mode is not None:
        update_data["send_range_mode"] = request.send_range_mode
    if request.send_range_start is not None:
        update_data["send_range_start"] = request.send_range_start
    if request.send_range_end is not None:
        update_data["send_range_end"] = request.send_range_end
    if request.add_unsubscribe_footer is not None:
        update_data["add_unsubscribe_footer"] = bool(request.add_unsubscribe_footer)
    if request.folder_id is not None:
        update_data["folder_id"] = await _ensure_default_folder_id(user.user_id, request.folder_id)
    if request.variable_fallbacks is not None:
        update_data["variable_fallbacks"] = request.variable_fallbacks or {}
    
    await db.campaigns.update_one(
        {"campaign_id": campaign_id},
        {"$set": update_data}
    )
    
    return {"message": "Campaign updated", "campaign_id": campaign_id}

@api_router.post("/campaigns/{campaign_id}/duplicate")
async def duplicate_campaign(campaign_id: str, user: User = Depends(get_current_user)):
    """Duplicate a campaign"""
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    new_campaign = Campaign(
        user_id=user.user_id,
        name=f"{campaign['name']} (Copy)",
        subject=campaign["subject"],
        body=campaign["body"],
        body_text=campaign.get("body_text"),
        from_name=campaign.get("from_name"),
        list_id=campaign.get("list_id"),
        account_ids=campaign.get("account_ids", []),
        total_emails=campaign.get("total_emails", 0),
        status="draft"
    )
    
    camp_dict = new_campaign.model_dump()
    camp_dict["created_at"] = camp_dict["created_at"].isoformat()
    camp_dict["updated_at"] = camp_dict["updated_at"].isoformat()
    
    await db.campaigns.insert_one(camp_dict)
    
    return {"campaign_id": new_campaign.campaign_id, "status": "draft", "message": "Campaign duplicated"}


# ---------- Campaign export / import / convert ----------

ROUTEMAIL_EXPORT_VERSION = 1

async def _resolve_list_name(user_id: str, list_id: Optional[str]) -> Optional[str]:
    if not list_id:
        return None
    doc = await db.email_lists.find_one(
        {"list_id": list_id, "user_id": user_id}, {"_id": 0, "name": 1}
    )
    return (doc or {}).get("name")

async def _resolve_account_emails(user_id: str, account_ids: List[str]) -> List[str]:
    if not account_ids:
        return []
    docs = await db.email_accounts.find(
        {"user_id": user_id, "account_id": {"$in": account_ids}},
        {"_id": 0, "email": 1}
    ).to_list(len(account_ids))
    return [d["email"] for d in docs if d.get("email")]

async def _resolve_dne_names(user_id: str, list_ids: List[str]) -> List[str]:
    if not list_ids:
        return []
    docs = await db.dne_lists.find(
        {"user_id": user_id, "list_id": {"$in": list_ids}},
        {"_id": 0, "name": 1}
    ).to_list(len(list_ids))
    return [d["name"] for d in docs if d.get("name")]

async def _unique_campaign_name(user_id: str, base: str) -> str:
    """Append '(Imported)' if `base` is taken; if that is also taken, append numeric suffix."""
    existing = await db.campaigns.find_one(
        {"user_id": user_id, "name": base}, {"_id": 0, "name": 1}
    )
    if not existing:
        return base
    candidate = f"{base} (Imported)"
    n = 2
    while await db.campaigns.find_one(
        {"user_id": user_id, "name": candidate}, {"_id": 0, "name": 1}
    ):
        candidate = f"{base} (Imported {n})"
        n += 1
    return candidate

async def _unique_drip_name(user_id: str, base: str) -> str:
    existing = await db.drip_campaigns.find_one(
        {"user_id": user_id, "name": base}, {"_id": 0, "name": 1}
    )
    if not existing:
        return base
    candidate = f"{base} (Imported)"
    n = 2
    while await db.drip_campaigns.find_one(
        {"user_id": user_id, "name": candidate}, {"_id": 0, "name": 1}
    ):
        candidate = f"{base} (Imported {n})"
        n += 1
    return candidate


@api_router.get("/campaigns/{campaign_id}/export")
async def export_campaign(campaign_id: str, user: User = Depends(get_current_user)):
    """Export a single normal campaign as JSON. NEVER includes sent logs, recipient
    progress, analytics or replies."""
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id}, {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    payload = {
        "schema_version": ROUTEMAIL_EXPORT_VERSION,
        "type": "campaign",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "campaign": {
            "name": campaign.get("name", "Untitled"),
            "from_name": campaign.get("from_name"),
            "subject": campaign.get("subject", ""),
            "body": campaign.get("body", ""),
            "body_text": campaign.get("body_text"),
            "list_name": await _resolve_list_name(user.user_id, campaign.get("list_id")),
            "account_emails": await _resolve_account_emails(user.user_id, campaign.get("account_ids") or []),
            "dne_list_names": await _resolve_dne_names(user.user_id, campaign.get("suppression_list_ids") or []),
            "send_range_mode": campaign.get("send_range_mode", "all"),
            "send_range_start": campaign.get("send_range_start"),
            "send_range_end": campaign.get("send_range_end"),
            "scheduled_at": campaign.get("scheduled_at"),
            "schedule_timezone": campaign.get("timezone"),
            "add_unsubscribe_footer": bool(campaign.get("add_unsubscribe_footer", False)),
            "tracking_opens": bool(campaign.get("tracking_opens", True)),
            "tracking_clicks": bool(campaign.get("tracking_clicks", True)),
            "created_at": campaign.get("created_at"),
        },
    }
    fname = f"routemail-campaign-{(campaign.get('name') or 'export').replace(' ', '_')[:48]}.json"
    return Response(
        content=json.dumps(payload, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@api_router.post("/campaigns/import")
async def import_campaign(payload: Dict[str, Any] = Body(...), user: User = Depends(get_current_user)):
    """Import a campaign payload (produced by /campaigns/{id}/export). Always saved as DRAFT.
    Operational fields (sent logs, recipient progress, analytics) are deliberately ignored even
    if present in the payload. References to lists / accounts / DNE lists are resolved by NAME
    or EMAIL when possible; missing references silently fall back to empty.
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    if payload.get("type") and payload.get("type") != "campaign":
        raise HTTPException(status_code=400, detail="This file is not a campaign export")
    data = payload.get("campaign") or payload  # accept either wrapper
    name = (data.get("name") or "Imported Campaign").strip()[:140] or "Imported Campaign"
    final_name = await _unique_campaign_name(user.user_id, name)

    # Resolve list by name
    list_id = None
    list_name = data.get("list_name")
    if list_name:
        match = await db.email_lists.find_one(
            {"user_id": user.user_id, "name": list_name}, {"_id": 0, "list_id": 1}
        )
        list_id = (match or {}).get("list_id")
    # Resolve accounts by email
    account_ids: List[str] = []
    for em in (data.get("account_emails") or []):
        acct = await db.email_accounts.find_one(
            {"user_id": user.user_id, "email": (em or "").strip().lower()},
            {"_id": 0, "account_id": 1},
        )
        if acct:
            account_ids.append(acct["account_id"])
    # Resolve DNE lists by name
    dne_ids: List[str] = []
    for nm in (data.get("dne_list_names") or []):
        d = await db.dne_lists.find_one(
            {"user_id": user.user_id, "name": nm}, {"_id": 0, "list_id": 1}
        )
        if d:
            dne_ids.append(d["list_id"])

    new_campaign = Campaign(
        user_id=user.user_id,
        name=final_name,
        subject=str(data.get("subject") or "")[:300],
        body=str(data.get("body") or ""),
        body_text=data.get("body_text"),
        from_name=data.get("from_name"),
        list_id=list_id,
        account_ids=account_ids,
        suppression_list_ids=dne_ids,
        send_range_mode=str(data.get("send_range_mode") or "all"),
        send_range_start=data.get("send_range_start"),
        send_range_end=data.get("send_range_end"),
        add_unsubscribe_footer=bool(data.get("add_unsubscribe_footer", False)),
        status="draft",
    )
    doc = new_campaign.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    # Preserve tracking flags if present
    if "tracking_opens" in data:
        doc["tracking_opens"] = bool(data["tracking_opens"])
    if "tracking_clicks" in data:
        doc["tracking_clicks"] = bool(data["tracking_clicks"])
    await db.campaigns.insert_one(doc)
    return {
        "campaign_id": new_campaign.campaign_id,
        "name": final_name,
        "status": "draft",
        "list_matched": bool(list_id),
        "accounts_matched": len(account_ids),
        "dne_lists_matched": len(dne_ids),
    }


@api_router.post("/campaigns/{campaign_id}/convert-to-drip")
async def convert_campaign_to_drip(campaign_id: str, user: User = Depends(get_current_user)):
    """Convert a normal campaign into a draft drip campaign. The original campaign is
    NEVER modified or deleted. The new drip has one step (Step 1) carrying the original
    subject/body, plus mapped from_name, account_ids, suppression_list_ids and tracking
    flags. Schedule settings are seeded with sensible defaults.
    """
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id}, {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    base_name = campaign.get("name") or "Untitled"
    new_name = await _unique_drip_name(user.user_id, f"{base_name} (Drip)")
    new_drip_id = f"drip_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    step_one = {
        "step_number": 1,
        "subject": campaign.get("subject", ""),
        "body": campaign.get("body", ""),
        "body_text": campaign.get("body_text"),
        "delay_days": 0,
        "delay_hours": 0,
    }
    schedule = {
        "timezone": campaign.get("timezone") or "UTC",
        "sending_days": [0, 1, 2, 3, 4],
        "start_time": "09:00",
        "end_time": "18:00",
        "randomize_time": False,
    }
    new_doc = {
        "drip_id": new_drip_id,
        "user_id": user.user_id,
        "name": new_name,
        "from_name": campaign.get("from_name"),
        "account_ids": list(campaign.get("account_ids") or []),
        "steps": [step_one],
        "schedule": schedule,
        "stop_on_reply": True,
        "stop_on_bounce": True,
        "suppression_list_ids": list(campaign.get("suppression_list_ids") or []),
        "tracking_opens": bool(campaign.get("tracking_opens", True)),
        "tracking_clicks": bool(campaign.get("tracking_clicks", True)),
        "add_unsubscribe_footer": bool(campaign.get("add_unsubscribe_footer", False)),
        "status": "draft",
        "total_sent": 0,
        "total_contacts": 0,
        "started_at": None,
        "completed_at": None,
        "paused_at": None,
        "created_at": now_iso,
        "updated_at": now_iso,
        "source_campaign_id": campaign_id,
    }
    await db.drip_campaigns.insert_one(new_doc)
    return {
        "drip_id": new_drip_id,
        "name": new_name,
        "status": "draft",
        "source_campaign_id": campaign_id,
    }


@api_router.get("/drip-campaigns/{drip_id}/export")
async def export_drip_campaign(drip_id: str, user: User = Depends(get_current_user)):
    """Export a single drip campaign as JSON (no recipient progress, sent logs, analytics)."""
    drip = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id}, {"_id": 0}
    )
    if not drip:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    payload = {
        "schema_version": ROUTEMAIL_EXPORT_VERSION,
        "type": "drip_campaign",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "drip": {
            "name": drip.get("name", "Untitled Drip"),
            "from_name": drip.get("from_name"),
            "list_name": await _resolve_list_name(user.user_id, drip.get("list_id")),
            "account_emails": await _resolve_account_emails(user.user_id, drip.get("account_ids") or []),
            "dne_list_names": await _resolve_dne_names(user.user_id, drip.get("suppression_list_ids") or []),
            "steps": [
                {
                    "step_number": s.get("step_number"),
                    "subject": s.get("subject", ""),
                    "body": s.get("body", ""),
                    "body_text": s.get("body_text"),
                    "delay_days": int(s.get("delay_days", 0) or 0),
                    "delay_hours": int(s.get("delay_hours", 0) or 0),
                }
                for s in (drip.get("steps") or [])
            ],
            "schedule": dict(drip.get("schedule") or {}),
            "stop_on_reply": bool(drip.get("stop_on_reply", True)),
            "stop_on_bounce": bool(drip.get("stop_on_bounce", True)),
            "tracking_opens": bool(drip.get("tracking_opens", True)),
            "tracking_clicks": bool(drip.get("tracking_clicks", True)),
            "add_unsubscribe_footer": bool(drip.get("add_unsubscribe_footer", False)),
            "created_at": drip.get("created_at"),
        },
    }
    fname = f"routemail-drip-{(drip.get('name') or 'export').replace(' ', '_')[:48]}.json"
    return Response(
        content=json.dumps(payload, indent=2, default=str),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@api_router.post("/drip-campaigns/import")
async def import_drip_campaign(payload: Dict[str, Any] = Body(...), user: User = Depends(get_current_user)):
    """Import a drip campaign payload. Always saved as DRAFT."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    if payload.get("type") and payload.get("type") != "drip_campaign":
        raise HTTPException(status_code=400, detail="This file is not a drip campaign export")
    data = payload.get("drip") or payload
    name = (data.get("name") or "Imported Drip").strip()[:140] or "Imported Drip"
    final_name = await _unique_drip_name(user.user_id, name)

    # Resolve accounts by email
    account_ids: List[str] = []
    for em in (data.get("account_emails") or []):
        acct = await db.email_accounts.find_one(
            {"user_id": user.user_id, "email": (em or "").strip().lower()},
            {"_id": 0, "account_id": 1},
        )
        if acct:
            account_ids.append(acct["account_id"])
    # Resolve DNE lists by name
    dne_ids: List[str] = []
    for nm in (data.get("dne_list_names") or []):
        d = await db.dne_lists.find_one(
            {"user_id": user.user_id, "name": nm}, {"_id": 0, "list_id": 1}
        )
        if d:
            dne_ids.append(d["list_id"])

    # Normalise steps
    raw_steps = data.get("steps") or []
    steps: List[Dict[str, Any]] = []
    for i, s in enumerate(raw_steps, start=1):
        if not isinstance(s, dict):
            continue
        steps.append({
            "step_number": int(s.get("step_number") or i),
            "subject": str(s.get("subject") or "")[:300],
            "body": str(s.get("body") or ""),
            "body_text": s.get("body_text"),
            "delay_days": int(s.get("delay_days") or 0),
            "delay_hours": int(s.get("delay_hours") or 0),
        })
    if not steps:
        raise HTTPException(status_code=400, detail="Imported drip must have at least one step")

    new_drip_id = f"drip_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    schedule = dict(data.get("schedule") or {})
    # Defensive defaults
    schedule.setdefault("timezone", "UTC")
    schedule.setdefault("sending_days", [0, 1, 2, 3, 4])
    schedule.setdefault("start_time", "09:00")
    schedule.setdefault("end_time", "18:00")
    schedule.setdefault("randomize_time", False)

    doc = {
        "drip_id": new_drip_id,
        "user_id": user.user_id,
        "name": final_name,
        "from_name": data.get("from_name"),
        "account_ids": account_ids,
        "steps": steps,
        "schedule": schedule,
        "stop_on_reply": bool(data.get("stop_on_reply", True)),
        "stop_on_bounce": bool(data.get("stop_on_bounce", True)),
        "suppression_list_ids": dne_ids,
        "tracking_opens": bool(data.get("tracking_opens", True)),
        "tracking_clicks": bool(data.get("tracking_clicks", True)),
        "add_unsubscribe_footer": bool(data.get("add_unsubscribe_footer", False)),
        "status": "draft",
        "total_sent": 0,
        "total_contacts": 0,
        "started_at": None,
        "completed_at": None,
        "paused_at": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.drip_campaigns.insert_one(doc)
    return {
        "drip_id": new_drip_id,
        "name": final_name,
        "status": "draft",
        "steps_imported": len(steps),
        "accounts_matched": len(account_ids),
        "dne_lists_matched": len(dne_ids),
    }


@api_router.post("/campaigns/test-email/preview")
async def preview_test_email(request: TestEmailPreviewRequest, user: User = Depends(get_current_user)):  # noqa: ARG001
    """Render subject + body against the supplied recipient data so the UI
    can show exactly what the recipient will see — never sends an email.
    Honours the same empty-subject => "Re: <prior_subject>" rule as the
    actual drip worker, so previews stay truthful for follow-up steps."""
    raw_subject = (request.subject or "").strip()
    prior_subject = (request.prior_subject or "").strip()
    data = request.recipient_data or {}
    fallbacks = request.variable_fallbacks or {}
    from template_render import render_template as _render

    if raw_subject:
        rendered_subject = _render(raw_subject, data, fallbacks=fallbacks)
    elif prior_subject:
        rendered_prior = _render(prior_subject, data, fallbacks=fallbacks).strip()
        rendered_subject = rendered_prior if rendered_prior.lower().startswith("re:") else f"Re: {rendered_prior}"
    else:
        rendered_subject = ""

    rendered_body = _render(request.body or "", data, fallbacks=fallbacks)
    # Surface any variables that couldn't be resolved so the UI can warn.
    from template_render import extract_template_variables, _lookup as _tpl_lookup  # type: ignore
    referenced = extract_template_variables(request.subject or "") | extract_template_variables(request.body or "")
    unresolved = sorted(v for v in referenced if _tpl_lookup(data, v) is None and v not in {"unsubscribe_url"})
    return {
        "rendered_subject": rendered_subject,
        "rendered_body": rendered_body,
        "is_threaded_reply": not raw_subject and bool(prior_subject),
        "unresolved_variables": unresolved,
    }


@api_router.post("/campaigns/send-test")
async def send_test_email(request: SendTestEmailRequest, user: User = Depends(get_current_user)):
    """Send a test email preview without affecting campaign stats.

    For drip step-2-and-beyond, callers may pass an empty subject — we
    auto-substitute "Re: <prior_subject>" so the rendered preview matches
    what the actual drip send will produce. Callers pass the prior subject
    via ``request.prior_subject`` (rendered against the same contact).
    """
    
    # Resolve the effective subject. Empty subject is allowed when the
    # caller supplied a `prior_subject` — that's the "continue the same
    # thread" use case.
    raw_subject = (request.subject or "").strip()
    prior_subject = (getattr(request, "prior_subject", None) or "").strip()
    if not raw_subject:
        if prior_subject:
            raw_subject = prior_subject if prior_subject.lower().startswith("re:") else f"Re: {prior_subject}"
        else:
            raise HTTPException(status_code=400, detail="Subject line is required")
    
    if not request.body or not request.body.strip():
        raise HTTPException(status_code=400, detail="Email body is required")
    
    # Get specific account if account_id provided, otherwise get first connected account
    if request.account_id:
        account = await db.email_accounts.find_one(
            {"user_id": user.user_id, "account_id": request.account_id, "status": "connected"},
            {"_id": 0}
        )
        if not account:
            raise HTTPException(status_code=400, detail="Selected account not found or not connected.")
    else:
        account = await db.email_accounts.find_one(
            {"user_id": user.user_id, "status": "connected"},
            {"_id": 0}
        )
    
    if not account:
        raise HTTPException(status_code=400, detail="No connected email account found. Please add an account first.")
    
    # Check that account has SMTP credentials (field is smtp_password_encrypted in DB)
    if not account.get("smtp_password_encrypted") or not account.get("smtp_host"):
        raise HTTPException(status_code=400, detail="Selected account is not configured for sending. Please check your SMTP settings.")
    
    # Get user info for from_name
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    from_name = request.from_name or user_doc.get("name") or account.get("display_name") or "Test"
    
    # Decrypt credentials
    try:
        smtp_password = decrypt_data(account["smtp_password_encrypted"])
        if not smtp_password:
            raise ValueError("Empty password after decryption")
    except Exception as e:
        logger.error(f"Failed to decrypt account credentials: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to decrypt account credentials. Please re-add your email account.")
    
    # Prepare email content with test indicator
    test_subject = f"[TEST] {raw_subject}"
    body_html = request.body
    
    # Merge {{variables}} from a selected contact row, if provided.
    if request.recipient_data:
        try:
            test_subject = f"[TEST] {replace_variables(raw_subject, request.recipient_data)}"
            body_html = replace_variables(request.body, request.recipient_data)
        except Exception as e:
            logger.warning(f"send-test variable merge failed: {e}")
    
    # Add test banner to email body
    test_banner = """
    <div style="background-color: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 12px; margin-bottom: 20px; text-align: center;">
        <strong style="color: #92400e;">🧪 TEST EMAIL</strong>
        <p style="color: #78350f; margin: 4px 0 0 0; font-size: 13px;">This is a test preview. Campaign stats are not affected.</p>
    </div>
    """
    test_body = test_banner + body_html
    
    # Create email message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = test_subject
    msg['From'] = f"{from_name} <{account['email']}>"
    msg['To'] = request.test_email
    
    # Plain text version
    plain_text = re.sub('<[^<]+?>', '', body_html)
    part1 = MIMEText(plain_text, 'plain')
    part2 = MIMEText(test_body, 'html')
    msg.attach(part1)
    msg.attach(part2)
    
    # Send via SMTP
    server = None
    try:
        smtp_host = account.get("smtp_host")
        smtp_port = account.get("smtp_port", 587)
        smtp_username = account.get("smtp_username") or account.get("email")
        encryption = account.get("smtp_encryption", "tls")
        
        logger.info(f"Connecting to SMTP: {smtp_host}:{smtp_port} (encryption: {encryption})")
        
        if encryption == "ssl":
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
            server.starttls()
        
        server.login(smtp_username, smtp_password)
        server.sendmail(account['email'], request.test_email, msg.as_string())
        
        logger.info(f"Test email sent successfully to {request.test_email} from {account['email']}")
        
        return {
            "success": True,
            "message": f"Test email sent successfully to {request.test_email}",
            "from_account": account["email"]
        }
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {str(e)}")
        raise HTTPException(status_code=400, detail="SMTP authentication failed. Please check your email account credentials.")
    except smtplib.SMTPConnectError as e:
        logger.error(f"SMTP connection failed: {str(e)}")
        raise HTTPException(status_code=400, detail="Could not connect to email server. Please check your SMTP settings.")
    except smtplib.SMTPRecipientsRefused as e:
        logger.error(f"Recipient refused: {str(e)}")
        raise HTTPException(status_code=400, detail="The test email address was rejected by the server.")
    except Exception as e:
        logger.error(f"Failed to send test email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send test email: {str(e)}")
    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass

@api_router.post("/campaigns/{campaign_id}/preflight")
async def preflight_campaign(campaign_id: str, user: User = Depends(get_current_user)):
    """Pre-send validation — flag unresolved variables before launch."""
    from template_render import analyse_contacts
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id},
        {"_id": 0},
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    contacts: List[Dict[str, Any]] = []
    if campaign.get("list_id"):
        contacts = await db.email_list_contacts.find(
            {"list_id": campaign["list_id"], "user_id": user.user_id, "is_valid": True},
            {"_id": 0},
        ).limit(2000).to_list(2000)
    result = analyse_contacts(
        [campaign.get("subject", ""), campaign.get("body", ""), campaign.get("body_text", "") or ""],
        contacts,
    )
    return result


@api_router.post("/drip-campaigns/{drip_id}/preflight")
async def preflight_drip(drip_id: str, user: User = Depends(get_current_user)):
    """Pre-send validation for a drip campaign — checks every step."""
    from template_render import analyse_contacts
    drip = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id},
        {"_id": 0},
    )
    if not drip:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    contacts = await db.drip_contacts.find(
        {"drip_id": drip_id, "user_id": user.user_id},
        {"_id": 0},
    ).limit(2000).to_list(2000)
    template_parts: List[str] = []
    for step in (drip.get("steps") or []):
        template_parts.append(step.get("subject", "") or "")
        template_parts.append(step.get("body", "") or "")
    result = analyse_contacts(template_parts, contacts)
    return result


@api_router.post("/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: str, background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """Start a campaign"""
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign["status"] == "running":
        raise HTTPException(status_code=400, detail="Campaign is already running")
    
    if campaign["status"] == "completed":
        raise HTTPException(status_code=400, detail="Campaign is already completed. Duplicate it to send again.")
    
    # Validate campaign
    if not campaign.get("list_id"):
        raise HTTPException(status_code=400, detail="No email list selected")
    
    if not campaign.get("subject"):
        raise HTTPException(status_code=400, detail="Subject line is required")
    
    if not campaign.get("body"):
        raise HTTPException(status_code=400, detail="Email body is required")
    
    # Get email accounts
    account_ids = campaign.get("account_ids", [])
    if not account_ids:
        accounts = await db.email_accounts.find(
            {"user_id": user.user_id, "status": "connected"},
            {"_id": 0}
        ).to_list(100)
        account_ids = [a["account_id"] for a in accounts]
    else:
        accounts = await db.email_accounts.find(
            {"user_id": user.user_id, "account_id": {"$in": account_ids}, "status": "connected"},
            {"_id": 0}
        ).to_list(100)
        account_ids = [a["account_id"] for a in accounts]
    
    if not accounts:
        raise HTTPException(status_code=400, detail="No connected email accounts available. Please add at least one account.")
    
    # Get email list
    email_list = await db.email_lists.find_one(
        {"list_id": campaign["list_id"], "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not email_list:
        raise HTTPException(status_code=404, detail="Email list not found")
    
    if not email_list.get("emails") or len(email_list["emails"]) == 0:
        raise HTTPException(status_code=400, detail="Email list is empty")
    
    # Check for existing queue (prevent duplicate creation)
    existing_queue = await db.email_queue.count_documents({"campaign_id": campaign_id})
    
    if existing_queue == 0:
        # Apply send-range filter (if user picked 'range' instead of 'all')
        all_emails = email_list["emails"]
        send_mode = campaign.get("send_range_mode", "all")
        if send_mode == "range":
            start = campaign.get("send_range_start") or 1
            end = campaign.get("send_range_end") or len(all_emails)
            try:
                start = max(1, int(start))
                end = min(len(all_emails), int(end))
            except (TypeError, ValueError):
                start, end = 1, len(all_emails)
            if start > end:
                raise HTTPException(status_code=400, detail="Send-range start must be <= end")
            selected_emails = all_emails[start - 1:end]
        else:
            selected_emails = all_emails
        
        queue_items = []
        for email_data in selected_emails:
            item = EmailQueueItem(
                campaign_id=campaign_id,
                user_id=user.user_id,
                recipient_email=email_data.get("email", ""),
                recipient_data=email_data
            )
            item_dict = item.model_dump()
            queue_items.append(item_dict)
        
        if queue_items:
            await db.email_queue.insert_many(queue_items)
        
        # Update total_emails to reflect what we'll actually send
        await db.campaigns.update_one(
            {"campaign_id": campaign_id},
            {"$set": {"total_emails": len(queue_items)}}
        )
    
    # Update campaign status and lock it
    await db.campaigns.update_one(
        {"campaign_id": campaign_id},
        {"$set": {
            "status": "running",
            "is_locked": True,
            "account_ids": account_ids,
            "scheduled_at": None,  # Clear scheduled_at when started immediately
            "started_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Start background task
    background_tasks.add_task(process_campaign_queue, campaign_id, user.user_id)
    
    return {"message": "Campaign started", "status": "running", "campaign_id": campaign_id}

@api_router.post("/campaigns/{campaign_id}/schedule")
async def schedule_campaign(campaign_id: str, user: User = Depends(get_current_user)):
    """Schedule a campaign (validate and set status to scheduled)"""
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign["status"] == "running":
        raise HTTPException(status_code=400, detail="Campaign is already running")
    
    if campaign["status"] == "completed":
        raise HTTPException(status_code=400, detail="Campaign is already completed")
    
    if not campaign.get("scheduled_at"):
        raise HTTPException(status_code=400, detail="No scheduled time set")
    
    # Validate campaign has required fields
    if not campaign.get("list_id"):
        raise HTTPException(status_code=400, detail="No email list selected")
    
    if not campaign.get("subject"):
        raise HTTPException(status_code=400, detail="Subject line is required")
    
    if not campaign.get("body"):
        raise HTTPException(status_code=400, detail="Email body is required")
    
    # Validate email accounts
    account_ids = campaign.get("account_ids", [])
    if not account_ids:
        accounts = await db.email_accounts.find(
            {"user_id": user.user_id, "status": "connected"},
            {"_id": 0}
        ).to_list(100)
        if not accounts:
            raise HTTPException(status_code=400, detail="No connected email accounts available")
    
    # Update status to scheduled
    await db.campaigns.update_one(
        {"campaign_id": campaign_id},
        {"$set": {
            "status": "scheduled",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return {"message": "Campaign scheduled", "status": "scheduled", "scheduled_at": campaign.get("scheduled_at")}

@api_router.post("/campaigns/{campaign_id}/unschedule")
async def unschedule_campaign(campaign_id: str, user: User = Depends(get_current_user)):
    """Unschedule a scheduled campaign (return to draft)"""
    result = await db.campaigns.update_one(
        {"campaign_id": campaign_id, "user_id": user.user_id, "status": "scheduled"},
        {"$set": {
            "status": "draft",
            "scheduled_at": None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Campaign not found or not scheduled")
    
    return {"message": "Campaign unscheduled", "status": "draft"}

@api_router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str, user: User = Depends(get_current_user)):
    """Pause a running or scheduled campaign"""
    # Find the campaign first
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    current_status = campaign.get("status")
    
    # Only allow pausing running or scheduled campaigns
    if current_status not in ["running", "scheduled"]:
        raise HTTPException(status_code=400, detail=f"Cannot pause campaign with status '{current_status}'. Only running or scheduled campaigns can be paused.")
    
    # Store the previous status so we know what to resume to
    previous_status = current_status
    
    result = await db.campaigns.update_one(
        {"campaign_id": campaign_id, "user_id": user.user_id},
        {"$set": {
            "status": "paused",
            "paused_at": datetime.now(timezone.utc).isoformat(),
            "previous_status": previous_status,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Failed to pause campaign")
    
    # Log the action
    logger.info(f"[CAMPAIGN_PAUSED] User: {user.email} | Campaign: {campaign_id} | Previous status: {previous_status}")
    
    return {
        "success": True,
        "message": "Campaign paused successfully",
        "status": "paused",
        "previous_status": previous_status
    }

@api_router.post("/campaigns/{campaign_id}/resume")
async def resume_campaign(campaign_id: str, background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """Resume a paused campaign"""
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id, "status": {"$in": ["paused", "paused_daily_limit"]}},
        {"_id": 0}
    )
    
    if not campaign:
        raise HTTPException(status_code=400, detail="Campaign not found or not paused")
    
    # Get the previous status to determine how to resume
    previous_status = campaign.get("previous_status", "running")
    
    # Update status to running (we always resume as running, even if it was scheduled before)
    await db.campaigns.update_one(
        {"campaign_id": campaign_id},
        {"$set": {
            "status": "running",
            "resumed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        },
        "$unset": {
            "paused_at": "",
            "previous_status": ""
        }}
    )
    
    # Log the action
    logger.info(f"[CAMPAIGN_RESUMED] User: {user.email} | Campaign: {campaign_id} | Previous status: {previous_status}")
    
    # Start processing the campaign queue
    background_tasks.add_task(process_campaign_queue, campaign_id, user.user_id)
    
    return {
        "success": True,
        "message": "Campaign resumed successfully",
        "status": "running"
    }

@api_router.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str, user: User = Depends(get_current_user)):
    """Delete a campaign"""
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign["status"] == "running":
        raise HTTPException(status_code=400, detail="Cannot delete running campaign. Pause it first.")
    
    await db.email_queue.delete_many({"campaign_id": campaign_id})
    await db.campaigns.delete_one({"campaign_id": campaign_id})
    
    return {"message": "Campaign deleted"}

# ==================== DRIP CAMPAIGNS ====================

@api_router.get("/drip-campaigns")
async def list_drip_campaigns(user: User = Depends(get_current_user)):
    """List all drip campaigns for the current user"""
    campaigns = await db.drip_campaigns.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    if campaigns:
        folder_ids = {c.get("folder_id") for c in campaigns if c.get("folder_id")}
        folder_name_by_id: Dict[str, str] = {}
        if folder_ids:
            async for f in db.lead_folders.find(
                {"user_id": user.user_id, "folder_id": {"$in": list(folder_ids)}},
                {"_id": 0, "folder_id": 1, "name": 1},
            ):
                folder_name_by_id[f["folder_id"]] = f["name"]
        for c in campaigns:
            did = c.get("drip_id")
            c["folder_name"] = folder_name_by_id.get(c.get("folder_id") or "")
            c["reply_count"] = await db.replies.count_documents(
                {"user_id": user.user_id, "drip_campaign_id": did}
            )
            c["lead_count"] = await db.leads.count_documents(
                {"user_id": user.user_id, "source_drip_id": did}
            )
    return campaigns

@api_router.post("/drip-campaigns")
async def create_drip_campaign(request: CreateDripCampaignRequest, user: User = Depends(get_current_user)):
    """Create a new drip campaign (in draft)"""
    drip_id = f"drip_{uuid.uuid4().hex[:12]}"
    
    # Normalize step numbers
    steps = []
    for idx, step in enumerate(request.steps):
        step_dict = step.model_dump()
        step_dict["step_number"] = idx + 1
        steps.append(step_dict)
    
    campaign = {
        "drip_id": drip_id,
        "user_id": user.user_id,
        "name": request.name,
        "from_name": request.from_name,
        "account_ids": request.account_ids,
        "steps": steps,
        "schedule": request.schedule.model_dump(),
        "stop_on_reply": request.stop_on_reply,
        "stop_on_bounce": request.stop_on_bounce,
        "suppression_list_ids": request.suppression_list_ids,
        "status": "draft",  # draft, running, paused, completed
        "total_sent": 0,
        "total_contacts": 0,
        "folder_id": await _ensure_default_folder_id(user.user_id, request.folder_id),
        "variable_fallbacks": request.variable_fallbacks or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.drip_campaigns.insert_one(campaign)
    campaign.pop("_id", None)
    return campaign

@api_router.get("/drip-campaigns/{drip_id}")
async def get_drip_campaign(drip_id: str, user: User = Depends(get_current_user)):
    """Get drip campaign with live stats"""
    campaign = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    
    # Get per-status contact counts
    active_count = await db.drip_contacts.count_documents({"drip_id": drip_id, "status": "active"})
    completed_count = await db.drip_contacts.count_documents({"drip_id": drip_id, "status": "completed"})
    replied_count = await db.drip_contacts.count_documents({"drip_id": drip_id, "status": "replied"})
    bounced_count = await db.drip_contacts.count_documents({"drip_id": drip_id, "status": "bounced"})
    suppressed_count = await db.drip_contacts.count_documents({"drip_id": drip_id, "status": "suppressed"})
    total_contacts = await db.drip_contacts.count_documents({"drip_id": drip_id})
    sent_logs = await db.drip_logs.count_documents({"drip_id": drip_id, "status": "sent"})
    failed_logs = await db.drip_logs.count_documents({"drip_id": drip_id, "status": "failed"})
    suppressed_logs = await db.drip_logs.count_documents({"drip_id": drip_id, "status": "suppressed"})
    
    campaign["stats"] = {
        "total_contacts": total_contacts,
        "active": active_count,
        "completed": completed_count,
        "replied": replied_count,
        "bounced": bounced_count,
        "suppressed": suppressed_count,
        "emails_sent": sent_logs,
        "emails_failed": failed_logs,
        "emails_suppressed": suppressed_logs,
    }
    return campaign

@api_router.put("/drip-campaigns/{drip_id}")
async def update_drip_campaign(drip_id: str, request: UpdateDripCampaignRequest, user: User = Depends(get_current_user)):
    """Update a drip campaign (draft or paused only)"""
    campaign = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    
    if campaign["status"] == "running":
        raise HTTPException(status_code=400, detail="Pause the campaign before editing")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if request.name is not None:
        update_data["name"] = request.name
    if request.from_name is not None:
        update_data["from_name"] = request.from_name
    if request.account_ids is not None:
        update_data["account_ids"] = request.account_ids
    if request.steps is not None:
        steps = []
        for idx, step in enumerate(request.steps):
            step_dict = step.model_dump()
            step_dict["step_number"] = idx + 1
            steps.append(step_dict)
        update_data["steps"] = steps
    if request.schedule is not None:
        update_data["schedule"] = request.schedule.model_dump()
    if request.stop_on_reply is not None:
        update_data["stop_on_reply"] = request.stop_on_reply
    if request.stop_on_bounce is not None:
        update_data["stop_on_bounce"] = request.stop_on_bounce
    if request.suppression_list_ids is not None:
        update_data["suppression_list_ids"] = request.suppression_list_ids
    if request.folder_id is not None:
        update_data["folder_id"] = await _ensure_default_folder_id(user.user_id, request.folder_id)
    if request.variable_fallbacks is not None:
        update_data["variable_fallbacks"] = request.variable_fallbacks or {}

    await db.drip_campaigns.update_one({"drip_id": drip_id}, {"$set": update_data})
    return {"message": "Drip campaign updated", "drip_id": drip_id}


class RenameDripCampaignRequest(BaseModel):
    name: str


@api_router.post("/drip-campaigns/{drip_id}/rename")
async def rename_drip_campaign(drip_id: str, request: RenameDripCampaignRequest, user: User = Depends(get_current_user)):
    """Rename a drip campaign. Only updates the name — never the sequence, schedule, logs, analytics, or campaign_id."""
    new_name = (request.name or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Campaign name cannot be blank")
    campaign = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id}, {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    # Uniqueness within the user's drip campaigns
    clash = await db.drip_campaigns.find_one(
        {
            "user_id": user.user_id,
            "name": new_name,
            "drip_id": {"$ne": drip_id},
        },
        {"_id": 0, "drip_id": 1},
    )
    if clash:
        raise HTTPException(status_code=400, detail="A drip campaign with this name already exists")
    await db.drip_campaigns.update_one(
        {"drip_id": drip_id, "user_id": user.user_id},
        {"$set": {"name": new_name, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"drip_id": drip_id, "name": new_name}


@api_router.post("/drip-campaigns/{drip_id}/duplicate")
async def duplicate_drip_campaign(drip_id: str, user: User = Depends(get_current_user)):
    """Duplicate an existing drip campaign as a fresh draft. Never copies analytics, logs, or recipient progress."""
    campaign = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id}, {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    new_drip_id = f"drip_{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    new_doc = {
        "drip_id": new_drip_id,
        "user_id": user.user_id,
        "name": f"{campaign.get('name', 'Untitled')} (Copy)",
        "from_name": campaign.get("from_name"),
        "account_ids": list(campaign.get("account_ids") or []),
        "steps": [dict(s) for s in (campaign.get("steps") or [])],
        "schedule": dict(campaign.get("schedule") or {}),
        "stop_on_reply": campaign.get("stop_on_reply", True),
        "stop_on_bounce": campaign.get("stop_on_bounce", True),
        "suppression_list_ids": list(campaign.get("suppression_list_ids") or []),
        "tracking_opens": campaign.get("tracking_opens", True),
        "tracking_clicks": campaign.get("tracking_clicks", True),
        "add_unsubscribe_footer": campaign.get("add_unsubscribe_footer", False),
        # Reset everything operational
        "status": "draft",
        "total_sent": 0,
        "total_contacts": 0,
        "started_at": None,
        "completed_at": None,
        "paused_at": None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.drip_campaigns.insert_one(new_doc)
    return {"drip_id": new_drip_id, "status": "draft", "name": new_doc["name"]}


@api_router.delete("/drip-campaigns/{drip_id}")
async def delete_drip_campaign(drip_id: str, user: User = Depends(get_current_user)):
    """Delete drip campaign plus its contacts and logs"""
    campaign = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    
    if campaign["status"] == "running":
        raise HTTPException(status_code=400, detail="Pause the campaign before deleting")
    
    await db.drip_contacts.delete_many({"drip_id": drip_id})
    await db.drip_logs.delete_many({"drip_id": drip_id})
    await db.drip_campaigns.delete_one({"drip_id": drip_id})
    return {"message": "Drip campaign deleted"}

@api_router.post("/drip-campaigns/{drip_id}/contacts")
async def add_drip_contacts(drip_id: str, request: AddDripContactsRequest, user: User = Depends(get_current_user)):
    """Enroll contacts from an email list into the drip campaign"""
    campaign = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    
    email_list = await db.email_lists.find_one(
        {"list_id": request.list_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not email_list:
        raise HTTPException(status_code=404, detail="Email list not found")
    
    # Build contact records; skip duplicates already enrolled
    existing_emails = set()
    existing_cursor = db.drip_contacts.find(
        {"drip_id": drip_id},
        {"_id": 0, "email": 1}
    )
    async for doc in existing_cursor:
        existing_emails.add(doc.get("email", "").lower())
    
    # Apply send-range filter on the source list rows
    all_rows = email_list.get("emails", [])
    send_mode = (request.send_range_mode or "all").lower()
    if send_mode == "range":
        start = max(1, int(request.send_range_start or 1))
        end = min(len(all_rows), int(request.send_range_end or len(all_rows)))
        if start > end:
            selected_rows = []
        else:
            selected_rows = all_rows[start - 1:end]
    else:
        selected_rows = all_rows
    
    new_docs = []
    skipped = 0
    for row in selected_rows:
        email_addr = (row.get("email") or "").strip().lower()
        if not email_addr or email_addr in existing_emails:
            skipped += 1
            continue
        existing_emails.add(email_addr)
        new_docs.append({
            "contact_id": f"dc_{uuid.uuid4().hex[:12]}",
            "drip_id": drip_id,
            "user_id": user.user_id,
            "email": email_addr,
            "data": row,
            "current_step": 0,
            "status": "active",
            "next_send_at": datetime.now(timezone.utc).isoformat(),  # first step eligible immediately
            "enrolled_at": datetime.now(timezone.utc).isoformat(),
        })
    
    if new_docs:
        await db.drip_contacts.insert_many(new_docs)
    
    total_contacts = await db.drip_contacts.count_documents({"drip_id": drip_id})
    await db.drip_campaigns.update_one(
        {"drip_id": drip_id},
        {"$set": {"total_contacts": total_contacts, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {
        "added": len(new_docs),
        "skipped_duplicates": skipped,
        "total_contacts": total_contacts,
    }

@api_router.get("/drip-campaigns/{drip_id}/contacts")
async def list_drip_contacts(
    drip_id: str,
    user: User = Depends(get_current_user),
    status: Optional[str] = Query(None),
    skip: int = Query(0),
    limit: int = Query(50),
):
    """List contacts enrolled in a drip campaign"""
    campaign = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    
    query = {"drip_id": drip_id}
    if status:
        query["status"] = status
    
    contacts = await db.drip_contacts.find(
        query, {"_id": 0}
    ).sort("enrolled_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.drip_contacts.count_documents(query)
    
    return {"contacts": contacts, "total": total, "skip": skip, "limit": limit}

@api_router.get("/drip-campaigns/{drip_id}/logs")
async def list_drip_logs(
    drip_id: str,
    user: User = Depends(get_current_user),
    status: Optional[str] = Query(None),
    skip: int = Query(0),
    limit: int = Query(50),
):
    """List send logs for a drip campaign"""
    campaign = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    
    query = {"drip_id": drip_id}
    if status:
        query["status"] = status
    
    logs = await db.drip_logs.find(
        query, {"_id": 0}
    ).sort("sent_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.drip_logs.count_documents(query)
    
    return {"logs": logs, "total": total, "skip": skip, "limit": limit}

@api_router.get("/drip-campaigns/{drip_id}/logs/export")
async def export_drip_logs(drip_id: str, user: User = Depends(get_current_user)):
    """Export drip logs as CSV"""
    campaign = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    
    logs = await db.drip_logs.find(
        {"drip_id": drip_id}, {"_id": 0}
    ).sort("sent_at", -1).to_list(10000)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Recipient", "Step", "Subject", "Sent From", "Status", "Sent At", "Error"])
    for log in logs:
        writer.writerow([
            log.get("contact_email", ""),
            (log.get("step", 0) or 0) + 1,
            log.get("subject", ""),
            log.get("account_email", ""),
            log.get("status", ""),
            log.get("sent_at", ""),
            log.get("error", ""),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=drip_{drip_id}_logs.csv"}
    )

@api_router.post("/drip-campaigns/{drip_id}/start")
async def start_drip_campaign(drip_id: str, user: User = Depends(get_current_user)):
    """Start (or activate) a drip campaign"""
    campaign = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    
    if not campaign.get("steps"):
        raise HTTPException(status_code=400, detail="Add at least one step before starting")
    if not campaign.get("account_ids"):
        raise HTTPException(status_code=400, detail="Select at least one email account before starting")
    
    contact_count = await db.drip_contacts.count_documents({"drip_id": drip_id})
    if contact_count == 0:
        raise HTTPException(status_code=400, detail="Add contacts before starting the campaign")
    
    await db.drip_campaigns.update_one(
        {"drip_id": drip_id},
        {"$set": {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"message": "Drip campaign started", "drip_id": drip_id}

@api_router.post("/drip-campaigns/{drip_id}/pause")
async def pause_drip_campaign(drip_id: str, user: User = Depends(get_current_user)):
    """Pause a running drip campaign"""
    campaign = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    if campaign["status"] != "running":
        raise HTTPException(status_code=400, detail="Only running campaigns can be paused")
    
    await db.drip_campaigns.update_one(
        {"drip_id": drip_id},
        {"$set": {"status": "paused", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Drip campaign paused", "drip_id": drip_id}

@api_router.post("/drip-campaigns/{drip_id}/resume")
async def resume_drip_campaign(drip_id: str, user: User = Depends(get_current_user)):
    """Resume a paused drip campaign"""
    campaign = await db.drip_campaigns.find_one(
        {"drip_id": drip_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Drip campaign not found")
    if campaign["status"] != "paused":
        raise HTTPException(status_code=400, detail="Only paused campaigns can be resumed")
    
    await db.drip_campaigns.update_one(
        {"drip_id": drip_id},
        {"$set": {"status": "running", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"message": "Drip campaign resumed", "drip_id": drip_id}

# ==================== DO NOT EMAIL (DNE) ENDPOINTS ====================

@api_router.get("/dne-stats")
async def dne_stats(user: User = Depends(get_current_user)):
    """Aggregate Do Not Email counters: emails blocked vs domains blocked across all lists."""
    pipeline = [
        {"$match": {"user_id": user.user_id}},
        {"$group": {"_id": {"$ifNull": ["$type", "email"]}, "count": {"$sum": 1}}},
    ]
    by_type = {row["_id"]: row["count"] async for row in db.dne_emails.aggregate(pipeline)}
    return {
        "emails_blocked": int(by_type.get("email", 0)),
        "domains_blocked": int(by_type.get("domain", 0)),
        "total_blocked": int(by_type.get("email", 0)) + int(by_type.get("domain", 0)),
    }

@api_router.get("/dne-lists")
async def list_dne_lists(user: User = Depends(get_current_user)):
    """List all Do Not Email lists for the current user (global first)."""
    await ensure_global_dne_list(user.user_id)  # lazy-create on first access
    lists = await db.dne_lists.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(500)
    globals_ = [item for item in lists if item.get("is_global")]
    others = sorted(
        [item for item in lists if not item.get("is_global")],
        key=lambda x: x.get("created_at", ""),
        reverse=True,
    )
    return globals_ + others

@api_router.post("/dne-lists")
async def create_dne_list(request: CreateDNEListRequest, user: User = Depends(get_current_user)):
    """Create a new (non-global) DNE list."""
    name = (request.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    
    new_list = DNEList(user_id=user.user_id, name=name, is_global=False).model_dump()
    new_list["created_at"] = new_list["created_at"].isoformat()
    await db.dne_lists.insert_one(new_list)
    new_list.pop("_id", None)
    return new_list

@api_router.get("/dne-lists/{list_id}")
async def get_dne_list(
    list_id: str,
    user: User = Depends(get_current_user),
    skip: int = Query(0),
    limit: int = Query(100),
    search: Optional[str] = Query(None),
):
    """Fetch DNE list metadata + a page of emails."""
    dne = await db.dne_lists.find_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not dne:
        raise HTTPException(status_code=404, detail="DNE list not found")
    
    query = {"list_id": list_id, "user_id": user.user_id}
    if search:
        query["email"] = {"$regex": re.escape(search.strip().lower())}
    
    emails = await db.dne_emails.find(
        query, {"_id": 0}
    ).sort("added_at", -1).skip(skip).limit(limit).to_list(limit)
    total = await db.dne_emails.count_documents(query)
    
    dne["emails"] = emails
    dne["total_filtered"] = total
    dne["skip"] = skip
    dne["limit"] = limit
    return dne

@api_router.post("/dne-lists/{list_id}/emails")
async def add_dne_emails(list_id: str, request: AddDNEEmailsRequest, user: User = Depends(get_current_user)):
    """Add one or more entries (email OR domain, normalised + deduped) to a DNE list.
    
    Each entry in `emails` may be:
      - A full email address (john@example.com)
      - A bare domain (example.com)
      - A leading-@ shortcut (@example.com)
    Domain entries block ALL addresses at that domain.
    """
    dne = await db.dne_lists.find_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not dne:
        raise HTTPException(status_code=404, detail="DNE list not found")
    
    seen = set()
    cleaned: List[Dict[str, str]] = []
    invalid = 0
    # Build queue from `entries` (typed) first, then `emails` (auto-detected)
    queue: List[Any] = list(request.entries or []) + list(request.emails or [])
    for raw in queue:
        if isinstance(raw, dict):
            val = (raw.get("value") or "").strip().lower().lstrip("@")
            t = (raw.get("type") or "").strip().lower() or None
            if not val:
                invalid += 1
                continue
            if t == "email" and _EMAIL_PATTERN.match(val):
                entry = {"type": "email", "value": val}
            elif t == "domain" and _DOMAIN_PATTERN.match(val):
                entry = {"type": "domain", "value": val}
            else:
                entry = classify_dne_entry(val)
        else:
            entry = classify_dne_entry(raw)
        if not entry:
            invalid += 1
            continue
        key = (entry["type"], entry["value"])
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(entry)
    
    if not cleaned:
        return {"added": 0, "skipped_duplicates": 0, "invalid": invalid, "total": dne.get("email_count", 0)}
    
    values_only = [c["value"] for c in cleaned]
    existing = await db.dne_emails.find(
        {"list_id": list_id, "email": {"$in": values_only}},
        {"_id": 0, "email": 1}
    ).to_list(len(values_only))
    already = {x["email"] for x in existing}
    
    new_docs = [{
        "user_id": user.user_id,
        "list_id": list_id,
        "email": c["value"],
        "type": c["type"],
        "source": "manual",
        "added_at": datetime.now(timezone.utc).isoformat(),
    } for c in cleaned if c["value"] not in already]
    
    if new_docs:
        try:
            await db.dne_emails.insert_many(new_docs, ordered=False)
        except Exception as ex:
            logger.warning(f"DNE insert race (ignored): {ex}")
    
    count = await db.dne_emails.count_documents({"list_id": list_id})
    await db.dne_lists.update_one(
        {"list_id": list_id},
        {"$set": {"email_count": count}}
    )
    
    return {
        "added": len(new_docs),
        "skipped_duplicates": len(already),
        "invalid": invalid,
        "total": count,
    }

@api_router.post("/dne-lists/{list_id}/upload")
async def upload_dne_emails(
    list_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Upload a CSV / Excel file and add all valid emails to the DNE list."""
    import pandas as pd
    
    dne = await db.dne_lists.find_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not dne:
        raise HTTPException(status_code=404, detail="DNE list not found")
    
    filename = (file.filename or "").lower()
    allowed = ['.csv', '.xlsx', '.xls']
    file_ext = next((x for x in allowed if filename.endswith(x)), None)
    if not file_ext:
        raise HTTPException(status_code=400, detail="Only CSV / Excel files are allowed")
    
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 2MB limit")
    
    emails_from_file: List[str] = []
    try:
        if file_ext == '.csv':
            text = content.decode('utf-8', errors='ignore')
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            if not rows:
                raise HTTPException(status_code=400, detail="File is empty")
            header = [h.strip().lower() for h in rows[0]]
            value_idx = None
            type_idx = header.index("type") if "type" in header else None
            start_row = 0
            # Prefer explicit columns: 'value' or 'email' or 'domain'
            for col_name in ("value", "email", "domain", "address"):
                if col_name in header:
                    value_idx = header.index(col_name)
                    start_row = 1
                    break
            if value_idx is None and len(header) == 1:
                # Single-column file — treat first row as data too
                value_idx = 0
                start_row = 0
            elif value_idx is None:
                raise HTTPException(status_code=400, detail="CSV must contain an 'email', 'domain' or 'value' column")
            for r in rows[start_row:]:
                if value_idx >= len(r):
                    continue
                raw = (r[value_idx] or "").strip()
                if not raw:
                    continue
                # If a 'type' column exists, honour it via @ shortcut for domains
                if type_idx is not None and type_idx < len(r):
                    t = (r[type_idx] or "").strip().lower()
                    if t == "domain" and "@" not in raw:
                        raw = raw.lstrip("@")
                emails_from_file.append(raw)
        else:
            try:
                df = pd.read_excel(io.BytesIO(content), engine='openpyxl' if file_ext == '.xlsx' else 'xlrd')
            except Exception:
                df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
            df.columns = [str(c).strip().lower() for c in df.columns]
            target_col = None
            for col_name in ("value", "email", "domain", "address"):
                if col_name in df.columns:
                    target_col = col_name
                    break
            if target_col is None and len(df.columns) == 1:
                target_col = df.columns[0]
            if target_col is None:
                raise HTTPException(status_code=400, detail="File must contain an 'email', 'domain' or 'value' column")
            emails_from_file = df[target_col].fillna('').astype(str).tolist()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DNE upload parse error: {e}")
        raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")
    
    result = await add_dne_emails(list_id, AddDNEEmailsRequest(emails=emails_from_file), user)
    return result

@api_router.delete("/dne-lists/{list_id}/emails")
async def remove_dne_email(list_id: str, request: RemoveDNEEmailRequest, user: User = Depends(get_current_user)):
    """Remove a single email from a DNE list."""
    dne = await db.dne_lists.find_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not dne:
        raise HTTPException(status_code=404, detail="DNE list not found")
    
    email_norm = (request.email or "").strip().lower().lstrip("@")
    res = await db.dne_emails.delete_one(
        {"list_id": list_id, "user_id": user.user_id, "email": email_norm}
    )
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Email not found in this list")
    
    count = await db.dne_emails.count_documents({"list_id": list_id})
    await db.dne_lists.update_one(
        {"list_id": list_id},
        {"$set": {"email_count": count}}
    )
    return {"message": "Email removed", "email_count": count}

@api_router.delete("/dne-lists/{list_id}")
async def delete_dne_list(list_id: str, user: User = Depends(get_current_user)):
    """Delete a DNE list (Global list cannot be deleted)."""
    dne = await db.dne_lists.find_one(
        {"list_id": list_id, "user_id": user.user_id},
        {"_id": 0}
    )
    if not dne:
        raise HTTPException(status_code=404, detail="DNE list not found")
    if dne.get("is_global"):
        raise HTTPException(status_code=400, detail="The Global Do Not Email list cannot be deleted")
    
    await db.dne_emails.delete_many({"list_id": list_id, "user_id": user.user_id})
    await db.dne_lists.delete_one({"list_id": list_id, "user_id": user.user_id})
    
    # Unlink from any campaigns / drips that referenced it
    await db.campaigns.update_many(
        {"user_id": user.user_id, "suppression_list_ids": list_id},
        {"$pull": {"suppression_list_ids": list_id}}
    )
    await db.drip_campaigns.update_many(
        {"user_id": user.user_id, "suppression_list_ids": list_id},
        {"$pull": {"suppression_list_ids": list_id}}
    )
    return {"message": "DNE list deleted"}

# ==================== BLOG ENDPOINTS ====================

async def get_super_admin_user(request: Request) -> dict:
    """Get current user and verify super_admin role.
    (Hoisted here so blog/admin endpoints defined earlier can use it as a Depends.)
    """
    user = await get_current_user(request)
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    role = user_doc.get("role", "user")
    if role != "super_admin":
        raise HTTPException(status_code=403, detail="Access denied. Super admin required.")
    return user_doc

async def get_blog_manager_user(request: Request) -> dict:
    """Allow access for super_admin OR any user with `can_manage_blogs=True`.
    Used by /admin/blogs endpoints so a delegated user can manage blogs without
    being promoted to super_admin.
    """
    user = await get_current_user(request)
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    if user_doc.get("role") == "super_admin":
        return user_doc
    if bool(user_doc.get("can_manage_blogs")):
        return user_doc
    raise HTTPException(status_code=403, detail="Access denied. Blog management permission required.")

async def get_infrastructure_user(request: Request) -> dict:
    """Allow access for super_admin OR any user with `can_access_infrastructure=True`.
    Used by /api/infrastructure/* endpoints. This is an internal-only module —
    hidden from regular users completely.
    """
    user = await get_current_user(request)
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    if user_doc.get("role") == "super_admin":
        return user_doc
    if bool(user_doc.get("can_access_infrastructure")):
        return user_doc
    raise HTTPException(status_code=403, detail="Access denied. Infrastructure module access required.")

def _slugify(text: str) -> str:
    text = re.sub(r'[^A-Za-z0-9]+', '-', (text or '').strip().lower())
    return text.strip('-') or f"post-{uuid.uuid4().hex[:6]}"

@api_router.get("/blogs/public")
async def list_public_blogs(skip: int = Query(0), limit: int = Query(20)):
    """List published blogs — public, no auth required."""
    cursor = db.blogs.find(
        {"status": "published"},
        {"_id": 0, "content": 0}  # listings don't need full content
    ).sort("published_at", -1).skip(skip).limit(min(50, max(1, limit)))
    return await cursor.to_list(50)

@api_router.get("/blogs/public/{slug}")
async def get_public_blog(slug: str):
    """Get a single published blog by slug — public, no auth required."""
    blog = await db.blogs.find_one(
        {"slug": slug, "status": "published"},
        {"_id": 0}
    )
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    return blog

@api_router.get("/admin/blogs")
async def admin_list_blogs(admin: dict = Depends(get_blog_manager_user)):
    """List all blogs (drafts + published). Open to super_admin OR users with can_manage_blogs."""
    blogs = await db.blogs.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return blogs

@api_router.post("/admin/blogs")
async def admin_create_blog(request: CreateBlogRequest, admin: dict = Depends(get_blog_manager_user)):
    """Create a new blog. Open to super_admin OR users with can_manage_blogs."""
    if not request.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Content is required")
    
    slug = (request.slug or "").strip() or _slugify(request.title)
    slug = _slugify(slug)
    # Ensure uniqueness — append suffix if needed
    base_slug = slug
    n = 2
    while await db.blogs.find_one({"slug": slug}, {"slug": 1}):
        slug = f"{base_slug}-{n}"
        n += 1
    
    status_value = request.status if request.status in ("draft", "published") else "draft"
    now = datetime.now(timezone.utc)
    blog = Blog(
        slug=slug,
        title=request.title.strip(),
        excerpt=(request.excerpt or "").strip(),
        content=request.content,
        featured_image_url=request.featured_image_url,
        author=(request.author or "RouteMail Team").strip(),
        seo_title=(request.seo_title or "").strip() or None,
        seo_description=(request.seo_description or "").strip() or None,
        status=status_value,
        published_at=now if status_value == "published" else None,
        created_by=admin["user_id"],
        created_at=now,
        updated_at=now,
    ).model_dump()
    blog["created_at"] = blog["created_at"].isoformat()
    blog["updated_at"] = blog["updated_at"].isoformat()
    if blog.get("published_at"):
        blog["published_at"] = blog["published_at"].isoformat()
    
    await db.blogs.insert_one(blog)
    blog.pop("_id", None)
    return blog

@api_router.get("/admin/blogs/{blog_id}")
async def admin_get_blog(blog_id: str, admin: dict = Depends(get_blog_manager_user)):
    blog = await db.blogs.find_one({"blog_id": blog_id}, {"_id": 0})
    if not blog:
        raise HTTPException(status_code=404, detail="Blog not found")
    return blog

@api_router.put("/admin/blogs/{blog_id}")
async def admin_update_blog(blog_id: str, request: UpdateBlogRequest, admin: dict = Depends(get_blog_manager_user)):
    existing = await db.blogs.find_one({"blog_id": blog_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Blog not found")
    
    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if request.title is not None:
        update_data["title"] = request.title.strip()
    if request.slug is not None:
        new_slug = _slugify(request.slug.strip())
        if new_slug != existing.get("slug"):
            # ensure unique
            base = new_slug
            n = 2
            while await db.blogs.find_one({"slug": new_slug, "blog_id": {"$ne": blog_id}}, {"slug": 1}):
                new_slug = f"{base}-{n}"
                n += 1
            update_data["slug"] = new_slug
    if request.excerpt is not None:
        update_data["excerpt"] = request.excerpt.strip()
    if request.content is not None:
        update_data["content"] = request.content
    if request.featured_image_url is not None:
        update_data["featured_image_url"] = request.featured_image_url
    if request.author is not None:
        update_data["author"] = request.author.strip()
    if request.seo_title is not None:
        update_data["seo_title"] = request.seo_title.strip() or None
    if request.seo_description is not None:
        update_data["seo_description"] = request.seo_description.strip() or None
    if request.status is not None and request.status in ("draft", "published"):
        update_data["status"] = request.status
        # Set published_at the first time status flips to published
        if request.status == "published" and not existing.get("published_at"):
            update_data["published_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.blogs.update_one({"blog_id": blog_id}, {"$set": update_data})
    updated = await db.blogs.find_one({"blog_id": blog_id}, {"_id": 0})
    return updated

@api_router.delete("/admin/blogs/{blog_id}")
async def admin_delete_blog(blog_id: str, admin: dict = Depends(get_blog_manager_user)):
    res = await db.blogs.delete_one({"blog_id": blog_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Blog not found")
    return {"message": "Blog deleted"}

@api_router.post("/admin/blogs/upload-image")
async def admin_upload_blog_image(
    file: UploadFile = File(...),
    admin: dict = Depends(get_blog_manager_user),
):
    """Upload a featured image — stored as a base64 data URI in the DB.
    Keeps deployment simple (no external CDN required).
    """
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    content_type = (file.content_type or "").lower()
    if content_type not in allowed:
        raise HTTPException(status_code=400, detail="Unsupported image type. Use JPG/PNG/WEBP/GIF.")
    
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image size exceeds maximum allowed size of 5 MB")
    
    import base64
    data_uri = f"data:{content_type};base64,{base64.b64encode(content).decode('ascii')}"
    return {"url": data_uri}

# ==================== SUPPRESSION LIST ====================

@api_router.get("/suppression")
async def get_suppression_list(user: User = Depends(get_current_user)):
    items = await db.suppression_list.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(1000)
    return items

@api_router.post("/suppression")
async def add_to_suppression(request: AddToSuppressionRequest, user: User = Depends(get_current_user)):
    """Add either an email or a domain entry to the suppression register + Global DNE."""
    entry = classify_dne_entry(request.email)
    if not entry:
        raise HTTPException(status_code=400, detail="Invalid email or domain value")
    value, entry_type = entry["value"], entry["type"]

    existing = await db.suppression_list.find_one(
        {"user_id": user.user_id, "email": value}
    )
    if not existing:
        await db.suppression_list.insert_one({
            "user_id": user.user_id,
            "email": value,
            "type": entry_type,
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
    # Mirror into Global DNE list so it's visible in the UI
    await add_email_to_global_dne(user.user_id, value, entry_type=entry_type, source="manual")
    return {"message": "Added to suppression list", "type": entry_type, "value": value}


def _unsubscribe_html_response(message: str, domain_hint: str = "") -> "Response":
    """Render a clean, public-facing HTML confirmation page (no login required)."""
    safe_msg = (message or "").replace("<", "&lt;").replace(">", "&gt;")
    html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <meta name=\"robots\" content=\"noindex,nofollow\" />
  <title>You've been unsubscribed</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-height: 100vh; display:flex; align-items:center; justify-content:center;
           font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
           background: linear-gradient(135deg,#f8fafc 0%,#eef2ff 100%); color:#0f172a; padding: 24px; }}
    .card {{ background:#fff; border:1px solid #e2e8f0; border-radius: 18px; padding: 40px 36px;
            max-width: 460px; width: 100%; box-shadow: 0 12px 40px rgba(15,23,42,0.08); text-align:center; }}
    .badge {{ width:64px; height:64px; border-radius:50%; background:#dcfce7; color:#16a34a;
              display:inline-flex; align-items:center; justify-content:center; margin-bottom:20px; }}
    h1 {{ font-size: 22px; margin: 0 0 12px; color:#0f172a; }}
    p {{ margin: 0 0 10px; color:#475569; line-height: 1.6; font-size: 15px; }}
    .hint {{ margin-top: 18px; font-size: 12px; color:#94a3b8; }}
  </style>
</head>
<body>
  <main class=\"card\" role=\"main\">
    <div class=\"badge\" aria-hidden=\"true\">
      <svg xmlns=\"http://www.w3.org/2000/svg\" width=\"32\" height=\"32\" viewBox=\"0 0 24 24\" fill=\"none\"
           stroke=\"currentColor\" stroke-width=\"2.5\" stroke-linecap=\"round\" stroke-linejoin=\"round\">
        <polyline points=\"20 6 9 17 4 12\"></polyline>
      </svg>
    </div>
    <h1>You have been successfully unsubscribed.</h1>
    <p>{safe_msg}</p>
    <p class=\"hint\">You can safely close this window.</p>
  </main>
</body>
</html>"""
    return Response(content=html, media_type="text/html", status_code=200)


async def _process_unsubscribe(user_id: str, email: str) -> None:
    """Shared logic: add to suppression + Global DNE + stop active drips for this email."""
    if not email:
        return
    email_norm = email.strip().lower()
    if not email_norm:
        return
    existing = await db.suppression_list.find_one(
        {"user_id": user_id, "email": email_norm}
    )
    if not existing:
        await db.suppression_list.insert_one({
            "user_id": user_id,
            "email": email_norm,
            "type": "email",
            "source": "unsubscribe",
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
    # Mirror into Global DNE list so the user sees it in the UI
    await add_email_to_global_dne(user_id, email_norm, entry_type="email", source="unsubscribe")
    # Immediately stop any active drip sequences for this contact across all the user's drips
    await db.drip_contacts.update_many(
        {
            "user_id": user_id,
            "email": email_norm,
            "status": {"$in": ["active", "paused"]},
        },
        {"$set": {
            "status": "unsubscribed",
            "unsubscribed_at": datetime.now(timezone.utc).isoformat(),
        }}
    )


def make_unsubscribe_token(user_id: str, email: str) -> str:
    """Generate a signed unsubscribe token (HMAC-SHA256) — opaque, no internal IDs leaked.
    Token format: b64url(payload).b64url(signature)
    payload = JSON {u:user_id, e:email_lower}
    """
    import hmac
    import hashlib
    import base64
    import json as _json
    secret = (os.environ.get("UNSUBSCRIBE_SECRET") or os.environ.get("ENCRYPTION_KEY") or "routemail-default-secret").encode()
    payload = _json.dumps({"u": user_id, "e": (email or "").strip().lower()}, separators=(",", ":")).encode()
    sig = hmac.new(secret, payload, hashlib.sha256).digest()
    return f"{base64.urlsafe_b64encode(payload).decode().rstrip('=')}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"


def verify_unsubscribe_token(token: str) -> Optional[Dict[str, str]]:
    """Verify a signed token; returns {u, e} dict or None."""
    import hmac
    import hashlib
    import base64
    import json as _json
    secret = (os.environ.get("UNSUBSCRIBE_SECRET") or os.environ.get("ENCRYPTION_KEY") or "routemail-default-secret").encode()
    try:
        p_b64, s_b64 = token.split(".", 1)
        # Restore padding
        p_pad = p_b64 + "=" * (-len(p_b64) % 4)
        s_pad = s_b64 + "=" * (-len(s_b64) % 4)
        payload = base64.urlsafe_b64decode(p_pad.encode())
        sig = base64.urlsafe_b64decode(s_pad.encode())
        expected = hmac.new(secret, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        data = _json.loads(payload.decode())
        if "u" not in data or "e" not in data:
            return None
        return data
    except Exception:
        return None


@api_router.get("/unsubscribe/u/{token}")
async def unsubscribe_token(token: str):
    """Public token-based unsubscribe endpoint. Returns a styled HTML confirmation page.
    Does NOT expose internal user_id or email in the URL.
    """
    data = verify_unsubscribe_token(token)
    if not data:
        return _unsubscribe_html_response("This unsubscribe link is invalid or has expired.")
    await _process_unsubscribe(data["u"], data["e"])
    return _unsubscribe_html_response("You will no longer receive emails from this sender.")


@api_router.get("/unsubscribe/{user_id}/{email}")
async def unsubscribe(user_id: str, email: str):
    """Legacy unsubscribe endpoint (kept for already-sent emails). Returns HTML confirmation."""
    await _process_unsubscribe(user_id, email)
    return _unsubscribe_html_response("You will no longer receive emails from this sender.")

# ==================== DASHBOARD STATS ====================

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(user: User = Depends(get_current_user)):
    accounts = await db.email_accounts.find(
        {"user_id": user.user_id},
        {"_id": 0, "smtp_password_encrypted": 0}
    ).to_list(100)
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    account_stats = []
    total_available_today = 0
    
    for acc in accounts:
        daily_count = acc.get("daily_send_count", 0) if acc.get("last_send_date") == today else 0
        daily_limit = acc.get("daily_limit", 50)
        remaining = daily_limit - daily_count
        total_available_today += max(0, remaining)
        
        account_stats.append({
            "account_id": acc["account_id"],
            "email": acc["email"],
            "display_name": acc["display_name"],
            "account_type": acc.get("account_type", "smtp"),
            "status": acc["status"],
            "daily_sent": daily_count,
            "daily_limit": daily_limit,
            "remaining": max(0, remaining)
        })
    
    campaigns = await db.campaigns.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    total_sent = sum(c.get("sent_count", 0) for c in campaigns)
    total_failed = sum(c.get("failed_count", 0) for c in campaigns)
    
    current_campaign = await db.campaigns.find_one(
        {"user_id": user.user_id, "status": {"$in": ["running", "paused", "paused_daily_limit"]}},
        {"_id": 0}
    )
    
    lists = await db.email_lists.find(
        {"user_id": user.user_id},
        {"_id": 0, "emails": 0}
    ).to_list(100)
    
    total_contacts = sum(lst.get("valid_emails", 0) for lst in lists)
    
    return {
        "accounts": account_stats,
        "total_accounts": len(accounts),
        "total_available_today": total_available_today,
        "total_sent": total_sent,
        "total_failed": total_failed,
        "total_contacts": total_contacts,
        "total_lists": len(lists),
        "total_campaigns": len(campaigns),
        "campaigns": campaigns,
        "current_campaign": current_campaign,
        "subscription_status": user.subscription_status
    }

# ==================== BACKGROUND EMAIL PROCESSING ====================

def replace_variables(template: str, data: dict) -> str:
    """Deprecated — kept for callers. Delegates to template_render.render_template
    which handles {{var}}, {var}, fallbacks, HTML entities, and strips stray braces."""
    from template_render import render_template as _render
    return _render(template, data or {})

async def send_email_smtp(account: dict, to_email: str, subject: str, body_html: str, body_text: str, from_name: str, user_id: str, add_unsubscribe_footer: bool = False) -> dict:
    """Send email via SMTP"""
    try:
        password = decrypt_data(account.get("smtp_password_encrypted", ""))
        if not password:
            return {"success": False, "error": "Could not decrypt SMTP password"}
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{from_name} <{account['email']}>" if from_name else account['email']
        msg['To'] = to_email
        # Stable Message-ID we can match against later when replies arrive via IMAP
        from email.utils import make_msgid as _make_msgid
        msg_id = _make_msgid(domain="routemail.app")
        msg['Message-ID'] = msg_id
        
        frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
        unsubscribe_token_str = make_unsubscribe_token(user_id, to_email)
        unsubscribe_url = f"{frontend_url}/api/unsubscribe/u/{unsubscribe_token_str}"
        
        # Resolve {{unsubscribe_url}} token if the user inserted an Unsubscribe link in the editor
        body_html = (body_html or "").replace("{{unsubscribe_url}}", unsubscribe_url)
        body_text = (body_text or "").replace("{{unsubscribe_url}}", unsubscribe_url)
        
        # Default unsubscribe footer is now OPT-IN per campaign (was previously always-on).
        # We only append it when the campaign explicitly enabled `add_unsubscribe_footer`,
        # AND the email body does not already contain the per-recipient unsubscribe URL.
        body_has_unsub = unsubscribe_url in body_html or unsubscribe_url in body_text
        if add_unsubscribe_footer and not body_has_unsub:
            unsubscribe_text = f"\n\n---\nTo unsubscribe: {unsubscribe_url}"
            unsubscribe_html = f'<br><br><hr><p style="font-size:12px;color:#666;">To unsubscribe, <a href="{unsubscribe_url}">click here</a></p>'
        else:
            unsubscribe_text = ""
            unsubscribe_html = ""
        
        part1 = MIMEText((body_text or "") + unsubscribe_text, 'plain')
        part2 = MIMEText(body_html + unsubscribe_html, 'html')
        
        msg.attach(part1)
        msg.attach(part2)
        
        host = account.get("smtp_host", "")
        port = account.get("smtp_port", 587)
        encryption = account.get("smtp_encryption", "tls")
        
        if encryption == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            server = smtplib.SMTP(host, port, timeout=30)
            if encryption == "tls":
                server.starttls()
        
        server.login(account.get("smtp_username", ""), password)
        server.sendmail(account['email'], to_email, msg.as_string())
        server.quit()

        return {"success": True, "message_id": msg_id}
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "error": "SMTP authentication failed"}
    except smtplib.SMTPRecipientsRefused:
        return {"success": False, "error": "Recipient refused"}
    except Exception as e:
        return {"success": False, "error": str(e)}

async def process_campaign_queue(campaign_id: str, user_id: str):
    """Process campaign queue with rotational sending"""
    logger.info(f"Starting campaign processing: {campaign_id}")
    
    while True:
        campaign = await db.campaigns.find_one(
            {"campaign_id": campaign_id},
            {"_id": 0}
        )
        
        if not campaign or campaign["status"] != "running":
            logger.info(f"Campaign {campaign_id} stopped or not running")
            break
        
        queue_item = await db.email_queue.find_one(
            {"campaign_id": campaign_id, "status": "pending"},
            {"_id": 0}
        )
        
        if not queue_item:
            # No more emails, mark campaign complete
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {"$set": {
                    "status": "completed",
                    "is_locked": False,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            logger.info(f"Campaign {campaign_id} completed")
            break
        
        # Real-time DNE / suppression check — before account selection & send
        suppression_list_ids = campaign.get("suppression_list_ids", [])
        if await is_email_suppressed(user_id, queue_item.get("recipient_email", ""), suppression_list_ids):
            await db.email_queue.update_one(
                {"queue_id": queue_item["queue_id"]},
                {"$set": {
                    "status": "suppressed",
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "error_message": "Recipient is on a Do Not Email list",
                }}
            )
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {
                    "$inc": {"suppressed_count": 1},
                    "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                }
            )
            logger.info(f"Campaign {campaign_id}: suppressed {queue_item['recipient_email']}")
            continue
        
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        account_ids = campaign.get("account_ids", [])
        
        if account_ids:
            accounts = await db.email_accounts.find(
                {"user_id": user_id, "account_id": {"$in": account_ids}, "status": "connected"},
                {"_id": 0}
            ).to_list(100)
        else:
            accounts = await db.email_accounts.find(
                {"user_id": user_id, "status": "connected"},
                {"_id": 0}
            ).to_list(100)
        
        if not accounts:
            logger.error(f"No accounts available for campaign {campaign_id}")
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {"$set": {"status": "failed", "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            break
        
        # Find available account with remaining quota
        current_index = campaign.get("current_account_index", 0)
        account = None
        checked = 0
        
        while checked < len(accounts):
            idx = (current_index + checked) % len(accounts)
            acc = accounts[idx]
            
            # Reset count if new day
            if acc.get("last_send_date") != today:
                await db.email_accounts.update_one(
                    {"account_id": acc["account_id"]},
                    {"$set": {
                        "daily_send_count": 0,
                        "last_send_date": today,
                        "last_reset_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                acc["daily_send_count"] = 0
            
            daily_limit = acc.get("daily_limit", 50)
            if acc.get("daily_send_count", 0) < daily_limit:
                account = acc
                current_index = (idx + 1) % len(accounts)
                break
            
            checked += 1
        
        if not account:
            # All accounts hit daily limit
            logger.info(f"All accounts hit daily limit for campaign {campaign_id}")
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {"$set": {"status": "paused_daily_limit", "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
            break
        
        # Replace variables — use the unified renderer with campaign-level fallbacks
        from template_render import render_template as _render_tmpl
        recipient_data = queue_item.get("recipient_data", {}) or {}
        fallbacks = campaign.get("variable_fallbacks") or {}
        subject = _render_tmpl(campaign["subject"], recipient_data, fallbacks=fallbacks)
        body_html = _render_tmpl(campaign["body"], recipient_data, fallbacks=fallbacks)
        body_text = _render_tmpl(campaign.get("body_text", ""), recipient_data, fallbacks=fallbacks) if campaign.get("body_text") else ""
        # From Name resolution: campaign-level override takes priority over account-level
        campaign_from_name = (campaign.get("from_name") or "").strip()
        account_from_name = (account.get("from_name") or "").strip() or account.get("display_name", "")
        from_name = campaign_from_name or account_from_name
        
        # Send email
        if account.get("account_type") == "smtp" and account.get("smtp_host"):
            result = await send_email_smtp(
                account=account,
                to_email=queue_item["recipient_email"],
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                from_name=from_name,
                user_id=user_id,
                add_unsubscribe_footer=bool(campaign.get("add_unsubscribe_footer", False)),
            )
        else:
            # Simulated sending for demo accounts
            logger.info(f"[SIMULATED] Sending to {queue_item['recipient_email']}")
            result = {"success": random.random() < 0.95}
            if not result["success"]:
                result["error"] = "Simulated failure"
        
        # Update queue item
        if result.get("success"):
            # Track outbound for Unibox reply matching + Sent Email Viewer
            await register_sent_email(
                db,
                user_id=user_id,
                account_id=account["account_id"],
                sender_email=account.get("email", ""),
                recipient_email=queue_item["recipient_email"],
                subject=subject,
                message_id=result.get("message_id"),
                campaign_id=campaign_id,
                campaign_name=campaign.get("name"),
                folder_id=campaign.get("folder_id"),
                body_html=body_html,
                body_text=body_text,
                from_name=from_name,
            )
            await db.email_queue.update_one(
                {"queue_id": queue_item["queue_id"]},
                {"$set": {
                    "status": "sent",
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "assigned_account_id": account["account_id"]
                }}
            )
            
            await db.email_accounts.update_one(
                {"account_id": account["account_id"]},
                {"$set": {
                    "daily_send_count": account.get("daily_send_count", 0) + 1,
                    "last_send_date": today
                }}
            )
            
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {
                    "$inc": {"sent_count": 1},
                    "$set": {
                        "current_account_index": current_index,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
        else:
            await db.email_queue.update_one(
                {"queue_id": queue_item["queue_id"]},
                {"$set": {
                    "status": "failed",
                    "error_message": result.get("error", "Unknown error"),
                    "assigned_account_id": account["account_id"],
                    "sent_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {
                    "$inc": {"failed_count": 1},
                    "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                }
            )
            
            # Mark account as error if too many failures
            recent_failures = await db.email_queue.count_documents({
                "campaign_id": campaign_id,
                "assigned_account_id": account["account_id"],
                "status": "failed"
            })
            
            if recent_failures >= 5:
                await db.email_accounts.update_one(
                    {"account_id": account["account_id"]},
                    {"$set": {"status": "error", "last_error": result.get("error", "Multiple failures")}}
                )
        
        # Use account's configured send delay (with small randomization)
        base_delay = account.get("send_delay", 30)
        delay = base_delay + random.uniform(-2, 2)  # Add slight randomization
        delay = max(10, delay)  # Minimum 10 seconds
        logger.info(f"Waiting {delay:.1f}s before next email (account delay: {base_delay}s)")
        await asyncio.sleep(delay)

# ==================== SUPER ADMIN MIDDLEWARE ====================

async def _legacy_get_super_admin_user_DEPRECATED(request: Request) -> dict:
    """Deprecated: use the hoisted definition near the blog endpoints."""
    return await get_super_admin_user(request)

# ==================== SUPER ADMIN ENDPOINTS ====================

@api_router.get("/admin/stats")
async def get_admin_stats(admin: dict = Depends(get_super_admin_user)):
    """Get platform-wide statistics for super admin"""
    try:
        # Total users
        total_users = await db.users.count_documents({})
        
        # Active users (logged in last 7 days)
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        active_sessions = await db.user_sessions.distinct("user_id", {
            "expires_at": {"$gt": seven_days_ago}
        })
        active_users = len(active_sessions)
        
        # Total campaigns
        total_campaigns = await db.campaigns.count_documents({})
        
        # Total emails sent
        total_emails_sent = await db.email_queue.count_documents({"status": "sent"})
        
        # Total connected accounts
        total_accounts = await db.email_accounts.count_documents({})
        
        # Total email lists
        total_lists = await db.email_lists.count_documents({})
        
        # Running campaigns
        running_campaigns = await db.campaigns.count_documents({"status": "running"})
        
        # Failed emails
        failed_emails = await db.email_queue.count_documents({"status": "failed"})
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_campaigns": total_campaigns,
            "total_emails_sent": total_emails_sent,
            "total_accounts": total_accounts,
            "total_lists": total_lists,
            "running_campaigns": running_campaigns,
            "failed_emails": failed_emails
        }
    except Exception as e:
        logger.error(f"Admin stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/admin/users")
async def get_admin_users(
    admin: dict = Depends(get_super_admin_user),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """Get all users with stats for super admin"""
    try:
        query = {}
        
        # Search by email or name
        if search:
            query["$or"] = [
                {"email": {"$regex": search, "$options": "i"}},
                {"name": {"$regex": search, "$options": "i"}}
            ]
        
        # Filter by subscription status
        if status:
            query["subscription_status"] = status
        
        # Get total count
        total = await db.users.count_documents(query)
        
        # Get paginated users
        skip = (page - 1) * limit
        users_cursor = db.users.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
        users = await users_cursor.to_list(length=limit)
        
        # Enrich each user with stats
        enriched_users = []
        for user in users:
            user_id = user["user_id"]
            
            # Count accounts
            accounts_count = await db.email_accounts.count_documents({"user_id": user_id})
            
            # Count campaigns
            campaigns_count = await db.campaigns.count_documents({"user_id": user_id})
            
            # Count emails sent
            user_campaigns = await db.campaigns.distinct("campaign_id", {"user_id": user_id})
            emails_sent = await db.email_queue.count_documents({
                "campaign_id": {"$in": user_campaigns},
                "status": "sent"
            }) if user_campaigns else 0
            
            # Get last session
            last_session = await db.user_sessions.find_one(
                {"user_id": user_id},
                {"_id": 0, "created_at": 1}
            )
            
            enriched_users.append({
                "user_id": user["user_id"],
                "email": user["email"],
                "name": user.get("name", ""),
                "role": user.get("role", "user"),
                "can_manage_blogs": bool(user.get("can_manage_blogs", False)),
                "can_access_infrastructure": bool(user.get("can_access_infrastructure", False)),
                "subscription_status": user.get("subscription_status", "inactive"),
                "created_at": user.get("created_at"),
                "accounts_count": accounts_count,
                "campaigns_count": campaigns_count,
                "emails_sent": emails_sent,
                "last_login": last_session.get("created_at") if last_session else None
            })
        
        return {
            "users": enriched_users,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }
    except Exception as e:
        logger.error(f"Admin users error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/admin/users/{user_id}")
async def get_admin_user_detail(
    user_id: str,
    admin: dict = Depends(get_super_admin_user)
):
    """Get detailed info about a specific user for super admin"""
    try:
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get accounts (metadata only, no credentials)
        accounts = await db.email_accounts.find(
            {"user_id": user_id},
            {"_id": 0, "smtp_password_encrypted": 0, "smtp_username": 0}
        ).to_list(length=100)
        
        # Get campaigns
        campaigns = await db.campaigns.find(
            {"user_id": user_id},
            {"_id": 0}
        ).sort("created_at", -1).to_list(length=50)
        
        # Get email lists
        lists = await db.email_lists.find(
            {"user_id": user_id},
            {"_id": 0, "emails": 0}  # Exclude email data for privacy
        ).to_list(length=50)
        
        # Get sending stats
        user_campaigns = [c["campaign_id"] for c in campaigns]
        emails_sent = await db.email_queue.count_documents({
            "campaign_id": {"$in": user_campaigns},
            "status": "sent"
        }) if user_campaigns else 0
        emails_failed = await db.email_queue.count_documents({
            "campaign_id": {"$in": user_campaigns},
            "status": "failed"
        }) if user_campaigns else 0
        
        return {
            "user": {
                "user_id": user["user_id"],
                "email": user["email"],
                "name": user.get("name", ""),
                "picture": user.get("picture"),
                "role": user.get("role", "user"),
                "subscription_status": user.get("subscription_status", "inactive"),
                "created_at": user.get("created_at")
            },
            "accounts": accounts,
            "campaigns": campaigns,
            "lists": lists,
            "stats": {
                "total_accounts": len(accounts),
                "total_campaigns": len(campaigns),
                "total_lists": len(lists),
                "emails_sent": emails_sent,
                "emails_failed": emails_failed
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin user detail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/admin/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role_data: dict,
    admin: dict = Depends(get_super_admin_user)
):
    """Update user role (super_admin only)"""
    try:
        new_role = role_data.get("role")
        if new_role not in ["user", "super_admin"]:
            raise HTTPException(status_code=400, detail="Invalid role. Must be 'user' or 'super_admin'")
        
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Safety: prevent removing the last remaining super_admin
        if user.get("role") == "super_admin" and new_role != "super_admin":
            super_admin_count = await db.users.count_documents({"role": "super_admin"})
            if super_admin_count <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot remove Super Admin access — at least one Super Admin must remain. Grant Super Admin to another user first."
                )
            # Extra guard: if the acting admin is demoting themselves and they are the ONLY one, block.
            # (Already covered above, but explicit message when self-demoting.)
            if user.get("user_id") == admin.get("user_id") and super_admin_count <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="You cannot remove your own Super Admin access while you are the only Super Admin."
                )
        
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"role": new_role}}
        )
        
        return {"message": f"User role updated to {new_role}", "user_id": user_id, "role": new_role}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update role error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.put("/admin/users/{user_id}/blog-permission")
async def update_blog_permission(
    user_id: str,
    payload: dict,
    admin: dict = Depends(get_super_admin_user)
):
    """Grant or revoke `can_manage_blogs` for a user (super_admin only).

    Body: { "can_manage_blogs": true | false }

    Super admins always have implicit blog management — toggling this on a
    super_admin is a no-op against role but the flag is still persisted so
    that a future demotion preserves the permission unless explicitly cleared.
    """
    if "can_manage_blogs" not in payload:
        raise HTTPException(status_code=400, detail="`can_manage_blogs` boolean required in body")
    new_value = bool(payload.get("can_manage_blogs"))

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "can_manage_blogs": new_value,
            "blog_permission_updated_at": datetime.now(timezone.utc).isoformat(),
            "blog_permission_updated_by": admin.get("user_id"),
        }}
    )

    # Audit log
    try:
        await db.admin_logs.insert_one({
            "log_id": f"log_{uuid.uuid4().hex[:12]}",
            "admin_user_id": admin.get("user_id"),
            "target_user_id": user_id,
            "action": "blog_permission_updated",
            "details": {"can_manage_blogs": new_value},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    return {
        "message": f"Blog management permission {'granted' if new_value else 'revoked'}",
        "user_id": user_id,
        "can_manage_blogs": new_value,
    }


@api_router.put("/admin/users/{user_id}/infrastructure-permission")
async def update_infrastructure_permission(
    user_id: str,
    payload: dict,
    admin: dict = Depends(get_super_admin_user)
):
    """Grant or revoke `can_access_infrastructure` for a user (super_admin only).

    Body: { "can_access_infrastructure": true | false }

    The Infrastructure module is INTERNAL-ONLY — visible to super_admins and
    any user explicitly granted this flag. Standard users never see it.
    """
    if "can_access_infrastructure" not in payload:
        raise HTTPException(status_code=400, detail="`can_access_infrastructure` boolean required in body")
    new_value = bool(payload.get("can_access_infrastructure"))

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {
            "can_access_infrastructure": new_value,
            "infrastructure_permission_updated_at": datetime.now(timezone.utc).isoformat(),
            "infrastructure_permission_updated_by": admin.get("user_id"),
        }}
    )

    try:
        await db.admin_logs.insert_one({
            "log_id": f"log_{uuid.uuid4().hex[:12]}",
            "admin_user_id": admin.get("user_id"),
            "target_user_id": user_id,
            "action": "infrastructure_permission_updated",
            "details": {"can_access_infrastructure": new_value},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass

    return {
        "message": f"Infrastructure module access {'granted' if new_value else 'revoked'}",
        "user_id": user_id,
        "can_access_infrastructure": new_value,
    }

@api_router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: dict = Depends(get_super_admin_user)
):
    """Delete a user and all their data (super_admin only)"""
    try:
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Prevent deleting super admin
        if user.get("role") == "super_admin":
            raise HTTPException(status_code=400, detail="Cannot delete super admin user")
        
        # Delete user's data
        await db.email_accounts.delete_many({"user_id": user_id})
        await db.email_lists.delete_many({"user_id": user_id})
        
        # Delete campaigns and queue items
        campaigns = await db.campaigns.distinct("campaign_id", {"user_id": user_id})
        if campaigns:
            await db.email_queue.delete_many({"campaign_id": {"$in": campaigns}})
        await db.campaigns.delete_many({"user_id": user_id})
        
        # Delete sessions
        await db.user_sessions.delete_many({"user_id": user_id})
        
        # Delete user
        await db.users.delete_one({"user_id": user_id})
        
        return {"message": "User deleted successfully", "user_id": user_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete user error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/admin/users/{user_id}/force-password-reset")
async def force_password_reset(
    user_id: str,
    background_tasks: BackgroundTasks,
    admin: dict = Depends(get_super_admin_user)
):
    """Force send password reset email to a user (super_admin only)"""
    try:
        # Find the target user
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # (Google OAuth removed — legacy Google users CAN now reset password.)
        # Generate secure reset token
        reset_token = secrets.token_urlsafe(32)
        reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Store reset token in user document
        await db.users.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "reset_token": reset_token,
                    "reset_expires": reset_expires.isoformat()
                }
            }
        )
        
        # Log admin action
        admin_log = {
            "admin_email": admin["email"],
            "target_user_email": user["email"],
            "target_user_id": user_id,
            "action": "FORCE_PASSWORD_RESET",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.admin_logs.insert_one(admin_log)
        logger.info(f"Admin {admin['email']} forced password reset for user {user['email']}")
        
        # Send reset email in background
        reset_link = f"{FRONTEND_URL}/reset-password?token={reset_token}"
        logger.info(f"Force password reset link for {user['email']}: {reset_link}")
        html_content = get_password_reset_email_html(reset_link)
        
        background_tasks.add_task(
            send_email_async,
            user["email"],
            "Reset Your RouteMail Password",
            html_content
        )
        
        return {
            "message": "Password reset email sent successfully",
            "user_email": user["email"]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Force password reset error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper function to map price_id to plan and currency
def get_plan_info_from_price_id(price_id: str) -> dict:
    """Get plan name and currency from Stripe price ID"""
    if not price_id:
        return {"plan": "free", "currency": "N/A"}
    
    price_mapping = {
        STRIPE_PRICES.get("starter_usd"): {"plan": "starter", "currency": "USD"},
        STRIPE_PRICES.get("growth_usd"): {"plan": "growth", "currency": "USD"},
        STRIPE_PRICES.get("starter_inr"): {"plan": "starter", "currency": "INR"},
        STRIPE_PRICES.get("growth_inr"): {"plan": "growth", "currency": "INR"},
    }
    # Add Custom Plan slabs
    for s in CUSTOM_PLAN_SLABS:
        slab_price_id = STRIPE_PRICES.get(s["slug"])
        if slab_price_id:
            price_mapping[slab_price_id] = {"plan": s["slug"], "currency": "USD"}
    
    return price_mapping.get(price_id, {"plan": "unknown", "currency": "unknown"})

@api_router.get("/admin/users/{user_id}/subscription")
async def get_admin_user_subscription(
    user_id: str,
    admin: dict = Depends(get_super_admin_user)
):
    """Get detailed subscription information for a user (super_admin only)"""
    try:
        # Find the user
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        plan_type = user.get("plan_type", "free")
        subscription_status = user.get("subscription_status", "active")
        stripe_customer_id = user.get("stripe_customer_id")
        stripe_subscription_id = user.get("stripe_subscription_id")
        
        # Initialize response with local data
        subscription_info = {
            "user_id": user_id,
            "email": user.get("email"),
            "current_plan": plan_type.capitalize() if plan_type else "Free",
            "billing_status": subscription_status,
            "plan_source": user.get("plan_source", "free"),
            "stripe_customer_id": stripe_customer_id or "N/A",
            "stripe_subscription_id": stripe_subscription_id or "N/A",
            "stripe_price_id": "N/A",
            "currency": "N/A",
            "subscription_end_date": None,
            "grace_period_end": None,
            "downgraded_to_free_at": user.get("downgraded_to_free_at"),
            "downgrade_reason": user.get("downgrade_reason"),
            "is_permanent_plan": user.get("email", "").lower() in PERMANENT_PLAN_ASSIGNMENTS,
            "admin_override_active": user.get("admin_override_active", False),
            "admin_override_plan": user.get("admin_override_plan"),
            "admin_override_updated_at": user.get("admin_override_updated_at"),
            "admin_override_max_accounts": user.get("admin_override_max_accounts"),
            "admin_override_max_contacts": user.get("admin_override_max_contacts"),
            "has_stripe_subscription": bool(stripe_subscription_id),
        }
        
        # Determine effective plan source
        if subscription_info["admin_override_active"]:
            subscription_info["plan_source"] = "admin_override"
            subscription_info["billing_status"] = "admin_override"
            subscription_info["current_plan"] = user.get("admin_override_plan", "free").capitalize()
        elif subscription_info["is_permanent_plan"]:
            subscription_info["plan_source"] = "permanent"
            subscription_info["billing_status"] = "permanent"
            subscription_info["notes"] = "Permanently assigned plan (bypasses Stripe)"
        elif stripe_subscription_id:
            subscription_info["plan_source"] = "stripe"
        
        # Get billing cycle end from local storage
        billing_cycle_end = user.get("billing_cycle_end")
        if billing_cycle_end:
            subscription_info["subscription_end_date"] = billing_cycle_end
        
        # Get grace period end if any
        grace_period_end = user.get("grace_period_end")
        if grace_period_end:
            subscription_info["grace_period_end"] = grace_period_end
        
        # Try to get additional details from Stripe if subscription exists
        if stripe_subscription_id and stripe_subscription_id != "N/A" and stripe.api_key:
            try:
                stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
                
                # Get price ID and derive currency/plan
                if stripe_sub.get("items") and stripe_sub["items"].get("data"):
                    price_id = stripe_sub["items"]["data"][0].get("price", {}).get("id")
                    if price_id:
                        subscription_info["stripe_price_id"] = price_id
                        plan_info = get_plan_info_from_price_id(price_id)
                        subscription_info["currency"] = plan_info["currency"]
                
                # Get subscription end date from Stripe
                if stripe_sub.get("current_period_end"):
                    period_end = datetime.fromtimestamp(stripe_sub["current_period_end"], tz=timezone.utc)
                    subscription_info["subscription_end_date"] = period_end.isoformat()
                
                # Update billing status from Stripe
                subscription_info["billing_status"] = stripe_sub.get("status", subscription_status)
                
            except stripe.error.StripeError as e:
                logger.warning(f"Could not fetch Stripe subscription for {user_id}: {e}")
                # Keep local data if Stripe fails
        
        # For free users with no Stripe info, derive currency as N/A
        if plan_type == "free" and not stripe_subscription_id:
            subscription_info["currency"] = "N/A"
            subscription_info["stripe_price_id"] = "N/A"
            subscription_info["stripe_customer_id"] = stripe_customer_id or "N/A"
            subscription_info["stripe_subscription_id"] = "N/A"
        
        # Log admin action
        admin_log = {
            "admin_email": admin["email"],
            "target_user_email": user.get("email"),
            "target_user_id": user_id,
            "action": "VIEW_SUBSCRIPTION_DETAILS",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.admin_logs.insert_one(admin_log)
        
        return subscription_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin subscription detail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== ADMIN PLAN OVERRIDE ENDPOINTS ====================

class AdminPlanOverrideRequest(BaseModel):
    plan: str  # "free", "starter", "growth", or "custom_*"

@api_router.post("/admin/users/{user_id}/assign-plan")
async def admin_assign_plan(
    user_id: str,
    request: AdminPlanOverrideRequest,
    admin: dict = Depends(get_super_admin_user)
):
    """
    Assign a plan to a user via admin override.
    Supports `free` (downgrade), `starter`, `growth`, or custom_* slabs.
    Only works for users WITHOUT an active Stripe subscription.
    """
    try:
        # Find the user
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Validate plan type
        valid_plans = {"free", "starter", "growth"} | {s["slug"] for s in CUSTOM_PLAN_SLABS}
        if request.plan not in valid_plans:
            raise HTTPException(status_code=400, detail=f"Plan must be one of: {sorted(valid_plans)}")
        
        # Check if user has active Stripe subscription
        stripe_sub_id = user.get("stripe_subscription_id")
        if stripe_sub_id:
            raise HTTPException(
                status_code=400, 
                detail="This user has an active Stripe subscription. Plan changes must be handled through Stripe billing."
            )
        
        # Check if user is a permanent plan user
        if user.get("email", "").lower() in PERMANENT_PLAN_ASSIGNMENTS:
            raise HTTPException(
                status_code=400,
                detail="This user has a permanently assigned plan that cannot be overridden."
            )
        
        # Apply admin override (or — when assigning `free` — wipe overrides and use base plan)
        if request.plan == "free":
            was_paid = (
                user.get("plan_type") in ("starter", "growth")
                or (user.get("plan_type", "").startswith("custom_"))
                or user.get("admin_override_active")
            )
            update_data = {
                "admin_override_active": False,
                "admin_override_plan": None,
                "plan_type": "free",
                "plan_source": "free",
                "admin_override_updated_at": datetime.now(timezone.utc).isoformat(),
                "subscription_status": "active",
                "trial_ends_at": None,
                "grace_period_end": None,
            }
            if was_paid:
                # Only mark a true downgrade — don't show the banner to users
                # who were already on the Free Plan.
                update_data["downgraded_to_free_at"] = datetime.now(timezone.utc).isoformat()
                update_data["downgrade_reason"] = "admin_assigned"
        else:
            update_data = {
                "admin_override_active": True,
                "admin_override_plan": request.plan,
                "plan_type": request.plan,
                "plan_source": "admin_override",
                "admin_override_updated_at": datetime.now(timezone.utc).isoformat(),
                "subscription_status": "active",
                "trial_ends_at": None,
            }
        
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
        
        # Log admin action
        action_type = f"ADMIN_ASSIGN_{request.plan.upper()}"
        admin_log = {
            "admin_email": admin["email"],
            "target_user_email": user.get("email"),
            "target_user_id": user_id,
            "action": action_type,
            "plan_assigned": request.plan,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.admin_logs.insert_one(admin_log)
        
        logger.info(f"Admin {admin['email']} assigned {request.plan} plan to user {user.get('email')}")
        
        return {
            "success": True,
            "message": f"Successfully assigned {request.plan.capitalize()} plan to user",
            "user_id": user_id,
            "plan": request.plan,
            "source": "admin_override"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin plan assignment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/admin/users/{user_id}/remove-override")
async def admin_remove_override(
    user_id: str,
    admin: dict = Depends(get_super_admin_user)
):
    """
    Remove admin plan override and revert user to free plan.
    """
    try:
        # Find the user
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if override is active
        if not user.get("admin_override_active"):
            raise HTTPException(status_code=400, detail="User does not have an active admin override")
        
        # Remove override and revert to Free Plan (no expiry)
        update_data = {
            "admin_override_active": False,
            "admin_override_plan": None,
            "plan_type": "free",
            "plan_source": "free",
            "admin_override_updated_at": datetime.now(timezone.utc).isoformat(),
            "subscription_status": "active",
            "trial_ends_at": None,
        }
        
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
        
        # Log admin action
        admin_log = {
            "admin_email": admin["email"],
            "target_user_email": user.get("email"),
            "target_user_id": user_id,
            "action": "ADMIN_REMOVE_OVERRIDE",
            "previous_plan": user.get("admin_override_plan"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.admin_logs.insert_one(admin_log)
        
        logger.info(f"Admin {admin['email']} removed plan override for user {user.get('email')}")
        
        return {
            "success": True,
            "message": "Successfully removed admin override. User reverted to free plan.",
            "user_id": user_id,
            "plan": "free",
            "source": "free"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin remove override error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class AdminLimitOverrideRequest(BaseModel):
    max_accounts: Optional[int] = None  # None = clear override; int >= 0 sets it
    max_contacts: Optional[int] = None  # None = clear override; int >= 0 sets it (also caps monthly recipients)

@api_router.post("/admin/users/{user_id}/limit-override")
async def admin_set_limit_override(
    user_id: str,
    request: AdminLimitOverrideRequest,
    admin: dict = Depends(get_super_admin_user)
):
    """
    Set or clear per-user max_accounts / max_contacts overrides.
    These take priority over plan limits while set, do NOT touch Stripe,
    and do NOT change plan_type or plan_source.
    Pass null in a field to clear that specific override.
    """
    try:
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if request.max_accounts is not None and request.max_accounts < 0:
            raise HTTPException(status_code=400, detail="max_accounts must be >= 0")
        if request.max_contacts is not None and request.max_contacts < 0:
            raise HTTPException(status_code=400, detail="max_contacts must be >= 0")

        update_set = {"admin_override_updated_at": datetime.now(timezone.utc).isoformat()}
        update_unset = {}
        # max_accounts
        if request.max_accounts is None:
            # Only unset if it was set; harmless either way.
            update_unset["admin_override_max_accounts"] = ""
        else:
            update_set["admin_override_max_accounts"] = int(request.max_accounts)
        # max_contacts
        if request.max_contacts is None:
            update_unset["admin_override_max_contacts"] = ""
        else:
            update_set["admin_override_max_contacts"] = int(request.max_contacts)

        update_doc = {"$set": update_set}
        if update_unset:
            update_doc["$unset"] = update_unset
        await db.users.update_one({"user_id": user_id}, update_doc)

        admin_log = {
            "admin_email": admin["email"],
            "target_user_email": user.get("email"),
            "target_user_id": user_id,
            "action": "ADMIN_SET_LIMIT_OVERRIDE",
            "max_accounts": request.max_accounts,
            "max_contacts": request.max_contacts,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await db.admin_logs.insert_one(admin_log)
        logger.info(
            f"Admin {admin['email']} set limit override for {user.get('email')}: "
            f"max_accounts={request.max_accounts}, max_contacts={request.max_contacts}"
        )

        # Return the resolved effective limits so the UI can refresh.
        effective = await get_user_plan_limits(user_id)
        return {
            "success": True,
            "user_id": user_id,
            "effective_limits": effective,
            "max_accounts_override": request.max_accounts,
            "max_contacts_override": request.max_contacts,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin limit override error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin remove override error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== STRIPE SUBSCRIPTION ENDPOINTS ====================

class CreateCheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str

@api_router.get("/subscription/status")
async def get_subscription_status(user: User = Depends(get_current_user)):
    """Get current user's subscription status and limits"""
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    sub_status = await check_subscription_active(user.user_id)
    limits = await get_user_plan_limits(user.user_id)
    account_usage = await check_account_limit(user.user_id)
    contact_usage = await check_contact_limit(user.user_id)
    recipient_usage = await check_recipient_limit(user.user_id)
    
    return {
        "plan_type": user_doc.get("plan_type", "free"),
        "subscription_status": user_doc.get("subscription_status", "active"),
        "subscription_active": sub_status.get("active", False),
        "status_details": sub_status,
        "trial_ends_at": user_doc.get("trial_ends_at"),
        "billing_cycle_end": user_doc.get("billing_cycle_end"),
        "downgraded_to_free_at": user_doc.get("downgraded_to_free_at"),
        "downgrade_reason": user_doc.get("downgrade_reason"),
        "limits": limits,
        "usage": {
            "accounts": account_usage,
            "contacts": contact_usage,
            "recipients": recipient_usage
        }
    }

@api_router.get("/subscription/prices")
async def get_subscription_prices():
    """Get available subscription prices"""
    custom_slabs = []
    for s in CUSTOM_PLAN_SLABS:
        custom_slabs.append({
            "slug": s["slug"],
            "label": s["label"],
            "contacts_per_month": s["contacts"],
            "price_usd": s["price_usd"],
            "price_id": STRIPE_PRICES.get(s["slug"]),
            "available": bool(STRIPE_PRICES.get(s["slug"])),
        })
    return {
        "plans": [
            {
                "name": "Starter",
                "prices": {
                    "usd": {"price_id": STRIPE_PRICES["starter_usd"], "amount": 99, "currency": "USD"},
                    "inr": {"price_id": STRIPE_PRICES["starter_inr"], "amount": 7999, "currency": "INR"}
                },
                "features": {
                    "max_accounts": 10,
                    "max_contacts": 4000,
                    "max_monthly_recipients": 4000
                }
            },
            {
                "name": "Growth",
                "prices": {
                    "usd": {"price_id": STRIPE_PRICES["growth_usd"], "amount": 149, "currency": "USD"},
                    "inr": {"price_id": STRIPE_PRICES["growth_inr"], "amount": 11999, "currency": "INR"}
                },
                "features": {
                    "max_accounts": 15,
                    "max_contacts": 10000,
                    "max_monthly_recipients": 10000
                }
            }
        ],
        "custom_plan": {
            "name": "Custom",
            "currency": "USD",
            "slabs": custom_slabs,
        },
        "free_plan": {
            "name": "Free",
            "free_forever": True,
            "price_usd": 0,
            "features": {
                "max_accounts": 3,
                "max_contacts": 500,
                "max_monthly_recipients": 500
            }
        }
    }

@api_router.post("/subscription/create-checkout")
async def create_checkout_session(request: CreateCheckoutRequest, user: User = Depends(get_current_user)):
    """Create a Stripe checkout session for subscription"""
    try:
        user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get or create Stripe customer
        customer_id = user_doc.get("stripe_customer_id")
        
        if not customer_id:
            # Create new Stripe customer
            customer = stripe.Customer.create(
                email=user_doc["email"],
                name=user_doc.get("name", ""),
                metadata={"user_id": user.user_id}
            )
            customer_id = customer.id
            
            # Save customer ID
            await db.users.update_one(
                {"user_id": user.user_id},
                {"$set": {"stripe_customer_id": customer_id}}
            )
        
        # Determine plan from price_id
        plan_type = "starter"
        if request.price_id in [STRIPE_PRICES["growth_usd"], STRIPE_PRICES["growth_inr"]]:
            plan_type = "growth"
        else:
            for s in CUSTOM_PLAN_SLABS:
                if request.price_id == STRIPE_PRICES.get(s["slug"]):
                    plan_type = s["slug"]
                    break
        
        # Create checkout session
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price": request.price_id,
                "quantity": 1
            }],
            mode="subscription",
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={
                "user_id": user.user_id,
                "plan_type": plan_type
            },
            subscription_data={
                "metadata": {
                    "user_id": user.user_id,
                    "plan_type": plan_type
                }
            }
        )
        
        return {"checkout_url": checkout_session.url, "session_id": checkout_session.id}
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Checkout error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/subscription/create-portal")
async def create_customer_portal(user: User = Depends(get_current_user)):
    """Create a Stripe customer portal session for managing subscription"""
    try:
        user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")
        
        customer_id = user_doc.get("stripe_customer_id")
        if not customer_id:
            raise HTTPException(status_code=400, detail="No subscription found")
        
        # Create portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{os.environ['FRONTEND_URL']}/dashboard"
        )
        
        return {"portal_url": portal_session.url}
    
    except stripe.error.StripeError as e:
        logger.error(f"Stripe portal error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Portal error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    event_type = event["type"]
    data = event["data"]["object"]
    
    logger.info(f"Received Stripe webhook: {event_type}")
    
    try:
        if event_type == "checkout.session.completed":
            await handle_checkout_completed(data)
        elif event_type == "invoice.paid":
            await handle_invoice_paid(data)
        elif event_type == "invoice.payment_failed":
            await handle_payment_failed(data)
        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(data)
        elif event_type == "customer.subscription.updated":
            await handle_subscription_updated(data)
    except Exception as e:
        logger.error(f"Webhook handler error: {e}")
        # Return 200 to avoid retries
    
    return {"status": "success"}

async def handle_checkout_completed(session):
    """Handle successful checkout"""
    try:
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        plan_type = metadata.get("plan_type", "starter")
        
        if not user_id:
            # Try to find by customer email
            customer = stripe.Customer.retrieve(customer_id)
            user = await db.users.find_one({"email": customer.email}, {"_id": 0})
            if user:
                user_id = user["user_id"]
        
        if not user_id:
            logger.error(f"Could not find user for checkout: {session.get('id')}")
            return
        
        # Get subscription details
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        update_data = {
            "plan_type": plan_type,
            "subscription_status": "active",
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "billing_cycle_start": datetime.fromtimestamp(subscription.current_period_start, tz=timezone.utc).isoformat(),
            "billing_cycle_end": datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc).isoformat(),
            "trial_ends_at": None,
            "grace_period_end": None
        }
        
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
        
        logger.info(f"User {user_id} upgraded to {plan_type}")
        
        # Send admin notification for new subscription (non-blocking, fail-safe)
        try:
            # Get user email and subscription details
            user = await db.users.find_one({"user_id": user_id}, {"_id": 0, "email": 1})
            user_email = user.get("email", "Unknown") if user else "Unknown"
            
            # Get amount from subscription
            amount_total = session.get("amount_total", 0)
            currency = session.get("currency", "usd").upper()
            
            # Format amount (convert from cents)
            if amount_total:
                if currency == "INR":
                    amount_str = f"₹{amount_total / 100:,.0f}"
                else:
                    amount_str = f"${amount_total / 100:,.2f}"
            else:
                amount_str = "N/A"
            
            admin_html = get_admin_subscription_notification_html(
                user_email=user_email,
                plan=plan_type,
                currency=currency,
                amount=amount_str,
                customer_id=customer_id or "N/A",
                subscription_id=subscription_id or "N/A"
            )
            asyncio.create_task(send_admin_notification("New Paid Subscription on RouteMail", admin_html))
        except Exception as notify_err:
            logger.error(f"Failed to send admin subscription notification: {notify_err}")
            # Don't interrupt webhook processing
        
    except Exception as e:
        logger.error(f"handle_checkout_completed error: {e}")

async def handle_invoice_paid(invoice):
    """Handle successful invoice payment (renewal)"""
    try:
        customer_id = invoice.get("customer")
        subscription_id = invoice.get("subscription")
        
        user = await db.users.find_one({"stripe_customer_id": customer_id}, {"_id": 0})
        if not user:
            logger.warning(f"No user found for customer: {customer_id}")
            return
        
        # Get subscription details
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        # Check if this is a new billing cycle
        old_cycle_end = user.get("billing_cycle_end")
        new_cycle_start = datetime.fromtimestamp(subscription.current_period_start, tz=timezone.utc)
        
        update_data = {
            "subscription_status": "active",
            "billing_cycle_start": new_cycle_start.isoformat(),
            "billing_cycle_end": datetime.fromtimestamp(subscription.current_period_end, tz=timezone.utc).isoformat(),
            "grace_period_end": None
        }
        
        # Reset recipient counter if new billing cycle
        if old_cycle_end:
            if isinstance(old_cycle_end, str):
                old_cycle_end = datetime.fromisoformat(old_cycle_end.replace('Z', '+00:00'))
            if new_cycle_start > old_cycle_end:
                update_data["monthly_unique_recipient_count"] = 0
                update_data["last_recipient_reset_date"] = new_cycle_start.isoformat()
        
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": update_data}
        )
        
        logger.info(f"Invoice paid for user {user['user_id']}")
        
    except Exception as e:
        logger.error(f"handle_invoice_paid error: {e}")

async def handle_payment_failed(invoice):
    """Handle failed payment"""
    try:
        customer_id = invoice.get("customer")
        
        user = await db.users.find_one({"stripe_customer_id": customer_id}, {"_id": 0})
        if not user:
            return
        
        grace_end = datetime.now(timezone.utc) + timedelta(days=7)
        
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "subscription_status": "past_due",
                "grace_period_end": grace_end.isoformat()
            }}
        )
        
        logger.info(f"Payment failed for user {user['user_id']}, grace period until {grace_end}")
        
    except Exception as e:
        logger.error(f"handle_payment_failed error: {e}")

async def handle_subscription_deleted(subscription):
    """Handle subscription cancellation — keep user on their paid plan until billing_cycle_end,
    then downgrade lazily via check_subscription_active(). If the cycle is already past
    when this webhook fires, downgrade immediately.
    """
    try:
        customer_id = subscription.get("customer")
        
        user = await db.users.find_one({"stripe_customer_id": customer_id}, {"_id": 0})
        if not user:
            return
        
        cycle_end_raw = user.get("billing_cycle_end")
        is_past = True
        if cycle_end_raw:
            try:
                ce = (datetime.fromisoformat(cycle_end_raw.replace('Z', '+00:00'))
                      if isinstance(cycle_end_raw, str) else cycle_end_raw)
                if ce.tzinfo is None:
                    ce = ce.replace(tzinfo=timezone.utc)
                is_past = datetime.now(timezone.utc) >= ce
            except Exception:
                is_past = True

        if is_past:
            # Already past cycle end — immediate downgrade
            await _downgrade_to_free_plan(user["user_id"], reason="subscription_deleted")
        else:
            # Stay on the paid plan until cycle ends; check_subscription_active will
            # detect cycle expiry and call _downgrade_to_free_plan automatically.
            await db.users.update_one(
                {"user_id": user["user_id"]},
                {"$set": {
                    "subscription_status": "canceled",
                    "stripe_subscription_id": None,
                }}
            )
        
        logger.info(f"Subscription canceled for user {user['user_id']} (immediate_downgrade={is_past})")
        
    except Exception as e:
        logger.error(f"handle_subscription_deleted error: {e}")

async def handle_subscription_updated(subscription):
    """Handle subscription updates (downgrades scheduled at period end)"""
    try:
        customer_id = subscription.get("customer")
        cancel_at_period_end = subscription.get("cancel_at_period_end", False)
        
        user = await db.users.find_one({"stripe_customer_id": customer_id}, {"_id": 0})
        if not user:
            return
        
        update_data = {}
        
        if cancel_at_period_end:
            update_data["subscription_status"] = "canceled_pending"
        else:
            # Subscription reactivated
            update_data["subscription_status"] = "active"
            update_data["billing_cycle_end"] = datetime.fromtimestamp(
                subscription.current_period_end, tz=timezone.utc
            ).isoformat()
        
        if update_data:
            await db.users.update_one(
                {"user_id": user["user_id"]},
                {"$set": update_data}
            )
        
        logger.info(f"Subscription updated for user {user['user_id']}")
        
    except Exception as e:
        logger.error(f"handle_subscription_updated error: {e}")

# ==================== BASIC ROUTES ====================

@api_router.get("/")
async def root():
    return {"message": "Rotation Email Tool API"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include the router
from backup_routes import build_backup_router
from unibox_routes import build_unibox_router, run_imap_worker, register_sent_email
from sent_email_routes import build_sent_email_router
from admin_backup_routes import build_admin_backup_router
from reports_routes import build_reports_router
from infrastructure_routes import build_infrastructure_router
api_router.include_router(build_backup_router(db, get_current_user))
api_router.include_router(build_unibox_router(db, get_current_user, fernet))
api_router.include_router(build_admin_backup_router(db, get_super_admin_user))
api_router.include_router(build_reports_router(db, get_current_user))
api_router.include_router(build_infrastructure_router(db, get_infrastructure_user))
api_router.include_router(build_sent_email_router(db, get_current_user))
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Backup-Summary", "Content-Disposition"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
