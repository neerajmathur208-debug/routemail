"""
Test suite for Admin Plan Override functionality.
Tests the following features:
1. POST /api/admin/users/{id}/assign-plan - Assign Starter/Growth plan to non-Stripe users
2. POST /api/admin/users/{id}/remove-override - Revert user to free plan
3. Plan override blocked for users with Stripe subscriptions
4. Plan override blocked for permanent plan users
5. Admin logs created for override actions
6. Subscription endpoint returns admin_override_active and plan_source fields
"""

import pytest
import requests
import os
from datetime import datetime, timezone, timedelta
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestAdminPlanOverride:
    """Test cases for admin plan override feature"""
    
    @pytest.fixture(autouse=True)
    def setup_test_data(self, request):
        """Create test users and admin session for each test"""
        # Generate unique IDs
        timestamp = int(datetime.now().timestamp() * 1000)
        self.admin_user_id = f"test_admin_{timestamp}"
        self.admin_session_token = f"test_session_admin_{timestamp}"
        self.regular_user_id = f"test_user_{timestamp}"
        self.stripe_user_id = f"test_stripe_user_{timestamp}"
        
        self.admin_email = "dhruvmathur208@gmail.com"
        self.regular_email = f"test_regular_{timestamp}@example.com"
        self.stripe_email = f"test_stripe_{timestamp}@example.com"
        
        # Use mongosh to set up test data
        import subprocess
        
        # Create super admin user and session
        admin_setup = f'''
        use('test_database');
        db.users.deleteMany({{user_id: {{$regex: /^test_admin_/}}}});
        db.users.deleteMany({{user_id: {{$regex: /^test_user_/}}}});
        db.users.deleteMany({{user_id: {{$regex: /^test_stripe_user_/}}}});
        db.user_sessions.deleteMany({{session_token: {{$regex: /^test_session_/}}}});
        
        // Create super admin user
        db.users.insertOne({{
            user_id: "{self.admin_user_id}",
            email: "{self.admin_email}",
            name: "Super Admin Test",
            role: "super_admin",
            provider: "test",
            plan_type: "free",
            subscription_status: "active",
            created_at: new Date().toISOString()
        }});
        
        // Create session for super admin
        db.user_sessions.insertOne({{
            user_id: "{self.admin_user_id}",
            session_token: "{self.admin_session_token}",
            expires_at: new Date(Date.now() + 7*24*60*60*1000),
            created_at: new Date()
        }});
        
        // Create regular user (no Stripe subscription)
        db.users.insertOne({{
            user_id: "{self.regular_user_id}",
            email: "{self.regular_email}",
            name: "Test Regular User",
            role: "user",
            provider: "email",
            plan_type: "free",
            subscription_status: "trialing",
            trial_ends_at: new Date(Date.now() + 14*24*60*60*1000).toISOString(),
            created_at: new Date().toISOString()
        }});
        
        // Create user with Stripe subscription
        db.users.insertOne({{
            user_id: "{self.stripe_user_id}",
            email: "{self.stripe_email}",
            name: "Test Stripe User",
            role: "user",
            provider: "email",
            plan_type: "starter",
            subscription_status: "active",
            stripe_subscription_id: "sub_test12345678",
            stripe_customer_id: "cus_test12345678",
            created_at: new Date().toISOString()
        }});
        '''
        
        result = subprocess.run(
            ['mongosh', '--eval', admin_setup],
            capture_output=True, text=True
        )
        
        yield
        
        # Cleanup after test
        cleanup_script = f'''
        use('test_database');
        db.users.deleteMany({{user_id: "{self.admin_user_id}"}});
        db.users.deleteMany({{user_id: "{self.regular_user_id}"}});
        db.users.deleteMany({{user_id: "{self.stripe_user_id}"}});
        db.user_sessions.deleteMany({{session_token: "{self.admin_session_token}"}});
        db.admin_logs.deleteMany({{target_user_id: {{$in: ["{self.regular_user_id}", "{self.stripe_user_id}"]}}}});
        '''
        subprocess.run(['mongosh', '--eval', cleanup_script], capture_output=True)
    
    @pytest.fixture
    def admin_headers(self):
        """Return headers with admin session token"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.admin_session_token}"
        }
    
    def test_health_check(self):
        """Test API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        print("✅ Health check passed")
    
    def test_assign_starter_plan_success(self, admin_headers):
        """Test assigning Starter plan to user without Stripe subscription"""
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{self.regular_user_id}/assign-plan",
            headers=admin_headers,
            json={"plan": "starter"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["success"] == True
        assert data["plan"] == "starter"
        assert data["source"] == "admin_override"
        print(f"✅ Successfully assigned Starter plan: {data}")
    
    def test_assign_growth_plan_success(self, admin_headers):
        """Test assigning Growth plan to user without Stripe subscription"""
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{self.regular_user_id}/assign-plan",
            headers=admin_headers,
            json={"plan": "growth"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["success"] == True
        assert data["plan"] == "growth"
        assert data["source"] == "admin_override"
        print(f"✅ Successfully assigned Growth plan: {data}")
    
    def test_assign_plan_blocked_for_stripe_user(self, admin_headers):
        """Test that plan assignment is blocked for users with Stripe subscription"""
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{self.stripe_user_id}/assign-plan",
            headers=admin_headers,
            json={"plan": "starter"}
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "Stripe subscription" in data.get("detail", "")
        print(f"✅ Plan assignment correctly blocked for Stripe user: {data}")
    
    def test_assign_plan_invalid_plan_type(self, admin_headers):
        """Test that invalid plan types are rejected"""
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{self.regular_user_id}/assign-plan",
            headers=admin_headers,
            json={"plan": "enterprise"}  # Invalid plan
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "starter" in data.get("detail", "") or "growth" in data.get("detail", "")
        print(f"✅ Invalid plan type correctly rejected: {data}")
    
    def test_assign_plan_user_not_found(self, admin_headers):
        """Test error handling for non-existent user"""
        response = requests.post(
            f"{BASE_URL}/api/admin/users/nonexistent_user_12345/assign-plan",
            headers=admin_headers,
            json={"plan": "starter"}
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print(f"✅ Non-existent user correctly returns 404")
    
    def test_remove_override_success(self, admin_headers):
        """Test removing admin override and reverting to free plan"""
        # First assign a plan
        assign_response = requests.post(
            f"{BASE_URL}/api/admin/users/{self.regular_user_id}/assign-plan",
            headers=admin_headers,
            json={"plan": "growth"}
        )
        assert assign_response.status_code == 200
        
        # Now remove the override
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{self.regular_user_id}/remove-override",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data["success"] == True
        assert data["plan"] == "free"
        assert data["source"] == "free"
        print(f"✅ Successfully removed override: {data}")
    
    def test_remove_override_no_active_override(self, admin_headers):
        """Test error when trying to remove non-existent override"""
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{self.regular_user_id}/remove-override",
            headers=admin_headers
        )
        
        # User doesn't have override active
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert "active admin override" in data.get("detail", "").lower()
        print(f"✅ Remove override correctly rejected for user without override: {data}")
    
    def test_subscription_endpoint_shows_admin_override(self, admin_headers):
        """Test that subscription endpoint returns admin_override_active and plan_source"""
        # First assign a plan
        assign_response = requests.post(
            f"{BASE_URL}/api/admin/users/{self.regular_user_id}/assign-plan",
            headers=admin_headers,
            json={"plan": "starter"}
        )
        assert assign_response.status_code == 200
        
        # Now check subscription endpoint
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{self.regular_user_id}/subscription",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("admin_override_active") == True, f"Expected admin_override_active=True, got {data}"
        assert data.get("plan_source") == "admin_override", f"Expected plan_source='admin_override', got {data}"
        assert data.get("admin_override_plan") == "starter", f"Expected admin_override_plan='starter', got {data}"
        print(f"✅ Subscription endpoint correctly shows admin override info: {data}")
    
    def test_subscription_endpoint_shows_stripe_source(self, admin_headers):
        """Test that subscription endpoint shows stripe source for Stripe users"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{self.stripe_user_id}/subscription",
            headers=admin_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        assert data.get("has_stripe_subscription") == True, f"Expected has_stripe_subscription=True, got {data}"
        print(f"✅ Subscription endpoint correctly identifies Stripe user: {data}")
    
    def test_admin_log_created_for_assign(self, admin_headers):
        """Test that admin logs are created for plan assignment"""
        import subprocess
        
        # Assign a plan
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{self.regular_user_id}/assign-plan",
            headers=admin_headers,
            json={"plan": "starter"}
        )
        assert response.status_code == 200
        
        # Check admin logs in database
        check_logs = f'''
        use('test_database');
        var log = db.admin_logs.findOne({{
            target_user_id: "{self.regular_user_id}",
            action: "ADMIN_ASSIGN_STARTER"
        }});
        print(JSON.stringify(log));
        '''
        
        result = subprocess.run(
            ['mongosh', '--eval', check_logs],
            capture_output=True, text=True
        )
        
        assert "ADMIN_ASSIGN_STARTER" in result.stdout, f"Expected admin log with ADMIN_ASSIGN_STARTER, got: {result.stdout}"
        print(f"✅ Admin log created for plan assignment")
    
    def test_admin_log_created_for_remove_override(self, admin_headers):
        """Test that admin logs are created for removing override"""
        import subprocess
        
        # First assign a plan
        assign_response = requests.post(
            f"{BASE_URL}/api/admin/users/{self.regular_user_id}/assign-plan",
            headers=admin_headers,
            json={"plan": "growth"}
        )
        assert assign_response.status_code == 200
        
        # Remove the override
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{self.regular_user_id}/remove-override",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        # Check admin logs in database
        check_logs = f'''
        use('test_database');
        var log = db.admin_logs.findOne({{
            target_user_id: "{self.regular_user_id}",
            action: "ADMIN_REMOVE_OVERRIDE"
        }});
        print(JSON.stringify(log));
        '''
        
        result = subprocess.run(
            ['mongosh', '--eval', check_logs],
            capture_output=True, text=True
        )
        
        assert "ADMIN_REMOVE_OVERRIDE" in result.stdout, f"Expected admin log with ADMIN_REMOVE_OVERRIDE, got: {result.stdout}"
        print(f"✅ Admin log created for removing override")
    
    def test_requires_super_admin_auth(self):
        """Test that endpoints require super admin authentication"""
        # Test without auth
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{self.regular_user_id}/assign-plan",
            headers={"Content-Type": "application/json"},
            json={"plan": "starter"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print(f"✅ Endpoints correctly require authentication")


class TestPermanentPlanBlocked:
    """Test that permanent plan users cannot be overridden"""
    
    @pytest.fixture(autouse=True)
    def setup_permanent_user(self, request):
        """Create test admin session"""
        timestamp = int(datetime.now().timestamp() * 1000)
        self.admin_user_id = f"test_admin_perm_{timestamp}"
        self.admin_session_token = f"test_session_perm_{timestamp}"
        
        import subprocess
        
        # Create super admin user and session
        admin_setup = f'''
        use('test_database');
        db.users.deleteMany({{user_id: {{$regex: /^test_admin_perm_/}}}});
        db.user_sessions.deleteMany({{session_token: {{$regex: /^test_session_perm_/}}}});
        
        // Create super admin user
        db.users.insertOne({{
            user_id: "{self.admin_user_id}",
            email: "dhruvmathur208@gmail.com",
            name: "Super Admin Test",
            role: "super_admin",
            provider: "test",
            plan_type: "free",
            subscription_status: "active",
            created_at: new Date().toISOString()
        }});
        
        // Create session for super admin
        db.user_sessions.insertOne({{
            user_id: "{self.admin_user_id}",
            session_token: "{self.admin_session_token}",
            expires_at: new Date(Date.now() + 7*24*60*60*1000),
            created_at: new Date()
        }});
        '''
        
        subprocess.run(['mongosh', '--eval', admin_setup], capture_output=True)
        
        yield
        
        # Cleanup
        cleanup_script = f'''
        use('test_database');
        db.users.deleteMany({{user_id: "{self.admin_user_id}"}});
        db.user_sessions.deleteMany({{session_token: "{self.admin_session_token}"}});
        '''
        subprocess.run(['mongosh', '--eval', cleanup_script], capture_output=True)
    
    @pytest.fixture
    def admin_headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.admin_session_token}"
        }
    
    def test_assign_plan_blocked_for_permanent_user(self, admin_headers):
        """Test that plan assignment is blocked for permanent plan users"""
        import subprocess
        
        # Get the user_id of a permanent plan user
        get_user = '''
        use('test_database');
        var user = db.users.findOne({email: "dhruvmathur5@gmail.com"});
        print(user ? user.user_id : "NOT_FOUND");
        '''
        
        result = subprocess.run(
            ['mongosh', '--eval', get_user],
            capture_output=True, text=True
        )
        
        # Parse user_id from output
        lines = result.stdout.strip().split('\n')
        permanent_user_id = None
        for line in lines:
            if line.startswith('user_'):
                permanent_user_id = line.strip()
                break
        
        if permanent_user_id:
            response = requests.post(
                f"{BASE_URL}/api/admin/users/{permanent_user_id}/assign-plan",
                headers=admin_headers,
                json={"plan": "growth"}
            )
            
            assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
            data = response.json()
            assert "permanently assigned plan" in data.get("detail", "").lower()
            print(f"✅ Plan assignment correctly blocked for permanent plan user: {data}")
        else:
            pytest.skip("Permanent plan user not found in database")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
