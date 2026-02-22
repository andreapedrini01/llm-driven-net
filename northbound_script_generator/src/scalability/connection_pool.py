"""Connection pooling for database and network connections."""

import logging
import threading
import time
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty, Full
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool as pg_pool
from psycopg2.extras import RealDictCursor


T = TypeVar('T')


@dataclass
class ConnectionStats:
    """Statistics for a connection."""
    connection_id: str
    created_at: datetime
    last_used: datetime
    total_uses: int = 0
    total_errors: int = 0
    is_active: bool = True


class GenericConnectionPool(Generic[T]):
    """
    Generic connection pool for any type of connection.
    
    Features:
    - Connection reuse
    - Automatic connection validation
    - Connection lifecycle management
    - Statistics tracking
    """
    
    def __init__(
        self,
        name: str,
        min_connections: int,
        max_connections: int,
        connection_factory: Callable[[], T],
        connection_validator: Optional[Callable[[T], bool]] = None,
        connection_closer: Optional[Callable[[T], None]] = None,
        max_idle_time: int = 300,  # 5 minutes
        validation_interval: int = 60  # 1 minute
    ):
        self.logger = logging.getLogger(f"ConnectionPool-{name}")
        self.name = name
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_factory = connection_factory
        self.connection_validator = connection_validator
        self.connection_closer = connection_closer
        self.max_idle_time = max_idle_time
        self.validation_interval = validation_interval
        
        # Connection pool
        self.available_connections: Queue[T] = Queue(maxsize=max_connections)
        self.active_connections: Dict[int, T] = {}
        self.connection_stats: Dict[int, ConnectionStats] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics
        self.stats = {
            "total_created": 0,
            "total_destroyed": 0,
            "total_acquired": 0,
            "total_released": 0,
            "total_errors": 0,
            "current_size": 0,
            "active_connections": 0
        }
        
        # Validation thread
        self._validation_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Initialize minimum connections
        self._initialize_pool()
        
        # Start validation thread
        self.start_validation()
        
        self.logger.info(
            f"Connection pool initialized: min={min_connections}, max={max_connections}"
        )
    
    def _initialize_pool(self):
        """Initialize pool with minimum connections."""
        for _ in range(self.min_connections):
            try:
                conn = self._create_connection()
                self.available_connections.put_nowait(conn)
            except Exception as e:
                self.logger.error(f"Failed to create initial connection: {e}")
    
    def _create_connection(self) -> T:
        """Create a new connection."""
        try:
            conn = self.connection_factory()
            
            conn_id = id(conn)
            
            with self._lock:
                self.connection_stats[conn_id] = ConnectionStats(
                    connection_id=str(conn_id),
                    created_at=datetime.now(),
                    last_used=datetime.now()
                )
                
                self.stats["total_created"] += 1
                self.stats["current_size"] += 1
            
            self.logger.debug(f"Created connection {conn_id}")
            return conn
        
        except Exception as e:
            self.logger.error(f"Failed to create connection: {e}")
            self.stats["total_errors"] += 1
            raise
    
    def _validate_connection(self, conn: T) -> bool:
        """Validate a connection."""
        if self.connection_validator is None:
            return True
        
        try:
            return self.connection_validator(conn)
        except Exception as e:
            self.logger.warning(f"Connection validation failed: {e}")
            return False
    
    def _close_connection(self, conn: T):
        """Close a connection."""
        try:
            if self.connection_closer:
                self.connection_closer(conn)
            
            conn_id = id(conn)
            
            with self._lock:
                if conn_id in self.connection_stats:
                    del self.connection_stats[conn_id]
                
                self.stats["total_destroyed"] += 1
                self.stats["current_size"] -= 1
            
            self.logger.debug(f"Closed connection {conn_id}")
        
        except Exception as e:
            self.logger.error(f"Error closing connection: {e}")
    
    @contextmanager
    def get_connection(self, timeout: float = 30.0):
        """
        Get a connection from the pool (context manager).
        
        Args:
            timeout: Maximum time to wait for a connection
        
        Yields:
            Connection from the pool
        """
        conn = None
        try:
            conn = self.acquire(timeout)
            yield conn
        finally:
            if conn is not None:
                self.release(conn)
    
    def acquire(self, timeout: float = 30.0) -> T:
        """
        Acquire a connection from the pool.
        
        Args:
            timeout: Maximum time to wait for a connection
        
        Returns:
            Connection from the pool
        
        Raises:
            Empty: If no connection available within timeout
        """
        start_time = time.time()
        
        while True:
            try:
                # Try to get available connection
                conn = self.available_connections.get(timeout=min(1.0, timeout))
                
                # Validate connection
                if self._validate_connection(conn):
                    conn_id = id(conn)
                    
                    with self._lock:
                        self.active_connections[conn_id] = conn
                        
                        if conn_id in self.connection_stats:
                            stats = self.connection_stats[conn_id]
                            stats.last_used = datetime.now()
                            stats.total_uses += 1
                        
                        self.stats["total_acquired"] += 1
                        self.stats["active_connections"] = len(self.active_connections)
                    
                    return conn
                else:
                    # Connection invalid, close and create new one
                    self._close_connection(conn)
                    
                    if self.stats["current_size"] < self.max_connections:
                        conn = self._create_connection()
                        self.available_connections.put_nowait(conn)
            
            except Empty:
                # No available connections, try to create new one
                with self._lock:
                    if self.stats["current_size"] < self.max_connections:
                        try:
                            conn = self._create_connection()
                            self.available_connections.put_nowait(conn)
                            continue
                        except Exception as e:
                            self.logger.error(f"Failed to create new connection: {e}")
                
                # Check timeout
                if time.time() - start_time >= timeout:
                    raise Empty("No connection available within timeout")
                
                time.sleep(0.1)
    
    def release(self, conn: T, error: bool = False):
        """
        Release a connection back to the pool.
        
        Args:
            conn: Connection to release
            error: Whether the connection had an error
        """
        conn_id = id(conn)
        
        with self._lock:
            if conn_id in self.active_connections:
                del self.active_connections[conn_id]
                self.stats["active_connections"] = len(self.active_connections)
            
            if error and conn_id in self.connection_stats:
                self.connection_stats[conn_id].total_errors += 1
        
        if error:
            # Close connection on error
            self._close_connection(conn)
            
            # Create replacement if below minimum
            if self.stats["current_size"] < self.min_connections:
                try:
                    new_conn = self._create_connection()
                    self.available_connections.put_nowait(new_conn)
                except Exception as e:
                    self.logger.error(f"Failed to create replacement connection: {e}")
        else:
            # Return to pool
            try:
                self.available_connections.put_nowait(conn)
                self.stats["total_released"] += 1
            except Full:
                # Pool full, close connection
                self._close_connection(conn)
    
    def start_validation(self):
        """Start connection validation thread."""
        if self._running:
            return
        
        self._running = True
        self._validation_thread = threading.Thread(
            target=self._validation_loop,
            daemon=True,
            name=f"PoolValidator-{self.name}"
        )
        self._validation_thread.start()
        
        self.logger.info("Started validation thread")
    
    def stop_validation(self):
        """Stop connection validation thread."""
        if not self._running:
            return
        
        self._running = False
        
        if self._validation_thread:
            self._validation_thread.join(timeout=10)
        
        self.logger.info("Stopped validation thread")
    
    def _validation_loop(self):
        """Validation loop for checking idle connections."""
        while self._running:
            try:
                self._validate_idle_connections()
                time.sleep(self.validation_interval)
            except Exception as e:
                self.logger.error(f"Error in validation loop: {e}")
                time.sleep(5)
    
    def _validate_idle_connections(self):
        """Validate and clean up idle connections."""
        now = datetime.now()
        
        # Check connection stats for idle connections
        with self._lock:
            idle_connections = []
            
            for conn_id, stats in self.connection_stats.items():
                if conn_id not in self.active_connections:
                    idle_time = (now - stats.last_used).total_seconds()
                    
                    if idle_time > self.max_idle_time:
                        idle_connections.append(conn_id)
            
            # Remove idle connections if above minimum
            for conn_id in idle_connections:
                if self.stats["current_size"] > self.min_connections:
                    # Find and remove connection from available queue
                    # This is a simplified approach - in production, you'd want a better way
                    self.logger.debug(f"Removing idle connection {conn_id}")
    
    def close_all(self):
        """Close all connections in the pool."""
        self.stop_validation()
        
        # Close active connections
        with self._lock:
            for conn in list(self.active_connections.values()):
                self._close_connection(conn)
            
            self.active_connections.clear()
        
        # Close available connections
        while not self.available_connections.empty():
            try:
                conn = self.available_connections.get_nowait()
                self._close_connection(conn)
            except Empty:
                break
        
        self.logger.info("Closed all connections")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            return {
                "name": self.name,
                "min_connections": self.min_connections,
                "max_connections": self.max_connections,
                "available_connections": self.available_connections.qsize(),
                **self.stats
            }


class PostgreSQLConnectionPool:
    """PostgreSQL connection pool using psycopg2."""
    
    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        min_connections: int = 5,
        max_connections: int = 20
    ):
        self.logger = logging.getLogger("PostgreSQLConnectionPool")
        
        try:
            self.pool = pg_pool.ThreadedConnectionPool(
                min_connections,
                max_connections,
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                cursor_factory=RealDictCursor
            )
            
            self.logger.info(
                f"PostgreSQL connection pool created: "
                f"min={min_connections}, max={max_connections}"
            )
        
        except Exception as e:
            self.logger.error(f"Failed to create PostgreSQL connection pool: {e}")
            raise
        
        # Statistics
        self.stats = {
            "total_acquired": 0,
            "total_released": 0,
            "total_errors": 0
        }
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool (context manager)."""
        conn = None
        try:
            conn = self.pool.getconn()
            self.stats["total_acquired"] += 1
            yield conn
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
            self.stats["total_errors"] += 1
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.pool.putconn(conn)
                self.stats["total_released"] += 1
    
    def close_all(self):
        """Close all connections in the pool."""
        try:
            self.pool.closeall()
            self.logger.info("Closed all PostgreSQL connections")
        except Exception as e:
            self.logger.error(f"Error closing connections: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return self.stats.copy()
