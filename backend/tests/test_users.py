import pytest
import requests

class TestUsers:
    """User management endpoint tests"""

    def test_get_users_lists_users_sorted_by_rating_desc(self, base_url, admin_client):
        """GET /api/users lists users sorted by rating descending"""
        response = admin_client.get(f"{base_url}/api/users")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        users = response.json()
        assert isinstance(users, list), "Response should be a list"
        assert len(users) > 0, "Should have at least admin user"
        
        # Check sorting by rating (descending)
        ratings = [u["rating"] for u in users]
        assert ratings == sorted(ratings, reverse=True), "Users should be sorted by rating descending"
        
        # Check no MongoDB _id exposure
        for user in users:
            assert "_id" not in user, "MongoDB _id should not be exposed"
            assert "password_hash" not in user, "Password hash should not be exposed"
            assert "id" in user
            assert "email" in user
            assert "rating" in user

    def test_put_users_me_updates_name_shirt_number_profile_picture(self, base_url, api_client, test_run_id):
        """PUT /api/users/me updates name, shirt_number, profile_picture"""
        # First register a new user
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_update_user_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Original Name",
            "shirt_number": 5
        })
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        user_id = register_response.json()["user"]["id"]
        
        # Update profile
        update_response = api_client.put(
            f"{base_url}/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "Updated Name",
                "shirt_number": 99,
                "profile_picture": "data:image/png;base64,iVBORw0KGgo="
            }
        )
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        
        updated_user = update_response.json()
        assert updated_user["name"] == "Updated Name"
        assert updated_user["shirt_number"] == 99
        assert updated_user["profile_picture"] == "data:image/png;base64,iVBORw0KGgo="
        assert "_id" not in updated_user
        
        # Verify persistence with GET /api/auth/me
        me_response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["name"] == "Updated Name"
        assert me_data["shirt_number"] == 99
        assert me_data["profile_picture"] == "data:image/png;base64,iVBORw0KGgo="

    def test_post_users_grant_edit_admin_only_toggles_can_edit_matches(self, base_url, api_client, admin_client, test_run_id):
        """POST /api/users/grant-edit (admin only) toggles can_edit_matches"""
        # Register a regular user
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_editor_user_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Editor User"
        })
        assert register_response.status_code == 200
        user_id = register_response.json()["user"]["id"]
        user_token = register_response.json()["token"]
        
        # Verify user cannot edit matches initially
        initial_user = register_response.json()["user"]
        assert initial_user["can_edit_matches"] == False
        
        # Admin grants edit access
        grant_response = admin_client.post(f"{base_url}/api/users/grant-edit", json={
            "user_id": user_id,
            "can_edit_matches": True
        })
        assert grant_response.status_code == 200, f"Expected 200, got {grant_response.status_code}: {grant_response.text}"
        
        granted_user = grant_response.json()
        assert granted_user["can_edit_matches"] == True
        assert "_id" not in granted_user
        
        # Verify persistence
        me_response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert me_response.status_code == 200
        assert me_response.json()["can_edit_matches"] == True
        
        # Admin revokes edit access
        revoke_response = admin_client.post(f"{base_url}/api/users/grant-edit", json={
            "user_id": user_id,
            "can_edit_matches": False
        })
        assert revoke_response.status_code == 200
        assert revoke_response.json()["can_edit_matches"] == False

    def test_non_admin_cannot_grant_edit_access_403(self, base_url, api_client, test_run_id):
        """Non-admin user cannot grant edit access (403)"""
        # Register two regular users
        user1_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_regular1_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Regular User 1"
        })
        assert user1_response.status_code == 200
        user1_token = user1_response.json()["token"]
        
        user2_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_regular2_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Regular User 2"
        })
        assert user2_response.status_code == 200
        user2_id = user2_response.json()["user"]["id"]
        
        # User1 tries to grant edit access to User2
        grant_response = api_client.post(
            f"{base_url}/api/users/grant-edit",
            headers={"Authorization": f"Bearer {user1_token}"},
            json={
                "user_id": user2_id,
                "can_edit_matches": True
            }
        )
        assert grant_response.status_code == 403, f"Expected 403, got {grant_response.status_code}"
