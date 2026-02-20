from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, UploadFile, File, BackgroundTasks, Depends, Query
from fastapi.responses import RedirectResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
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
    status: str = "draft"  # draft, running, paused, paused_daily_limit, completed, failed
    total_emails: int = 0
    sent_count: int = 0
    failed_count: int = 0
    current_account_index: int = 0
    is_locked: bool = False  # Prevents editing when running
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

class UpdateCampaignRequest(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    body_text: Optional[str] = None
    from_name: Optional[str] = None
    list_id: Optional[str] = None
    account_ids: Optional[List[str]] = None

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
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {
                "name": name, 
                "picture": picture,
                "subscription_status": "active",
                "subscription_expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
            }}
        )
    else:
        new_user = User(
            user_id=user_id,
            email=email,
            name=name,
            picture=picture,
            subscription_status="active",
            subscription_expires_at=datetime.now(timezone.utc) + timedelta(days=365)
        )
        user_dict = new_user.model_dump()
        user_dict["created_at"] = user_dict["created_at"].isoformat()
        if user_dict.get("subscription_expires_at"):
            user_dict["subscription_expires_at"] = user_dict["subscription_expires_at"].isoformat()
        await db.users.insert_one(user_dict)
    
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
    return user_doc

@api_router.get("/auth/me")
async def get_me(user: User = Depends(get_current_user)):
    return user.model_dump()

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie(key="session_token", path="/", secure=True, samesite="none")
    return {"message": "Logged out"}

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
    
    return accounts

@api_router.post("/accounts/smtp")
async def add_smtp_account(request: AddSMTPAccountRequest, user: User = Depends(get_current_user)):
    """Add a new SMTP email account"""
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
    
    content = await file.read()
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
        status="draft"
    )
    
    camp_dict = campaign.model_dump()
    camp_dict["created_at"] = camp_dict["created_at"].isoformat()
    camp_dict["updated_at"] = camp_dict["updated_at"].isoformat()
    
    await db.campaigns.insert_one(camp_dict)
    
    return {"campaign_id": campaign.campaign_id, "status": campaign.status}

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
            "started_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Start background task
    background_tasks.add_task(process_campaign_queue, campaign_id, user.user_id)
    
    return {"message": "Campaign started", "status": "running", "campaign_id": campaign_id}

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
        
        unsubscribe_url = f"https://bulk-send-hub.preview.emergentagent.com/api/unsubscribe/{user_id}/{to_email}"
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
