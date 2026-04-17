import pytest
import requests
import os
import time

# Unique test run identifier to avoid email conflicts
TEST_RUN_ID = str(int(time.time()))

@pytest.fixture(scope="session")
def base_url():
    """Get base URL from environment"""
    url = os.environ.get('EXPO_PUBLIC_BACKEND_URL')
    if not url:
        pytest.fail("EXPO_PUBLIC_BACKEND_URL not set in environment")
    return url.rstrip('/')

@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="session")
def admin_token(base_url):
    """Get admin token for tests requiring admin access"""
    session = requests.Session()
    response = session.post(f"{base_url}/api/auth/login", json={
        "email": "admin@clubdodo.com",
        "password": "dodo2026"
    })
    if response.status_code != 200:
        pytest.fail(f"Admin login failed: {response.status_code} {response.text}")
    return response.json()["token"]

@pytest.fixture
def admin_client(api_client, admin_token):
    """API client with admin authentication"""
    api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return api_client

@pytest.fixture(scope="session")
def test_run_id():
    """Unique identifier for this test run"""
    return TEST_RUN_ID
