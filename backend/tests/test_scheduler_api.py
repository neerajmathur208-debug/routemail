"""
Backend API Tests for Campaign Scheduler Feature
Tests for:
- POST /api/campaigns (with scheduled_at parameter)
- POST /api/campaigns/{id}/schedule 
- POST /api/campaigns/{id}/unschedule
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndBasicEndpoints:
    """Basic health and API availability tests"""
    
    def test_health_endpoint(self):
        """Test /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASS: /api/health returns healthy status")

    def test_root_endpoint(self):
        """Test /api/ returns API info"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"PASS: /api/ returns: {data}")


class TestCampaignSchedulerEndpoints:
    """Tests for Campaign Scheduler API endpoints"""
    
    def test_campaigns_endpoint_exists(self):
        """Test GET /api/campaigns endpoint exists (requires auth)"""
        response = requests.get(f"{BASE_URL}/api/campaigns")
        # Without auth, should return 401
        assert response.status_code == 401
        print("PASS: /api/campaigns requires authentication (returns 401 without auth)")

    def test_campaign_schedule_endpoint_exists(self):
        """Test POST /api/campaigns/{id}/schedule endpoint exists"""
        # Using a fake campaign ID - should return 401 (auth required) not 404
        response = requests.post(f"{BASE_URL}/api/campaigns/test_campaign_id/schedule")
        # Without auth, should return 401
        assert response.status_code == 401
        print("PASS: /api/campaigns/{id}/schedule requires authentication (returns 401)")

    def test_campaign_unschedule_endpoint_exists(self):
        """Test POST /api/campaigns/{id}/unschedule endpoint exists"""
        # Using a fake campaign ID - should return 401 (auth required) not 404
        response = requests.post(f"{BASE_URL}/api/campaigns/test_campaign_id/unschedule")
        # Without auth, should return 401
        assert response.status_code == 401
        print("PASS: /api/campaigns/{id}/unschedule requires authentication (returns 401)")

    def test_campaign_create_endpoint_exists(self):
        """Test POST /api/campaigns endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/campaigns", json={})
        # Without auth, should return 401
        assert response.status_code == 401
        print("PASS: POST /api/campaigns requires authentication (returns 401)")


class TestCampaignStartPauseResumeEndpoints:
    """Tests for Campaign Start/Pause/Resume endpoints"""
    
    def test_campaign_start_endpoint_exists(self):
        """Test POST /api/campaigns/{id}/start endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/campaigns/test_campaign_id/start")
        assert response.status_code == 401
        print("PASS: /api/campaigns/{id}/start requires authentication")

    def test_campaign_pause_endpoint_exists(self):
        """Test POST /api/campaigns/{id}/pause endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/campaigns/test_campaign_id/pause")
        assert response.status_code == 401
        print("PASS: /api/campaigns/{id}/pause requires authentication")

    def test_campaign_resume_endpoint_exists(self):
        """Test POST /api/campaigns/{id}/resume endpoint exists"""
        response = requests.post(f"{BASE_URL}/api/campaigns/test_campaign_id/resume")
        assert response.status_code == 401
        print("PASS: /api/campaigns/{id}/resume requires authentication")


class TestOtherCoreEndpoints:
    """Tests for other core endpoints to ensure they're working"""
    
    def test_accounts_endpoint_requires_auth(self):
        """Test GET /api/accounts requires auth"""
        response = requests.get(f"{BASE_URL}/api/accounts")
        assert response.status_code == 401
        print("PASS: /api/accounts requires authentication")

    def test_lists_endpoint_requires_auth(self):
        """Test GET /api/lists requires auth"""
        response = requests.get(f"{BASE_URL}/api/lists")
        assert response.status_code == 401
        print("PASS: /api/lists requires authentication")

    def test_dashboard_stats_requires_auth(self):
        """Test GET /api/dashboard/stats requires auth"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code == 401
        print("PASS: /api/dashboard/stats requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
