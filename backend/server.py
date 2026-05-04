from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, UploadFile, File, BackgroundTasks, Depends, Query, Header
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
}

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

# Warmup email subjects with (RTM) marker
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
]

# Warmup email body templates (human-like content)
WARMUP_BODIES = [
    "Hi there,\n\nJust wanted to touch base on this. Let me know your thoughts when you get a chance.\n\nBest regards",
    "Hey,\n\nHope you're doing well. Wanted to follow up on our previous conversation. Any updates?\n\nThanks",
    "Hi,\n\nQuick question - have you had a chance to look at this? No rush, just checking in.\n\nCheers",
    "Hello,\n\nJust a brief note to see how things are going. Let me know if you need anything from my end.\n\nBest",
    "Hi there,\n\nWanted to share a quick update. Things are progressing well on our end. Will keep you posted.\n\nThanks",
    "Hey,\n\nCircling back on this topic. Would love to hear your feedback when you have a moment.\n\nRegards",
    "Hi,\n\nJust following up to make sure this didn't get lost in your inbox. Let me know when you're free to chat.\n\nBest",
    "Hello,\n\nHope all is well! Just wanted to check in and see if there's anything we need to discuss.\n\nThanks",
    "Hi there,\n\nQuick sync - are we still on track for the timeline we discussed? Let me know.\n\nCheers",
    "Hey,\n\nJust a friendly reminder about this. No pressure, but wanted to make sure it's on your radar.\n\nBest regards",
]

# Warmup reply templates
WARMUP_REPLIES = [
    "Thanks for reaching out! I'll take a look and get back to you soon.",
    "Got it, thanks for the update. Will review and follow up.",
    "Appreciate you checking in. Everything looks good on my end.",
    "Thanks! Yes, I've been working on this. Will send an update shortly.",
    "Good to hear from you. Let me check on this and I'll respond in detail.",
    "Thanks for following up. I'm still working through this - will update you soon.",
    "Received, thank you! I'll review and get back to you.",
    "Thanks for the reminder. I'll prioritize this and respond soon.",
]

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
    
    # Select random subject and body
    subject = random.choice(WARMUP_SUBJECTS)
    body = random.choice(WARMUP_BODIES)
    
    # Add some randomization to body
    greetings = ["Hi", "Hey", "Hello", "Hi there"]
    body = body.replace("Hi there", random.choice(greetings))
    
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
    user_id = campaign.get("user_id")
    
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
    except:
        tz = pytz.UTC
    
    # Get current time in campaign timezone
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)
    
    # Check if current day is a sending day (0=Monday, 6=Sunday)
    current_day = now_local.weekday()
    if current_day not in sending_days:
        return
    
    # Parse start and end times
    try:
        start_hour, start_min = map(int, start_time.split(":"))
        end_hour, end_min = map(int, end_time.split(":"))
    except:
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
    
    # Find contacts that need processing
    contacts = await db.drip_contacts.find({
        "drip_id": drip_id,
        "status": "active",
        "next_send_at": {"$lte": now_utc.isoformat()}
    }, {"_id": 0}).to_list(100)
    
    # Load accounts for sending
    accounts = await db.email_accounts.find({
        "account_id": {"$in": account_ids},
        "status": "connected"
    }, {"_id": 0}).to_list(100)
    
    if not accounts:
        return
    
    for contact in contacts:
        try:
            await process_drip_contact(campaign, contact, steps, accounts, randomize_time, tz, start_minutes, end_minutes)
        except Exception as e:
            logger.error(f"[DRIP] Error processing contact {contact.get('email')}: {e}")

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
        return
    
    step = steps[current_step]
    
    # Check stop conditions
    stop_on_reply = campaign.get("stop_on_reply", True)
    stop_on_bounce = campaign.get("stop_on_bounce", True)
    
    if stop_on_reply and contact.get("replied"):
        await db.drip_contacts.update_one(
            {"contact_id": contact_id},
            {"$set": {"status": "replied"}}
        )
        return
    
    if stop_on_bounce and contact.get("bounced"):
        await db.drip_contacts.update_one(
            {"contact_id": contact_id},
            {"$set": {"status": "bounced"}}
        )
        return
    
    # Select account (rotate)
    account_index = hash(contact_id) % len(accounts)
    account = accounts[account_index]
    
    # Check account daily limit
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if account.get("last_reset_date") != today:
        await db.email_accounts.update_one(
            {"account_id": account.get("account_id")},
            {"$set": {"daily_send_count": 0, "last_reset_date": today}}
        )
        account["daily_send_count"] = 0
    
    daily_limit = account.get("daily_limit", 50)
    if account.get("daily_send_count", 0) >= daily_limit:
        # Try next account
        for i in range(len(accounts)):
            alt_account = accounts[(account_index + i + 1) % len(accounts)]
            if alt_account.get("daily_send_count", 0) < alt_account.get("daily_limit", 50):
                account = alt_account
                break
        else:
            # All accounts at limit
            return
    
    # Prepare email content
    subject = step.get("subject", "")
    body = step.get("body", "")
    
    # Replace placeholders with contact data
    contact_data = contact.get("data", {})
    for key, value in contact_data.items():
        placeholder = "{" + key + "}"
        subject = subject.replace(placeholder, str(value) if value else "")
        body = body.replace(placeholder, str(value) if value else "")
    
    recipient_email = contact.get("email")
    
    # Send email
    try:
        success = await send_drip_email(account, recipient_email, subject, body)
        
        if success:
            # Update account send count
            await db.email_accounts.update_one(
                {"account_id": account.get("account_id")},
                {"$inc": {"daily_send_count": 1}}
            )
            
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

async def send_drip_email(account: dict, recipient: str, subject: str, body: str) -> bool:
    """Send a drip campaign email using SMTP"""
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
        msg['From'] = f"{account.get('display_name', '')} <{account.get('email')}>"
        msg['To'] = recipient
        msg['Subject'] = subject
        
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
        
        return True
        
    except Exception as e:
        logger.error(f"[DRIP] SMTP error: {e}")
        return False

async def check_scheduled_campaigns():
    """Check for scheduled campaigns that need to be started"""
    global scheduler_running
    
    while scheduler_running:
        try:
            now = datetime.now(timezone.utc)
            
            # Find campaigns that are scheduled and ready to send
            scheduled_campaigns = await db.campaigns.find({
                "status": "scheduled",
                "scheduled_at": {"$ne": None}
            }, {"_id": 0}).to_list(100)
            
            for campaign in scheduled_campaigns:
                try:
                    scheduled_at = campaign.get("scheduled_at")
                    if not scheduled_at:
                        continue
                    
                    # Parse scheduled_at datetime
                    if isinstance(scheduled_at, str):
                        scheduled_dt = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
                    else:
                        scheduled_dt = scheduled_at
                    
                    # Make it timezone-aware if not
                    if scheduled_dt.tzinfo is None:
                        scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
                    
                    # Check if it's time to send
                    if now >= scheduled_dt:
                        logger.info(f"Starting scheduled campaign: {campaign['campaign_id']} - scheduled for {scheduled_at}")
                        
                        # Start the campaign
                        await start_scheduled_campaign(campaign)
                        
                except Exception as e:
                    logger.error(f"Error processing scheduled campaign {campaign.get('campaign_id')}: {e}")
            
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
            queue_items = []
            for email_data in email_list["emails"]:
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
    else:  # free/trialing
        subject = "Welcome to RouteMail – Your 14-Day Trial Has Started 🚀"
        features = """
            <li style="margin-bottom: 8px;">Connect up to <strong>3 email accounts</strong></li>
            <li style="margin-bottom: 8px;">Store up to <strong>500 contacts</strong></li>
            <li style="margin-bottom: 8px;">Send emails to <strong>500 contacts per month</strong></li>
        """
        intro = "Your 14-day free trial is now active."
        outro = "You can upgrade anytime from your dashboard to unlock higher limits and advanced sending power.<br><br>Let's get your first campaign live!"
    
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
                <strong>Trial Status:</strong> 14-day trial started.
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
    """Get the plan limits for a user"""
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return PLAN_LIMITS["free"]
    
    # Use effective plan resolution
    effective = await get_effective_user_plan(user_id)
    plan_type = effective.get("plan", "free")
    return PLAN_LIMITS.get(plan_type, PLAN_LIMITS["free"])

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
    """Check if user has active subscription or valid trial"""
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
    
    plan_type = user.get("plan_type", "free")
    status = user.get("subscription_status", "trialing")
    
    # Check for paid plans (Stripe)
    if plan_type in ["starter", "growth"]:
        if status == "active":
            return {"active": True, "plan": plan_type, "status": status, "source": "stripe"}
        elif status == "past_due":
            # Check grace period
            grace_end = user.get("grace_period_end")
            if grace_end:
                if isinstance(grace_end, str):
                    grace_end = datetime.fromisoformat(grace_end.replace('Z', '+00:00'))
                if grace_end.tzinfo is None:
                    grace_end = grace_end.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < grace_end:
                    return {"active": True, "plan": plan_type, "status": "grace_period", "grace_ends": grace_end.isoformat(), "source": "stripe"}
            return {"active": False, "reason": "Payment overdue", "status": status}
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
            return {"active": False, "reason": "Subscription canceled", "status": status}
    
    # Free plan - check trial
    if status == "trialing":
        trial_end = user.get("trial_ends_at")
        if trial_end:
            if isinstance(trial_end, str):
                trial_end = datetime.fromisoformat(trial_end.replace('Z', '+00:00'))
            if trial_end.tzinfo is None:
                trial_end = trial_end.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < trial_end:
                return {"active": True, "plan": "free", "status": "trialing", "trial_ends": trial_end.isoformat(), "source": "free"}
            else:
                # Trial expired
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"subscription_status": "expired"}}
                )
                return {"active": False, "reason": "Trial expired", "status": "expired"}
        return {"active": True, "plan": "free", "status": "trialing", "source": "free"}
    
    if status == "expired":
        return {"active": False, "reason": "Trial expired", "status": "expired"}
    
    return {"active": True, "plan": plan_type, "status": status, "source": "free"}

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
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password_encrypted: Optional[str] = None
    smtp_encryption: Optional[str] = None
    status: str = "connected"
    last_error: Optional[str] = None
    daily_limit: int = 50  # User-configurable (10-200)
    send_delay: int = 30  # Delay between emails in seconds (10-300)
    daily_send_count: int = 0
    last_send_date: Optional[str] = None
    last_reset_at: Optional[datetime] = None
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

class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str

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

class AddSMTPAccountRequest(BaseModel):
    email: str
    display_name: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    smtp_encryption: str = "tls"
    daily_limit: int = 50
    send_delay: int = 30  # Delay between emails in seconds (10-300)

class UpdateAccountLimitRequest(BaseModel):
    daily_limit: int

class UpdateAccountDelayRequest(BaseModel):
    send_delay: int

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

class AddToSuppressionRequest(BaseModel):
    email: str

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

@api_router.post("/auth/session")
async def exchange_session(request: SessionRequest, response: Response):
    """Exchange Emergent session_id for user data and set cookie"""
    try:
        async with httpx.AsyncClient() as client_http:
            resp = await client_http.get(
                "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                headers={"X-Session-ID": request.session_id}
            )
            
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid session")
            
            data = resp.json()
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")
    
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    session_token = data.get("session_token")
    email = data.get("email")
    name = data.get("name")
    picture = data.get("picture")
    
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})
    
    if existing_user:
        user_id = existing_user["user_id"]
        # Determine role - assign super_admin if email matches
        role = "super_admin" if email == SUPER_ADMIN_EMAIL else existing_user.get("role", "user")
        # Update user data - preserve provider if already set, otherwise set to 'google'
        update_data = {
            "name": name, 
            "picture": picture,
            "role": role
        }
        # Only set provider to google if not already an email user
        if existing_user.get("provider") != "email":
            update_data["provider"] = "google"
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
    else:
        # Determine role for new user
        role = "super_admin" if email == SUPER_ADMIN_EMAIL else "user"
        trial_end = datetime.now(timezone.utc) + timedelta(days=14)
        
        user_dict = {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "provider": "google",
            "role": role,
            # Subscription fields
            "plan_type": "free",
            "subscription_status": "trialing",
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "trial_ends_at": trial_end.isoformat(),
            "billing_cycle_start": None,
            "billing_cycle_end": None,
            "grace_period_end": None,
            "monthly_unique_recipient_count": 0,
            "last_recipient_reset_date": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(user_dict)
        
        # Send admin notification for new Google signup (non-blocking)
        try:
            admin_html = get_admin_signup_notification_html(email, "Google OAuth")
            asyncio.create_task(send_admin_notification("New User Signup on RouteMail", admin_html))
        except Exception as e:
            logger.error(f"Failed to send admin signup notification: {e}")
    
    # Apply permanent plan assignment if applicable (after user exists)
    await apply_permanent_plan_if_applicable(email, user_id)
    
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    session = UserSession(
        user_id=user_id,
        session_token=session_token,
        expires_at=expires_at
    )
    session_dict = session.model_dump()
    session_dict["expires_at"] = session_dict["expires_at"].isoformat()
    session_dict["created_at"] = session_dict["created_at"].isoformat()
    
    await db.user_sessions.insert_one(session_dict)
    
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60
    )
    
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    # Return consistent user data including role
    return {
        "user_id": user_doc["user_id"],
        "email": user_doc["email"],
        "name": user_doc.get("name", ""),
        "picture": user_doc.get("picture"),
        "subscription_status": user_doc.get("subscription_status", "active"),
        "role": user_doc.get("role", "user")
    }

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
            "subscription_status": user_doc.get("subscription_status", "trialing"),
            "plan_type": user_doc.get("plan_type", "free"),
            "role": user_doc.get("role", "user"),
            "trial_ends_at": user_doc.get("trial_ends_at"),
            "billing_cycle_end": user_doc.get("billing_cycle_end"),
            "subscription_active": sub_status.get("active", False),
            "onboarding_completed": user_doc.get("onboarding_completed", False)
        }
    return user.model_dump()

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
async def register_email(request: EmailRegisterRequest, background_tasks: BackgroundTasks):
    """Register a new user with email and password - requires email verification"""
    
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
            raise HTTPException(status_code=400, detail="This email is registered with Google. Please sign in with Google.")
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
    trial_end = datetime.now(timezone.utc) + timedelta(days=14)
    
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
        # Subscription fields
        "plan_type": "free",
        "subscription_status": "trialing",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "trial_ends_at": trial_end.isoformat(),
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
    
    if user.get("provider") == "google":
        logger.info(f"[RESEND] User uses Google sign-in: {email}")
        raise HTTPException(status_code=400, detail="This account uses Google sign-in")
    
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
async def login_email(request: EmailLoginRequest, response: Response):
    """Login with email and password"""
    # Find user
    user_doc = await db.users.find_one({"email": request.email}, {"_id": 0})
    
    if not user_doc:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Check if user registered with Google
    if user_doc.get("provider") == "google" or not user_doc.get("password_hash"):
        raise HTTPException(status_code=401, detail="This account uses Google sign-in. Please sign in with Google.")
    
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
    
    # Find user (don't reveal if email exists)
    user = await db.users.find_one({"email": email}, {"_id": 0})
    
    if not user or user.get("provider") == "google":
        # Don't reveal if email doesn't exist or uses Google
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
        {"_id": 0, "smtp_password_encrypted": 0}
    ).to_list(100)
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for acc in accounts:
        if acc.get("last_send_date") != today:
            acc["daily_send_count"] = 0
    
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
    
    # Validate daily limit (10-200)
    daily_limit = max(10, min(200, request.daily_limit))
    
    # Validate send delay (10-300 seconds)
    send_delay = max(10, min(300, request.send_delay))
    
    encrypted_password = encrypt_data(request.smtp_password)
    
    account = EmailAccount(
        user_id=user.user_id,
        account_type="smtp",
        email=request.email,
        display_name=request.display_name,
        smtp_host=request.smtp_host,
        smtp_port=request.smtp_port,
        smtp_username=request.smtp_username,
        smtp_password_encrypted=encrypted_password,
        smtp_encryption=request.smtp_encryption,
        daily_limit=daily_limit,
        send_delay=send_delay,
        status="connected",
        last_reset_at=datetime.now(timezone.utc)
    )
    
    acc_dict = account.model_dump()
    acc_dict["created_at"] = acc_dict["created_at"].isoformat()
    acc_dict["last_reset_at"] = acc_dict["last_reset_at"].isoformat()
    await db.email_accounts.insert_one(acc_dict)
    
    return {
        "account_id": account.account_id, 
        "email": account.email, 
        "status": "connected",
        "daily_limit": daily_limit,
        "message": "SMTP account connected successfully"
    }

@api_router.put("/accounts/{account_id}/limit")
async def update_account_limit(account_id: str, request: UpdateAccountLimitRequest, user: User = Depends(get_current_user)):
    """Update daily sending limit for an account"""
    # Validate limit (10-200)
    daily_limit = max(10, min(200, request.daily_limit))
    
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
    
    # Check file size (max 2MB)
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:  # 2MB limit
        raise HTTPException(status_code=400, detail="File size exceeds 2MB limit. Please upload a smaller file.")
    
    try:
        # Parse based on file type
        if file_ext == '.csv':
            text_content = content.decode('utf-8')
            reader = csv.DictReader(io.StringIO(text_content))
            column_headers = reader.fieldnames or []
            column_headers = [h.strip().lower() for h in column_headers]
            
            rows = []
            for row in reader:
                normalized_row = {k.lower().strip(): v.strip() if v else "" for k, v in row.items()}
                rows.append(normalized_row)
        else:
            # Excel file (.xlsx or .xls)
            try:
                df = pd.read_excel(io.BytesIO(content), engine='openpyxl' if file_ext == '.xlsx' else 'xlrd')
            except Exception:
                # Fallback to openpyxl for both
                df = pd.read_excel(io.BytesIO(content), engine='openpyxl')
            
            # Clean column headers
            df.columns = [str(col).strip().lower() for col in df.columns]
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
    """Get all campaigns"""
    campaigns = await db.campaigns.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
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
    
    campaign["pending_count"] = pending
    campaign["sent_count"] = sent
    campaign["failed_count"] = failed
    
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
            scheduled_at = datetime.fromisoformat(request.scheduled_at.replace('Z', '+00:00'))
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
        scheduled_at=scheduled_at
    )
    
    camp_dict = campaign.model_dump()
    camp_dict["created_at"] = camp_dict["created_at"].isoformat()
    camp_dict["updated_at"] = camp_dict["updated_at"].isoformat()
    if camp_dict.get("scheduled_at"):
        camp_dict["scheduled_at"] = camp_dict["scheduled_at"].isoformat()
    
    await db.campaigns.insert_one(camp_dict)
    
    return {"campaign_id": campaign.campaign_id, "status": campaign.status, "scheduled_at": request.scheduled_at}

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
    if request.scheduled_at is not None:
        if request.scheduled_at == "":
            update_data["scheduled_at"] = None
            if campaign["status"] == "scheduled":
                update_data["status"] = "draft"
        else:
            try:
                scheduled_dt = datetime.fromisoformat(request.scheduled_at.replace('Z', '+00:00'))
                update_data["scheduled_at"] = scheduled_dt.isoformat()
                update_data["status"] = "scheduled"
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid scheduled_at datetime format")
    
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

@api_router.post("/campaigns/send-test")
async def send_test_email(request: SendTestEmailRequest, user: User = Depends(get_current_user)):
    """Send a test email preview without affecting campaign stats"""
    
    # Validate inputs
    if not request.subject or not request.subject.strip():
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
    test_subject = f"[TEST] {request.subject}"
    
    # Add test banner to email body
    test_banner = """
    <div style="background-color: #fef3c7; border: 1px solid #f59e0b; border-radius: 8px; padding: 12px; margin-bottom: 20px; text-align: center;">
        <strong style="color: #92400e;">🧪 TEST EMAIL</strong>
        <p style="color: #78350f; margin: 4px 0 0 0; font-size: 13px;">This is a test preview. Campaign stats are not affected.</p>
    </div>
    """
    test_body = test_banner + request.body
    
    # Create email message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = test_subject
    msg['From'] = f"{from_name} <{account['email']}>"
    msg['To'] = request.test_email
    
    # Plain text version
    plain_text = re.sub('<[^<]+?>', '', request.body)
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
        queue_items = []
        for email_data in email_list["emails"]:
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
    existing = await db.suppression_list.find_one(
        {"user_id": user.user_id, "email": request.email.lower()}
    )
    
    if not existing:
        await db.suppression_list.insert_one({
            "user_id": user.user_id,
            "email": request.email.lower(),
            "added_at": datetime.now(timezone.utc).isoformat()
        })
    
    return {"message": "Added to suppression list"}

@api_router.get("/unsubscribe/{user_id}/{email}")
async def unsubscribe(user_id: str, email: str):
    existing = await db.suppression_list.find_one(
        {"user_id": user_id, "email": email.lower()}
    )
    
    if not existing:
        await db.suppression_list.insert_one({
            "user_id": user_id,
            "email": email.lower(),
            "added_at": datetime.now(timezone.utc).isoformat()
        })
    
    return {"message": "You have been unsubscribed successfully"}

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
    """Replace {{variable}} with values from data"""
    def replacer(match):
        var_name = match.group(1).strip().lower()
        return str(data.get(var_name, ""))
    
    result = re.sub(r'\{\{(\w+)\}\}', replacer, template)
    return result

async def send_email_smtp(account: dict, to_email: str, subject: str, body_html: str, body_text: str, from_name: str, user_id: str) -> dict:
    """Send email via SMTP"""
    try:
        password = decrypt_data(account.get("smtp_password_encrypted", ""))
        if not password:
            return {"success": False, "error": "Could not decrypt SMTP password"}
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{from_name} <{account['email']}>" if from_name else account['email']
        msg['To'] = to_email
        
        frontend_url = os.environ.get('FRONTEND_URL', '').rstrip('/')
        unsubscribe_url = f"{frontend_url}/api/unsubscribe/{user_id}/{to_email}"
        unsubscribe_text = f"\n\n---\nTo unsubscribe: {unsubscribe_url}"
        unsubscribe_html = f'<br><br><hr><p style="font-size:12px;color:#666;">To unsubscribe, <a href="{unsubscribe_url}">click here</a></p>'
        
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
        
        return {"success": True}
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
        
        # Replace variables
        recipient_data = queue_item.get("recipient_data", {})
        subject = replace_variables(campaign["subject"], recipient_data)
        body_html = replace_variables(campaign["body"], recipient_data)
        body_text = replace_variables(campaign.get("body_text", ""), recipient_data) if campaign.get("body_text") else ""
        from_name = campaign.get("from_name", account.get("display_name", ""))
        
        # Send email
        if account.get("account_type") == "smtp" and account.get("smtp_host"):
            result = await send_email_smtp(
                account=account,
                to_email=queue_item["recipient_email"],
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                from_name=from_name,
                user_id=user_id
            )
        else:
            # Simulated sending for demo accounts
            logger.info(f"[SIMULATED] Sending to {queue_item['recipient_email']}")
            result = {"success": random.random() < 0.95}
            if not result["success"]:
                result["error"] = "Simulated failure"
        
        # Update queue item
        if result.get("success"):
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

async def get_super_admin_user(request: Request) -> dict:
    """Get current user and verify super_admin role"""
    user = await get_current_user(request)
    user_doc = await db.users.find_one({"user_id": user.user_id}, {"_id": 0})
    
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    
    role = user_doc.get("role", "user")
    if role != "super_admin":
        raise HTTPException(status_code=403, detail="Access denied. Super admin required.")
    
    return user_doc

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
        
        # Check if user registered with Google (cannot reset password)
        if user.get("provider") == "google":
            raise HTTPException(status_code=400, detail="This user registered with Google. Cannot reset password for OAuth accounts.")
        
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
        subscription_status = user.get("subscription_status", "trialing")
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
            "trial_active": False,
            "trial_end_date": None,
            "subscription_end_date": None,
            "grace_period_end": None,
            "is_permanent_plan": user.get("email", "").lower() in PERMANENT_PLAN_ASSIGNMENTS,
            "admin_override_active": user.get("admin_override_active", False),
            "admin_override_plan": user.get("admin_override_plan"),
            "admin_override_updated_at": user.get("admin_override_updated_at"),
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
        
        # Check trial status
        trial_ends_at = user.get("trial_ends_at")
        if trial_ends_at:
            if isinstance(trial_ends_at, str):
                trial_dt = datetime.fromisoformat(trial_ends_at.replace('Z', '+00:00'))
            else:
                trial_dt = trial_ends_at
            if trial_dt.tzinfo is None:
                trial_dt = trial_dt.replace(tzinfo=timezone.utc)
            
            subscription_info["trial_end_date"] = trial_ends_at
            subscription_info["trial_active"] = datetime.now(timezone.utc) < trial_dt and subscription_status == "trialing"
        
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
    plan: str  # "starter" or "growth"

@api_router.post("/admin/users/{user_id}/assign-plan")
async def admin_assign_plan(
    user_id: str,
    request: AdminPlanOverrideRequest,
    admin: dict = Depends(get_super_admin_user)
):
    """
    Assign a plan to a user via admin override.
    Only works for users WITHOUT an active Stripe subscription.
    """
    try:
        # Find the user
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Validate plan type
        if request.plan not in ["starter", "growth"]:
            raise HTTPException(status_code=400, detail="Plan must be 'starter' or 'growth'")
        
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
        
        # Apply admin override
        update_data = {
            "admin_override_active": True,
            "admin_override_plan": request.plan,
            "plan_type": request.plan,
            "plan_source": "admin_override",
            "admin_override_updated_at": datetime.now(timezone.utc).isoformat(),
            # Clear trial expiry since they now have a plan
            "subscription_status": "active"
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
        
        # Remove override and revert to free
        update_data = {
            "admin_override_active": False,
            "admin_override_plan": None,
            "plan_type": "free",
            "plan_source": "free",
            "admin_override_updated_at": datetime.now(timezone.utc).isoformat(),
            "subscription_status": "trialing"  # Revert to trial status
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
        "subscription_status": user_doc.get("subscription_status", "trialing"),
        "subscription_active": sub_status.get("active", False),
        "status_details": sub_status,
        "trial_ends_at": user_doc.get("trial_ends_at"),
        "billing_cycle_end": user_doc.get("billing_cycle_end"),
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
        "free_plan": {
            "name": "Free Trial",
            "trial_days": 14,
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
    """Handle subscription cancellation"""
    try:
        customer_id = subscription.get("customer")
        
        user = await db.users.find_one({"stripe_customer_id": customer_id}, {"_id": 0})
        if not user:
            return
        
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {
                "plan_type": "free",
                "subscription_status": "canceled",
                "stripe_subscription_id": None,
                "billing_cycle_start": None,
                "billing_cycle_end": None
            }}
        )
        
        logger.info(f"Subscription canceled for user {user['user_id']}")
        
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
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
