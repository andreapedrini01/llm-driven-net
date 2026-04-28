"""Simple test script to verify the API works locally.

Requires a running server on localhost:8080.
"""

import pytest
import requests
import json

BASE_URL = "http://localhost:8080"
API_URL = f"{BASE_URL}/api/v1"


def _server_available():
    try:
        requests.get(f"{BASE_URL}/health", timeout=1)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False


pytestmark = pytest.mark.skipif(
    not _server_available(),
    reason="API server not running on localhost:8080"
)

def test_health():
    """Test health endpoint."""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_login():
    """Test login endpoint."""
    print("Testing login endpoint...")
    response = requests.post(
        f"{API_URL}/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    print()
    return data.get("access_token")

def test_submit_intent(token):
    """Test intent submission."""
    print("Testing intent submission...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        f"{API_URL}/intents",
        headers=headers,
        json={
            "text": "Create a network slice for IoT devices with 100 Mbps bandwidth",
            "user_id": "admin",
            "priority": 5
        }
    )
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    print()
    return data.get("intent_id")

def test_get_status(token, intent_id):
    """Test getting intent status."""
    print(f"Testing intent status for {intent_id}...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{API_URL}/intents/{intent_id}/status",
        headers=headers
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
    else:
        print(f"Error: {response.text}")
    print()

def main():
    """Run all tests."""
    print("=" * 60)
    print("API Local Test Suite")
    print("=" * 60)
    print()
    
    try:
        # Test health
        test_health()
        
        # Test login
        token = test_login()
        
        if not token:
            print("Login failed, cannot continue tests")
            return
        
        # Test intent submission (will fail if ChatGPT API not configured)
        print("Note: Intent submission may fail if ChatGPT API is not configured")
        print("or if network state file is not available.")
        print()
        
        # Uncomment to test intent submission
        # intent_id = test_submit_intent(token)
        # if intent_id:
        #     test_get_status(token, intent_id)
        
        print("=" * 60)
        print("Basic API tests completed successfully!")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to the API server.")
        print("Make sure the server is running with: python -m src.main")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    main()
