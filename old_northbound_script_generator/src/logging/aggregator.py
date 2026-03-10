"""Log aggregation for distributed deployments."""

import json
import logging
import threading
import time
import socket
import queue
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
import sqlite3


@dataclass
class LogEntry:
    """Aggregated log entry."""
    timestamp: datetime
    level: str
    logger: str
    message: str
    source_host: str
    source_instance: str
    module: str = ""
    function: str = ""
    line: int = 0
    extra_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
            "source_host": self.source_host,
            "source_instance": self.source_instance,
            "module": self.module,
            "function": self.function,
            "line": self.line,
            **self.extra_data
        }


class LogAggregator:
    """
    Aggregates logs from multiple distributed instances.
    
    Features:
    - Collects logs from multiple sources
    - Stores in centralized database
    - Provides query interface
    - Supports real-time streaming
    - Automatic cleanup of old logs
    """
    
    def __init__(
        self,
        db_path: str = "./logs/aggregated_logs.db",
        retention_days: int = 30,
        buffer_size: int = 1000,
        flush_interval: int = 10
    ):
        self.logger = logging.getLogger("LogAggregator")
        self.db_path = Path(db_path)
        self.retention_days = retention_days
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        
        # Create database directory
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Log buffer for batch inserts
        self.log_buffer: queue.Queue = queue.Queue(maxsize=buffer_size)
        
        # Background thread for flushing logs
        self.flush_thread = threading.Thread(target=self._flush_worker, daemon=True)
        self.flush_thread.start()
        
        # Statistics
        self.stats = {
            "total_logs_received": 0,
            "total_logs_stored": 0,
            "total_logs_dropped": 0,
            "last_flush_time": None,
            "buffer_size": 0
        }
        
        # Get hostname for source identification
        self.hostname = socket.gethostname()
        
        self.logger.info("LogAggregator initialized")
    
    def _init_database(self):
        """Initialize SQLite database for log storage."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                level TEXT NOT NULL,
                logger TEXT NOT NULL,
                message TEXT NOT NULL,
                source_host TEXT NOT NULL,
                source_instance TEXT NOT NULL,
                module TEXT,
                function TEXT,
                line INTEGER,
                extra_data TEXT
            )
        ''')
        
        # Create indexes for efficient querying
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON logs(timestamp DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_level 
            ON logs(level)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_logger 
            ON logs(logger)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_source 
            ON logs(source_host, source_instance)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_composite 
            ON logs(timestamp DESC, level, logger)
        ''')
        
        conn.commit()
        conn.close()
    
    def add_log(
        self,
        level: str,
        logger: str,
        message: str,
        source_instance: str = "default",
        **extra
    ):
        """
        Add log entry to aggregator.
        
        Args:
            level: Log level
            logger: Logger name
            message: Log message
            source_instance: Source instance identifier
            **extra: Additional fields
        """
        try:
            self.stats["total_logs_received"] += 1
            
            log_entry = LogEntry(
                timestamp=datetime.now(),
                level=level,
                logger=logger,
                message=message,
                source_host=self.hostname,
                source_instance=source_instance,
                module=extra.get("module", ""),
                function=extra.get("function", ""),
                line=extra.get("line", 0),
                extra_data={k: v for k, v in extra.items() 
                           if k not in ["module", "function", "line"]}
            )
            
            # Add to buffer
            try:
                self.log_buffer.put_nowait(log_entry)
                self.stats["buffer_size"] = self.log_buffer.qsize()
            except queue.Full:
                self.stats["total_logs_dropped"] += 1
                self.logger.warning("Log buffer full, dropping log entry")
        
        except Exception as e:
            self.logger.error(f"Failed to add log entry: {e}")
    
    def _flush_worker(self):
        """Background worker to flush logs to database."""
        while True:
            try:
                time.sleep(self.flush_interval)
                self._flush_buffer()
            except Exception as e:
                self.logger.error(f"Error in flush worker: {e}")
    
    def _flush_buffer(self):
        """Flush log buffer to database."""
        if self.log_buffer.empty():
            return
        
        logs_to_flush = []
        
        # Collect logs from buffer
        while not self.log_buffer.empty() and len(logs_to_flush) < 100:
            try:
                log_entry = self.log_buffer.get_nowait()
                logs_to_flush.append(log_entry)
            except queue.Empty:
                break
        
        if not logs_to_flush:
            return
        
        # Batch insert to database
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for log_entry in logs_to_flush:
                cursor.execute('''
                    INSERT INTO logs 
                    (timestamp, level, logger, message, source_host, source_instance,
                     module, function, line, extra_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    log_entry.timestamp.isoformat(),
                    log_entry.level,
                    log_entry.logger,
                    log_entry.message,
                    log_entry.source_host,
                    log_entry.source_instance,
                    log_entry.module,
                    log_entry.function,
                    log_entry.line,
                    json.dumps(log_entry.extra_data)
                ))
            
            conn.commit()
            conn.close()
            
            self.stats["total_logs_stored"] += len(logs_to_flush)
            self.stats["last_flush_time"] = datetime.now().isoformat()
            self.stats["buffer_size"] = self.log_buffer.qsize()
            
            self.logger.debug(f"Flushed {len(logs_to_flush)} logs to database")
        
        except Exception as e:
            self.logger.error(f"Failed to flush logs to database: {e}")
            # Put logs back in buffer
            for log_entry in logs_to_flush:
                try:
                    self.log_buffer.put_nowait(log_entry)
                except queue.Full:
                    self.stats["total_logs_dropped"] += 1
    
    def query_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        levels: Optional[List[str]] = None,
        loggers: Optional[List[str]] = None,
        source_hosts: Optional[List[str]] = None,
        source_instances: Optional[List[str]] = None,
        message_pattern: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Query logs with filters.
        
        Args:
            start_time: Start timestamp filter
            end_time: End timestamp filter
            levels: Log levels to include
            loggers: Logger names to include
            source_hosts: Source hosts to include
            source_instances: Source instances to include
            message_pattern: Message pattern (SQL LIKE)
            limit: Maximum number of results
            offset: Result offset for pagination
        
        Returns:
            List of log entries as dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build query
            query = "SELECT * FROM logs WHERE 1=1"
            params = []
            
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())
            
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())
            
            if levels:
                placeholders = ','.join('?' * len(levels))
                query += f" AND level IN ({placeholders})"
                params.extend(levels)
            
            if loggers:
                placeholders = ','.join('?' * len(loggers))
                query += f" AND logger IN ({placeholders})"
                params.extend(loggers)
            
            if source_hosts:
                placeholders = ','.join('?' * len(source_hosts))
                query += f" AND source_host IN ({placeholders})"
                params.extend(source_hosts)
            
            if source_instances:
                placeholders = ','.join('?' * len(source_instances))
                query += f" AND source_instance IN ({placeholders})"
                params.extend(source_instances)
            
            if message_pattern:
                query += " AND message LIKE ?"
                params.append(f"%{message_pattern}%")
            
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            
            # Convert results to dictionaries
            columns = [desc[0] for desc in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                log_dict = dict(zip(columns, row))
                
                # Parse extra_data JSON
                if log_dict.get('extra_data'):
                    try:
                        log_dict['extra_data'] = json.loads(log_dict['extra_data'])
                    except json.JSONDecodeError:
                        log_dict['extra_data'] = {}
                
                results.append(log_dict)
            
            conn.close()
            
            return results
        
        except Exception as e:
            self.logger.error(f"Failed to query logs: {e}")
            return []
    
    def get_log_statistics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get log statistics for time range.
        
        Args:
            start_time: Start timestamp
            end_time: End timestamp
        
        Returns:
            Dictionary with statistics
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build time filter
            time_filter = ""
            params = []
            
            if start_time:
                time_filter += " AND timestamp >= ?"
                params.append(start_time.isoformat())
            
            if end_time:
                time_filter += " AND timestamp <= ?"
                params.append(end_time.isoformat())
            
            # Total logs
            cursor.execute(f"SELECT COUNT(*) FROM logs WHERE 1=1{time_filter}", params)
            total_logs = cursor.fetchone()[0]
            
            # Logs by level
            cursor.execute(
                f"SELECT level, COUNT(*) FROM logs WHERE 1=1{time_filter} GROUP BY level",
                params
            )
            logs_by_level = dict(cursor.fetchall())
            
            # Logs by logger
            cursor.execute(
                f"SELECT logger, COUNT(*) FROM logs WHERE 1=1{time_filter} GROUP BY logger ORDER BY COUNT(*) DESC LIMIT 10",
                params
            )
            top_loggers = dict(cursor.fetchall())
            
            # Logs by source
            cursor.execute(
                f"SELECT source_host, source_instance, COUNT(*) FROM logs WHERE 1=1{time_filter} GROUP BY source_host, source_instance",
                params
            )
            logs_by_source = [
                {"host": row[0], "instance": row[1], "count": row[2]}
                for row in cursor.fetchall()
            ]
            
            conn.close()
            
            return {
                "total_logs": total_logs,
                "logs_by_level": logs_by_level,
                "top_loggers": top_loggers,
                "logs_by_source": logs_by_source,
                "time_range": {
                    "start": start_time.isoformat() if start_time else None,
                    "end": end_time.isoformat() if end_time else None
                }
            }
        
        except Exception as e:
            self.logger.error(f"Failed to get log statistics: {e}")
            return {}
    
    def cleanup_old_logs(self) -> int:
        """
        Clean up logs older than retention period.
        
        Returns:
            Number of logs deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM logs WHERE timestamp < ?",
                (cutoff_date.isoformat(),)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            self.logger.info(f"Cleaned up {deleted_count} old log entries")
            return deleted_count
        
        except Exception as e:
            self.logger.error(f"Failed to cleanup old logs: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregator statistics."""
        return {
            **self.stats,
            "retention_days": self.retention_days,
            "buffer_max_size": self.buffer_size,
            "flush_interval": self.flush_interval,
            "hostname": self.hostname
        }
    
    def close(self):
        """Flush remaining logs and cleanup."""
        self.logger.info("Closing LogAggregator")
        self._flush_buffer()


# Global log aggregator instance
_log_aggregator: Optional[LogAggregator] = None


def get_log_aggregator(
    db_path: str = "./logs/aggregated_logs.db",
    retention_days: int = 30
) -> LogAggregator:
    """Get or create global log aggregator instance."""
    global _log_aggregator
    
    if _log_aggregator is None:
        _log_aggregator = LogAggregator(
            db_path=db_path,
            retention_days=retention_days
        )
    
    return _log_aggregator
