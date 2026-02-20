"""Rate limiting for API endpoints and request throttling."""

import logging
import threading
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from collections import deque


class RateLimitStrategy(str, Enum):
    """Rate limiting strategies."""
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_second: float
    burst_size: int
    strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    retry_after: float = 0.0
    remaining: int = 0
    limit: int = 0
    reset_time: Optional[datetime] = None


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter.
    
    Allows bursts up to bucket capacity while maintaining average rate.
    """
    
    def __init__(
        self,
        rate: float,
        capacity: int
    ):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.time()
        self.lock = threading.Lock()
    
    def allow_request(self, tokens: int = 1) -> Tuple[bool, float]:
        """
        Check if request is allowed.
        
        Args:
            tokens: Number of tokens to consume
        
        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        with self.lock:
            now = time.time()
            
            # Add tokens based on time elapsed
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            # Check if enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0
            else:
                # Calculate retry after
                tokens_needed = tokens - self.tokens
                retry_after = tokens_needed / self.rate
                return False, retry_after
    
    def get_remaining(self) -> int:
        """Get remaining tokens."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            return int(tokens)


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter.
    
    Tracks requests in a sliding time window.
    """
    
    def __init__(
        self,
        max_requests: int,
        window_seconds: int
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()
        self.lock = threading.Lock()
    
    def allow_request(self) -> Tuple[bool, float]:
        """
        Check if request is allowed.
        
        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        with self.lock:
            now = time.time()
            cutoff = now - self.window_seconds
            
            # Remove old requests
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()
            
            # Check if under limit
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True, 0.0
            else:
                # Calculate retry after
                oldest = self.requests[0]
                retry_after = oldest + self.window_seconds - now
                return False, max(0.0, retry_after)
    
    def get_remaining(self) -> int:
        """Get remaining requests in window."""
        with self.lock:
            now = time.time()
            cutoff = now - self.window_seconds
            
            # Remove old requests
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()
            
            return self.max_requests - len(self.requests)


class RateLimiter:
    """
    Multi-strategy rate limiter with per-client tracking.
    
    Features:
    - Multiple rate limiting strategies
    - Per-client rate limits
    - Global rate limits
    - Statistics tracking
    """
    
    def __init__(
        self,
        default_config: RateLimitConfig,
        enable_global_limit: bool = True,
        global_requests_per_second: float = 1000.0,
        global_burst_size: int = 2000
    ):
        self.logger = logging.getLogger("RateLimiter")
        self.default_config = default_config
        self.enable_global_limit = enable_global_limit
        
        # Per-client limiters
        self.client_limiters: Dict[str, any] = {}
        self.client_lock = threading.RLock()
        
        # Global limiter
        if enable_global_limit:
            self.global_limiter = TokenBucketRateLimiter(
                rate=global_requests_per_second,
                capacity=global_burst_size
            )
        else:
            self.global_limiter = None
        
        # Statistics
        self.stats = {
            "total_requests": 0,
            "allowed_requests": 0,
            "rejected_requests": 0,
            "unique_clients": 0,
            "global_rejections": 0
        }
        
        self.logger.info(
            f"RateLimiter initialized: strategy={default_config.strategy}, "
            f"rate={default_config.requests_per_second}/s"
        )
    
    def _get_or_create_limiter(self, client_id: str, config: Optional[RateLimitConfig] = None):
        """Get or create rate limiter for client."""
        with self.client_lock:
            if client_id not in self.client_limiters:
                cfg = config or self.default_config
                
                if cfg.strategy == RateLimitStrategy.TOKEN_BUCKET:
                    limiter = TokenBucketRateLimiter(
                        rate=cfg.requests_per_second,
                        capacity=cfg.burst_size
                    )
                elif cfg.strategy == RateLimitStrategy.SLIDING_WINDOW:
                    limiter = SlidingWindowRateLimiter(
                        max_requests=int(cfg.requests_per_second),
                        window_seconds=1
                    )
                else:
                    # Default to token bucket
                    limiter = TokenBucketRateLimiter(
                        rate=cfg.requests_per_second,
                        capacity=cfg.burst_size
                    )
                
                self.client_limiters[client_id] = limiter
                self.stats["unique_clients"] = len(self.client_limiters)
            
            return self.client_limiters[client_id]
    
    def check_rate_limit(
        self,
        client_id: str,
        tokens: int = 1,
        config: Optional[RateLimitConfig] = None
    ) -> RateLimitResult:
        """
        Check if request is allowed for client.
        
        Args:
            client_id: Client identifier
            tokens: Number of tokens to consume
            config: Optional custom config for this client
        
        Returns:
            RateLimitResult with decision and metadata
        """
        self.stats["total_requests"] += 1
        
        # Check global limit first
        if self.global_limiter:
            global_allowed, global_retry = self.global_limiter.allow_request(tokens)
            
            if not global_allowed:
                self.stats["rejected_requests"] += 1
                self.stats["global_rejections"] += 1
                
                return RateLimitResult(
                    allowed=False,
                    retry_after=global_retry,
                    remaining=0,
                    limit=0
                )
        
        # Check client limit
        limiter = self._get_or_create_limiter(client_id, config)
        allowed, retry_after = limiter.allow_request(tokens)
        
        if allowed:
            self.stats["allowed_requests"] += 1
        else:
            self.stats["rejected_requests"] += 1
        
        # Get remaining capacity
        remaining = limiter.get_remaining()
        
        # Calculate reset time
        reset_time = None
        if not allowed and retry_after > 0:
            reset_time = datetime.now() + timedelta(seconds=retry_after)
        
        return RateLimitResult(
            allowed=allowed,
            retry_after=retry_after,
            remaining=remaining,
            limit=self.default_config.burst_size,
            reset_time=reset_time
        )
    
    def set_client_config(self, client_id: str, config: RateLimitConfig):
        """Set custom rate limit config for a client."""
        with self.client_lock:
            # Remove existing limiter if any
            if client_id in self.client_limiters:
                del self.client_limiters[client_id]
            
            # Create new limiter with custom config
            self._get_or_create_limiter(client_id, config)
        
        self.logger.info(f"Set custom rate limit for client {client_id}")
    
    def remove_client(self, client_id: str):
        """Remove client from rate limiter."""
        with self.client_lock:
            if client_id in self.client_limiters:
                del self.client_limiters[client_id]
                self.stats["unique_clients"] = len(self.client_limiters)
                
                self.logger.debug(f"Removed client {client_id}")
    
    def get_client_stats(self, client_id: str) -> Optional[Dict[str, any]]:
        """Get statistics for a specific client."""
        with self.client_lock:
            if client_id not in self.client_limiters:
                return None
            
            limiter = self.client_limiters[client_id]
            
            return {
                "client_id": client_id,
                "remaining": limiter.get_remaining(),
                "limit": self.default_config.burst_size
            }
    
    def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics."""
        rejection_rate = 0.0
        if self.stats["total_requests"] > 0:
            rejection_rate = (
                self.stats["rejected_requests"] / self.stats["total_requests"] * 100
            )
        
        return {
            **self.stats,
            "rejection_rate": rejection_rate,
            "global_limit_enabled": self.enable_global_limit
        }
    
    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            "total_requests": 0,
            "allowed_requests": 0,
            "rejected_requests": 0,
            "unique_clients": len(self.client_limiters),
            "global_rejections": 0
        }
        
        self.logger.info("Reset rate limiter statistics")


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(
    default_config: Optional[RateLimitConfig] = None,
    **kwargs
) -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _rate_limiter
    
    if _rate_limiter is None:
        if default_config is None:
            default_config = RateLimitConfig(
                requests_per_second=100.0,
                burst_size=200,
                strategy=RateLimitStrategy.TOKEN_BUCKET
            )
        
        _rate_limiter = RateLimiter(default_config, **kwargs)
    
    return _rate_limiter
