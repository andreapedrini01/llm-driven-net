"""Integration tests for security middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.security_middleware import (
    RateLimitMiddleware,
    InputSanitizationMiddleware,
    SecurityHeadersMiddleware,
    setup_security_middleware
)
from src.utils.input_sanitization import RateLimitConfig


@pytest.fixture
def app():
    """Create test FastAPI app."""
    app = FastAPI()
    
    @app.get("/test")
    async def test_endpoint():
        return {"message": "success"}
    
    @app.post("/submit")
    async def submit_endpoint(data: dict):
        return {"received": data}
    
    @app.get("/health")
    async def health_endpoint():
        return {"status": "healthy"}
    
    return app


@pytest.fixture
def client_with_rate_limit(app):
    """Create test client with rate limiting."""
    # Reset global rate limiter
    import src.utils.input_sanitization as sanitization_module
    sanitization_module._rate_limiter = None
    
    config = RateLimitConfig(
        requests_per_minute=10,  # Increased to avoid burst limit
        burst_size=10
    )
    app.add_middleware(RateLimitMiddleware, config=config)
    return TestClient(app)


@pytest.fixture
def client_with_sanitization(app):
    """Create test client with input sanitization."""
    app.add_middleware(InputSanitizationMiddleware, max_length=100)
    return TestClient(app)


@pytest.fixture
def client_with_security_headers(app):
    """Create test client with security headers."""
    app.add_middleware(SecurityHeadersMiddleware)
    return TestClient(app)


@pytest.fixture
def client_with_all_security(app):
    """Create test client with all security middleware."""
    # Reset global instances
    import src.utils.input_sanitization as sanitization_module
    sanitization_module._rate_limiter = None
    sanitization_module._input_sanitizer = None
    
    setup_security_middleware(app)
    return TestClient(app)


class TestRateLimitMiddleware:
    """Test rate limit middleware."""
    
    def test_allows_normal_requests(self, client_with_rate_limit):
        """Test that normal requests are allowed."""
        response = client_with_rate_limit.get("/test")
        assert response.status_code == 200
        assert response.json() == {"message": "success"}
    
    def test_blocks_excessive_requests(self, client_with_rate_limit):
        """Test that excessive requests are blocked."""
        # Make requests up to limit
        for i in range(10):
            response = client_with_rate_limit.get("/test")
            assert response.status_code == 200
        
        # Next request should be blocked
        response = client_with_rate_limit.get("/test")
        assert response.status_code == 429
        assert "rate_limit_exceeded" in response.json()["error"]
    
    def test_adds_rate_limit_headers(self, client_with_rate_limit):
        """Test that rate limit headers are added."""
        response = client_with_rate_limit.get("/test")
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
    
    def test_skips_health_checks(self, client_with_rate_limit):
        """Test that health checks are not rate limited."""
        # Make many health check requests
        for i in range(20):
            response = client_with_rate_limit.get("/health")
            assert response.status_code == 200


class TestInputSanitizationMiddleware:
    """Test input sanitization middleware."""
    
    def test_allows_safe_input(self, client_with_sanitization):
        """Test that safe input is allowed."""
        response = client_with_sanitization.post(
            "/submit",
            json={"text": "Configure bandwidth for switch1"}
        )
        assert response.status_code == 200
    
    def test_blocks_sql_injection(self, client_with_sanitization):
        """Test that SQL injection is blocked."""
        response = client_with_sanitization.post(
            "/submit",
            json={"text": "SELECT * FROM users WHERE id=1"}
        )
        assert response.status_code == 400
        assert "security_violation" in response.json()["error"]
    
    def test_blocks_xss(self, client_with_sanitization):
        """Test that XSS is blocked."""
        response = client_with_sanitization.post(
            "/submit",
            json={"text": "<script>alert('XSS')</script>"}
        )
        assert response.status_code == 400
        assert "security_violation" in response.json()["error"]
    
    def test_blocks_command_injection(self, client_with_sanitization):
        """Test that command injection is blocked."""
        response = client_with_sanitization.post(
            "/submit",
            json={"text": "test; rm -rf /"}
        )
        assert response.status_code == 400
        assert "security_violation" in response.json()["error"]
    
    def test_handles_invalid_json(self, client_with_sanitization):
        """Test handling of invalid JSON."""
        response = client_with_sanitization.post(
            "/submit",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 400
        assert "invalid_json" in response.json()["error"]
    
    def test_skips_get_requests(self, client_with_sanitization):
        """Test that GET requests are not sanitized."""
        response = client_with_sanitization.get("/test")
        assert response.status_code == 200
    
    def test_skips_health_checks(self, client_with_sanitization):
        """Test that health checks are not sanitized."""
        response = client_with_sanitization.get("/health")
        assert response.status_code == 200


class TestSecurityHeadersMiddleware:
    """Test security headers middleware."""
    
    def test_adds_security_headers(self, client_with_security_headers):
        """Test that security headers are added."""
        response = client_with_security_headers.get("/test")
        
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        
        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        
        assert "X-XSS-Protection" in response.headers
        assert "Strict-Transport-Security" in response.headers
        assert "Content-Security-Policy" in response.headers


class TestFullSecurityStack:
    """Test all security middleware together."""
    
    def test_all_security_features(self, client_with_all_security):
        """Test that all security features work together."""
        # Make a safe request
        response = client_with_all_security.get("/test")
        
        # Should succeed
        assert response.status_code == 200
        
        # Should have security headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-RateLimit-Limit" in response.headers
    
    def test_blocks_malicious_input_with_rate_limit(self, client_with_all_security):
        """Test that malicious input is blocked even with rate limiting."""
        response = client_with_all_security.post(
            "/submit",
            json={"text": "DROP TABLE users"}
        )
        
        # Should be blocked by sanitization
        assert response.status_code == 400
        assert "security_violation" in response.json()["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
