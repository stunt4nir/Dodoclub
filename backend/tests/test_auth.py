import pytest
import requests

class TestAuth:
    """Authentication endpoint tests"""

    def test_register_creates_user_returns_token_and_user(self, base_url, api_client, test_run_id):
        """POST /api/auth/register creates user, returns {token, user}"""
        payload = {
            "email": f"TEST_user_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Test User",
            "shirt_number": 10
        }
        response = api_client.post(f"{base_url}/api/auth/register", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data, "Response missing 'token' field"
        assert "user" in data, "Response missing 'user' field"
        assert isinstance(data["token"], str), "Token should be a string"
        assert len(data["token"]) > 20, "Token seems too short"
        
        user = data["user"]
        assert user["email"] == payload["email"].lower(), "Email should be lowercase"
        assert user["name"] == payload["name"]
        assert user["shirt_number"] == payload["shirt_number"]
        assert user["role"] == "user", "First registered user should have role 'user'"
        assert user["can_edit_matches"] == False, "Regular user should not have edit access by default"
        assert user["goals"] == 0
        assert user["assists"] == 0
        assert user["matches_played"] == 0
        assert user["rating"] == 0.0
        assert "id" in user
        assert "_id" not in user, "MongoDB _id should not be exposed"
        
        # Verify persistence with GET
        token = data["token"]
        me_response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["id"] == user["id"]
        assert me_data["email"] == user["email"]

    def test_login_with_admin_returns_admin_role(self, base_url, api_client, test_run_id):
        """POST /api/auth/login with admin credentials returns admin role"""
        response = api_client.post(f"{base_url}/api/auth/login", json={
            "email": "admin@clubdodo.com",
            "password": "dodo2026"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "token" in data
        assert "user" in data
        
        user = data["user"]
        assert user["email"] == "admin@clubdodo.com"
        assert user["role"] == "admin", "Admin user should have role 'admin'"
        assert user["can_edit_matches"] == True, "Admin should have edit access"
        assert "_id" not in user, "MongoDB _id should not be exposed"

    def test_login_with_invalid_credentials_returns_401(self, base_url, api_client, test_run_id):
        """POST /api/auth/login with wrong password returns 401"""
        response = api_client.post(f"{base_url}/api/auth/login", json={
            "email": "admin@clubdodo.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    def test_get_me_with_bearer_token_returns_user(self, base_url, api_client, admin_token):
        """GET /api/auth/me with Bearer token returns user"""
        response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        user = response.json()
        assert user["email"] == "admin@clubdodo.com"
        assert user["role"] == "admin"
        assert "id" in user
        assert "_id" not in user, "MongoDB _id should not be exposed"

    def test_get_me_without_token_returns_401(self, base_url, api_client, test_run_id):
        """GET /api/auth/me without token returns 401"""
        response = api_client.get(f"{base_url}/api/auth/me")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    def test_get_me_with_invalid_token_returns_401(self, base_url, api_client, test_run_id):
        """GET /api/auth/me with invalid token returns 401"""
        response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
