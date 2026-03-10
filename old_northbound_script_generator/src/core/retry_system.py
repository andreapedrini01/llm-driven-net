"""
Advanced Retry System with Exponential Backoff and Circuit Breaker
Implements resilient retry mechanisms for external service calls
"""

import asyncio
import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
import pickle
from queue import Queue, Empty, Full
import uuid

from src.models.action_models import NetworkAction


class RetryStrategy(str, Enum):
    """Available retry strategies."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    FIBONACCI_BACKOFF = "fibonacci_backoff"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, rejecting calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0  # seconds
    max_delay: float = 60.0  # seconds
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    backoff_multiplier: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd
    timeout_per_attempt: float = 30.0  # seconds
    
    # Circuit breaker settings
    failure_threshold: int = 5  # failures before opening circuit
    recovery_timeout: float = 60.0  # seconds to wait before trying half-open
    success_threshold: int = 3  # successes needed to close circuit from half-open
    
    # Persistent queue settings
    enable_persistent_queue: bool = True
    queue_max_size: int = 1000
    queue_persistence_path: str = "./logs/retry_queue.db"


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
    circuit_breaker_triggered: bool = False


class CircuitBreaker:
    """Circuit breaker implementation for external service protection."""
    
    def __init__(self, name: str, config: RetryConfig):
        self.name = name
        self.config = config
        self.logger = logging.getLogger(f"CircuitBreaker-{name}")
        
        # State management
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state_change_time = datetime.now()
        
        # Statistics
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        
        # Thread safety
        self.lock = threading.Lock()
    
    def can_execute(self) -> bool:
        """Check if execution is allowed based on circuit breaker state."""
        with self.lock:
            if self.state == CircuitBreakerState.CLOSED:
                return True
            
            elif self.state == CircuitBreakerState.OPEN:
                # Check if recovery timeout has passed
                if (datetime.now() - self.state_change_time).total_seconds() >= self.config.recovery_timeout:
                    self.logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.state_change_time = datetime.now()
                    return True
                return False
            
            elif self.state == CircuitBreakerState.HALF_OPEN:
                return True
            
            return False
    
    def record_success(self):
        """Record a successful operation."""
        with self.lock:
            self.total_calls += 1
            self.total_successes += 1
            
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.logger.info(f"Circuit breaker {self.name} transitioning to CLOSED")
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    self.state_change_time = datetime.now()
            
            elif self.state == CircuitBreakerState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0
    
    def record_failure(self):
        """Record a failed operation."""
        with self.lock:
            self.total_calls += 1
            self.total_failures += 1
            self.last_failure_time = datetime.now()
            
            if self.state == CircuitBreakerState.CLOSED:
                self.failure_count += 1
                if self.failure_count >= self.config.failure_threshold:
                    self.logger.warning(f"Circuit breaker {self.name} transitioning to OPEN")
                    self.state = CircuitBreakerState.OPEN
                    self.state_change_time = datetime.now()
            
            elif self.state == CircuitBreakerState.HALF_OPEN:
                self.logger.warning(f"Circuit breaker {self.name} transitioning back to OPEN")
                self.state = CircuitBreakerState.OPEN
                self.success_count = 0
                self.state_change_time = datetime.now()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        with self.lock:
            uptime = (datetime.now() - self.state_change_time).total_seconds()
            success_rate = (self.total_successes / max(self.total_calls, 1)) * 100
            
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "total_calls": self.total_calls,
                "total_failures": self.total_failures,
                "total_successes": self.total_successes,
                "success_rate": success_rate,
                "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
                "state_change_time": self.state_change_time.isoformat(),
                "time_in_current_state": uptime
            }


class PersistentActionQueue:
    """Persistent queue for actions when controllers are unavailable."""
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.logger = logging.getLogger("PersistentActionQueue")
        
        # Create database path
        self.db_path = Path(config.queue_persistence_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # In-memory queue for fast access
        self.memory_queue = Queue(maxsize=config.queue_max_size)
        
        # Load existing items from database
        self._load_from_database()
        
        # Statistics
        self.stats = {
            "total_enqueued": 0,
            "total_dequeued": 0,
            "total_failed": 0,
            "current_size": 0,
            "last_enqueue": None,
            "last_dequeue": None
        }
        
        # Thread safety
        self.lock = threading.Lock()
    
    def _init_database(self):
        """Initialize SQLite database for persistent storage."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS action_queue (
                id TEXT PRIMARY KEY,
                action_data BLOB NOT NULL,
                enqueue_time DATETIME NOT NULL,
                retry_count INTEGER DEFAULT 0,
                last_retry_time DATETIME,
                priority INTEGER DEFAULT 1000,
                max_retries INTEGER DEFAULT 3,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_priority_time 
            ON action_queue(priority DESC, enqueue_time ASC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_status 
            ON action_queue(status)
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_from_database(self):
        """Load pending actions from database into memory queue."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, action_data, priority, retry_count, max_retries
                FROM action_queue 
                WHERE status = 'pending'
                ORDER BY priority DESC, enqueue_time ASC
                LIMIT ?
            ''', (self.config.queue_max_size,))
            
            loaded_count = 0
            for row in cursor.fetchall():
                try:
                    action_id, action_data, priority, retry_count, max_retries = row
                    action = pickle.loads(action_data)
                    
                    queue_item = {
                        'id': action_id,
                        'action': action,
                        'priority': priority,
                        'retry_count': retry_count,
                        'max_retries': max_retries
                    }
                    
                    self.memory_queue.put_nowait(queue_item)
                    loaded_count += 1
                    
                except (pickle.PickleError, Full) as e:
                    self.logger.error(f"Failed to load action {action_id}: {e}")
            
            conn.close()
            self.logger.info(f"Loaded {loaded_count} actions from persistent storage")
            
        except Exception as e:
            self.logger.error(f"Failed to load from database: {e}")
    
    def enqueue(self, action: NetworkAction, max_retries: int = 3) -> bool:
        """Add action to persistent queue."""
        try:
            with self.lock:
                action_id = str(uuid.uuid4())
                
                # Serialize action
                action_data = pickle.dumps(action)
                
                # Store in database
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO action_queue 
                    (id, action_data, enqueue_time, priority, max_retries, status)
                    VALUES (?, ?, ?, ?, ?, 'pending')
                ''', (
                    action_id,
                    action_data,
                    datetime.now().isoformat(),
                    action.priority,
                    max_retries
                ))
                
                conn.commit()
                conn.close()
                
                # Add to memory queue if space available
                queue_item = {
                    'id': action_id,
                    'action': action,
                    'priority': action.priority,
                    'retry_count': 0,
                    'max_retries': max_retries
                }
                
                try:
                    self.memory_queue.put_nowait(queue_item)
                except Full:
                    self.logger.warning("Memory queue full, action stored in database only")
                
                # Update statistics
                self.stats["total_enqueued"] += 1
                self.stats["current_size"] = self.memory_queue.qsize()
                self.stats["last_enqueue"] = datetime.now().isoformat()
                
                self.logger.info(f"Enqueued action {action.id} with queue ID {action_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to enqueue action {action.id}: {e}")
            return False
    
    def dequeue(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """Get next action from queue."""
        try:
            # Try to get from memory queue first
            queue_item = self.memory_queue.get(timeout=timeout)
            
            with self.lock:
                # Update statistics
                self.stats["total_dequeued"] += 1
                self.stats["current_size"] = self.memory_queue.qsize()
                self.stats["last_dequeue"] = datetime.now().isoformat()
            
            return queue_item
            
        except Empty:
            # Try to load more items from database if memory queue is empty
            self._load_more_from_database()
            
            try:
                queue_item = self.memory_queue.get(timeout=0.1)
                
                with self.lock:
                    self.stats["total_dequeued"] += 1
                    self.stats["current_size"] = self.memory_queue.qsize()
                    self.stats["last_dequeue"] = datetime.now().isoformat()
                
                return queue_item
                
            except Empty:
                return None
    
    def _load_more_from_database(self):
        """Load more items from database when memory queue is empty."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get items not currently in memory
            cursor.execute('''
                SELECT id, action_data, priority, retry_count, max_retries
                FROM action_queue 
                WHERE status = 'pending'
                ORDER BY priority DESC, enqueue_time ASC
                LIMIT ?
            ''', (min(50, self.config.queue_max_size),))
            
            for row in cursor.fetchall():
                try:
                    action_id, action_data, priority, retry_count, max_retries = row
                    action = pickle.loads(action_data)
                    
                    queue_item = {
                        'id': action_id,
                        'action': action,
                        'priority': priority,
                        'retry_count': retry_count,
                        'max_retries': max_retries
                    }
                    
                    self.memory_queue.put_nowait(queue_item)
                    
                except (pickle.PickleError, Full):
                    break
            
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Failed to load more from database: {e}")
    
    def mark_completed(self, queue_id: str) -> bool:
        """Mark action as completed and remove from queue."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE action_queue 
                SET status = 'completed'
                WHERE id = ?
            ''', (queue_id,))
            
            conn.commit()
            conn.close()
            
            self.logger.debug(f"Marked action {queue_id} as completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to mark action {queue_id} as completed: {e}")
            return False
    
    def mark_failed(self, queue_id: str) -> bool:
        """Mark action as failed."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE action_queue 
                SET status = 'failed', last_retry_time = ?
                WHERE id = ?
            ''', (datetime.now().isoformat(), queue_id))
            
            conn.commit()
            conn.close()
            
            with self.lock:
                self.stats["total_failed"] += 1
            
            self.logger.warning(f"Marked action {queue_id} as failed")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to mark action {queue_id} as failed: {e}")
            return False
    
    def increment_retry_count(self, queue_id: str) -> bool:
        """Increment retry count for an action."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE action_queue 
                SET retry_count = retry_count + 1, last_retry_time = ?
                WHERE id = ?
            ''', (datetime.now().isoformat(), queue_id))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to increment retry count for {queue_id}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        with self.lock:
            # Get database stats
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('SELECT COUNT(*) FROM action_queue WHERE status = "pending"')
                pending_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM action_queue WHERE status = "completed"')
                completed_count = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM action_queue WHERE status = "failed"')
                failed_count = cursor.fetchone()[0]
                
                conn.close()
                
            except Exception as e:
                self.logger.error(f"Failed to get database stats: {e}")
                pending_count = completed_count = failed_count = 0
            
            return {
                **self.stats,
                "memory_queue_size": self.memory_queue.qsize(),
                "database_pending": pending_count,
                "database_completed": completed_count,
                "database_failed": failed_count,
                "total_in_database": pending_count + completed_count + failed_count
            }
    
    def cleanup_old_entries(self, days: int = 7) -> int:
        """Clean up old completed/failed entries from database."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM action_queue 
                WHERE status IN ('completed', 'failed') 
                AND enqueue_time < ?
            ''', (cutoff_date.isoformat(),))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            self.logger.info(f"Cleaned up {deleted_count} old queue entries")
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old entries: {e}")
            return 0


class AdvancedRetrySystem:
    """Advanced retry system with exponential backoff, circuit breaker, and persistent queue."""
    
    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.logger = logging.getLogger("AdvancedRetrySystem")
        
        # Circuit breakers for different services
        self.circuit_breakers = {}
        
        # Persistent queue for actions
        if self.config.enable_persistent_queue:
            self.persistent_queue = PersistentActionQueue(self.config)
        else:
            self.persistent_queue = None
        
        # Statistics
        self.stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "circuit_breaker_trips": 0,
            "queue_operations": 0
        }
        
        self.logger.info("Advanced retry system initialized")
    
    def get_circuit_breaker(self, service_name: str) -> CircuitBreaker:
        """Get or create circuit breaker for a service."""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(service_name, self.config)
        return self.circuit_breakers[service_name]
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt based on strategy."""
        if self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (self.config.backoff_multiplier ** (attempt - 1))
        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay * attempt
        elif self.config.strategy == RetryStrategy.FIBONACCI_BACKOFF:
            fib_a, fib_b = 1, 1
            for _ in range(attempt - 1):
                fib_a, fib_b = fib_b, fib_a + fib_b
            delay = self.config.base_delay * fib_a
        else:  # FIXED_DELAY
            delay = self.config.base_delay
        
        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay)
        
        # Add jitter to prevent thundering herd
        if self.config.jitter:
            import random
            jitter_factor = random.uniform(0.8, 1.2)
            delay *= jitter_factor
        
        return delay
    
    def execute_with_retry(self, 
                          operation: Callable,
                          service_name: str,
                          *args, 
                          **kwargs) -> RetryResult:
        """Execute operation with retry logic and circuit breaker protection."""
        circuit_breaker = self.get_circuit_breaker(service_name)
        attempts = []
        start_time = time.time()
        
        self.stats["total_operations"] += 1
        
        # Check circuit breaker
        if not circuit_breaker.can_execute():
            self.stats["circuit_breaker_trips"] += 1
            return RetryResult(
                success=False,
                error=f"Circuit breaker {service_name} is OPEN",
                attempts=attempts,
                total_time=0.0,
                circuit_breaker_triggered=True
            )
        
        for attempt in range(1, self.config.max_attempts + 1):
            attempt_start = time.time()
            
            try:
                self.logger.debug(f"Attempt {attempt}/{self.config.max_attempts} for {service_name}")
                
                # Execute the operation with timeout
                result = operation(*args, **kwargs)
                
                # Record successful attempt
                response_time = time.time() - attempt_start
                attempts.append(RetryAttempt(
                    attempt_number=attempt,
                    timestamp=datetime.now(),
                    delay_before=0.0 if attempt == 1 else attempts[-1].delay_before if attempts else 0.0,
                    success=True,
                    response_time=response_time
                ))
                
                # Record success in circuit breaker
                circuit_breaker.record_success()
                
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
                
                # Record failed attempt
                attempts.append(RetryAttempt(
                    attempt_number=attempt,
                    timestamp=datetime.now(),
                    delay_before=0.0 if attempt == 1 else attempts[-1].delay_before if attempts else 0.0,
                    error=error_msg,
                    success=False,
                    response_time=response_time
                ))
                
                self.logger.warning(f"Attempt {attempt} failed for {service_name}: {error_msg}")
                
                # If this is the last attempt, record failure and return
                if attempt >= self.config.max_attempts:
                    circuit_breaker.record_failure()
                    total_time = time.time() - start_time
                    self.stats["failed_operations"] += 1
                    
                    return RetryResult(
                        success=False,
                        error=error_msg,
                        attempts=attempts,
                        total_time=total_time
                    )
                
                # Calculate delay for next attempt
                delay = self.calculate_delay(attempt)
                attempts[-1].delay_before = delay
                
                self.logger.debug(f"Waiting {delay:.2f}s before retry {attempt + 1}")
                time.sleep(delay)
        
        # Should not reach here, but just in case
        circuit_breaker.record_failure()
        total_time = time.time() - start_time
        self.stats["failed_operations"] += 1
        
        return RetryResult(
            success=False,
            error="Maximum retry attempts exceeded",
            attempts=attempts,
            total_time=total_time
        )
    
    def queue_action_for_retry(self, action: NetworkAction, max_retries: int = None) -> bool:
        """Queue action for later retry when service is unavailable."""
        if not self.persistent_queue:
            self.logger.error("Persistent queue not enabled")
            return False
        
        max_retries = max_retries or self.config.max_attempts
        success = self.persistent_queue.enqueue(action, max_retries)
        
        if success:
            self.stats["queue_operations"] += 1
            self.logger.info(f"Queued action {action.id} for later retry")
        
        return success
    
    def process_queued_actions(self, 
                              processor: Callable[[NetworkAction], bool],
                              service_name: str,
                              max_actions: int = 10) -> Dict[str, Any]:
        """Process queued actions when service becomes available."""
        if not self.persistent_queue:
            return {"processed": 0, "successful": 0, "failed": 0, "requeued": 0}
        
        processed = 0
        successful = 0
        failed = 0
        requeued = 0
        
        circuit_breaker = self.get_circuit_breaker(service_name)
        
        # Check if service is available
        if not circuit_breaker.can_execute():
            self.logger.debug(f"Service {service_name} not available for processing queue")
            return {"processed": 0, "successful": 0, "failed": 0, "requeued": 0}
        
        for _ in range(max_actions):
            queue_item = self.persistent_queue.dequeue(timeout=0.1)
            if not queue_item:
                break
            
            processed += 1
            action = queue_item['action']
            queue_id = queue_item['id']
            retry_count = queue_item['retry_count']
            max_retries = queue_item['max_retries']
            
            try:
                self.logger.info(f"Processing queued action {action.id} (attempt {retry_count + 1})")
                
                # Try to process the action
                if processor(action):
                    # Success
                    self.persistent_queue.mark_completed(queue_id)
                    circuit_breaker.record_success()
                    successful += 1
                    self.logger.info(f"Successfully processed queued action {action.id}")
                else:
                    # Failed
                    circuit_breaker.record_failure()
                    
                    if retry_count < max_retries:
                        # Requeue for another attempt
                        self.persistent_queue.increment_retry_count(queue_id)
                        self.persistent_queue.enqueue(action, max_retries - retry_count - 1)
                        requeued += 1
                        self.logger.warning(f"Requeued action {action.id} for retry")
                    else:
                        # Max retries exceeded
                        self.persistent_queue.mark_failed(queue_id)
                        failed += 1
                        self.logger.error(f"Action {action.id} failed after {max_retries} attempts")
                
            except Exception as e:
                self.logger.error(f"Error processing queued action {action.id}: {e}")
                circuit_breaker.record_failure()
                
                if retry_count < max_retries:
                    self.persistent_queue.increment_retry_count(queue_id)
                    self.persistent_queue.enqueue(action, max_retries - retry_count - 1)
                    requeued += 1
                else:
                    self.persistent_queue.mark_failed(queue_id)
                    failed += 1
        
        result = {
            "processed": processed,
            "successful": successful,
            "failed": failed,
            "requeued": requeued
        }
        
        if processed > 0:
            self.logger.info(f"Processed {processed} queued actions: {successful} successful, {failed} failed, {requeued} requeued")
        
        return result
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics."""
        circuit_breaker_stats = {}
        for name, cb in self.circuit_breakers.items():
            circuit_breaker_stats[name] = cb.get_stats()
        
        queue_stats = {}
        if self.persistent_queue:
            queue_stats = self.persistent_queue.get_stats()
        
        return {
            "retry_system": self.stats,
            "circuit_breakers": circuit_breaker_stats,
            "persistent_queue": queue_stats,
            "config": {
                "max_attempts": self.config.max_attempts,
                "base_delay": self.config.base_delay,
                "max_delay": self.config.max_delay,
                "strategy": self.config.strategy.value,
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout
            }
        }
    
    def cleanup(self):
        """Cleanup resources and old data."""
        if self.persistent_queue:
            self.persistent_queue.cleanup_old_entries()
        
        self.logger.info("Advanced retry system cleanup completed")