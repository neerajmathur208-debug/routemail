from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, UploadFile, File, BackgroundTasks, Depends
from fastapi.responses import RedirectResponse
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

# Stripe integration
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Stripe setup
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', 'sk_test_emergent')
SUBSCRIPTION_AMOUNT = 99.00  # $99/year

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

# ==================== MODELS ====================

class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    subscription_status: str = "inactive"  # active, inactive, expired
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
    email: str
    display_name: str
    status: str = "connected"  # connected, error, disconnected
    daily_send_count: int = 0
    last_send_date: Optional[str] = None  # YYYY-MM-DD format
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class EmailList(BaseModel):
    list_id: str = Field(default_factory=lambda: f"list_{uuid.uuid4().hex[:12]}")
    user_id: str
    name: str
    total_emails: int = 0
    valid_emails: int = 0
    emails: List[Dict[str, Any]] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Campaign(BaseModel):
    campaign_id: str = Field(default_factory=lambda: f"camp_{uuid.uuid4().hex[:12]}")
    user_id: str
    list_id: str
    subject: str
    body: str
    status: str = "draft"  # draft, running, paused, completed
    total_emails: int = 0
    sent_count: int = 0
    failed_count: int = 0
    current_account_index: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class EmailQueueItem(BaseModel):
    queue_id: str = Field(default_factory=lambda: f"q_{uuid.uuid4().hex[:12]}")
    campaign_id: str
    user_id: str
    to_email: str
    to_name: Optional[str] = None
    company: Optional[str] = None
    custom_fields: Dict[str, Any] = {}
    status: str = "pending"  # pending, sent, failed
    sent_at: Optional[datetime] = None
    sent_from_account: Optional[str] = None
    error_reason: Optional[str] = None

class PaymentTransaction(BaseModel):
    transaction_id: str = Field(default_factory=lambda: f"txn_{uuid.uuid4().hex[:12]}")
    user_id: str
    session_id: str
    amount: float
    currency: str = "usd"
    status: str = "pending"  # pending, paid, failed, expired
    payment_status: str = "initiated"
    metadata: Dict[str, str] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ==================== REQUEST/RESPONSE MODELS ====================

class SessionRequest(BaseModel):
    session_id: str

class AddEmailAccountRequest(BaseModel):
    email: str
    display_name: str

class CreateListRequest(BaseModel):
    name: str
    emails: List[Dict[str, Any]]

class CreateCampaignRequest(BaseModel):
    list_id: str
    subject: str
    body: str

class CheckoutRequest(BaseModel):
    origin_url: str

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

async def require_active_subscription(user: User = Depends(get_current_user)) -> User:
    """Require user to have active subscription"""
    if user.subscription_status != "active":
        raise HTTPException(status_code=403, detail="Active subscription required")
    return user

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
    
    # Check if user exists
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})
    
    if existing_user:
        user_id = existing_user["user_id"]
        # Update user info
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture}}
        )
    else:
        # Create new user
        new_user = User(
            user_id=user_id,
            email=email,
            name=name,
            picture=picture
        )
        user_dict = new_user.model_dump()
        user_dict["created_at"] = user_dict["created_at"].isoformat()
        if user_dict.get("subscription_expires_at"):
            user_dict["subscription_expires_at"] = user_dict["subscription_expires_at"].isoformat()
        await db.users.insert_one(user_dict)
    
    # Create session
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
    
    # Get updated user
    user_doc = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    
    return user_doc

@api_router.get("/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    """Get current user info"""
    return user.model_dump()

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout and clear session"""
    session_token = request.cookies.get("session_token")
    
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    
    response.delete_cookie(
        key="session_token",
        path="/",
        secure=True,
        samesite="none"
    )
    
    return {"message": "Logged out"}

# ==================== STRIPE PAYMENT ENDPOINTS ====================

@api_router.post("/payments/checkout")
async def create_checkout(request: CheckoutRequest, user: User = Depends(get_current_user)):
    """Create Stripe checkout session for subscription"""
    host_url = request.origin_url.rstrip("/")
    webhook_url = f"{host_url}/api/webhook/stripe"
    
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    
    success_url = f"{host_url}/subscription?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{host_url}/subscription"
    
    checkout_request = CheckoutSessionRequest(
        amount=SUBSCRIPTION_AMOUNT,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id": user.user_id,
            "plan": "yearly",
            "source": "web_checkout"
        }
    )
    
    session = await stripe_checkout.create_checkout_session(checkout_request)
    
    # Create payment transaction record
    transaction = PaymentTransaction(
        user_id=user.user_id,
        session_id=session.session_id,
        amount=SUBSCRIPTION_AMOUNT,
        currency="usd",
        status="pending",
        payment_status="initiated",
        metadata={"plan": "yearly"}
    )
    tx_dict = transaction.model_dump()
    tx_dict["created_at"] = tx_dict["created_at"].isoformat()
    await db.payment_transactions.insert_one(tx_dict)
    
    return {"url": session.url, "session_id": session.session_id}

@api_router.get("/payments/status/{session_id}")
async def get_payment_status(session_id: str, request: Request, user: User = Depends(get_current_user)):
    """Check payment status and activate subscription if paid"""
    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}api/webhook/stripe"
    
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
    
    try:
        status = await stripe_checkout.get_checkout_status(session_id)
    except Exception as e:
        logger.error(f"Error getting checkout status: {e}")
        raise HTTPException(status_code=400, detail="Failed to get payment status")
    
    # Update transaction
    tx_doc = await db.payment_transactions.find_one(
        {"session_id": session_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if tx_doc and tx_doc.get("payment_status") != "paid":
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "status": status.status,
                "payment_status": status.payment_status
            }}
        )
        
        # Activate subscription if paid
        if status.payment_status == "paid":
            expires_at = datetime.now(timezone.utc) + timedelta(days=365)
            await db.users.update_one(
                {"user_id": user.user_id},
                {"$set": {
                    "subscription_status": "active",
                    "subscription_expires_at": expires_at.isoformat()
                }}
            )
    
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency
    }

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    body = await request.body()
    signature = request.headers.get("Stripe-Signature")
    
    # For now, just log the webhook
    logger.info(f"Received Stripe webhook")
    
    return {"received": True}

# ==================== EMAIL ACCOUNT ENDPOINTS ====================

@api_router.get("/accounts")
async def get_email_accounts(user: User = Depends(get_current_user)):
    """Get all connected email accounts"""
    accounts = await db.email_accounts.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    
    # Reset daily count if it's a new day
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for acc in accounts:
        if acc.get("last_send_date") != today:
            acc["daily_send_count"] = 0
    
    return accounts

@api_router.post("/accounts")
async def add_email_account(request: AddEmailAccountRequest, user: User = Depends(require_active_subscription)):
    """Add a new email account (simulated - no real OAuth)"""
    # Check if account already exists
    existing = await db.email_accounts.find_one(
        {"user_id": user.user_id, "email": request.email},
        {"_id": 0}
    )
    
    if existing:
        raise HTTPException(status_code=400, detail="Email account already connected")
    
    account = EmailAccount(
        user_id=user.user_id,
        email=request.email,
        display_name=request.display_name
    )
    
    acc_dict = account.model_dump()
    acc_dict["created_at"] = acc_dict["created_at"].isoformat()
    await db.email_accounts.insert_one(acc_dict)
    
    return {"account_id": account.account_id, "email": account.email, "status": "connected"}

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
        {"_id": 0, "emails": 0}  # Exclude full email list for performance
    ).to_list(100)
    
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
    user: User = Depends(require_active_subscription)
):
    """Upload and parse CSV file"""
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    content = await file.read()
    text_content = content.decode('utf-8')
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(text_content))
    emails = []
    seen_emails = set()
    
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    
    for row in reader:
        # Normalize column names (lowercase, strip)
        normalized_row = {k.lower().strip(): v.strip() if v else "" for k, v in row.items()}
        
        email = normalized_row.get('email', '')
        
        if not email or not email_pattern.match(email):
            continue
        
        # Check for duplicates
        if email.lower() in seen_emails:
            continue
        
        seen_emails.add(email.lower())
        
        emails.append({
            "email": email,
            "first_name": normalized_row.get('first_name', ''),
            "company": normalized_row.get('company', ''),
            "custom_fields": {k: v for k, v in normalized_row.items() if k not in ['email', 'first_name', 'company']}
        })
    
    if not emails:
        raise HTTPException(status_code=400, detail="No valid emails found in CSV")
    
    # Return preview (don't save yet)
    return {
        "total_rows": len(list(csv.DictReader(io.StringIO(text_content)))) + len(emails),
        "valid_emails": len(emails),
        "duplicates_removed": len(seen_emails),
        "preview": emails[:10],
        "emails": emails
    }

@api_router.post("/lists")
async def create_email_list(request: CreateListRequest, user: User = Depends(require_active_subscription)):
    """Save email list"""
    # Check suppression list
    suppression = await db.suppression_list.find(
        {"user_id": user.user_id},
        {"_id": 0, "email": 1}
    ).to_list(10000)
    
    suppressed_emails = {s["email"].lower() for s in suppression}
    
    # Filter out suppressed emails
    filtered_emails = [e for e in request.emails if e["email"].lower() not in suppressed_emails]
    
    email_list = EmailList(
        user_id=user.user_id,
        name=request.name,
        total_emails=len(request.emails),
        valid_emails=len(filtered_emails),
        emails=filtered_emails
    )
    
    list_dict = email_list.model_dump()
    list_dict["created_at"] = list_dict["created_at"].isoformat()
    await db.email_lists.insert_one(list_dict)
    
    return {
        "list_id": email_list.list_id,
        "name": email_list.name,
        "total_emails": email_list.total_emails,
        "valid_emails": email_list.valid_emails
    }

@api_router.delete("/lists/{list_id}")
async def delete_email_list(list_id: str, user: User = Depends(get_current_user)):
    """Delete an email list"""
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
    
    # Get queue stats
    pending = await db.email_queue.count_documents({"campaign_id": campaign_id, "status": "pending"})
    sent = await db.email_queue.count_documents({"campaign_id": campaign_id, "status": "sent"})
    failed = await db.email_queue.count_documents({"campaign_id": campaign_id, "status": "failed"})
    
    campaign["pending_count"] = pending
    campaign["sent_count"] = sent
    campaign["failed_count"] = failed
    
    return campaign

@api_router.post("/campaigns")
async def create_campaign(request: CreateCampaignRequest, user: User = Depends(require_active_subscription)):
    """Create a new campaign"""
    # Check for existing running campaign
    running = await db.campaigns.find_one(
        {"user_id": user.user_id, "status": "running"},
        {"_id": 0}
    )
    
    if running:
        raise HTTPException(status_code=400, detail="You already have a running campaign. Please wait for it to complete.")
    
    # Get email list
    email_list = await db.email_lists.find_one(
        {"list_id": request.list_id, "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not email_list:
        raise HTTPException(status_code=404, detail="Email list not found")
    
    campaign = Campaign(
        user_id=user.user_id,
        list_id=request.list_id,
        subject=request.subject,
        body=request.body,
        total_emails=len(email_list["emails"])
    )
    
    camp_dict = campaign.model_dump()
    camp_dict["created_at"] = camp_dict["created_at"].isoformat()
    if camp_dict.get("started_at"):
        camp_dict["started_at"] = camp_dict["started_at"].isoformat()
    if camp_dict.get("completed_at"):
        camp_dict["completed_at"] = camp_dict["completed_at"].isoformat()
    
    await db.campaigns.insert_one(camp_dict)
    
    return {"campaign_id": campaign.campaign_id, "status": campaign.status}

@api_router.post("/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: str, background_tasks: BackgroundTasks, user: User = Depends(require_active_subscription)):
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
        raise HTTPException(status_code=400, detail="Campaign is already completed")
    
    # Get email accounts
    accounts = await db.email_accounts.find(
        {"user_id": user.user_id, "status": "connected"},
        {"_id": 0}
    ).to_list(100)
    
    if not accounts:
        raise HTTPException(status_code=400, detail="No connected email accounts. Please add at least one account.")
    
    # Get email list
    email_list = await db.email_lists.find_one(
        {"list_id": campaign["list_id"], "user_id": user.user_id},
        {"_id": 0}
    )
    
    if not email_list:
        raise HTTPException(status_code=404, detail="Email list not found")
    
    # Create queue items
    queue_items = []
    for email_data in email_list["emails"]:
        item = EmailQueueItem(
            campaign_id=campaign_id,
            user_id=user.user_id,
            to_email=email_data["email"],
            to_name=email_data.get("first_name"),
            company=email_data.get("company"),
            custom_fields=email_data.get("custom_fields", {})
        )
        item_dict = item.model_dump()
        queue_items.append(item_dict)
    
    if queue_items:
        await db.email_queue.insert_many(queue_items)
    
    # Update campaign status
    await db.campaigns.update_one(
        {"campaign_id": campaign_id},
        {"$set": {
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Start background task
    background_tasks.add_task(process_campaign_queue, campaign_id, user.user_id)
    
    return {"message": "Campaign started", "status": "running"}

@api_router.post("/campaigns/{campaign_id}/pause")
async def pause_campaign(campaign_id: str, user: User = Depends(get_current_user)):
    """Pause a running campaign"""
    result = await db.campaigns.update_one(
        {"campaign_id": campaign_id, "user_id": user.user_id, "status": "running"},
        {"$set": {"status": "paused"}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Campaign not found or not running")
    
    return {"message": "Campaign paused", "status": "paused"}

@api_router.post("/campaigns/{campaign_id}/resume")
async def resume_campaign(campaign_id: str, background_tasks: BackgroundTasks, user: User = Depends(require_active_subscription)):
    """Resume a paused campaign"""
    campaign = await db.campaigns.find_one(
        {"campaign_id": campaign_id, "user_id": user.user_id, "status": "paused"},
        {"_id": 0}
    )
    
    if not campaign:
        raise HTTPException(status_code=400, detail="Campaign not found or not paused")
    
    await db.campaigns.update_one(
        {"campaign_id": campaign_id},
        {"$set": {"status": "running"}}
    )
    
    background_tasks.add_task(process_campaign_queue, campaign_id, user.user_id)
    
    return {"message": "Campaign resumed", "status": "running"}

# ==================== SUPPRESSION LIST ====================

@api_router.get("/suppression")
async def get_suppression_list(user: User = Depends(get_current_user)):
    """Get suppression list"""
    items = await db.suppression_list.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(1000)
    
    return items

@api_router.post("/suppression")
async def add_to_suppression(email: str, user: User = Depends(get_current_user)):
    """Add email to suppression list"""
    existing = await db.suppression_list.find_one(
        {"user_id": user.user_id, "email": email.lower()}
    )
    
    if not existing:
        await db.suppression_list.insert_one({
            "user_id": user.user_id,
            "email": email.lower(),
            "added_at": datetime.now(timezone.utc).isoformat()
        })
    
    return {"message": "Added to suppression list"}

# Unsubscribe endpoint (public)
@api_router.get("/unsubscribe/{user_id}/{email}")
async def unsubscribe(user_id: str, email: str):
    """Public unsubscribe endpoint"""
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
    """Get dashboard statistics"""
    # Get account stats
    accounts = await db.email_accounts.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    account_stats = []
    total_available_today = 0
    
    for acc in accounts:
        daily_count = acc.get("daily_send_count", 0) if acc.get("last_send_date") == today else 0
        remaining = 50 - daily_count
        total_available_today += max(0, remaining)
        
        account_stats.append({
            "account_id": acc["account_id"],
            "email": acc["email"],
            "display_name": acc["display_name"],
            "status": acc["status"],
            "daily_sent": daily_count,
            "daily_limit": 50,
            "remaining": max(0, remaining)
        })
    
    # Get campaign stats
    campaigns = await db.campaigns.find(
        {"user_id": user.user_id},
        {"_id": 0}
    ).to_list(100)
    
    total_sent = sum(c.get("sent_count", 0) for c in campaigns)
    total_failed = sum(c.get("failed_count", 0) for c in campaigns)
    
    # Get current campaign
    current_campaign = await db.campaigns.find_one(
        {"user_id": user.user_id, "status": "running"},
        {"_id": 0}
    )
    
    # Get lists
    lists = await db.email_lists.find(
        {"user_id": user.user_id},
        {"_id": 0, "emails": 0}
    ).to_list(100)
    
    total_contacts = sum(l.get("valid_emails", 0) for l in lists)
    
    return {
        "accounts": account_stats,
        "total_accounts": len(accounts),
        "total_available_today": total_available_today,
        "total_sent": total_sent,
        "total_failed": total_failed,
        "total_contacts": total_contacts,
        "total_lists": len(lists),
        "total_campaigns": len(campaigns),
        "current_campaign": current_campaign,
        "subscription_status": user.subscription_status,
        "subscription_expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None
    }

# ==================== BACKGROUND EMAIL PROCESSING ====================

async def process_campaign_queue(campaign_id: str, user_id: str):
    """Process campaign queue with rotational sending"""
    logger.info(f"Starting campaign processing: {campaign_id}")
    
    while True:
        # Check campaign status
        campaign = await db.campaigns.find_one(
            {"campaign_id": campaign_id},
            {"_id": 0}
        )
        
        if not campaign or campaign["status"] != "running":
            logger.info(f"Campaign {campaign_id} stopped or not running")
            break
        
        # Get next pending email
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
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            logger.info(f"Campaign {campaign_id} completed")
            break
        
        # Get available accounts
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        accounts = await db.email_accounts.find(
            {"user_id": user_id, "status": "connected"},
            {"_id": 0}
        ).to_list(100)
        
        if not accounts:
            logger.error(f"No accounts available for campaign {campaign_id}")
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {"$set": {"status": "paused"}}
            )
            break
        
        # Find available account (rotational)
        current_index = campaign.get("current_account_index", 0)
        account = None
        checked = 0
        
        while checked < len(accounts):
            idx = (current_index + checked) % len(accounts)
            acc = accounts[idx]
            
            # Reset count if new day
            if acc.get("last_send_date") != today:
                acc["daily_send_count"] = 0
            
            if acc.get("daily_send_count", 0) < 50:
                account = acc
                current_index = (idx + 1) % len(accounts)
                break
            
            checked += 1
        
        if not account:
            # All accounts hit daily limit
            logger.info(f"All accounts hit daily limit for campaign {campaign_id}")
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {"$set": {"status": "paused"}}
            )
            break
        
        # Send email (simulated)
        success = await send_email_simulated(
            from_account=account,
            to_email=queue_item["to_email"],
            to_name=queue_item.get("to_name"),
            company=queue_item.get("company"),
            subject=campaign["subject"],
            body=campaign["body"],
            user_id=user_id
        )
        
        # Update queue item
        if success:
            await db.email_queue.update_one(
                {"queue_id": queue_item["queue_id"]},
                {"$set": {
                    "status": "sent",
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "sent_from_account": account["account_id"]
                }}
            )
            
            # Update account send count
            await db.email_accounts.update_one(
                {"account_id": account["account_id"]},
                {"$set": {
                    "daily_send_count": account.get("daily_send_count", 0) + 1,
                    "last_send_date": today
                }}
            )
            
            # Update campaign stats
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {
                    "$inc": {"sent_count": 1},
                    "$set": {"current_account_index": current_index}
                }
            )
        else:
            await db.email_queue.update_one(
                {"queue_id": queue_item["queue_id"]},
                {"$set": {
                    "status": "failed",
                    "error_reason": "Simulated send failure"
                }}
            )
            
            await db.campaigns.update_one(
                {"campaign_id": campaign_id},
                {"$inc": {"failed_count": 1}}
            )
        
        # Random delay between 30-90 seconds (reduced to 2-5 seconds for demo)
        delay = random.uniform(2, 5)
        logger.info(f"Waiting {delay:.1f}s before next email")
        await asyncio.sleep(delay)

async def send_email_simulated(from_account: dict, to_email: str, to_name: Optional[str], 
                                company: Optional[str], subject: str, body: str, user_id: str) -> bool:
    """Simulate sending an email (replace with real SMTP later)"""
    
    # Personalize subject and body
    personalized_subject = subject
    personalized_body = body
    
    if to_name:
        personalized_subject = personalized_subject.replace("{first_name}", to_name)
        personalized_body = personalized_body.replace("{first_name}", to_name)
    else:
        personalized_subject = personalized_subject.replace("{first_name}", "")
        personalized_body = personalized_body.replace("{first_name}", "")
    
    if company:
        personalized_subject = personalized_subject.replace("{company}", company)
        personalized_body = personalized_body.replace("{company}", company)
    else:
        personalized_subject = personalized_subject.replace("{company}", "")
        personalized_body = personalized_body.replace("{company}", "")
    
    # Add unsubscribe link
    unsubscribe_link = f"\n\n---\nTo unsubscribe, click here: /api/unsubscribe/{user_id}/{to_email}"
    personalized_body += unsubscribe_link
    
    logger.info(f"[SIMULATED] Sending email from {from_account['email']} to {to_email}")
    logger.info(f"[SIMULATED] Subject: {personalized_subject}")
    
    # Simulate 95% success rate
    return random.random() < 0.95

# ==================== BASIC ROUTES ====================

@api_router.get("/")
async def root():
    return {"message": "Rotation Email Tool API"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include the router in the main app
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
