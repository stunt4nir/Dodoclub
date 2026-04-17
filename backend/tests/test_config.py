import pytest
import requests

class TestConfig:
    """Club configuration endpoint tests"""

    def test_get_config_public_no_auth_required(self, base_url, api_client, test_run_id):
        """GET /api/config returns club_name/club_logo (public, no auth required)"""
        response = api_client.get(f"{base_url}/api/config")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        config = response.json()
        assert "club_name" in config
        assert "club_logo" in config
        assert isinstance(config["club_name"], str), "club_name should be a string"
        assert len(config["club_name"]) > 0, "club_name should not be empty"
        assert "_id" not in config, "MongoDB _id should not be exposed"

    def test_put_config_admin_only_updates_club_name_and_logo(self, base_url, admin_client):
        """PUT /api/config (admin only) updates club_name and club_logo"""
        # Update config
        update_response = admin_client.put(f"{base_url}/api/config", json={
            "club_name": "TEST Club Updated",
            "club_logo": "data:image/png;base64,TEST_LOGO_DATA"
        })
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        
        updated_config = update_response.json()
        assert updated_config["club_name"] == "TEST Club Updated"
        assert updated_config["club_logo"] == "data:image/png;base64,TEST_LOGO_DATA"
        assert "_id" not in updated_config
        
        # Verify persistence with GET
        get_response = admin_client.get(f"{base_url}/api/config")
        assert get_response.status_code == 200
        config = get_response.json()
        assert config["club_name"] == "TEST Club Updated"
        assert config["club_logo"] == "data:image/png;base64,TEST_LOGO_DATA"
        
        # Restore original config
        restore_response = admin_client.put(f"{base_url}/api/config", json={
            "club_name": "Club Dodo",
            "club_logo": None
        })
        assert restore_response.status_code == 200

    def test_put_config_non_admin_returns_403(self, base_url, api_client, test_run_id):
        """PUT /api/config by non-admin returns 403"""
        # Register regular user
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_config_user_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Config Test User"
        })
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        
        # Try to update config
        update_response = api_client.put(
            f"{base_url}/api/config",
            headers={"Authorization": f"Bearer {token}"},
            json={"club_name": "Hacked Club"}
        )
        assert update_response.status_code == 403, f"Expected 403, got {update_response.status_code}"
