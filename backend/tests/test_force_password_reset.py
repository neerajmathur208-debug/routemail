"""
Test Force Password Reset Feature
- Tests /api/admin/users/{user_id}/force-password-reset endpoint
- Requires super_admin role to access
"""
import pytest
import requests
import os
from datetime import datetime, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://mailrotate-demo.preview.emergentagent.com')


class TestForcePasswordReset:
    """Tests for the Force Password Reset admin feature"""
    
    @pytest.fixture(scope="class")
    def super_admin_session(self):
        """Create a super admin session for testing"""
        import subprocess
        result = subprocess.run([
            'mongosh', '--quiet', '--eval', '''
use('test_database');
var userId = 'test-super-admin-pytest-' + Date.now();
var sessionToken = 'test_super_session_pytest_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'pytest.superadmin.' + Date.now() + '@example.com',
  name: 'Pytest Super Admin',
  provider: 'email',
  role: 'super_admin',
  subscription_status: 'active',
  plan_type: 'growth',
  email_verified: true,
  created_at: new Date().toISOString()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print(JSON.stringify({user_id: userId, session_token: sessionToken}));
'''
        ], capture_output=True, text=True)
        import json
        # Parse the last line which contains the JSON
        lines = result.stdout.strip().split('\n')
        for line in reversed(lines):
            if '{' in line and '}' in line:
                return json.loads(line)
        pytest.skip("Failed to create super admin session")
    
    @pytest.fixture(scope="class")
    def regular_user(self):
        """Create a regular user for testing password reset"""
        import subprocess
        result = subprocess.run([
            'mongosh', '--quiet', '--eval', '''
use('test_database');
var userId = 'test-regular-user-pytest-' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'pytest.regular.' + Date.now() + '@example.com',
  name: 'Pytest Regular User',
  provider: 'email',
  role: 'user',
  subscription_status: 'active',
  plan_type: 'free',
  email_verified: true,
  created_at: new Date().toISOString()
});
print(JSON.stringify({user_id: userId}));
'''
        ], capture_output=True, text=True)
        import json
        lines = result.stdout.strip().split('\n')
        for line in reversed(lines):
            if '{' in line and '}' in line:
                return json.loads(line)
        pytest.skip("Failed to create regular user")
    
    @pytest.fixture(scope="class")
    def google_user(self):
        """Create a Google OAuth user for testing"""
        import subprocess
        result = subprocess.run([
            'mongosh', '--quiet', '--eval', '''
use('test_database');
var userId = 'test-google-user-pytest-' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'pytest.google.' + Date.now() + '@example.com',
  name: 'Pytest Google User',
  provider: 'google',
  role: 'user',
  subscription_status: 'active',
  plan_type: 'free',
  email_verified: true,
  created_at: new Date().toISOString()
});
print(JSON.stringify({user_id: userId}));
'''
        ], capture_output=True, text=True)
        import json
        lines = result.stdout.strip().split('\n')
        for line in reversed(lines):
            if '{' in line and '}' in line:
                return json.loads(line)
        pytest.skip("Failed to create Google user")
    
    @pytest.fixture(scope="class")
    def regular_user_session(self):
        """Create a regular user session (non-admin)"""
        import subprocess
        result = subprocess.run([
            'mongosh', '--quiet', '--eval', '''
use('test_database');
var userId = 'test-nonadmin-pytest-' + Date.now();
var sessionToken = 'test_nonadmin_session_pytest_' + Date.now();
db.users.insertOne({
  user_id: userId,
  email: 'pytest.nonadmin.' + Date.now() + '@example.com',
  name: 'Pytest Non-Admin',
  provider: 'email',
  role: 'user',
  subscription_status: 'active',
  plan_type: 'free',
  email_verified: true,
  created_at: new Date().toISOString()
});
db.user_sessions.insertOne({
  user_id: userId,
  session_token: sessionToken,
  expires_at: new Date(Date.now() + 7*24*60*60*1000),
  created_at: new Date()
});
print(JSON.stringify({user_id: userId, session_token: sessionToken}));
'''
        ], capture_output=True, text=True)
        import json
        lines = result.stdout.strip().split('\n')
        for line in reversed(lines):
            if '{' in line and '}' in line:
                return json.loads(line)
        pytest.skip("Failed to create regular user session")
    
    def test_force_reset_requires_auth(self):
        """Test that force password reset endpoint requires authentication"""
        response = requests.post(
            f"{BASE_URL}/api/admin/users/any-user-id/force-password-reset"
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}: {response.text}"
        print("✓ Force password reset requires authentication")
    
    def test_force_reset_requires_super_admin(self, regular_user_session):
        """Test that force password reset endpoint requires super_admin role"""
        session_token = regular_user_session['session_token']
        response = requests.post(
            f"{BASE_URL}/api/admin/users/any-user-id/force-password-reset",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for non-admin, got {response.status_code}: {response.text}"
        print("✓ Force password reset requires super_admin role")
    
    def test_force_reset_user_not_found(self, super_admin_session):
        """Test force reset returns 404 for non-existent user"""
        session_token = super_admin_session['session_token']
        response = requests.post(
            f"{BASE_URL}/api/admin/users/non-existent-user-id/force-password-reset",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        assert "not found" in response.json().get("detail", "").lower()
        print("✓ Force password reset returns 404 for non-existent user")
    
    def test_force_reset_google_user_fails(self, super_admin_session, google_user):
        """Test force reset fails for Google OAuth users"""
        session_token = super_admin_session['session_token']
        user_id = google_user['user_id']
        
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{user_id}/force-password-reset",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 400, f"Expected 400 for Google user, got {response.status_code}: {response.text}"
        assert "google" in response.json().get("detail", "").lower()
        print("✓ Force password reset correctly rejects Google OAuth users")
    
    def test_force_reset_success(self, super_admin_session, regular_user):
        """Test force reset succeeds for email users"""
        session_token = super_admin_session['session_token']
        user_id = regular_user['user_id']
        
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{user_id}/force-password-reset",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert "sent" in data.get("message", "").lower() or "success" in data.get("message", "").lower()
        assert "user_email" in data
        print(f"✓ Force password reset successful for user {data.get('user_email')}")
    
    def test_force_reset_creates_token(self, super_admin_session, regular_user):
        """Test that force reset creates a reset token in the database"""
        import subprocess
        import json
        
        session_token = super_admin_session['session_token']
        user_id = regular_user['user_id']
        
        # Call force reset
        response = requests.post(
            f"{BASE_URL}/api/admin/users/{user_id}/force-password-reset",
            headers={"Authorization": f"Bearer {session_token}"}
        )
        assert response.status_code == 200
        
        # Check database for reset token
        result = subprocess.run([
            'mongosh', '--quiet', '--eval', f'''
use('test_database');
var user = db.users.findOne({{user_id: "{user_id}"}});
print(JSON.stringify({{
  has_reset_token: !!user.reset_token,
  has_reset_expires: !!user.reset_expires
}}));
'''
        ], capture_output=True, text=True)
        
        lines = result.stdout.strip().split('\n')
        for line in reversed(lines):
            if '{' in line and '}' in line:
                data = json.loads(line)
                assert data.get('has_reset_token') == True, "Reset token not found in database"
                assert data.get('has_reset_expires') == True, "Reset expiry not found in database"
                print("✓ Force password reset creates token in database")
                return
        
        pytest.fail("Could not verify reset token in database")


class TestAdminEndpointSecurity:
    """Additional security tests for admin endpoints"""
    
    def test_admin_stats_requires_super_admin(self):
        """Test that admin stats endpoint requires super_admin role"""
        response = requests.get(f"{BASE_URL}/api/admin/stats")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Admin stats endpoint requires authentication")
    
    def test_admin_users_requires_super_admin(self):
        """Test that admin users list endpoint requires super_admin role"""
        response = requests.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code == 401, f"Expected 401 without auth, got {response.status_code}"
        print("✓ Admin users endpoint requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
