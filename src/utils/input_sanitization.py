"""Input sanitization and security module.

This module provides:
- Input validation and sanitization
- Security checks for malicious inputs
- Rate limiting and abuse prevention
- SQL injection prevention
- XSS prevention
- Command injection prevention
"""

import re
import html
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import hashlib
import asyncio


logger = logging.getLogger(__name__)


class ThreatLevel(Enum):
    """Threat level classification."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AttackType(Enum):
    """Types of potential attacks."""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    COMMAND_INJECTION = "command_injection"
    PATH_TRAVERSAL = "path_traversal"
    SCRIPT_INJECTION = "script_injection"
    BUFFER_OVERFLOW = "buffer_overflow"
    MALFORMED_INPUT = "malformed_input"
    EXCESSIVE_LENGTH = "excessive_length"
    INVALID_CHARACTERS = "invalid_characters"
    RATE_LIMIT_VIOLATION = "rate_limit_violation"


@dataclass
class SecurityViolation:
    """Represents a security violation detected in input."""
    attack_type: AttackType
    threat_level: ThreatLevel
    description: str
    detected_pattern: str
    timestamp: datetime = field(default_factory=datetime.now)
    source_ip: Optional[str] = None
    user_id: Optional[str] = None
    blocked: bool = False


@dataclass
class SanitizationResult:
    """Result of input sanitization."""
    original_input: str
    sanitized_input: str
    is_safe: bool
    violations: List[SecurityViolation] = field(default_factory=list)
    modifications_made: List[str] = field(default_factory=list)
    threat_level: ThreatLevel = ThreatLevel.SAFE


class InputSanitizer:
    """Sanitizes and validates user inputs for security threats."""
    
    # Dangerous patterns to detect
    SQL_INJECTION_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bSELECT\b.*\bFROM\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bUPDATE\b.*\bSET\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(--\s*$)",
        r"(;\s*DROP\b)",
        r"(\bOR\b\s+\d+\s*=\s*\d+)",
        r"(\bAND\b\s+\d+\s*=\s*\d+)",
        r"('.*OR.*'.*=.*')",
    ]
    
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
        r"<object[^>]*>",
        r"<embed[^>]*>",
        r"<img[^>]*onerror",
        r"<svg[^>]*onload",
    ]
    
    COMMAND_INJECTION_PATTERNS = [
        r"[;&|`$()]",
        r"\$\(.*\)",
        r"`.*`",
        r"&&",
        r"\|\|",
        r">\s*/dev/",
    ]
    
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.",
        r"~\/",
        r"/etc/",
        r"/proc/",
        r"/sys/",
        r"C:\\",
        r"\\\\",
    ]
    
    # Allowed character sets
    ALPHANUMERIC = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    ALPHANUMERIC_EXTENDED = ALPHANUMERIC | set(" _-.,!?@")
    NETWORK_SAFE = ALPHANUMERIC | set(" _-.:/@")
    
    def __init__(
        self,
        max_length: int = 1000,
        strict_mode: bool = False,
        allow_html: bool = False
    ):
        """Initialize input sanitizer.
        
        Args:
            max_length: Maximum allowed input length
            strict_mode: If True, apply stricter validation rules
            allow_html: If True, allow safe HTML tags
        """
        self.max_length = max_length
        self.strict_mode = strict_mode
        self.allow_html = allow_html
        
        # Compile regex patterns for performance
        self._sql_patterns = [re.compile(p, re.IGNORECASE) for p in self.SQL_INJECTION_PATTERNS]
        self._xss_patterns = [re.compile(p, re.IGNORECASE) for p in self.XSS_PATTERNS]
        self._cmd_patterns = [re.compile(p) for p in self.COMMAND_INJECTION_PATTERNS]
        self._path_patterns = [re.compile(p) for p in self.PATH_TRAVERSAL_PATTERNS]
        
        logger.info(
            f"Input sanitizer initialized: max_length={max_length}, "
            f"strict_mode={strict_mode}, allow_html={allow_html}"
        )
    
    def sanitize(
        self,
        input_text: str,
        context: str = "general",
        user_id: Optional[str] = None,
        source_ip: Optional[str] = None
    ) -> SanitizationResult:
        """Sanitize input text and detect security threats.
        
        Args:
            input_text: Text to sanitize
            context: Context of the input (e.g., 'intent', 'query', 'config')
            user_id: Optional user identifier
            source_ip: Optional source IP address
            
        Returns:
            SanitizationResult with sanitized text and threat analysis
        """
        if not isinstance(input_text, str):
            return SanitizationResult(
                original_input=str(input_text),
                sanitized_input="",
                is_safe=False,
                violations=[SecurityViolation(
                    attack_type=AttackType.MALFORMED_INPUT,
                    threat_level=ThreatLevel.HIGH,
                    description="Input is not a string",
                    detected_pattern=str(type(input_text)),
                    user_id=user_id,
                    source_ip=source_ip,
                    blocked=True
                )],
                threat_level=ThreatLevel.HIGH
            )
        
        violations: List[SecurityViolation] = []
        modifications: List[str] = []
        sanitized = input_text
        
        # Check length
        if len(input_text) > self.max_length:
            violations.append(SecurityViolation(
                attack_type=AttackType.EXCESSIVE_LENGTH,
                threat_level=ThreatLevel.MEDIUM,
                description=f"Input exceeds maximum length of {self.max_length}",
                detected_pattern=f"Length: {len(input_text)}",
                user_id=user_id,
                source_ip=source_ip,
                blocked=True
            ))
            sanitized = sanitized[:self.max_length]
            modifications.append(f"Truncated to {self.max_length} characters")
        
        # Check for SQL injection
        sql_violations = self._detect_sql_injection(sanitized, user_id, source_ip)
        violations.extend(sql_violations)
        
        # Check for XSS
        xss_violations = self._detect_xss(sanitized, user_id, source_ip)
        violations.extend(xss_violations)
        
        # Check for command injection
        cmd_violations = self._detect_command_injection(sanitized, user_id, source_ip)
        violations.extend(cmd_violations)
        
        # Check for path traversal
        path_violations = self._detect_path_traversal(sanitized, user_id, source_ip)
        violations.extend(path_violations)
        
        # Remove null bytes
        if '\x00' in sanitized:
            sanitized = sanitized.replace('\x00', '')
            modifications.append("Removed null bytes")
        
        # Apply sanitization based on context
        if context == "intent":
            sanitized = self._sanitize_intent(sanitized)
            modifications.append("Applied intent-specific sanitization")
        elif context == "query":
            sanitized = self._sanitize_query(sanitized)
            modifications.append("Applied query-specific sanitization")
        elif context == "config":
            sanitized = self._sanitize_config(sanitized)
            modifications.append("Applied config-specific sanitization")
        else:
            sanitized = self._sanitize_general(sanitized)
            modifications.append("Applied general sanitization")
        
        # Normalize whitespace
        sanitized = ' '.join(sanitized.split())
        if sanitized != input_text.strip():
            modifications.append("Normalized whitespace")
        
        # Determine overall threat level
        threat_level = self._calculate_threat_level(violations)
        
        # Determine if input is safe
        is_safe = threat_level in [ThreatLevel.SAFE, ThreatLevel.LOW]
        
        # Log security violations
        if violations:
            logger.warning(
                f"Security violations detected: {len(violations)} violations, "
                f"threat_level={threat_level.value}, user_id={user_id}, "
                f"source_ip={source_ip}"
            )
            for violation in violations:
                logger.debug(
                    f"Violation: {violation.attack_type.value} - {violation.description}"
                )
        
        return SanitizationResult(
            original_input=input_text,
            sanitized_input=sanitized,
            is_safe=is_safe,
            violations=violations,
            modifications_made=modifications,
            threat_level=threat_level
        )
    
    def _detect_sql_injection(
        self,
        text: str,
        user_id: Optional[str],
        source_ip: Optional[str]
    ) -> List[SecurityViolation]:
        """Detect SQL injection patterns."""
        violations = []
        
        for pattern in self._sql_patterns:
            matches = pattern.findall(text)
            if matches:
                violations.append(SecurityViolation(
                    attack_type=AttackType.SQL_INJECTION,
                    threat_level=ThreatLevel.CRITICAL,
                    description="Potential SQL injection detected",
                    detected_pattern=str(matches[0]) if matches else "",
                    user_id=user_id,
                    source_ip=source_ip,
                    blocked=True
                ))
        
        return violations
    
    def _detect_xss(
        self,
        text: str,
        user_id: Optional[str],
        source_ip: Optional[str]
    ) -> List[SecurityViolation]:
        """Detect XSS patterns."""
        violations = []
        
        for pattern in self._xss_patterns:
            matches = pattern.findall(text)
            if matches:
                violations.append(SecurityViolation(
                    attack_type=AttackType.XSS,
                    threat_level=ThreatLevel.HIGH,
                    description="Potential XSS attack detected",
                    detected_pattern=str(matches[0]) if matches else "",
                    user_id=user_id,
                    source_ip=source_ip,
                    blocked=True
                ))
        
        return violations
    
    def _detect_command_injection(
        self,
        text: str,
        user_id: Optional[str],
        source_ip: Optional[str]
    ) -> List[SecurityViolation]:
        """Detect command injection patterns."""
        violations = []
        
        for pattern in self._cmd_patterns:
            matches = pattern.findall(text)
            if matches:
                violations.append(SecurityViolation(
                    attack_type=AttackType.COMMAND_INJECTION,
                    threat_level=ThreatLevel.CRITICAL,
                    description="Potential command injection detected",
                    detected_pattern=str(matches[0]) if matches else "",
                    user_id=user_id,
                    source_ip=source_ip,
                    blocked=True
                ))
        
        return violations
    
    def _detect_path_traversal(
        self,
        text: str,
        user_id: Optional[str],
        source_ip: Optional[str]
    ) -> List[SecurityViolation]:
        """Detect path traversal patterns."""
        violations = []
        
        for pattern in self._path_patterns:
            matches = pattern.findall(text)
            if matches:
                violations.append(SecurityViolation(
                    attack_type=AttackType.PATH_TRAVERSAL,
                    threat_level=ThreatLevel.HIGH,
                    description="Potential path traversal detected",
                    detected_pattern=str(matches[0]) if matches else "",
                    user_id=user_id,
                    source_ip=source_ip,
                    blocked=True
                ))
        
        return violations
    
    def _sanitize_intent(self, text: str) -> str:
        """Sanitize network intent text."""
        # Allow network-specific characters
        sanitized = ''.join(c for c in text if c in self.NETWORK_SAFE or c.isspace())
        return sanitized.strip()
    
    def _sanitize_query(self, text: str) -> str:
        """Sanitize query text."""
        # More restrictive for queries
        sanitized = ''.join(c for c in text if c in self.ALPHANUMERIC_EXTENDED or c.isspace())
        return sanitized.strip()
    
    def _sanitize_config(self, text: str) -> str:
        """Sanitize configuration text."""
        # Very restrictive for config
        sanitized = ''.join(c for c in text if c in self.ALPHANUMERIC or c in "._-")
        return sanitized.strip()
    
    def _sanitize_general(self, text: str) -> str:
        """General sanitization."""
        # Escape HTML if not allowed
        if not self.allow_html:
            text = html.escape(text)
        
        # Remove control characters except newline and tab
        sanitized = ''.join(c for c in text if c.isprintable() or c in '\n\t')
        return sanitized.strip()
    
    def _calculate_threat_level(self, violations: List[SecurityViolation]) -> ThreatLevel:
        """Calculate overall threat level from violations."""
        if not violations:
            return ThreatLevel.SAFE
        
        # Get highest threat level
        threat_levels = [v.threat_level for v in violations]
        
        if ThreatLevel.CRITICAL in threat_levels:
            return ThreatLevel.CRITICAL
        elif ThreatLevel.HIGH in threat_levels:
            return ThreatLevel.HIGH
        elif ThreatLevel.MEDIUM in threat_levels:
            return ThreatLevel.MEDIUM
        else:
            return ThreatLevel.LOW
    
    def validate_network_resource_name(self, name: str) -> bool:
        """Validate network resource name format.
        
        Args:
            name: Resource name to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not name or len(name) > 255:
            return False
        
        # Allow alphanumeric, underscore, hyphen, dot, colon
        pattern = r'^[a-zA-Z0-9_\-.:]+$'
        return bool(re.match(pattern, name))
    
    def validate_ip_address(self, ip: str) -> bool:
        """Validate IP address format.
        
        Args:
            ip: IP address to validate
            
        Returns:
            True if valid IPv4 or IPv6 address
        """
        # IPv4 pattern
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(ipv4_pattern, ip):
            parts = ip.split('.')
            return all(0 <= int(part) <= 255 for part in parts)
        
        # IPv6 pattern (more comprehensive)
        # Matches full IPv6, compressed IPv6 (::), and mixed formats
        ipv6_patterns = [
            r'^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$',  # Full format
            r'^::([0-9a-fA-F]{1,4}:){0,6}[0-9a-fA-F]{1,4}$',  # Compressed start
            r'^([0-9a-fA-F]{1,4}:){1,7}:$',  # Compressed end
            r'^([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}$',  # Compressed middle
            r'^::$',  # All zeros
            r'^::1$',  # Loopback
        ]
        
        for pattern in ipv6_patterns:
            if re.match(pattern, ip):
                return True
        
        return False


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10
    block_duration_minutes: int = 15


@dataclass
class RateLimitEntry:
    """Entry for tracking rate limit per client."""
    client_id: str
    request_timestamps: deque = field(default_factory=lambda: deque(maxlen=10000))
    blocked_until: Optional[datetime] = None
    total_requests: int = 0
    blocked_count: int = 0


class RateLimiter:
    """Rate limiter for abuse prevention."""
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """Initialize rate limiter.
        
        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()
        self._clients: Dict[str, RateLimitEntry] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        
        logger.info(
            f"Rate limiter initialized: "
            f"{self.config.requests_per_minute} req/min, "
            f"{self.config.requests_per_hour} req/hour"
        )
    
    async def check_rate_limit(
        self,
        client_id: str,
        user_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Check if client is within rate limits.
        
        Args:
            client_id: Client identifier (IP address or user ID)
            user_id: Optional user identifier for logging
            
        Returns:
            Tuple of (is_allowed, reason_if_blocked)
        """
        async with self._lock:
            now = datetime.now()
            
            # Get or create client entry
            if client_id not in self._clients:
                self._clients[client_id] = RateLimitEntry(client_id=client_id)
            
            entry = self._clients[client_id]
            entry.total_requests += 1
            
            # Check if client is blocked
            if entry.blocked_until and now < entry.blocked_until:
                remaining = (entry.blocked_until - now).total_seconds()
                reason = f"Rate limit exceeded. Blocked for {remaining:.0f} more seconds"
                logger.warning(
                    f"Rate limit block active for {client_id}: {reason}",
                    extra={"client_id": client_id, "user_id": user_id}
                )
                return False, reason
            
            # Clear block if expired
            if entry.blocked_until and now >= entry.blocked_until:
                entry.blocked_until = None
                logger.info(f"Rate limit block expired for {client_id}")
            
            # Add current request timestamp
            entry.request_timestamps.append(now)
            
            # Check per-minute limit
            one_minute_ago = now - timedelta(minutes=1)
            recent_requests = sum(
                1 for ts in entry.request_timestamps
                if ts > one_minute_ago
            )
            
            if recent_requests > self.config.requests_per_minute:
                entry.blocked_until = now + timedelta(minutes=self.config.block_duration_minutes)
                entry.blocked_count += 1
                reason = (
                    f"Exceeded {self.config.requests_per_minute} requests per minute. "
                    f"Blocked for {self.config.block_duration_minutes} minutes"
                )
                logger.error(
                    f"Rate limit exceeded for {client_id}: {reason}",
                    extra={
                        "client_id": client_id,
                        "user_id": user_id,
                        "requests_per_minute": recent_requests,
                        "blocked_count": entry.blocked_count
                    }
                )
                return False, reason
            
            # Check per-hour limit
            one_hour_ago = now - timedelta(hours=1)
            hourly_requests = sum(
                1 for ts in entry.request_timestamps
                if ts > one_hour_ago
            )
            
            if hourly_requests > self.config.requests_per_hour:
                entry.blocked_until = now + timedelta(minutes=self.config.block_duration_minutes)
                entry.blocked_count += 1
                reason = (
                    f"Exceeded {self.config.requests_per_hour} requests per hour. "
                    f"Blocked for {self.config.block_duration_minutes} minutes"
                )
                logger.error(
                    f"Rate limit exceeded for {client_id}: {reason}",
                    extra={
                        "client_id": client_id,
                        "user_id": user_id,
                        "requests_per_hour": hourly_requests,
                        "blocked_count": entry.blocked_count
                    }
                )
                return False, reason
            
            # Check burst limit
            ten_seconds_ago = now - timedelta(seconds=10)
            burst_requests = sum(
                1 for ts in entry.request_timestamps
                if ts > ten_seconds_ago
            )
            
            if burst_requests > self.config.burst_size:
                entry.blocked_until = now + timedelta(minutes=5)
                entry.blocked_count += 1
                reason = (
                    f"Exceeded burst limit of {self.config.burst_size} requests in 10 seconds. "
                    f"Blocked for 5 minutes"
                )
                logger.error(
                    f"Burst limit exceeded for {client_id}: {reason}",
                    extra={
                        "client_id": client_id,
                        "user_id": user_id,
                        "burst_requests": burst_requests,
                        "blocked_count": entry.blocked_count
                    }
                )
                return False, reason
            
            return True, None
    
    async def reset_client(self, client_id: str) -> None:
        """Reset rate limit for a client.
        
        Args:
            client_id: Client identifier
        """
        async with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]
                logger.info(f"Rate limit reset for {client_id}")
    
    async def get_client_stats(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get rate limit statistics for a client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            Dictionary with client statistics or None
        """
        async with self._lock:
            if client_id not in self._clients:
                return None
            
            entry = self._clients[client_id]
            now = datetime.now()
            
            one_minute_ago = now - timedelta(minutes=1)
            one_hour_ago = now - timedelta(hours=1)
            
            return {
                "client_id": client_id,
                "total_requests": entry.total_requests,
                "blocked_count": entry.blocked_count,
                "is_blocked": entry.blocked_until is not None and now < entry.blocked_until,
                "blocked_until": entry.blocked_until,
                "requests_last_minute": sum(
                    1 for ts in entry.request_timestamps if ts > one_minute_ago
                ),
                "requests_last_hour": sum(
                    1 for ts in entry.request_timestamps if ts > one_hour_ago
                ),
            }
    
    async def cleanup_old_entries(self) -> None:
        """Clean up old rate limit entries."""
        async with self._lock:
            now = datetime.now()
            one_day_ago = now - timedelta(days=1)
            
            # Remove entries with no recent activity
            to_remove = []
            for client_id, entry in self._clients.items():
                if entry.request_timestamps:
                    last_request = entry.request_timestamps[-1]
                    if last_request < one_day_ago:
                        to_remove.append(client_id)
            
            for client_id in to_remove:
                del self._clients[client_id]
            
            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} old rate limit entries")
    
    async def start_cleanup_task(self, interval_hours: int = 1) -> None:
        """Start periodic cleanup task.
        
        Args:
            interval_hours: Cleanup interval in hours
        """
        async def cleanup_loop():
            while True:
                await asyncio.sleep(interval_hours * 3600)
                await self.cleanup_old_entries()
        
        self._cleanup_task = asyncio.create_task(cleanup_loop())
        logger.info(f"Started rate limiter cleanup task (interval: {interval_hours}h)")
    
    async def stop_cleanup_task(self) -> None:
        """Stop periodic cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped rate limiter cleanup task")


# Global instances
_input_sanitizer: Optional[InputSanitizer] = None
_rate_limiter: Optional[RateLimiter] = None


def get_input_sanitizer(
    max_length: int = 1000,
    strict_mode: bool = False,
    allow_html: bool = False
) -> InputSanitizer:
    """Get or create global input sanitizer instance.
    
    Args:
        max_length: Maximum allowed input length
        strict_mode: If True, apply stricter validation rules
        allow_html: If True, allow safe HTML tags
        
    Returns:
        InputSanitizer instance
    """
    global _input_sanitizer
    if _input_sanitizer is None:
        _input_sanitizer = InputSanitizer(
            max_length=max_length,
            strict_mode=strict_mode,
            allow_html=allow_html
        )
    return _input_sanitizer


def get_rate_limiter(config: Optional[RateLimitConfig] = None) -> RateLimiter:
    """Get or create global rate limiter instance.
    
    Args:
        config: Rate limit configuration
        
    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(config)
    return _rate_limiter
