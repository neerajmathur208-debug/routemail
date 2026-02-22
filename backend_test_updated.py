#!/usr/bin/env python3
import requests
import sys
import json
import uuid
import io
import csv
from datetime import datetime, timezone, timedelta

class MultiSenderEmailAPITester:
    def __init__(self, base_url="https://routemail-preview.preview.emergentagent.com"):
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

    def run_api_test(self, name, method, endpoint, expected_status, data=None, headers=None, files=None):
        """Run a single API test"""
        url = f"{self.api_base}{endpoint}"
        default_headers = {}
        
        # Only set Content-Type for JSON requests
        if files is None and data is not None:
            default_headers['Content-Type'] = 'application/json'
        
        if self.session_token:
            default_headers['Authorization'] = f'Bearer {self.session_token}'
        
        if headers:
            default_headers.update(headers)

        try:
            if method == 'GET':
                response = requests.get(url, headers=default_headers, timeout=15)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, headers={k:v for k,v in default_headers.items() if k != 'Content-Type'}, timeout=15)
                else:
                    response = requests.post(url, json=data, headers=default_headers, timeout=15)
            elif method == 'DELETE':
                response = requests.delete(url, headers=default_headers, timeout=15)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=default_headers, timeout=15)

            success = response.status_code == expected_status
            details = ""
            
            if not success:
                details = f"Expected {expected_status}, got {response.status_code}"
                try:
                    error_data = response.json()
                    if 'detail' in error_data:
                        details += f" - {error_data['detail']}"
                except:
                    details += f" - {response.text[:200]}"
            
            return self.log_test(f"{name} ({method} {endpoint})", success, details), response.json() if success and response.content else {}

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
            if self.user_id:
                db.users.delete_many({"user_id": self.user_id})
                db.user_sessions.delete_many({"user_id": self.user_id})
                db.email_accounts.delete_many({"user_id": self.user_id})
                db.email_lists.delete_many({"user_id": self.user_id})
                db.campaigns.delete_many({"user_id": self.user_id})
                db.email_queue.delete_many({"user_id": self.user_id})
            
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
        
        # Test /api/auth/me with valid token (should succeed)
        self.run_api_test("Auth Me (With Token)", "GET", "/auth/me", 200)

    def test_smtp_account_management(self):
        """Test SMTP email account management"""
        print("\n📧 Testing SMTP Account Management...")
        
        # Get accounts (should be empty initially)
        success, data = self.run_api_test("Get Email Accounts", "GET", "/accounts", 200)
        
        # Test SMTP connection first
        smtp_test_data = {
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_username": "test@gmail.com",
            "smtp_password": "test_app_password",
            "smtp_encryption": "tls"
        }
        self.run_api_test("Test SMTP Connection", "POST", "/accounts/test-smtp", 200, smtp_test_data)
        
        # Add SMTP email account
        smtp_account_data = {
            "email": "test@gmail.com",
            "display_name": "Test Gmail Account",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_username": "test@gmail.com",
            "smtp_password": "test_app_password",
            "smtp_encryption": "tls"
        }
        success, data = self.run_api_test("Add SMTP Account", "POST", "/accounts/smtp", 400, smtp_account_data)  # Expect 400 due to invalid credentials
        
        # Try with different email to test duplicate detection
        smtp_account_data2 = {
            "email": "test2@outlook.com",
            "display_name": "Test Outlook Account", 
            "smtp_host": "smtp.office365.com",
            "smtp_port": 587,
            "smtp_username": "test2@outlook.com",
            "smtp_password": "test_app_password",
            "smtp_encryption": "tls"
        }
        self.run_api_test("Add Second SMTP Account", "POST", "/accounts/smtp", 400, smtp_account_data2)  # Also expect 400

    def test_csv_upload_and_lists(self):
        """Test CSV upload and email list management"""
        print("\n📋 Testing CSV Upload & List Management...")
        
        # Get lists (should be empty initially)
        self.run_api_test("Get Email Lists", "GET", "/lists", 200)
        
        # Create test CSV content
        csv_content = """email,first_name,last_name,company,city
john@example.com,John,Doe,Acme Corp,New York
jane@example.com,Jane,Smith,Tech Inc,Boston
bob@example.com,Bob,Johnson,Startup Co,San Francisco"""
        
        # Create CSV file for upload
        csv_file = io.StringIO(csv_content)
        files = {'file': ('test_contacts.csv', csv_file.getvalue(), 'text/csv')}
        
        # Test CSV upload
        success, upload_data = self.run_api_test("Upload CSV File", "POST", "/lists/upload", 200, files=files)
        
        if success and upload_data:
            print(f"   📊 CSV processed: {upload_data.get('valid_emails', 0)} valid emails")
            print(f"   🏷️  Column headers: {upload_data.get('column_headers', [])}")
            
            # Create email list from uploaded data
            list_data = {
                "name": "Test Contact List",
                "original_filename": upload_data.get('original_filename', 'test_contacts.csv'),
                "column_headers": upload_data.get('column_headers', []),
                "emails": upload_data.get('emails', [])
            }
            success, list_response = self.run_api_test("Create Email List", "POST", "/lists", 200, list_data)
            if success and 'list_id' in list_response:
                self.list_id = list_response['list_id']
                print(f"   📝 List ID: {self.list_id}")
                
                # Get specific list details
                self.run_api_test("Get Specific List", "GET", f"/lists/{self.list_id}", 200)
        
        # Get lists again (should have 1 list now)
        self.run_api_test("Get Email Lists (After Upload)", "GET", "/lists", 200)

    def test_campaign_management(self):
        """Test campaign management with rich text and variables"""
        print("\n🚀 Testing Campaign Management...")
        
        # Get campaigns (should be empty initially)
        self.run_api_test("Get Campaigns", "GET", "/campaigns", 200)
        
        if not self.list_id:
            print("   ⚠️  Skipping campaign tests - no list available")
            return
        
        # Create campaign with rich text and variables
        campaign_data = {
            "name": "Test Marketing Campaign",
            "subject": "Hi {{first_name}}, special offer for {{company}}!",
            "body": "<p>Hello <strong>{{first_name}}</strong>,</p><p>We have a special offer for <em>{{company}}</em> in {{city}}.</p><p>Best regards,<br>The Team</p>",
            "body_text": "Hello {{first_name}},\n\nWe have a special offer for {{company}} in {{city}}.\n\nBest regards,\nThe Team",
            "from_name": "Test Sender",
            "list_id": self.list_id,
            "account_ids": []  # Use all accounts
        }
        success, data = self.run_api_test("Create Rich Text Campaign", "POST", "/campaigns", 200, campaign_data)
        if success and 'campaign_id' in data:
            self.campaign_id = data['campaign_id']
            print(f"   🎯 Campaign ID: {self.campaign_id}")
        
        # Get campaigns again (should have 1 campaign)
        success, campaigns_data = self.run_api_test("Get Campaigns (After Create)", "GET", "/campaigns", 200)
        
        # Get specific campaign details
        if self.campaign_id:
            success, campaign_details = self.run_api_test("Get Campaign Details", "GET", f"/campaigns/{self.campaign_id}", 200)
            if success:
                print(f"   📊 Campaign status: {campaign_details.get('status', 'unknown')}")
                print(f"   📧 Total emails: {campaign_details.get('total_emails', 0)}")

    def test_campaign_operations(self):
        """Test campaign operations (start/pause/resume/duplicate)"""
        print("\n⚡ Testing Campaign Operations...")
        
        if not self.campaign_id:
            print("   ⚠️  Skipping campaign operations - no campaign available")
            return
        
        # Update campaign
        update_data = {
            "name": "Updated Test Campaign",
            "subject": "Updated: Hi {{first_name}}!"
        }
        self.run_api_test("Update Campaign", "PUT", f"/campaigns/{self.campaign_id}", 200, update_data)
        
        # Duplicate campaign
        success, duplicate_data = self.run_api_test("Duplicate Campaign", "POST", f"/campaigns/{self.campaign_id}/duplicate", 200)
        duplicate_id = duplicate_data.get('campaign_id') if success else None
        
        # Try to start campaign (will fail without SMTP accounts, but tests the endpoint)
        self.run_api_test("Start Campaign", "POST", f"/campaigns/{self.campaign_id}/start", 400)  # Expect 400 - no accounts
        
        # Test pause campaign (should fail since not running)
        self.run_api_test("Pause Campaign", "POST", f"/campaigns/{self.campaign_id}/pause", 400)
        
        # Test resume campaign (should fail since not paused)
        self.run_api_test("Resume Campaign", "POST", f"/campaigns/{self.campaign_id}/resume", 400)
        
        # Clean up duplicate campaign
        if duplicate_id:
            self.run_api_test("Delete Duplicate Campaign", "DELETE", f"/campaigns/{duplicate_id}", 200)

    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        print("\n📊 Testing Dashboard Stats...")
        
        success, data = self.run_api_test("Get Dashboard Stats", "GET", "/dashboard/stats", 200)
        if success:
            print(f"   📧 Total accounts: {data.get('total_accounts', 0)}")
            print(f"   👥 Total contacts: {data.get('total_contacts', 0)}")
            print(f"   🚀 Total campaigns: {data.get('total_campaigns', 0)}")
            print(f"   📈 Available today: {data.get('total_available_today', 0)}")
            print(f"   💳 Subscription: {data.get('subscription_status', 'N/A')}")
            
            # Check if campaign data is included
            campaigns = data.get('campaigns', [])
            if campaigns:
                print(f"   📊 Campaign statuses: {[c.get('status') for c in campaigns]}")

    def test_suppression_list(self):
        """Test suppression list functionality"""
        print("\n🚫 Testing Suppression List...")
        
        # Get suppression list
        self.run_api_test("Get Suppression List", "GET", "/suppression", 200)
        
        # Add email to suppression
        success, data = self.run_api_test("Add to Suppression", "POST", "/suppression", 200, "spam@example.com")

    def test_cleanup_endpoints(self):
        """Test delete endpoints"""
        print("\n🗑️  Testing Cleanup Operations...")
        
        # Delete campaign
        if self.campaign_id:
            self.run_api_test("Delete Campaign", "DELETE", f"/campaigns/{self.campaign_id}", 200)
        
        # Delete email list
        if self.list_id:
            self.run_api_test("Delete Email List", "DELETE", f"/lists/{self.list_id}", 200)

    def run_all_tests(self):
        """Run comprehensive API tests"""
        print("🚀 Starting Enhanced Multi-Sender Email API Tests")
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
        self.test_smtp_account_management()
        self.test_csv_upload_and_lists()
        self.test_campaign_management()
        self.test_campaign_operations()
        self.test_dashboard_stats()
        self.test_suppression_list()
        
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