"""
Simplified Retry System with Exponential Backoff
Essential retry logic without persistent queue and circuit breaker complexity
"""

import logging
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, List, Optional
from dataclasses import dataclass, field


class RetryStrategy(str, Enum):
    """Available retry strategies."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    backoff_multiplier: float = 2.0
    jitter: bool = True
    timeout_per_attempt: float = 30.0


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    attempt_number: int
    timestamp: datetime
    delay_before: float
    error: Optional[str] = None
    success: bool = False
    response_time: float = 0.0


@dataclass
class RetryResult:
    """Result of retry operation."""
    success: bool
    result: Any = None
    error: Optional[str] = None
    attempts: List[RetryAttempt] = field(default_factory=list)
    total_time: float = 0.0


class SimpleRetrySystem:
    """Simplified retry system with exponential backoff."""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.logger = logging.getLogger("SimpleRetrySystem")
        
        self.stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0
        }
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt based on strategy."""
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (self.config.backoff_multiplier ** (attempt - 1))
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * attempt
        else:  # FIXED_DELAY
            delay = self.config.base_delay
        
        delay = min(delay, self.config.max_delay)
        
        if self.config.jitter:
            import random
            jitter_factor = random.uniform(0.8, 1.2)
            delay *= jitter_factor
        
        return delay
    
    def execute_with_retry(self, operation: Callable, *args, **kwargs) -> RetryResult:
        """Execute operation with retry logic."""
        attempts = []
        start_time = time.time()
        
        self.stats["total_operations"] += 1
        
        for attempt in range(1, self.config.max_attempts + 1):
            attempt_start = time.time()
            
            try:
                self.logger.debug(f"Attempt {attempt}/{self.config.max_attempts}")
                
                result = operation(*args, **kwargs)
                
                response_time = time.time() - attempt_start
                attempts.append(RetryAttempt(
                    attempt_number=attempt,
                    timestamp=datetime.now(),
                    delay_before=0.0 if attempt == 1 else attempts[-1].delay_before if attempts else 0.0,
                    success=True,
                    response_time=response_time
                ))
                
                total_time = time.time() - start_time
                self.stats["successful_operations"] += 1
                
                return RetryResult(
                    success=True,
                    result=result,
                    attempts=attempts,
                    total_time=total_time
                )
                
            except Exception as e:
                response_time = time.time() - attempt_start
                error_msg = str(e)
                
                attempts.append(RetryAttempt(
                    attempt_number=attempt,
                    timestamp=datetime.now(),
                    delay_before=0.0 if attempt == 1 else attempts[-1].delay_before if attempts else 0.0,
                    error=error_msg,
                    success=False,
                    response_time=response_time
                ))
                
                self.logger.warning(f"Attempt {attempt} failed: {error_msg}")
                
                if attempt >= self.config.max_attempts:
                    total_time = time.time() - start_time
                    self.stats["failed_operations"] += 1
                    
                    return RetryResult(
                        success=False,
                        error=error_msg,
                        attempts=attempts,
                        total_time=total_time
                    )
                
                delay = self.calculate_delay(attempt)
                attempts[-1].delay_before = delay
                
                self.logger.debug(f"Waiting {delay:.2f}s before retry {attempt + 1}")
                time.sleep(delay)
        
        total_time = time.time() - start_time
        self.stats["failed_operations"] += 1
        
        return RetryResult(
            success=False,
            error="Maximum retry attempts exceeded",
            attempts=attempts,
            total_time=total_time
        )
    
    def get_stats(self) -> dict:
        """Get retry system statistics."""
        return self.stats.copy()
