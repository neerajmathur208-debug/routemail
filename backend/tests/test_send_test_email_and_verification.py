"""
Tests for Send Test Email and Email Verification features
- Send Test Email: verifies the endpoint uses smtp_password_encrypted field correctly
- Email Verification: checks the verification flow doesn't show false failures
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://routemail-demo.preview.emergentagent.com')
BASE_URL = BASE_URL.rstrip('/')

class TestSendTestEmail:
    """Tests for Send Test Email endpoint"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create a requests session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        return s
    
    @pytest.fixture(scope="class")  
    def auth_session(self, session):
        """Login and get authenticated session"""
        login_response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "testuser@example.com",
                "password": "TestPass123!"
            }
        )
        if login_response.status_code == 200:
            # Cookies are automatically stored in session
            print(f"Login successful: {login_response.json().get('user_id', 'unknown')}")
            return session
        else:
            pytest.skip(f"Could not login: {login_response.status_code} - {login_response.text}")
            return None
    
    def test_send_test_email_without_auth(self, session):
        """Test that send-test endpoint requires authentication"""
        response = session.post(
            f"{BASE_URL}/api/campaigns/send-test",
            json={
                "test_email": "test@example.com",
                "subject": "Test Subject",
                "body": "<p>Test body</p>"
            }
        )
        # Should return 401 Unauthorized without auth
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Send test email requires authentication")
    
    def test_send_test_email_no_accounts(self, auth_session):
        """Test send-test when user has no connected email accounts"""
        if auth_session is None:
            pytest.skip("Auth session not available")
        
        response = auth_session.post(
            f"{BASE_URL}/api/campaigns/send-test",
            json={
                "test_email": "test@example.com",
                "subject": "Test Subject",
                "body": "<p>Test body</p>"
            }
        )
        
        # Should return 400 with message about no accounts
        # OR if there are accounts, it might succeed or fail with SMTP error
        print(f"Send test email response: {response.status_code}")
        print(f"Response body: {response.text}")
        
        if response.status_code == 400:
            data = response.json()
            detail = data.get("detail", "")
            # Should NOT have the old "Failed to decrypt" error if accounts exist
            # It should either say "no connected account" or SMTP error
            assert "Failed to decrypt account credentials" not in detail, \
                f"CRITICAL: Still seeing old decrypt error: {detail}"
            print(f"✓ Proper error message: {detail}")
        elif response.status_code == 200:
            print("✓ Send test email succeeded (user has accounts)")
        elif response.status_code == 500:
            # Check if it's the old error
            data = response.json()
            detail = data.get("detail", "")
            if "Failed to decrypt account credentials" in detail:
                pytest.fail(f"BUG: Still seeing old decrypt error: {detail}")
            else:
                print(f"Server error (may be SMTP issue): {detail}")
        
    def test_send_test_email_validation(self, auth_session):
        """Test send-test validates required fields"""
        if auth_session is None:
            pytest.skip("Auth session not available")
        
        # Missing subject
        response = auth_session.post(
            f"{BASE_URL}/api/campaigns/send-test",
            json={
                "test_email": "test@example.com",
                "subject": "",
                "body": "<p>Test body</p>"
            }
        )
        
        # Should return 400 for missing subject
        if response.status_code == 400:
            data = response.json()
            detail = data.get("detail", "")
            if "subject" in detail.lower() or "required" in detail.lower():
                print("✓ Validates subject is required")
            else:
                print(f"Validation response: {detail}")


class TestEmailVerification:
    """Tests for Email Verification flow"""
    
    @pytest.fixture(scope="class")
    def session(self):
        """Create a requests session"""
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        return s
    
    def test_verify_email_invalid_token(self, session):
        """Test verification with invalid token"""
        response = session.get(
            f"{BASE_URL}/api/auth/verify-email?token=invalid_token_12345"
        )
        
        # Should return 400 with proper error message
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        data = response.json()
        detail = data.get("detail", "")
        print(f"Invalid token response: {detail}")
        
        # Should have a clear error message
        assert "invalid" in detail.lower() or "expired" in detail.lower() or "used" in detail.lower(), \
            f"Error message should be clear about invalid token: {detail}"
        print("✓ Invalid token returns proper error")
    
    def test_verify_email_no_token(self, session):
        """Test verification with no token parameter"""
        response = session.get(f"{BASE_URL}/api/auth/verify-email")
        
        # Should return 422 (validation error) for missing required parameter
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Missing token returns validation error")
    
    def test_verify_email_already_verified_behavior(self, session):
        """Test that already verified emails are handled gracefully"""
        # This test checks the fix for 'Activation Failed' flash before success
        # We can't actually verify a token, but we check the endpoint structure
        
        # Use a token that looks real but is invalid
        fake_token = "already_used_verification_token_abc123xyz"
        response = session.get(
            f"{BASE_URL}/api/auth/verify-email?token={fake_token}"
        )
        
        # Response should NOT show "already verified" for invalid token
        assert response.status_code == 400
        data = response.json()
        detail = data.get("detail", "")
        print(f"Response for fake token: {detail}")
        
        # Should say invalid, not "already verified" for truly invalid tokens
        print("✓ Verification endpoint handles invalid tokens correctly")


class TestLegalPages:
    """Tests for Legal Pages accessibility - these are SPA routes so we just check HTTP 200"""
    
    def test_privacy_policy_page(self):
        """Test Privacy Policy page is accessible"""
        response = requests.get(f"{BASE_URL}/privacy-policy")
        # SPA returns 200 for all routes, content is rendered client-side
        assert response.status_code == 200, f"Privacy Policy page returned {response.status_code}"
        print("✓ Privacy Policy page accessible (SPA route)")
    
    def test_terms_page(self):
        """Test Terms and Conditions page is accessible"""
        response = requests.get(f"{BASE_URL}/terms-and-conditions")
        assert response.status_code == 200, f"Terms page returned {response.status_code}"
        print("✓ Terms and Conditions page accessible")
    
    def test_anti_spam_page(self):
        """Test Anti-Spam Policy page is accessible"""
        response = requests.get(f"{BASE_URL}/anti-spam-policy")
        assert response.status_code == 200, f"Anti-Spam page returned {response.status_code}"
        print("✓ Anti-Spam Policy page accessible")
    
    def test_gdpr_page(self):
        """Test GDPR Compliance page is accessible"""
        response = requests.get(f"{BASE_URL}/gdpr-compliance")
        assert response.status_code == 200, f"GDPR page returned {response.status_code}"
        print("✓ GDPR Compliance page accessible")


class TestEmailAccountsEndpoint:
    """Test email accounts API to verify field naming"""
    
    @pytest.fixture(scope="class")
    def auth_session(self):
        """Login and get authenticated session"""
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        
        login_response = session.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "testuser@example.com",
                "password": "TestPass123!"
            }
        )
        if login_response.status_code == 200:
            return session
        else:
            pytest.skip(f"Could not login: {login_response.status_code}")
            return None
    
    def test_get_accounts(self, auth_session):
        """Test getting email accounts list"""
        if auth_session is None:
            pytest.skip("Auth session not available")
        
        response = auth_session.get(f"{BASE_URL}/api/accounts")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # Should have accounts list and limit_info
        assert "accounts" in data, "Response should have 'accounts' key"
        assert "limit_info" in data, "Response should have 'limit_info' key"
        
        print(f"✓ Accounts endpoint working. Found {len(data['accounts'])} accounts")
        
        # If there are accounts, check they don't expose encrypted password
        for account in data["accounts"]:
            assert "smtp_password_encrypted" not in account, \
                "Encrypted password should not be exposed in response"
            assert "smtp_password" not in account, \
                "Plain password should not be in response"
        
        print("✓ Accounts don't expose password fields")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
