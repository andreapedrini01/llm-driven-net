"""Quick test to verify the server starts correctly."""

import sys
import time
import subprocess
import requests
from pathlib import Path

def test_import():
    """Test that the main module can be imported."""
    try:
        print("Testing module import...")
        import src.main
        print("✓ Module imported successfully")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False

def test_app_creation():
    """Test that the FastAPI app can be created."""
    try:
        print("\nTesting app creation...")
        from src.main import create_app
        app = create_app()
        print(f"✓ App created successfully: {app.title}")
        return True
    except Exception as e:
        print(f"✗ App creation failed: {e}")
        return False

def test_health_endpoint():
    """Test that health endpoint is accessible."""
    try:
        print("\nTesting health endpoint...")
        from src.main import create_app
        from fastapi.testclient import TestClient
        
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        
        if response.status_code == 200:
            print(f"✓ Health endpoint working: {response.json()}")
            return True
        else:
            print(f"✗ Health endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Health endpoint test failed: {e}")
        return False

def test_server_startup():
    """Test that the server actually starts and responds to requests."""
    server_process = None
    try:
        print("\nTesting actual server startup...")
        
        # Start the server in a subprocess
        print("  Starting server process...")
        server_process = subprocess.Popen(
            [sys.executable, "-m", "src.main"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start (max 10 seconds)
        print("  Waiting for server to be ready...")
        max_attempts = 10
        for attempt in range(max_attempts):
            time.sleep(0.5)
            try:
                response = requests.get("http://localhost:8000/health", timeout=2)
                if response.status_code == 200:
                    print(f"✓ Server started and responding: {response.json()}")
                    return True
            except requests.exceptions.ConnectionError:
                # Server not ready yet
                continue
            except Exception as e:
                print(f"  Attempt {attempt + 1}/{max_attempts}: {e}")
                continue
        
        print(f"✗ Server did not respond after {max_attempts * 0.5} seconds")
        return False
        
    except Exception as e:
        print(f"✗ Server startup test failed: {e}")
        return False
    finally:
        # Clean up: terminate the server process
        if server_process:
            print("  Shutting down server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server_process.kill()
            print("  Server stopped")

def main():
    """Run all tests."""
    print("=" * 60)
    print("LLM Integration Module - Server Startup Test")
    print("=" * 60)
    
    server_process = None
    
    try:
        # Start the server first
        print("\n🚀 Starting server...")
        server_process = subprocess.Popen(
            [sys.executable, "-m", "src.main"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to be ready
        print("⏳ Waiting for server to be ready...")
        server_ready = False
        max_attempts = 20
        
        for attempt in range(max_attempts):
            time.sleep(0.5)
            try:
                response = requests.get("http://localhost:8000/health", timeout=2)
                if response.status_code == 200:
                    server_ready = True
                    print(f"✓ Server is ready and responding!")
                    break
            except requests.exceptions.ConnectionError:
                continue
            except Exception:
                continue
        
        if not server_ready:
            print(f"✗ Server did not start within {max_attempts * 0.5} seconds")
            return 1
        
        # Test connection 3 times to confirm stability
        print("\n🔄 Testing server stability (3 consecutive requests)...")
        consecutive_successes = 0
        
        for test_num in range(1, 4):
            try:
                response = requests.get("http://localhost:8000/health", timeout=2)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        consecutive_successes += 1
                        print(f"  Test {test_num}/3: ✓ Success - {data}")
                    except ValueError:
                        print(f"  Test {test_num}/3: ✓ Status 200 but response is: {response.text[:100]}")
                        consecutive_successes += 1
                else:
                    print(f"  Test {test_num}/3: ✗ Failed with status {response.status_code}")
                    break
            except Exception as e:
                print(f"  Test {test_num}/3: ✗ Failed - {e}")
                break
            time.sleep(0.3)
        
        if consecutive_successes == 3:
            print("\n✅ Server is stable and working correctly!")
        else:
            print(f"\n⚠️  Server stability test failed ({consecutive_successes}/3 successful)")
            return 1
        
        # Now run the other tests
        print("\n" + "=" * 60)
        print("Running Additional Tests")
        print("=" * 60)
        
        results = []
        
        # Test 1: Import
        results.append(("Import", test_import()))
        
        # Test 2: App Creation
        results.append(("App Creation", test_app_creation()))
        
        # Test 3: Health Endpoint
        results.append(("Health Endpoint", test_health_endpoint()))
        
        # Summary
        print("\n" + "=" * 60)
        print("Test Summary:")
        print("=" * 60)
        
        print("✓ PASS: Server Startup")
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for name, result in results:
            status = "✓ PASS" if result else "✗ FAIL"
            print(f"{status}: {name}")
        
        print(f"\nTotal: {passed + 1}/{total + 1} tests passed")
        
        if passed == total:
            print("\n🎉 All tests passed! Server is working correctly.")
            return 0
        else:
            print("\n⚠️  Some tests failed. Check the errors above.")
            return 1
            
    except Exception as e:
        print(f"\n✗ Error during testing: {e}")
        return 1
    finally:
        # Always shut down the server
        if server_process:
            print("\n🛑 Shutting down server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
                print("✓ Server stopped successfully")
            except subprocess.TimeoutExpired:
                server_process.kill()
                print("✓ Server forcefully stopped")

if __name__ == "__main__":
    sys.exit(main())
