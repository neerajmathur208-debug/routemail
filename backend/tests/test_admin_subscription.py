"""
Test cases for GET /api/admin/users/{user_id}/subscription endpoint
This endpoint allows super_admin to view detailed subscription info for any user.
"""
import pytest
import requests
import os
from datetime import datetime, timedelta, timezone
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAdminSubscriptionEndpoint:
    """Tests for the admin subscription details endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data - create super admin user and session"""
        import subprocess
        
        # Create unique identifiers for this test run
        self.test_id = f"test_{uuid.uuid4().hex[:8]}"
        self.super_admin_user_id = f"user_admin_{self.test_id}"
        self.super_admin_session = f"session_admin_{self.test_id}"
        self.super_admin_email = "test_super_admin@example.com"
        
        # Create regular test users
        self.free_user_id = f"user_free_{self.test_id}"
        self.starter_user_id = f"user_starter_{self.test_id}"
        self.growth_user_id = f"user_growth_{self.test_id}"
        self.trialing_user_id = f"user_trial_{self.test_id}"
        
        # Regular user session (non-admin)
        self.regular_user_id = f"user_regular_{self.test_id}"
        self.regular_session = f"session_regular_{self.test_id}"
        
        # Setup MongoDB test data
        setup_script = f'''
        use test_database;
        
        // Create super admin user
        db.users.insertOne({{
            user_id: "{self.super_admin_user_id}",
            email: "{self.super_admin_email}",
            name: "Test Super Admin",
            role: "super_admin",
            plan_type: "growth",
            subscription_status: "active",
            created_at: new Date().toISOString()
        }});
        
        // Create super admin session
        db.user_sessions.insertOne({{
            user_id: "{self.super_admin_user_id}",
            session_token: "{self.super_admin_session}",
            expires_at: new Date(Date.now() + 7*24*60*60*1000),
            created_at: new Date().toISOString()
        }});
        
        // Create regular user (non-admin)
        db.users.insertOne({{
            user_id: "{self.regular_user_id}",
            email: "regular_test@example.com",
            name: "Regular Test User",
            role: "user",
            plan_type: "free",
            subscription_status: "trialing",
            created_at: new Date().toISOString()
        }});
        
        // Create regular user session
        db.user_sessions.insertOne({{
            user_id: "{self.regular_user_id}",
            session_token: "{self.regular_session}",
            expires_at: new Date(Date.now() + 7*24*60*60*1000),
            created_at: new Date().toISOString()
        }});
        
        // Create FREE plan user (no stripe info)
        db.users.insertOne({{
            user_id: "{self.free_user_id}",
            email: "free_user_{self.test_id}@example.com",
            name: "Free Plan User",
            role: "user",
            plan_type: "free",
            subscription_status: "trialing",
            trial_ends_at: new Date(Date.now() + 14*24*60*60*1000).toISOString(),
            stripe_customer_id: null,
            stripe_subscription_id: null,
            created_at: new Date().toISOString()
        }});
        
        // Create STARTER plan user with USD
        db.users.insertOne({{
            user_id: "{self.starter_user_id}",
            email: "starter_user_{self.test_id}@example.com",
            name: "Starter Plan User",
            role: "user",
            plan_type: "starter",
            subscription_status: "active",
            stripe_customer_id: "cus_test_starter",
            stripe_subscription_id: null,
            billing_cycle_end: new Date(Date.now() + 30*24*60*60*1000).toISOString(),
            created_at: new Date().toISOString()
        }});
        
        // Create GROWTH plan user
        db.users.insertOne({{
            user_id: "{self.growth_user_id}",
            email: "growth_user_{self.test_id}@example.com",
            name: "Growth Plan User",
            role: "user",
            plan_type: "growth",
            subscription_status: "active",
            stripe_customer_id: "cus_test_growth",
            stripe_subscription_id: null,
            billing_cycle_end: new Date(Date.now() + 30*24*60*60*1000).toISOString(),
            created_at: new Date().toISOString()
        }});
        
        // Create TRIALING user
        db.users.insertOne({{
            user_id: "{self.trialing_user_id}",
            email: "trialing_user_{self.test_id}@example.com",
            name: "Trialing User",
            role: "user",
            plan_type: "free",
            subscription_status: "trialing",
            trial_ends_at: new Date(Date.now() + 7*24*60*60*1000).toISOString(),
            created_at: new Date().toISOString()
        }});
        
        print("Test data created successfully");
        '''
        
        result = subprocess.run(
            ['mongosh', '--quiet', '--eval', setup_script],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Setup error: {result.stderr}")
        
        yield
        
        # Cleanup
        cleanup_script = f'''
        use test_database;
        db.users.deleteMany({{ user_id: {{ $regex: "^user_.*{self.test_id}" }} }});
        db.user_sessions.deleteMany({{ session_token: {{ $regex: "^session_.*{self.test_id}" }} }});
        db.admin_logs.deleteMany({{ target_user_id: {{ $regex: ".*{self.test_id}" }} }});
        print("Test data cleaned up");
        '''
        subprocess.run(['mongosh', '--quiet', '--eval', cleanup_script], capture_output=True)
    
    def test_endpoint_requires_authentication(self):
        """Test that endpoint returns 401 without authentication"""
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{self.free_user_id}/subscription"
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✅ Endpoint requires authentication (401)")
    
    def test_endpoint_requires_super_admin_role(self):
        """Test that endpoint returns 403 for non-admin users"""
        headers = {"Authorization": f"Bearer {self.regular_session}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{self.free_user_id}/subscription",
            headers=headers
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
        assert "super admin" in response.json().get("detail", "").lower(), "Error should mention super admin"
        print("✅ Endpoint requires super_admin role (403)")
    
    def test_returns_404_for_nonexistent_user(self):
        """Test that endpoint returns 404 for non-existent user"""
        headers = {"Authorization": f"Bearer {self.super_admin_session}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/users/nonexistent_user_12345/subscription",
            headers=headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        print("✅ Returns 404 for non-existent user")
    
    def test_free_user_subscription_info(self):
        """Test subscription info for FREE plan user"""
        headers = {"Authorization": f"Bearer {self.super_admin_session}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{self.free_user_id}/subscription",
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields exist
        assert "current_plan" in data, "Missing current_plan"
        assert "currency" in data, "Missing currency"
        assert "stripe_customer_id" in data, "Missing stripe_customer_id"
        assert "stripe_subscription_id" in data, "Missing stripe_subscription_id"
        assert "stripe_price_id" in data, "Missing stripe_price_id"
        assert "billing_status" in data, "Missing billing_status"
        assert "trial_active" in data, "Missing trial_active"
        assert "trial_end_date" in data, "Missing trial_end_date"
        assert "subscription_end_date" in data, "Missing subscription_end_date"
        
        # Verify FREE user specific values
        assert data["current_plan"].lower() == "free", f"Expected Free plan, got {data['current_plan']}"
        assert data["currency"] == "N/A", f"Expected N/A currency for free user, got {data['currency']}"
        assert data["stripe_customer_id"] == "N/A", f"Expected N/A for stripe_customer_id, got {data['stripe_customer_id']}"
        assert data["stripe_subscription_id"] == "N/A", f"Expected N/A for stripe_subscription_id, got {data['stripe_subscription_id']}"
        assert data["stripe_price_id"] == "N/A", f"Expected N/A for stripe_price_id, got {data['stripe_price_id']}"
        
        print(f"✅ Free user subscription info correct: plan={data['current_plan']}, currency={data['currency']}")
    
    def test_starter_user_subscription_info(self):
        """Test subscription info for STARTER plan user"""
        headers = {"Authorization": f"Bearer {self.super_admin_session}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{self.starter_user_id}/subscription",
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify STARTER specific values
        assert data["current_plan"].lower() == "starter", f"Expected Starter plan, got {data['current_plan']}"
        assert data["billing_status"] == "active", f"Expected active status, got {data['billing_status']}"
        
        print(f"✅ Starter user subscription info correct: plan={data['current_plan']}, status={data['billing_status']}")
    
    def test_growth_user_subscription_info(self):
        """Test subscription info for GROWTH plan user"""
        headers = {"Authorization": f"Bearer {self.super_admin_session}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{self.growth_user_id}/subscription",
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify GROWTH specific values
        assert data["current_plan"].lower() == "growth", f"Expected Growth plan, got {data['current_plan']}"
        assert data["billing_status"] == "active", f"Expected active status, got {data['billing_status']}"
        
        print(f"✅ Growth user subscription info correct: plan={data['current_plan']}, status={data['billing_status']}")
    
    def test_trialing_user_has_trial_active(self):
        """Test that trialing user shows trial_active=True and trial_end_date"""
        headers = {"Authorization": f"Bearer {self.super_admin_session}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{self.trialing_user_id}/subscription",
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert data["trial_active"] == True, f"Expected trial_active=True for trialing user, got {data['trial_active']}"
        assert data["trial_end_date"] is not None, "Expected trial_end_date to be set"
        assert data["billing_status"] == "trialing", f"Expected trialing status, got {data['billing_status']}"
        
        print(f"✅ Trialing user has trial_active={data['trial_active']}, trial_end_date={data['trial_end_date']}")
    
    def test_response_contains_all_required_fields(self):
        """Verify all required fields are present in response"""
        headers = {"Authorization": f"Bearer {self.super_admin_session}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{self.free_user_id}/subscription",
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        
        required_fields = [
            "user_id",
            "email",
            "current_plan",
            "currency",
            "stripe_customer_id",
            "stripe_subscription_id",
            "stripe_price_id",
            "billing_status",
            "trial_active",
            "trial_end_date",
            "subscription_end_date",
            "is_permanent_plan"
        ]
        
        missing_fields = [f for f in required_fields if f not in data]
        assert len(missing_fields) == 0, f"Missing required fields: {missing_fields}"
        
        print(f"✅ All {len(required_fields)} required fields present in response")
    
    def test_admin_action_is_logged(self):
        """Test that viewing subscription details is logged in admin_logs"""
        import subprocess
        
        headers = {"Authorization": f"Bearer {self.super_admin_session}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{self.free_user_id}/subscription",
            headers=headers
        )
        assert response.status_code == 200
        
        # Check admin_logs collection
        check_script = f'''
        use test_database;
        const log = db.admin_logs.findOne({{
            target_user_id: "{self.free_user_id}",
            action: "VIEW_SUBSCRIPTION_DETAILS"
        }});
        if (log) {{
            print("LOG_FOUND:" + log.admin_email);
        }} else {{
            print("LOG_NOT_FOUND");
        }}
        '''
        result = subprocess.run(
            ['mongosh', '--quiet', '--eval', check_script],
            capture_output=True, text=True
        )
        
        assert "LOG_FOUND" in result.stdout, "Admin action was not logged"
        print("✅ Admin action logged in admin_logs collection")


class TestPermanentPlanUsers:
    """Test permanent plan users (dhruvmathur5@gmail.com, perfectdigitals208@gmail.com)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup super admin session to test permanent plan users"""
        import subprocess
        
        self.test_id = f"perm_{uuid.uuid4().hex[:8]}"
        self.super_admin_user_id = f"user_admin_{self.test_id}"
        self.super_admin_session = f"session_admin_{self.test_id}"
        
        # Permanent plan user IDs (need to find from DB or create test ones)
        self.starter_perm_user_id = f"user_perm_starter_{self.test_id}"
        self.growth_perm_user_id = f"user_perm_growth_{self.test_id}"
        
        setup_script = f'''
        use test_database;
        
        // Create super admin
        db.users.insertOne({{
            user_id: "{self.super_admin_user_id}",
            email: "admin_perm_test@example.com",
            name: "Perm Test Admin",
            role: "super_admin",
            plan_type: "growth",
            subscription_status: "active",
            created_at: new Date().toISOString()
        }});
        
        db.user_sessions.insertOne({{
            user_id: "{self.super_admin_user_id}",
            session_token: "{self.super_admin_session}",
            expires_at: new Date(Date.now() + 7*24*60*60*1000),
            created_at: new Date().toISOString()
        }});
        
        // Create permanent STARTER plan user (email matches PERMANENT_PLAN_STARTER_EMAILS)
        db.users.insertOne({{
            user_id: "{self.starter_perm_user_id}",
            email: "dhruvmathur5@gmail.com",
            name: "Permanent Starter User",
            role: "user",
            plan_type: "starter",
            subscription_status: "active",
            created_at: new Date().toISOString()
        }});
        
        // Create permanent GROWTH plan user (email matches PERMANENT_PLAN_GROWTH_EMAILS)
        db.users.insertOne({{
            user_id: "{self.growth_perm_user_id}",
            email: "perfectdigitals208@gmail.com",
            name: "Permanent Growth User",
            role: "user",
            plan_type: "growth",
            subscription_status: "active",
            created_at: new Date().toISOString()
        }});
        
        print("Permanent plan test data created");
        '''
        
        subprocess.run(['mongosh', '--quiet', '--eval', setup_script], capture_output=True)
        
        yield
        
        # Cleanup
        cleanup_script = f'''
        use test_database;
        db.users.deleteMany({{ user_id: {{ $regex: ".*{self.test_id}" }} }});
        db.user_sessions.deleteMany({{ session_token: {{ $regex: ".*{self.test_id}" }} }});
        db.admin_logs.deleteMany({{ target_user_id: {{ $regex: ".*{self.test_id}" }} }});
        '''
        subprocess.run(['mongosh', '--quiet', '--eval', cleanup_script], capture_output=True)
    
    def test_permanent_starter_plan_shows_is_permanent(self):
        """Test that permanent starter plan user shows is_permanent_plan=true"""
        headers = {"Authorization": f"Bearer {self.super_admin_session}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{self.starter_perm_user_id}/subscription",
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert data["is_permanent_plan"] == True, f"Expected is_permanent_plan=True, got {data['is_permanent_plan']}"
        assert data["billing_status"] == "permanent", f"Expected 'permanent' billing status, got {data['billing_status']}"
        assert "notes" in data, "Expected notes field for permanent plan user"
        
        print(f"✅ Permanent starter user: is_permanent_plan={data['is_permanent_plan']}, status={data['billing_status']}")
    
    def test_permanent_growth_plan_shows_is_permanent(self):
        """Test that permanent growth plan user shows is_permanent_plan=true"""
        headers = {"Authorization": f"Bearer {self.super_admin_session}"}
        response = requests.get(
            f"{BASE_URL}/api/admin/users/{self.growth_perm_user_id}/subscription",
            headers=headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        assert data["is_permanent_plan"] == True, f"Expected is_permanent_plan=True, got {data['is_permanent_plan']}"
        assert data["billing_status"] == "permanent", f"Expected 'permanent' billing status, got {data['billing_status']}"
        
        print(f"✅ Permanent growth user: is_permanent_plan={data['is_permanent_plan']}, status={data['billing_status']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
