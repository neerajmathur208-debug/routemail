"""
Test file for Stripe Subscription System APIs
Tests subscription endpoints, plan limits, and user registration with trial
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSubscriptionPricesEndpoint:
    """Tests for GET /api/subscription/prices - public endpoint"""
    
    def test_get_prices_returns_200(self):
        """Verify prices endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/subscription/prices")
        assert response.status_code == 200
        print(f"✓ GET /api/subscription/prices returns 200")
    
    def test_get_prices_returns_correct_structure(self):
        """Verify prices response has correct structure"""
        response = requests.get(f"{BASE_URL}/api/subscription/prices")
        data = response.json()
        
        # Check top-level keys
        assert "plans" in data, "Response missing 'plans'"
        assert "free_plan" in data, "Response missing 'free_plan'"
        
        # Check plans structure
        assert len(data["plans"]) >= 2, "Expected at least 2 paid plans"
        print(f"✓ Prices response has correct structure with {len(data['plans'])} plans")
    
    def test_starter_plan_has_correct_limits(self):
        """Verify Starter plan has correct limits"""
        response = requests.get(f"{BASE_URL}/api/subscription/prices")
        data = response.json()
        
        starter_plan = next((p for p in data["plans"] if p["name"] == "Starter"), None)
        assert starter_plan is not None, "Starter plan not found"
        
        features = starter_plan["features"]
        assert features["max_accounts"] == 10, f"Expected 10 accounts, got {features['max_accounts']}"
        assert features["max_contacts"] == 4000, f"Expected 4000 contacts, got {features['max_contacts']}"
        assert features["max_monthly_recipients"] == 4000, f"Expected 4000 recipients, got {features['max_monthly_recipients']}"
        print(f"✓ Starter plan limits: 10 accounts, 4000 contacts, 4000 recipients")
    
    def test_growth_plan_has_correct_limits(self):
        """Verify Growth plan has correct limits"""
        response = requests.get(f"{BASE_URL}/api/subscription/prices")
        data = response.json()
        
        growth_plan = next((p for p in data["plans"] if p["name"] == "Growth"), None)
        assert growth_plan is not None, "Growth plan not found"
        
        features = growth_plan["features"]
        assert features["max_accounts"] == 15, f"Expected 15 accounts, got {features['max_accounts']}"
        assert features["max_contacts"] == 10000, f"Expected 10000 contacts, got {features['max_contacts']}"
        assert features["max_monthly_recipients"] == 10000, f"Expected 10000 recipients, got {features['max_monthly_recipients']}"
        print(f"✓ Growth plan limits: 15 accounts, 10000 contacts, 10000 recipients")
    
    def test_free_plan_has_correct_limits(self):
        """Verify Free plan has correct limits"""
        response = requests.get(f"{BASE_URL}/api/subscription/prices")
        data = response.json()
        
        free_plan = data["free_plan"]
        features = free_plan["features"]
        
        assert features["max_accounts"] == 3, f"Expected 3 accounts, got {features['max_accounts']}"
        assert features["max_contacts"] == 500, f"Expected 500 contacts, got {features['max_contacts']}"
        assert features["max_monthly_recipients"] == 500, f"Expected 500 recipients, got {features['max_monthly_recipients']}"
        assert free_plan["trial_days"] == 14, f"Expected 14 trial days, got {free_plan['trial_days']}"
        print(f"✓ Free plan limits: 3 accounts, 500 contacts, 500 recipients, 14-day trial")
    
    def test_plans_have_usd_and_inr_pricing(self):
        """Verify both USD and INR pricing are available"""
        response = requests.get(f"{BASE_URL}/api/subscription/prices")
        data = response.json()
        
        for plan in data["plans"]:
            assert "usd" in plan["prices"], f"{plan['name']} missing USD pricing"
            assert "inr" in plan["prices"], f"{plan['name']} missing INR pricing"
            
            usd = plan["prices"]["usd"]
            inr = plan["prices"]["inr"]
            
            assert "price_id" in usd, f"{plan['name']} USD missing price_id"
            assert "amount" in usd, f"{plan['name']} USD missing amount"
            assert "price_id" in inr, f"{plan['name']} INR missing price_id"
            assert "amount" in inr, f"{plan['name']} INR missing amount"
        
        print(f"✓ All plans have USD and INR pricing with price_ids")


class TestSubscriptionStatusEndpoint:
    """Tests for GET /api/subscription/status - requires auth"""
    
    @pytest.fixture
    def test_user_session(self):
        """Create test user and return session for authenticated tests"""
        # Register a new test user
        test_email = f"test_sub_{uuid.uuid4().hex[:8]}@example.com"
        register_data = {
            "name": "Test Subscription User",
            "email": test_email,
            "password": "TestPass123!",
            "confirm_password": "TestPass123!"
        }
        
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/register", json=register_data)
        
        if response.status_code == 201:
            print(f"✓ Created test user: {test_email}")
        else:
            # If registration fails (user exists), try login
            login_data = {"email": test_email, "password": "TestPass123!"}
            response = session.post(f"{BASE_URL}/api/auth/login", json=login_data)
            if response.status_code == 200:
                print(f"✓ Logged in as existing test user: {test_email}")
            else:
                pytest.skip(f"Could not create/login test user: {response.text}")
        
        return session
    
    def test_subscription_status_requires_auth(self):
        """Verify subscription status endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/subscription/status")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ GET /api/subscription/status returns 401 without auth")
    
    def test_subscription_status_with_auth(self, test_user_session):
        """Verify authenticated user gets subscription status"""
        response = test_user_session.get(f"{BASE_URL}/api/subscription/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "plan_type" in data, "Missing plan_type in response"
        assert "subscription_status" in data, "Missing subscription_status in response"
        assert "limits" in data, "Missing limits in response"
        assert "usage" in data, "Missing usage in response"
        
        print(f"✓ Authenticated user gets subscription status: plan={data['plan_type']}, status={data['subscription_status']}")
    
    def test_new_user_has_free_trial(self, test_user_session):
        """Verify new users get free trial subscription"""
        response = test_user_session.get(f"{BASE_URL}/api/subscription/status")
        data = response.json()
        
        # New users should have 'free' plan with 'trialing' status
        assert data["plan_type"] == "free", f"Expected 'free' plan, got {data['plan_type']}"
        assert data["subscription_status"] == "trialing", f"Expected 'trialing' status, got {data['subscription_status']}"
        
        # Check trial_ends_at exists for trial users
        if data.get("trial_ends_at"):
            print(f"✓ New user has trial status with trial_ends_at: {data['trial_ends_at']}")
        else:
            print(f"✓ New user has trial status (plan_type=free, status=trialing)")
    
    def test_subscription_status_includes_usage_stats(self, test_user_session):
        """Verify subscription status includes usage statistics"""
        response = test_user_session.get(f"{BASE_URL}/api/subscription/status")
        data = response.json()
        
        usage = data.get("usage", {})
        assert "accounts" in usage, "Missing accounts usage"
        assert "contacts" in usage, "Missing contacts usage"
        assert "recipients" in usage, "Missing recipients usage"
        
        # Each usage should have current, limit, remaining
        for key in ["accounts", "contacts", "recipients"]:
            assert "current" in usage[key], f"Missing 'current' in {key}"
            assert "limit" in usage[key], f"Missing 'limit' in {key}"
            
        print(f"✓ Usage stats: accounts={usage['accounts']['current']}/{usage['accounts']['limit']}, " +
              f"contacts={usage['contacts']['current']}/{usage['contacts']['limit']}, " +
              f"recipients={usage['recipients']['current']}/{usage['recipients']['limit']}")


class TestCreateCheckoutEndpoint:
    """Tests for POST /api/subscription/create-checkout - requires auth"""
    
    @pytest.fixture
    def test_user_session(self):
        """Create test user and return session"""
        test_email = f"test_checkout_{uuid.uuid4().hex[:8]}@example.com"
        register_data = {
            "name": "Test Checkout User",
            "email": test_email,
            "password": "TestPass123!",
            "confirm_password": "TestPass123!"
        }
        
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/register", json=register_data)
        
        if response.status_code == 201:
            print(f"✓ Created test user: {test_email}")
        else:
            login_data = {"email": test_email, "password": "TestPass123!"}
            response = session.post(f"{BASE_URL}/api/auth/login", json=login_data)
            if response.status_code != 200:
                pytest.skip(f"Could not create/login test user")
        
        return session
    
    def test_create_checkout_requires_auth(self):
        """Verify create checkout requires authentication"""
        checkout_data = {
            "price_id": "price_1T3JubD2HZgi5NSCVPybSMdk",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel"
        }
        response = requests.post(f"{BASE_URL}/api/subscription/create-checkout", json=checkout_data)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print(f"✓ POST /api/subscription/create-checkout returns 401 without auth")
    
    def test_create_checkout_returns_url(self, test_user_session):
        """Verify create checkout returns checkout URL"""
        checkout_data = {
            "price_id": "price_1T3JubD2HZgi5NSCVPybSMdk",  # Starter USD
            "success_url": "https://routemail-drip.preview.emergentagent.com/dashboard?subscription=success",
            "cancel_url": "https://routemail-drip.preview.emergentagent.com/subscription?canceled=true"
        }
        
        response = test_user_session.post(
            f"{BASE_URL}/api/subscription/create-checkout",
            json=checkout_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "checkout_url" in data, "Missing checkout_url in response"
        assert "session_id" in data, "Missing session_id in response"
        assert "checkout.stripe.com" in data["checkout_url"], "Checkout URL should be stripe.com"
        
        print(f"✓ Created checkout session with URL: {data['checkout_url'][:60]}...")


class TestHealthEndpoint:
    """Basic health check"""
    
    def test_health_check(self):
        """Verify health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        print(f"✓ Health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
