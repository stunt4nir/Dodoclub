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

    # ---------- Forgot Password & Reset Password Tests ----------

    def test_forgot_password_with_existing_email_returns_dev_code(self, base_url, api_client, test_run_id):
        """POST /api/auth/forgot-password with existing email returns {ok: true, dev_code: '6-digit', message}"""
        # First register a test user
        email = f"TEST_forgot_{test_run_id}@clubdodo.com"
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": email,
            "password": "oldpass123",
            "name": "Forgot Test User"
        })
        assert register_response.status_code == 200, f"Registration failed: {register_response.text}"
        
        # Request forgot-password
        response = api_client.post(f"{base_url}/api/auth/forgot-password", json={
            "email": email
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["ok"] == True, "Response should have ok=true"
        assert "dev_code" in data, "Response missing 'dev_code' field"
        assert data["dev_code"] is not None, "dev_code should not be null for existing email"
        assert isinstance(data["dev_code"], str), "dev_code should be a string"
        assert len(data["dev_code"]) == 6, f"dev_code should be 6 digits, got {len(data['dev_code'])}"
        assert data["dev_code"].isdigit(), "dev_code should contain only digits"
        assert "message" in data, "Response missing 'message' field"

    def test_forgot_password_with_unknown_email_returns_null_code(self, base_url, api_client, test_run_id):
        """POST /api/auth/forgot-password with unknown email returns {ok: true, dev_code: null, message} (no enumeration)"""
        response = api_client.post(f"{base_url}/api/auth/forgot-password", json={
            "email": f"nonexistent_{test_run_id}@clubdodo.com"
        })
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["ok"] == True, "Response should have ok=true"
        assert "dev_code" in data, "Response missing 'dev_code' field"
        assert data["dev_code"] is None, "dev_code should be null for unknown email (no enumeration)"
        assert "message" in data, "Response missing 'message' field"

    def test_reset_password_with_correct_code_succeeds(self, base_url, api_client, test_run_id):
        """POST /api/auth/reset-password with correct email+code+new_password succeeds"""
        # Register user
        email = f"TEST_reset_{test_run_id}@clubdodo.com"
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": email,
            "password": "oldpass123",
            "name": "Reset Test User"
        })
        assert register_response.status_code == 200
        
        # Request forgot-password to get code
        forgot_response = api_client.post(f"{base_url}/api/auth/forgot-password", json={
            "email": email
        })
        assert forgot_response.status_code == 200
        code = forgot_response.json()["dev_code"]
        assert code is not None
        
        # Reset password with correct code
        reset_response = api_client.post(f"{base_url}/api/auth/reset-password", json={
            "email": email,
            "code": code,
            "new_password": "newpass123"
        })
        assert reset_response.status_code == 200, f"Expected 200, got {reset_response.status_code}: {reset_response.text}"
        
        data = reset_response.json()
        assert data["ok"] == True, "Response should have ok=true"
        assert "message" in data, "Response missing 'message' field"

    def test_reset_password_old_password_fails_new_password_works(self, base_url, api_client, test_run_id):
        """After successful reset, old password no longer works for login; new password works"""
        # Register user
        email = f"TEST_oldnew_{test_run_id}@clubdodo.com"
        old_password = "oldpass123"
        new_password = "newpass456"
        
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": email,
            "password": old_password,
            "name": "Old New Test User"
        })
        assert register_response.status_code == 200
        
        # Request forgot-password
        forgot_response = api_client.post(f"{base_url}/api/auth/forgot-password", json={
            "email": email
        })
        assert forgot_response.status_code == 200
        code = forgot_response.json()["dev_code"]
        
        # Reset password
        reset_response = api_client.post(f"{base_url}/api/auth/reset-password", json={
            "email": email,
            "code": code,
            "new_password": new_password
        })
        assert reset_response.status_code == 200
        
        # Try login with old password - should fail
        old_login_response = api_client.post(f"{base_url}/api/auth/login", json={
            "email": email,
            "password": old_password
        })
        assert old_login_response.status_code == 401, f"Old password should not work, got {old_login_response.status_code}"
        
        # Try login with new password - should succeed
        new_login_response = api_client.post(f"{base_url}/api/auth/login", json={
            "email": email,
            "password": new_password
        })
        assert new_login_response.status_code == 200, f"New password should work, got {new_login_response.status_code}: {new_login_response.text}"
        assert "token" in new_login_response.json()

    def test_reset_password_with_wrong_code_returns_400(self, base_url, api_client, test_run_id):
        """POST /api/auth/reset-password with wrong code returns 400 'Invalid code'"""
        # Register user
        email = f"TEST_wrongcode_{test_run_id}@clubdodo.com"
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": email,
            "password": "oldpass123",
            "name": "Wrong Code Test User"
        })
        assert register_response.status_code == 200
        
        # Request forgot-password
        forgot_response = api_client.post(f"{base_url}/api/auth/forgot-password", json={
            "email": email
        })
        assert forgot_response.status_code == 200
        
        # Try reset with wrong code
        reset_response = api_client.post(f"{base_url}/api/auth/reset-password", json={
            "email": email,
            "code": "999999",  # wrong code
            "new_password": "newpass123"
        })
        assert reset_response.status_code == 400, f"Expected 400, got {reset_response.status_code}"
        assert "Invalid code" in reset_response.json().get("detail", ""), "Error message should mention 'Invalid code'"

    def test_reset_password_with_used_code_returns_400(self, base_url, api_client, test_run_id):
        """POST /api/auth/reset-password with already-used code returns 400 (single-use token)"""
        # Register user
        email = f"TEST_usedcode_{test_run_id}@clubdodo.com"
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": email,
            "password": "oldpass123",
            "name": "Used Code Test User"
        })
        assert register_response.status_code == 200
        
        # Request forgot-password
        forgot_response = api_client.post(f"{base_url}/api/auth/forgot-password", json={
            "email": email
        })
        assert forgot_response.status_code == 200
        code = forgot_response.json()["dev_code"]
        
        # First reset - should succeed
        reset_response1 = api_client.post(f"{base_url}/api/auth/reset-password", json={
            "email": email,
            "code": code,
            "new_password": "newpass123"
        })
        assert reset_response1.status_code == 200
        
        # Try to use same code again - should fail
        reset_response2 = api_client.post(f"{base_url}/api/auth/reset-password", json={
            "email": email,
            "code": code,
            "new_password": "anotherpass456"
        })
        assert reset_response2.status_code == 400, f"Expected 400 for reused code, got {reset_response2.status_code}"
        # The error could be "No reset code has been requested" because the token is marked used
        error_detail = reset_response2.json().get("detail", "")
        assert "No reset code" in error_detail or "Invalid code" in error_detail, f"Unexpected error: {error_detail}"

    def test_reset_password_without_forgot_request_returns_400(self, base_url, api_client, test_run_id):
        """POST /api/auth/reset-password before any forgot-password request returns 400 'No reset code has been requested'"""
        # Register user but don't request forgot-password
        email = f"TEST_norequest_{test_run_id}@clubdodo.com"
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": email,
            "password": "oldpass123",
            "name": "No Request Test User"
        })
        assert register_response.status_code == 200
        
        # Try reset without requesting forgot-password first
        reset_response = api_client.post(f"{base_url}/api/auth/reset-password", json={
            "email": email,
            "code": "123456",
            "new_password": "newpass123"
        })
        assert reset_response.status_code == 400, f"Expected 400, got {reset_response.status_code}"
        error_detail = reset_response.json().get("detail", "")
        assert "No reset code has been requested" in error_detail, f"Expected 'No reset code has been requested', got: {error_detail}"

    def test_reset_password_validates_password_length(self, base_url, api_client, test_run_id):
        """POST /api/auth/reset-password validates password length (min 6 chars)"""
        # Register user
        email = f"TEST_shortpass_{test_run_id}@clubdodo.com"
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": email,
            "password": "oldpass123",
            "name": "Short Pass Test User"
        })
        assert register_response.status_code == 200
        
        # Request forgot-password
        forgot_response = api_client.post(f"{base_url}/api/auth/forgot-password", json={
            "email": email
        })
        assert forgot_response.status_code == 200
        code = forgot_response.json()["dev_code"]
        
        # Try reset with password < 6 chars
        reset_response = api_client.post(f"{base_url}/api/auth/reset-password", json={
            "email": email,
            "code": code,
            "new_password": "short"  # only 5 chars
        })
        assert reset_response.status_code == 422, f"Expected 422 validation error, got {reset_response.status_code}"

    def test_new_forgot_password_deletes_prior_tokens(self, base_url, api_client, test_run_id):
        """Requesting a new forgot-password code deletes prior pending tokens for that email (clean state)"""
        # Register user
        email = f"TEST_multicode_{test_run_id}@clubdodo.com"
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": email,
            "password": "oldpass123",
            "name": "Multi Code Test User"
        })
        assert register_response.status_code == 200
        
        # Request first code
        forgot_response1 = api_client.post(f"{base_url}/api/auth/forgot-password", json={
            "email": email
        })
        assert forgot_response1.status_code == 200
        code1 = forgot_response1.json()["dev_code"]
        
        # Request second code (should delete first)
        forgot_response2 = api_client.post(f"{base_url}/api/auth/forgot-password", json={
            "email": email
        })
        assert forgot_response2.status_code == 200
        code2 = forgot_response2.json()["dev_code"]
        assert code2 != code1, "Second code should be different from first"
        
        # Try to use first code - should fail (deleted)
        reset_response1 = api_client.post(f"{base_url}/api/auth/reset-password", json={
            "email": email,
            "code": code1,
            "new_password": "newpass123"
        })
        assert reset_response1.status_code == 400, f"First code should be invalid after second request, got {reset_response1.status_code}"
        
        # Use second code - should succeed
        reset_response2 = api_client.post(f"{base_url}/api/auth/reset-password", json={
            "email": email,
            "code": code2,
            "new_password": "newpass456"
        })
        assert reset_response2.status_code == 200, f"Second code should work, got {reset_response2.status_code}: {reset_response2.text}"
