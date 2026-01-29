"""Unit tests for the API Gateway."""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.api.gateway import app
from src.api.auth import auth_service, User, UserRole
from src.models.action_models import ActionType

client = TestClient(app)


class TestAPIGateway:
    """Test cases for API Gateway."""
    
    def setup_method(self):
        """Setup test environment."""
        # Create test user
        self.test_user = User(
            username="testuser",
            roles=[UserRole.OPERATOR],
            is_active=True,
            created_at=datetime.utcnow()
        )
        auth_service.users["testuser"] = self.test_user
        
        # Create test token
        self.test_token = auth_service.create_access_token(
            data={"sub": "testuser"}
        )
        self.auth_headers = {"Authorization": f"Bearer {self.test_token}"}
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] in ["healthy", "unhealthy"]
        assert "timestamp" in data
        assert "version" in data
        assert "services" in data
    
    def test_submit_action_without_auth(self):
        """Test submitting action without authentication."""
        action_data = {
            "type": "flow_mod",
            "target": "switch-1",
            "parameters": {
                "match": {"in_port": 1},
                "actions": ["output:2"]
            }
        }
        
        response = client.post("/api/v1/actions", json=action_data)
        assert response.status_code == 403  # Forbidden without auth
    
    def test_submit_valid_action(self):
        """Test submitting valid action with authentication."""
        action_data = {
            "type": "flow_mod",
            "target": "switch-1",
            "parameters": {
                "match": {"in_port": 1},
                "actions": ["output:2"]
            },
            "priority": 1000,
            "timeout": 30,
            "description": "Test flow rule"
        }
        
        response = client.post(
            "/api/v1/actions", 
            json=action_data,
            headers=self.auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "action_id" in data
        assert data["status"] == "pending"
        assert "message" in data
    
    def test_submit_invalid_action(self):
        """Test submitting invalid action."""
        action_data = {
            "type": "invalid_type",
            "target": "switch-1",
            "parameters": {}
        }
        
        response = client.post(
            "/api/v1/actions", 
            json=action_data,
            headers=self.auth_headers
        )
        assert response.status_code == 422  # Validation error
    
    def test_get_action_status(self):
        """Test getting action status."""
        # First submit an action
        action_data = {
            "type": "flow_mod",
            "target": "switch-1",
            "parameters": {
                "match": {"in_port": 1},
                "actions": ["output:2"]
            }
        }
        
        submit_response = client.post(
            "/api/v1/actions", 
            json=action_data,
            headers=self.auth_headers
        )
        action_id = submit_response.json()["action_id"]
        
        # Get action status
        response = client.get(
            f"/api/v1/actions/{action_id}",
            headers=self.auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["action_id"] == action_id
        assert "status" in data
        assert "created_at" in data
    
    def test_get_nonexistent_action(self):
        """Test getting status of nonexistent action."""
        response = client.get(
            "/api/v1/actions/nonexistent-id",
            headers=self.auth_headers
        )
        assert response.status_code == 404
    
    def test_list_actions(self):
        """Test listing actions."""
        response = client.get(
            "/api/v1/actions",
            headers=self.auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_list_actions_with_filter(self):
        """Test listing actions with status filter."""
        response = client.get(
            "/api/v1/actions?status_filter=pending",
            headers=self.auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_cancel_action(self):
        """Test cancelling an action."""
        # First submit an action
        action_data = {
            "type": "flow_mod",
            "target": "switch-1",
            "parameters": {
                "match": {"in_port": 1},
                "actions": ["output:2"]
            }
        }
        
        submit_response = client.post(
            "/api/v1/actions", 
            json=action_data,
            headers=self.auth_headers
        )
        action_id = submit_response.json()["action_id"]
        
        # Cancel the action
        response = client.delete(
            f"/api/v1/actions/{action_id}",
            headers=self.auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
    
    def test_batch_actions(self):
        """Test submitting batch actions."""
        batch_data = {
            "actions": [
                {
                    "type": "flow_mod",
                    "target": "switch-1",
                    "parameters": {
                        "match": {"in_port": 1},
                        "actions": ["output:2"]
                    }
                },
                {
                    "type": "flow_mod",
                    "target": "switch-2",
                    "parameters": {
                        "match": {"in_port": 1},
                        "actions": ["output:3"]
                    }
                }
            ],
            "execution_mode": "parallel"
        }
        
        response = client.post(
            "/api/v1/actions/batch",
            json=batch_data,
            headers=self.auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "batch_id" in data
        assert "action_ids" in data
        assert data["total_actions"] == 2
    
    def test_metrics_endpoint(self):
        """Test metrics endpoint."""
        response = client.get("/metrics")
        assert response.status_code == 200
        
        # Should return Prometheus-style metrics
        content = response.text
        assert "northbound_actions_total" in content


class TestAuthentication:
    """Test cases for authentication."""
    
    def test_login_success(self):
        """Test successful login."""
        login_data = {
            "username": "admin",
            "password": "password"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user_info" in data
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        login_data = {
            "username": "admin",
            "password": "wrong_password"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        assert response.status_code == 401
    
    def test_get_current_user(self):
        """Test getting current user info."""
        # First login to get token
        login_data = {
            "username": "admin",
            "password": "password"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        
        # Get user info
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["username"] == "admin"
        assert "roles" in data
    
    def test_refresh_token(self):
        """Test token refresh."""
        # First login to get refresh token
        login_data = {
            "username": "admin",
            "password": "password"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh token
        refresh_data = {"refresh_token": refresh_token}
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_create_api_key(self):
        """Test API key creation."""
        # First login as admin
        login_data = {
            "username": "admin",
            "password": "password"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create API key
        api_key_data = {
            "name": "test-key",
            "description": "Test API key",
            "permissions": ["read:actions", "write:actions"]
        }
        
        response = client.post(
            "/api/v1/auth/api-keys",
            json=api_key_data,
            headers=headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "api_key" in data
        assert data["name"] == "test-key"
    
    def test_list_api_keys(self):
        """Test listing API keys."""
        # First login as admin
        login_data = {
            "username": "admin",
            "password": "password"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # List API keys
        response = client.get("/api/v1/auth/api-keys", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)


if __name__ == "__main__":
    pytest.main([__file__])