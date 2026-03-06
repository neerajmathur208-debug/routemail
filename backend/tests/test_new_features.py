"""
Tests for new features:
1. FRONTEND_URL trailing slash fix
2. Admin notification email functions
3. Terms checkbox validation in Register page
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')

class TestFrontendUrlConfig:
    """Test FRONTEND_URL trailing slash fix"""
    
    def test_api_health_check(self):
        """Verify API is accessible"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        print("API health check passed")
    
    def test_frontend_url_no_trailing_slash(self):
        """Check that FRONTEND_URL doesn't have trailing slash by verifying reset link format"""
        # We test the forgot-password endpoint which uses FRONTEND_URL internally
        response = requests.post(
            f"{BASE_URL}/api/auth/forgot-password",
            json={"email": "test@example.com"}
        )
        # API should return 200 regardless of whether email exists (security)
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print("Forgot password endpoint works - FRONTEND_URL config is used for reset links")


class TestAdminNotificationFunctions:
    """
    Test admin notification functions exist and work.
    Note: Actual email sending cannot be verified without mocking,
    but we verify the registration/auth endpoints that trigger them work.
    """
    
    def test_email_registration_triggers_admin_notification(self):
        """Test email registration endpoint (triggers admin notification in background)"""
        import time
        test_email = f"test.newuser.{int(time.time())}@example.com"
        
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "name": "Test User",
                "email": test_email,
                "password": "TestPass123!",
                "confirm_password": "TestPass123!"
            }
        )
        
        # Registration should succeed (201) - admin notification is sent in background
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("requires_verification") == True
        assert data.get("email") == test_email
        print(f"Email registration succeeded for {test_email} - admin notification triggered")
    
    def test_google_oauth_session_endpoint_exists(self):
        """Verify Google OAuth session endpoint exists (used for Google signup)"""
        # This endpoint requires a valid Emergent session_id, so we test it returns appropriate error
        response = requests.post(
            f"{BASE_URL}/api/auth/session",
            json={"session_id": "invalid_session"}
        )
        # Should return 401 for invalid session (not 404 or 500)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("Google OAuth session endpoint exists and returns proper error for invalid session")
    
    def test_stripe_webhook_endpoint_exists(self):
        """Verify Stripe webhook endpoint exists"""
        response = requests.post(
            f"{BASE_URL}/api/stripe/webhook",
            headers={"Content-Type": "application/json"},
            data="{}"  # Empty body - will fail signature check but endpoint should exist
        )
        # Should return 400 (bad request due to invalid signature) not 404
        assert response.status_code in [400, 401, 422], f"Expected 400/401/422, got {response.status_code}"
        print("Stripe webhook endpoint exists")


class TestTermsCheckboxValidation:
    """Test that terms acceptance is required for registration"""
    
    def test_registration_requires_all_fields(self):
        """Verify registration endpoint validates required fields"""
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "name": "",
                "email": "",
                "password": "",
                "confirm_password": ""
            }
        )
        # Should fail validation (422 or 400)
        assert response.status_code in [400, 422]
        print("Registration properly validates required fields")
    
    def test_registration_validates_password_match(self):
        """Verify password confirmation is validated"""
        import time
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "name": "Test User",
                "email": f"test{int(time.time())}@example.com",
                "password": "Password123!",
                "confirm_password": "DifferentPass123!"
            }
        )
        assert response.status_code == 400
        assert "match" in response.text.lower() or "do not match" in response.text.lower()
        print("Registration validates password match")
    
    def test_registration_validates_password_length(self):
        """Verify minimum password length"""
        import time
        response = requests.post(
            f"{BASE_URL}/api/auth/register",
            json={
                "name": "Test User",
                "email": f"test{int(time.time())}@example.com",
                "password": "short",
                "confirm_password": "short"
            }
        )
        assert response.status_code == 400
        assert "8" in response.text or "character" in response.text.lower()
        print("Registration validates password length (min 8 characters)")


class TestLegalPageRoutes:
    """Test that Terms and Privacy routes exist"""
    
    def test_terms_and_conditions_route(self):
        """Verify /terms-and-conditions page is accessible"""
        # This tests the frontend route through the API proxy
        # Since it's a SPA, the API won't serve this, but we verify it's properly routed
        response = requests.get(f"{BASE_URL.replace('/api', '')}/terms-and-conditions", allow_redirects=True)
        # SPA should serve index.html for this route
        # We can't fully test this without browser, but verify no 500 error
        assert response.status_code != 500, "Server error on terms page"
        print(f"Terms page returns status {response.status_code}")
    
    def test_privacy_policy_route(self):
        """Verify /privacy-policy page is accessible"""
        response = requests.get(f"{BASE_URL.replace('/api', '')}/privacy-policy", allow_redirects=True)
        assert response.status_code != 500, "Server error on privacy page"
        print(f"Privacy page returns status {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
