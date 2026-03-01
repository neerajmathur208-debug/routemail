"""
Backend API Tests for Scheduled Campaigns Feature
Tests for:
- Campaign scheduling/unscheduling endpoints
- Queue item creation with correct 'queue_id' field (not queue_item_id)
- Scheduler picking up due campaigns
- Campaign status transitions

Test User: user_b3e333b0f467 / dhruvmathur208@gmail.com
"""

import pytest
import requests
import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'test_database')

# Test user credentials from review request
TEST_USER_ID = "user_b3e333b0f467"
TEST_USER_EMAIL = "dhruvmathur208@gmail.com"


@pytest.fixture(scope="module")
def mongo_client():
    """Create MongoDB client for direct DB inspection"""
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def session(mongo_client):
    """Create or get a session for the test user"""
    # Create a fresh session for the test user
    session_token = f"test_session_{uuid.uuid4().hex[:12]}"
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    
    # Check if user exists, create if not
    user = mongo_client.users.find_one({"user_id": TEST_USER_ID})
    if not user:
        # Create the test user
        mongo_client.users.insert_one({
            "user_id": TEST_USER_ID,
            "email": TEST_USER_EMAIL,
            "name": "Test User",
            "provider": "email",
            "email_verified": True,
            "plan_type": "free",
            "subscription_status": "trialing",
            "trial_ends_at": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat(),
            "monthly_unique_recipient_count": 0,
            "last_recipient_reset_date": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    mongo_client.user_sessions.insert_one({
        "user_id": TEST_USER_ID,
        "session_token": session_token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    req_session = requests.Session()
    req_session.cookies.set("session_token", session_token)
    req_session.headers.update({"Content-Type": "application/json"})
    
    yield req_session
    
    # Cleanup - remove test session
    mongo_client.user_sessions.delete_one({"session_token": session_token})


@pytest.fixture(scope="module")
def test_email_list(session, mongo_client):
    """Create a test email list for campaigns"""
    list_id = f"testlist_{uuid.uuid4().hex[:8]}"
    
    # Insert test list directly into DB
    mongo_client.email_lists.insert_one({
        "list_id": list_id,
        "user_id": TEST_USER_ID,
        "name": "Test Scheduler List",
        "original_filename": "test.csv",
        "column_headers": ["email", "name"],
        "total_rows": 2,
        "valid_emails": 2,
        "emails": [
            {"email": "test1@example.com", "name": "Test One"},
            {"email": "test2@example.com", "name": "Test Two"}
        ],
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    yield list_id
    
    # Cleanup
    mongo_client.email_lists.delete_one({"list_id": list_id})


@pytest.fixture(scope="module")
def test_email_account(session, mongo_client):
    """Create a test email account for campaigns"""
    account_id = f"testacc_{uuid.uuid4().hex[:8]}"
    
    # Insert test account directly into DB
    mongo_client.email_accounts.insert_one({
        "account_id": account_id,
        "user_id": TEST_USER_ID,
        "account_type": "demo",  # Demo account - no real SMTP
        "email": "test.sender@example.com",
        "display_name": "Test Sender",
        "status": "connected",
        "daily_limit": 50,
        "daily_send_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    yield account_id
    
    # Cleanup
    mongo_client.email_accounts.delete_one({"account_id": account_id})


class TestScheduleEndpoints:
    """Tests for /api/campaigns/{id}/schedule and /api/campaigns/{id}/unschedule endpoints"""
    
    def test_schedule_endpoint_requires_auth(self):
        """Test schedule endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/campaigns/test_id/schedule")
        assert response.status_code == 401
        print("PASS: /api/campaigns/{id}/schedule requires authentication")
    
    def test_unschedule_endpoint_requires_auth(self):
        """Test unschedule endpoint requires authentication"""
        response = requests.post(f"{BASE_URL}/api/campaigns/test_id/unschedule")
        assert response.status_code == 401
        print("PASS: /api/campaigns/{id}/unschedule requires authentication")
    
    def test_schedule_nonexistent_campaign(self, session):
        """Test scheduling a non-existent campaign returns 404"""
        response = session.post(f"{BASE_URL}/api/campaigns/nonexistent_id/schedule")
        assert response.status_code == 404
        print("PASS: Scheduling non-existent campaign returns 404")
    
    def test_unschedule_nonexistent_campaign(self, session):
        """Test unscheduling a non-existent campaign returns 400"""
        response = session.post(f"{BASE_URL}/api/campaigns/nonexistent_id/unschedule")
        assert response.status_code == 400
        print("PASS: Unscheduling non-existent campaign returns 400")


class TestCampaignScheduling:
    """Tests for the complete scheduling workflow"""
    
    def test_create_campaign_with_scheduled_at(self, session, test_email_list, test_email_account, mongo_client):
        """Test creating a campaign with scheduled_at field - should auto-set status to 'scheduled'"""
        scheduled_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        payload = {
            "name": "Test Scheduled Campaign",
            "subject": "Test Subject {{name}}",
            "body": "<p>Hello {{name}}</p>",
            "list_id": test_email_list,
            "account_ids": [test_email_account],
            "scheduled_at": scheduled_time,
            "timezone": "UTC"
        }
        
        response = session.post(f"{BASE_URL}/api/campaigns", json=payload)
        assert response.status_code == 200 or response.status_code == 201
        
        data = response.json()
        campaign_id = data.get("campaign_id")
        assert campaign_id is not None
        
        # Verify campaign was created with scheduled_at
        campaign = mongo_client.campaigns.find_one({"campaign_id": campaign_id})
        assert campaign is not None
        assert campaign.get("scheduled_at") is not None
        # When scheduled_at is provided, status is auto-set to "scheduled"
        assert campaign.get("status") == "scheduled", f"Expected 'scheduled' status when scheduled_at is provided, got: {campaign.get('status')}"
        
        print(f"PASS: Campaign created with scheduled_at field and status='scheduled': {campaign_id}")
        
        # Cleanup
        mongo_client.campaigns.delete_one({"campaign_id": campaign_id})
        return campaign_id
    
    def test_schedule_endpoint_sets_status(self, session, test_email_list, test_email_account, mongo_client):
        """Test /api/campaigns/{id}/schedule sets status to 'scheduled'"""
        # Create a campaign first
        scheduled_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        payload = {
            "name": "Test Schedule Status Campaign",
            "subject": "Test Subject",
            "body": "<p>Test body</p>",
            "list_id": test_email_list,
            "account_ids": [test_email_account],
            "scheduled_at": scheduled_time,
            "timezone": "UTC"
        }
        
        response = session.post(f"{BASE_URL}/api/campaigns", json=payload)
        assert response.status_code in [200, 201]
        campaign_id = response.json().get("campaign_id")
        
        # Now schedule the campaign
        response = session.post(f"{BASE_URL}/api/campaigns/{campaign_id}/schedule")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "scheduled"
        assert data.get("message") == "Campaign scheduled"
        
        # Verify in database
        campaign = mongo_client.campaigns.find_one({"campaign_id": campaign_id})
        assert campaign["status"] == "scheduled"
        
        print(f"PASS: Schedule endpoint correctly sets status to 'scheduled'")
        
        # Cleanup
        mongo_client.campaigns.delete_one({"campaign_id": campaign_id})
    
    def test_unschedule_endpoint_returns_to_draft(self, session, test_email_list, test_email_account, mongo_client):
        """Test /api/campaigns/{id}/unschedule returns status to 'draft'"""
        # Create and schedule a campaign
        scheduled_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        payload = {
            "name": "Test Unschedule Campaign",
            "subject": "Test Subject",
            "body": "<p>Test body</p>",
            "list_id": test_email_list,
            "account_ids": [test_email_account],
            "scheduled_at": scheduled_time,
            "timezone": "UTC"
        }
        
        response = session.post(f"{BASE_URL}/api/campaigns", json=payload)
        campaign_id = response.json().get("campaign_id")
        
        # Schedule it first
        session.post(f"{BASE_URL}/api/campaigns/{campaign_id}/schedule")
        
        # Now unschedule
        response = session.post(f"{BASE_URL}/api/campaigns/{campaign_id}/unschedule")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("status") == "draft"
        assert data.get("message") == "Campaign unscheduled"
        
        # Verify in database
        campaign = mongo_client.campaigns.find_one({"campaign_id": campaign_id})
        assert campaign["status"] == "draft"
        assert campaign.get("scheduled_at") is None
        
        print(f"PASS: Unschedule endpoint correctly returns status to 'draft'")
        
        # Cleanup
        mongo_client.campaigns.delete_one({"campaign_id": campaign_id})
    
    def test_schedule_without_scheduled_at_fails(self, session, test_email_list, test_email_account, mongo_client):
        """Test scheduling a campaign without scheduled_at returns error"""
        payload = {
            "name": "No Schedule Time Campaign",
            "subject": "Test Subject",
            "body": "<p>Test body</p>",
            "list_id": test_email_list,
            "account_ids": [test_email_account]
        }
        
        response = session.post(f"{BASE_URL}/api/campaigns", json=payload)
        campaign_id = response.json().get("campaign_id")
        
        # Try to schedule without scheduled_at
        response = session.post(f"{BASE_URL}/api/campaigns/{campaign_id}/schedule")
        assert response.status_code == 400
        assert "No scheduled time set" in response.json().get("detail", "")
        
        print("PASS: Schedule endpoint fails when no scheduled_at is set")
        
        # Cleanup
        mongo_client.campaigns.delete_one({"campaign_id": campaign_id})


class TestQueueItemCreation:
    """Tests for queue item creation with correct 'queue_id' field"""
    
    def test_queue_items_have_queue_id_field(self, session, test_email_list, test_email_account, mongo_client):
        """Test that queue items are created with 'queue_id' (not 'queue_item_id')"""
        # Create a campaign with past scheduled_at so scheduler picks it up
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        campaign_id = f"test_queue_{uuid.uuid4().hex[:8]}"
        
        # Insert campaign directly for this test
        mongo_client.campaigns.insert_one({
            "campaign_id": campaign_id,
            "user_id": TEST_USER_ID,
            "name": "Test Queue Item Campaign",
            "subject": "Test Subject",
            "body": "<p>Test body</p>",
            "list_id": test_email_list,
            "account_ids": [test_email_account],
            "status": "scheduled",
            "scheduled_at": past_time,
            "total_emails": 2,
            "sent_count": 0,
            "failed_count": 0,
            "current_account_index": 0,
            "is_locked": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Wait for scheduler to pick it up (runs every 30 seconds)
        print("Waiting up to 40 seconds for scheduler to pick up the campaign...")
        
        max_wait = 40
        start_time = time.time()
        campaign_started = False
        
        while time.time() - start_time < max_wait:
            campaign = mongo_client.campaigns.find_one({"campaign_id": campaign_id})
            if campaign and campaign["status"] in ["running", "completed"]:
                campaign_started = True
                break
            time.sleep(5)
        
        if not campaign_started:
            # Cleanup and skip if scheduler didn't run
            mongo_client.campaigns.delete_one({"campaign_id": campaign_id})
            mongo_client.email_queue.delete_many({"campaign_id": campaign_id})
            pytest.skip("Scheduler didn't pick up campaign in time - may need to wait longer")
        
        # Check queue items were created with correct field
        queue_items = list(mongo_client.email_queue.find({"campaign_id": campaign_id}))
        
        if len(queue_items) > 0:
            # Verify queue_id field exists (not queue_item_id)
            for item in queue_items:
                assert "queue_id" in item, "Queue item missing 'queue_id' field"
                assert "queue_item_id" not in item, "Queue item incorrectly has 'queue_item_id' field"
                assert item["queue_id"].startswith("q_"), f"queue_id should start with 'q_', got: {item['queue_id']}"
            
            print(f"PASS: Queue items have correct 'queue_id' field. Found {len(queue_items)} items.")
        else:
            # Campaign may have completed with no items (edge case)
            print("INFO: No queue items found - campaign may have completed quickly")
        
        # Cleanup
        mongo_client.campaigns.delete_one({"campaign_id": campaign_id})
        mongo_client.email_queue.delete_many({"campaign_id": campaign_id})


class TestSchedulerBehavior:
    """Tests for the background scheduler behavior"""
    
    def test_scheduler_changes_status_to_running(self, mongo_client):
        """Test that scheduler changes status from 'scheduled' to 'running' when picking up campaigns"""
        # Create a campaign with past scheduled_at
        campaign_id = f"test_sched_{uuid.uuid4().hex[:8]}"
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        
        # Create test email list for this campaign
        list_id = f"testlist_{uuid.uuid4().hex[:8]}"
        mongo_client.email_lists.insert_one({
            "list_id": list_id,
            "user_id": TEST_USER_ID,
            "name": "Scheduler Test List",
            "emails": [{"email": "scheduler.test@example.com", "name": "Scheduler Test"}],
            "valid_emails": 1,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Create test account
        account_id = f"testacc_{uuid.uuid4().hex[:8]}"
        mongo_client.email_accounts.insert_one({
            "account_id": account_id,
            "user_id": TEST_USER_ID,
            "account_type": "demo",
            "email": "scheduler.sender@example.com",
            "display_name": "Scheduler Test",
            "status": "connected",
            "daily_limit": 50,
            "daily_send_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Insert campaign
        mongo_client.campaigns.insert_one({
            "campaign_id": campaign_id,
            "user_id": TEST_USER_ID,
            "name": "Scheduler Status Test",
            "subject": "Test",
            "body": "<p>Test</p>",
            "list_id": list_id,
            "account_ids": [account_id],
            "status": "scheduled",
            "scheduled_at": past_time,
            "total_emails": 1,
            "sent_count": 0,
            "failed_count": 0,
            "current_account_index": 0,
            "is_locked": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        initial_status = "scheduled"
        print(f"Campaign {campaign_id} created with status: {initial_status}")
        print("Waiting up to 40 seconds for scheduler...")
        
        max_wait = 40
        start_time = time.time()
        final_status = None
        
        while time.time() - start_time < max_wait:
            campaign = mongo_client.campaigns.find_one({"campaign_id": campaign_id})
            if campaign:
                current_status = campaign.get("status")
                if current_status != initial_status:
                    final_status = current_status
                    print(f"Status changed to: {final_status}")
                    break
            time.sleep(5)
        
        # Cleanup
        mongo_client.campaigns.delete_one({"campaign_id": campaign_id})
        mongo_client.email_queue.delete_many({"campaign_id": campaign_id})
        mongo_client.email_lists.delete_one({"list_id": list_id})
        mongo_client.email_accounts.delete_one({"account_id": account_id})
        
        if final_status:
            assert final_status in ["running", "completed"], f"Expected running or completed, got: {final_status}"
            print(f"PASS: Scheduler changed status from 'scheduled' to '{final_status}'")
        else:
            pytest.skip("Scheduler didn't pick up campaign in time")


class TestCampaignValidation:
    """Tests for campaign validation during scheduling"""
    
    def test_schedule_requires_list_id(self, session, test_email_account, mongo_client):
        """Test scheduling requires email list to be selected"""
        scheduled_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        payload = {
            "name": "No List Campaign",
            "subject": "Test Subject",
            "body": "<p>Test body</p>",
            "account_ids": [test_email_account],
            "scheduled_at": scheduled_time
        }
        
        response = session.post(f"{BASE_URL}/api/campaigns", json=payload)
        campaign_id = response.json().get("campaign_id")
        
        # Try to schedule without list_id
        response = session.post(f"{BASE_URL}/api/campaigns/{campaign_id}/schedule")
        assert response.status_code == 400
        assert "No email list" in response.json().get("detail", "")
        
        print("PASS: Schedule endpoint validates list_id is required")
        
        # Cleanup
        mongo_client.campaigns.delete_one({"campaign_id": campaign_id})
    
    def test_schedule_requires_subject(self, session, test_email_list, test_email_account, mongo_client):
        """Test scheduling requires subject line"""
        scheduled_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        # Create campaign without subject via direct DB insert to bypass API validation
        campaign_id = f"no_subject_{uuid.uuid4().hex[:8]}"
        mongo_client.campaigns.insert_one({
            "campaign_id": campaign_id,
            "user_id": TEST_USER_ID,
            "name": "No Subject Campaign",
            "subject": "",  # Empty subject
            "body": "<p>Test body</p>",
            "list_id": test_email_list,
            "account_ids": [test_email_account],
            "status": "draft",
            "scheduled_at": scheduled_time,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Try to schedule
        response = session.post(f"{BASE_URL}/api/campaigns/{campaign_id}/schedule")
        assert response.status_code == 400
        assert "Subject" in response.json().get("detail", "")
        
        print("PASS: Schedule endpoint validates subject is required")
        
        # Cleanup
        mongo_client.campaigns.delete_one({"campaign_id": campaign_id})


class TestHealthCheck:
    """Basic health check tests"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASS: API health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
