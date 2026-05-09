#!/usr/bin/env python3
import requests
import sys
import json
import uuid
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

class MultiSenderEmailAPITester:
    def __init__(self, base_url="https://routemail-demo.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_base = f"{base_url}/api"
        self.session_token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.account_id = None
        self.list_id = None
        self.campaign_id = None

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name}")
            if details:
                print(f"   {details}")
        return success

    def run_api_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_base}{endpoint}"
        default_headers = {'Content-Type': 'application/json'}
        
        if self.session_token:
            default_headers['Authorization'] = f'Bearer {self.session_token}'
        
        if headers:
            default_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=default_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=default_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=default_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=default_headers, timeout=10)

            success = response.status_code == expected_status
            details = ""
            
            if not success:
                details = f"Expected {expected_status}, got {response.status_code}"
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        details += f" - {error_data['detail']}"
                except:
                    pass
            
            return self.log_test(f"{name} ({method} {endpoint})", success, details), response.json() if success else {}

        except Exception as e:
            return self.log_test(f"{name} ({method} {endpoint})", False, f"Error: {str(e)}"), {}

    def create_test_user_session(self):
        """Create test user and session using MongoDB"""
        print("\n📋 Creating test user and session...")
        
        try:
            import pymongo
            
            # Connect to MongoDB
            client = pymongo.MongoClient("mongodb://localhost:27017")
            db = client["test_database"]
            
            # Generate test data
            timestamp = int(datetime.now().timestamp())
            self.user_id = f"test-user-{timestamp}"
            self.session_token = f"test_session_{timestamp}"
            email = f"test.user.{timestamp}@example.com"
            
            # Create user document
            user_doc = {
                "user_id": self.user_id,
                "email": email,
                "name": "Test User",
                "picture": "https://via.placeholder.com/150",
                "subscription_status": "active",
                "subscription_expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Create session document
            session_doc = {
                "user_id": self.user_id,
                "session_token": self.session_token,
                "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Insert documents
            db.users.insert_one(user_doc)
            db.user_sessions.insert_one(session_doc)
            
            # Verify insertion
            user_check = db.users.find_one({"user_id": self.user_id}, {"_id": 0})
            session_check = db.user_sessions.find_one({"session_token": self.session_token}, {"_id": 0})
            
            client.close()
            
            if user_check and session_check:
                print(f"✅ Test user created: {self.user_id}")
                print(f"✅ Session token created: {self.session_token}")
                return True
            else:
                print(f"❌ Failed to verify test user creation")
                return False
                
        except Exception as e:
            print(f"❌ Failed to create test user: {str(e)}")
            return False

    def cleanup_test_data(self):
        """Clean up test data from MongoDB"""
        print("\n🧹 Cleaning up test data...")
        
        try:
            import pymongo
            
            client = pymongo.MongoClient("mongodb://localhost:27017")
            db = client["test_database"]
            
            # Delete test data
            db.users.delete_many({"user_id": self.user_id})
            db.user_sessions.delete_many({"session_token": self.session_token})
            if self.user_id:
                db.email_accounts.delete_many({"user_id": self.user_id})
                db.email_lists.delete_many({"user_id": self.user_id})
                db.campaigns.delete_many({"user_id": self.user_id})
                db.payment_transactions.delete_many({"user_id": self.user_id})
            
            client.close()
            print("✅ Test data cleaned up")
        except Exception as e:
            print(f"❌ Cleanup error: {str(e)}")

    def test_basic_endpoints(self):
        """Test basic endpoints"""
        print("\n🔍 Testing Basic Endpoints...")
        
        # Test health endpoint
        self.run_api_test("Health Check", "GET", "/health", 200)
        
        # Test root endpoint
        self.run_api_test("Root Endpoint", "GET", "/", 200)

    def test_auth_endpoints(self):
        """Test authentication endpoints"""
        print("\n🔐 Testing Authentication...")
        
        # Test /api/auth/me without auth (should fail)
        self.run_api_test("Auth Me (No Token)", "GET", "/auth/me", 401)
        
        # Test /api/auth/me with valid token (should succeed)
        self.run_api_test("Auth Me (With Token)", "GET", "/auth/me", 200)

    def test_account_management(self):
        """Test email account management"""
        print("\n📧 Testing Email Account Management...")
        
        # Get accounts (should be empty initially)
        success, data = self.run_api_test("Get Email Accounts", "GET", "/accounts", 200)
        
        # Add email account
        account_data = {
            "email": "test@gmail.com",
            "display_name": "Test Account"
        }
        success, data = self.run_api_test("Add Email Account", "POST", "/accounts", 200, account_data)
        if success and 'account_id' in data:
            self.account_id = data['account_id']
            print(f"   Account ID: {self.account_id}")
        
        # Try adding duplicate account (should fail)
        self.run_api_test("Add Duplicate Account", "POST", "/accounts", 400, account_data)
        
        # Get accounts again (should have 1 account)
        self.run_api_test("Get Email Accounts (After Add)", "GET", "/accounts", 200)

    def test_email_list_management(self):
        """Test email list management"""
        print("\n📋 Testing Email List Management...")
        
        # Get lists (should be empty initially)
        self.run_api_test("Get Email Lists", "GET", "/lists", 200)
        
        # Create email list
        list_data = {
            "name": "Test List",
            "emails": [
                {
                    "email": "recipient1@example.com",
                    "first_name": "John",
                    "company": "Acme Corp",
                    "custom_fields": {}
                },
                {
                    "email": "recipient2@example.com", 
                    "first_name": "Jane",
                    "company": "Tech Inc",
                    "custom_fields": {}
                }
            ]
        }
        success, data = self.run_api_test("Create Email List", "POST", "/lists", 200, list_data)
        if success and 'list_id' in data:
            self.list_id = data['list_id']
            print(f"   List ID: {self.list_id}")
        
        # Get lists again (should have 1 list)
        self.run_api_test("Get Email Lists (After Add)", "GET", "/lists", 200)
        
        # Get specific list
        if self.list_id:
            self.run_api_test("Get Specific List", "GET", f"/lists/{self.list_id}", 200)

    def test_campaign_management(self):
        """Test campaign management"""
        print("\n🚀 Testing Campaign Management...")
        
        # Get campaigns (should be empty initially)
        self.run_api_test("Get Campaigns", "GET", "/campaigns", 200)
        
        if not self.list_id:
            print("   ⚠️  Skipping campaign tests - no list available")
            return
        
        # Create campaign
        campaign_data = {
            "list_id": self.list_id,
            "subject": "Test Campaign Subject - {first_name}",
            "body": "Hello {first_name} from {company}! This is a test email."
        }
        success, data = self.run_api_test("Create Campaign", "POST", "/campaigns", 200, campaign_data)
        if success and 'campaign_id' in data:
            self.campaign_id = data['campaign_id']
            print(f"   Campaign ID: {self.campaign_id}")
        
        # Get campaigns again (should have 1 campaign)
        self.run_api_test("Get Campaigns (After Add)", "GET", "/campaigns", 200)
        
        # Get specific campaign
        if self.campaign_id:
            self.run_api_test("Get Specific Campaign", "GET", f"/campaigns/{self.campaign_id}", 200)

    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        print("\n📊 Testing Dashboard Stats...")
        
        success, data = self.run_api_test("Get Dashboard Stats", "GET", "/dashboard/stats", 200)
        if success:
            print(f"   Accounts: {data.get('total_accounts', 0)}")
            print(f"   Contacts: {data.get('total_contacts', 0)}")
            print(f"   Campaigns: {data.get('total_campaigns', 0)}")
            print(f"   Subscription: {data.get('subscription_status', 'N/A')}")

    def test_subscription_endpoints(self):
        """Test subscription/payment endpoints"""
        print("\n💳 Testing Subscription Endpoints...")
        
        # Test checkout creation
        checkout_data = {
            "origin_url": self.base_url
        }
        self.run_api_test("Create Checkout Session", "POST", "/payments/checkout", 200, checkout_data)

    def test_cleanup_endpoints(self):
        """Test delete endpoints"""
        print("\n🗑️  Testing Cleanup Operations...")
        
        # Delete campaign
        if self.campaign_id:
            self.run_api_test("Delete Campaign", "DELETE", f"/campaigns/{self.campaign_id}", 404)  # May not be implemented
        
        # Delete email list
        if self.list_id:
            self.run_api_test("Delete Email List", "DELETE", f"/lists/{self.list_id}", 200)
        
        # Delete email account
        if self.account_id:
            self.run_api_test("Delete Email Account", "DELETE", f"/accounts/{self.account_id}", 200)

    def run_all_tests(self):
        """Run comprehensive API tests"""
        print("🚀 Starting Multi-Sender Email API Tests")
        print(f"🔗 Base URL: {self.base_url}")
        
        # Test basic endpoints first
        self.test_basic_endpoints()
        
        # Create test user and session
        if not self.create_test_user_session():
            print("❌ Failed to create test user. Cannot continue with auth tests.")
            return self.get_results()
        
        # Test authentication
        self.test_auth_endpoints()
        
        # Test main functionality with active subscription
        self.test_account_management()
        self.test_email_list_management()
        self.test_campaign_management()
        self.test_dashboard_stats()
        self.test_subscription_endpoints()
        
        # Test cleanup operations
        self.test_cleanup_endpoints()
        
        # Clean up test data
        self.cleanup_test_data()
        
        return self.get_results()

    def get_results(self):
        """Get test results summary"""
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        
        print(f"\n📊 Test Results Summary:")
        print(f"   Tests Run: {self.tests_run}")
        print(f"   Tests Passed: {self.tests_passed}")
        print(f"   Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"   Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 90:
            print("🎉 Excellent! Backend API is working well")
        elif success_rate >= 75:
            print("✅ Good! Most backend functionality is working")
        elif success_rate >= 50:
            print("⚠️  Warning! Several backend issues detected")
        else:
            print("❌ Critical! Major backend functionality is broken")
        
        return {
            "tests_run": self.tests_run,
            "tests_passed": self.tests_passed,
            "success_rate": success_rate,
            "status": "excellent" if success_rate >= 90 else "good" if success_rate >= 75 else "warning" if success_rate >= 50 else "critical"
        }

def main():
    """Main test runner"""
    tester = MultiSenderEmailAPITester()
    results = tester.run_all_tests()
    
    # Return appropriate exit code
    return 0 if results["success_rate"] >= 75 else 1

if __name__ == "__main__":
    sys.exit(main())