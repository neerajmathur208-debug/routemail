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
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'https://routemail.co')
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
    logger.warning(f"WARNING: FRONTEND_URL is set to a preview domain. For production, ensure FRONTEND_URL=https://routemail.co")

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
    """Generate verification email HTML"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f4f4f5; margin: 0; padding: 40px 20px;">
        <div style="max-width: 560px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
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
    """Generate welcome email subject and HTML based on plan type"""
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
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f4f4f5; margin: 0; padding: 40px 20px;">
        <div style="max-width: 560px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
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
    """Generate password reset email HTML"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f4f4f5; margin: 0; padding: 40px 20px;">
        <div style="max-width: 560px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);">
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

# ==================== PLAN ENFORCEMENT HELPERS ====================

async def get_user_plan_limits(user_id: str) -> dict:
    """Get the plan limits for a user"""
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return PLAN_LIMITS["free"]
    
    plan_type = user.get("plan_type", "free")
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
    
    plan_type = user.get("plan_type", "free")
    status = user.get("subscription_status", "trialing")
    
    # Check for paid plans
    if plan_type in ["starter", "growth"]:
        if status == "active":
            return {"active": True, "plan": plan_type, "status": status}
        elif status == "past_due":
            # Check grace period
            grace_end = user.get("grace_period_end")
            if grace_end:
                if isinstance(grace_end, str):
                    grace_end = datetime.fromisoformat(grace_end.replace('Z', '+00:00'))
                if grace_end.tzinfo is None:
                    grace_end = grace_end.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < grace_end:
                    return {"active": True, "plan": plan_type, "status": "grace_period", "grace_ends": grace_end.isoformat()}
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
                    return {"active": True, "plan": plan_type, "status": "canceled_active", "ends": cycle_end.isoformat()}
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
                return {"active": True, "plan": "free", "status": "trialing", "trial_ends": trial_end.isoformat()}
            else:
                # Trial expired
                await db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"subscription_status": "expired"}}
                )
                return {"active": False, "reason": "Trial expired", "status": "expired"}
        return {"active": True, "plan": "free", "status": "trialing"}
    
    if status == "expired":
        return {"active": False, "reason": "Trial expired", "status": "expired"}
    
    return {"active": True, "plan": plan_type, "status": status}

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

class UpdateAccountLimitRequest(BaseModel):
    daily_limit: int

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
    # Validate passwords match
    if request.password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    # Validate password strength
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    
    # Check if user already exists
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
                if datetime.now(timezone.utc) > created_at + timedelta(hours=2):
                    # Delete expired unverified account
                    await db.users.delete_one({"email": request.email})
                else:
                    raise HTTPException(status_code=400, detail="Please check your email to verify your account. Check spam folder too.")
            else:
                raise HTTPException(status_code=400, detail="Email already registered")
        else:
            raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    password_hash = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Generate verification token
    verification_token = secrets.token_urlsafe(32)
    verification_expires = datetime.now(timezone.utc) + timedelta(hours=2)
    
    # Create user with proper subscription fields
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
        # Email verification
        "email_verified": False,
        "verification_token": verification_token,
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
    
    # Insert user document - ensure this completes before proceeding
    try:
        result = await db.users.insert_one(user_doc)
        logger.info(f"User created: {request.email} with user_id: {user_id}")
    except Exception as e:
        logger.error(f"Failed to create user {request.email}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create account. Please try again.")
    
    # Apply permanent plan assignment if applicable
    await apply_permanent_plan_if_applicable(request.email, user_id)
    
    # Send verification email in background (won't block response)
    first_name = request.name.split()[0] if request.name else "there"
    verification_link = f"{FRONTEND_URL}/verify-email?token={verification_token}"
    logger.info(f"Verification link for {request.email}: {verification_link}")
    html_content = get_verification_email_html(first_name, verification_link)
    
    background_tasks.add_task(
        send_email_async,
        request.email,
        "Verify Your RouteMail Account",
        html_content
    )
    
    # Return success - user is created, email will be sent in background
    return JSONResponse(
        status_code=201,
        content={
            "message": "Registration successful! Please check your email to verify your account.",
            "email": request.email,
            "requires_verification": True
        }
    )

@api_router.get("/auth/verify-email")
async def verify_email(token: str, response: Response, background_tasks: BackgroundTasks):
    """Verify email address with token"""
    if not token or len(token) < 10:
        raise HTTPException(status_code=400, detail="Invalid verification link.")
    
    # Find user with this token
    user = await db.users.find_one({"verification_token": token}, {"_id": 0})
    
    if not user:
        # Token not found - could be already used or invalid
        raise HTTPException(status_code=400, detail="Invalid verification link. The link may have already been used or expired.")
    
    # Check if already verified (shouldn't happen, but handle gracefully)
    if user.get("email_verified", False):
        # Already verified - clear token and return success
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$unset": {"verification_token": "", "verification_expires": ""}}
        )
        logger.info(f"User {user['email']} already verified, clearing token")
        return {
            "message": "Email already verified!",
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user.get("name"),
            "plan_type": user.get("plan_type", "free"),
            "verified": True,
            "redirect_url": f"{FRONTEND_URL}/dashboard"
        }
    
    # Check if token expired
    expires = user.get("verification_expires")
    if expires:
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires.replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > expires:
            # Delete expired user
            await db.users.delete_one({"user_id": user["user_id"]})
            logger.info(f"Deleted expired unverified user: {user['email']}")
            raise HTTPException(status_code=400, detail="Verification link has expired. Please register again.")
    
    # Mark email as verified and remove token atomically
    result = await db.users.update_one(
        {"user_id": user["user_id"], "verification_token": token},  # Ensure token still matches
        {
            "$set": {"email_verified": True},
            "$unset": {"verification_token": "", "verification_expires": ""}
        }
    )
    
    if result.modified_count == 0:
        # Token was already consumed (race condition)
        logger.warning(f"Token already consumed for user {user['email']}")
        raise HTTPException(status_code=400, detail="Invalid verification link. The link may have already been used.")
    
    logger.info(f"Email verified successfully for: {user['email']}")
    
    # Get updated user data
    updated_user = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    plan_type = updated_user.get("plan_type", "free") if updated_user else "free"
    
    # Send welcome email in background
    first_name = user.get("name", "").split()[0] if user.get("name") else "there"
    subject, html_content = get_welcome_email_html(first_name, plan_type)
    
    background_tasks.add_task(
        send_email_async,
        user["email"],
        subject,
        html_content
    )
    
    # Create session
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
    
    return {
        "message": "Email verified successfully!",
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user.get("name"),
        "plan_type": plan_type,
        "verified": True,
        "redirect_url": f"{FRONTEND_URL}/dashboard"
    }

@api_router.post("/auth/resend-verification")
async def resend_verification(email: EmailStr, background_tasks: BackgroundTasks):
    """Resend verification email"""
    user = await db.users.find_one({"email": email}, {"_id": 0})
    
    if not user:
        # Don't reveal if email exists
        return {"message": "If this email is registered, you will receive a verification link."}
    
    if user.get("email_verified", False):
        raise HTTPException(status_code=400, detail="Email is already verified")
    
    if user.get("provider") == "google":
        raise HTTPException(status_code=400, detail="This account uses Google sign-in")
    
    # Generate new verification token
    verification_token = secrets.token_urlsafe(32)
    verification_expires = datetime.now(timezone.utc) + timedelta(hours=2)
    
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "verification_token": verification_token,
                "verification_expires": verification_expires.isoformat()
            }
        }
    )
    
    # Send verification email
    first_name = user.get("name", "").split()[0] if user.get("name") else "there"
    verification_link = f"{FRONTEND_URL}/verify-email?token={verification_token}"
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
    """Upload and parse CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    # Check file size (max 2MB)
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:  # 2MB limit
        raise HTTPException(status_code=400, detail="File size exceeds 2MB limit. Please upload a smaller file.")
    
    text_content = content.decode('utf-8')
    
    reader = csv.DictReader(io.StringIO(text_content))
    column_headers = reader.fieldnames or []
    column_headers = [h.strip().lower() for h in column_headers]
    
    if 'email' not in column_headers:
        raise HTTPException(status_code=400, detail="CSV must contain an 'email' column")
    
    emails = []
    seen_emails = set()
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    for row in reader:
        normalized_row = {k.lower().strip(): v.strip() if v else "" for k, v in row.items()}
        email = normalized_row.get('email', '')
        
        if not email or not email_pattern.match(email):
            continue
        
        if email.lower() in seen_emails:
            continue
        
        seen_emails.add(email.lower())
        emails.append(normalized_row)
    
    if not emails:
        raise HTTPException(status_code=400, detail="No valid emails found in CSV")
    
    return {
        "original_filename": file.filename,
        "column_headers": column_headers,
        "total_rows": len(emails),
        "valid_emails": len(emails),
        "preview": emails[:10],
        "emails": emails
    }

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
    """Pause a running campaign"""
    result = await db.campaigns.update_one(
        {"campaign_id": campaign_id, "user_id": user.user_id, "status": "running"},
        {"$set": {"status": "paused", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Campaign not found or not running")
    
    return {"message": "Campaign paused", "status": "paused"}

@api_router.post("/campaigns/{campaign_id}/resume")
async def resume_campaign(campaign_id: str, background_tasks: BackgroundTasks, user: User = Depends(get_current_user)):
    """Resume a paused campaign"""
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id, "status": {"$in": ["paused", "paused_daily_limit"]}},
        {"_id": 0}
    )
    
    if not campaign:
        raise HTTPException(status_code=400, detail="Campaign not found or not paused")
    
    await db.campaigns.update_one(
        {"campaign_id": campaign_id},
        {"$set": {"status": "running", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    background_tasks.add_task(process_campaign_queue, campaign_id, user.user_id)
    
    return {"message": "Campaign resumed", "status": "running"}

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
        
        # Random delay between sends
        delay = random.uniform(3, 8)
        logger.info(f"Waiting {delay:.1f}s before next email")
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
