"""Advanced structured logging with filters and rotation."""

import logging
import logging.handlers
import json
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum


class LogLevel(str, Enum):
    """Log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter."""
    
    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields
        if self.include_extra:
            for key, value in record.__dict__.items():
                if key not in [
                    'name', 'msg', 'args', 'created', 'filename', 'funcName',
                    'levelname', 'levelno', 'lineno', 'module', 'msecs',
                    'message', 'pathname', 'process', 'processName',
                    'relativeCreated', 'thread', 'threadName', 'exc_info',
                    'exc_text', 'stack_info'
                ]:
                    log_data[key] = value
        
        return json.dumps(log_data)


class LogFilter:
    """
    Advanced log filter supporting:
    - Timestamp range filtering
    - Log level filtering
    - Component/logger name filtering
    - Message pattern matching
    """
    
    def __init__(
        self,
        min_level: Optional[LogLevel] = None,
        max_level: Optional[LogLevel] = None,
        loggers: Optional[list] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        message_pattern: Optional[str] = None
    ):
        self.min_level = min_level
        self.max_level = max_level
        self.loggers = loggers or []
        self.start_time = start_time
        self.end_time = end_time
        self.message_pattern = message_pattern
        
        # Convert log levels to numeric values
        self.min_level_num = getattr(logging, min_level.value, 0) if min_level else 0
        self.max_level_num = getattr(logging, max_level.value, 100) if max_level else 100
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record based on criteria."""
        # Check log level
        if not (self.min_level_num <= record.levelno <= self.max_level_num):
            return False
        
        # Check logger name
        if self.loggers and record.name not in self.loggers:
            # Check if any logger pattern matches
            if not any(record.name.startswith(logger) for logger in self.loggers):
                return False
        
        # Check timestamp
        record_time = datetime.fromtimestamp(record.created)
        if self.start_time and record_time < self.start_time:
            return False
        if self.end_time and record_time > self.end_time:
            return False
        
        # Check message pattern
        if self.message_pattern:
            import re
            if not re.search(self.message_pattern, record.getMessage()):
                return False
        
        return True


class StructuredLogger:
    """
    Advanced logger with structured logging, rotation, and filtering.
    """
    
    def __init__(
        self,
        name: str,
        level: LogLevel = LogLevel.INFO,
        structured: bool = True,
        file_path: Optional[str] = None,
        file_rotation: bool = True,
        max_bytes: int = 10485760,  # 10MB
        backup_count: int = 5,
        console_output: bool = True,
        syslog_enabled: bool = False,
        syslog_address: tuple = ('localhost', 514)
    ):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.value))
        self.logger.propagate = False
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Setup formatters
        if structured:
            formatter = StructuredFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        # Console handler
        if console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # File handler with rotation
        if file_path:
            file_path_obj = Path(file_path)
            file_path_obj.parent.mkdir(parents=True, exist_ok=True)
            
            if file_rotation:
                file_handler = logging.handlers.RotatingFileHandler(
                    file_path,
                    maxBytes=max_bytes,
                    backupCount=backup_count
                )
            else:
                file_handler = logging.FileHandler(file_path)
            
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        
        # Syslog handler
        if syslog_enabled:
            try:
                syslog_handler = logging.handlers.SysLogHandler(address=syslog_address)
                syslog_handler.setFormatter(formatter)
                self.logger.addHandler(syslog_handler)
            except Exception as e:
                self.logger.warning(f"Failed to setup syslog handler: {e}")
    
    def debug(self, message: str, **kwargs):
        """Log debug message with extra fields."""
        self.logger.debug(message, extra=kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message with extra fields."""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with extra fields."""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with extra fields."""
        self.logger.error(message, extra=kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message with extra fields."""
        self.logger.critical(message, extra=kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        self.logger.exception(message, extra=kwargs)
    
    def add_filter(self, log_filter: LogFilter):
        """Add custom filter to logger."""
        self.logger.addFilter(log_filter)
    
    def set_level(self, level: LogLevel):
        """Change log level dynamically."""
        self.logger.setLevel(getattr(logging, level.value))


# Global logger registry
_loggers: Dict[str, StructuredLogger] = {}


def setup_logging(
    level: LogLevel = LogLevel.INFO,
    structured: bool = True,
    file_path: Optional[str] = None,
    file_rotation: bool = True,
    max_bytes: int = 10485760,
    backup_count: int = 5,
    console_output: bool = True,
    syslog_enabled: bool = False,
    syslog_address: tuple = ('localhost', 514),
    component_levels: Optional[Dict[str, LogLevel]] = None
):
    """
    Setup global logging configuration.
    
    Args:
        level: Default log level
        structured: Enable JSON structured logging
        file_path: Log file path
        file_rotation: Enable log rotation
        max_bytes: Max log file size before rotation
        backup_count: Number of backup files to keep
        console_output: Enable console output
        syslog_enabled: Enable syslog
        syslog_address: Syslog server address
        component_levels: Per-component log level overrides
    """
    # Setup root logger
    root_logger = StructuredLogger(
        name="root",
        level=level,
        structured=structured,
        file_path=file_path,
        file_rotation=file_rotation,
        max_bytes=max_bytes,
        backup_count=backup_count,
        console_output=console_output,
        syslog_enabled=syslog_enabled,
        syslog_address=syslog_address
    )
    
    _loggers["root"] = root_logger
    
    # Setup component-specific loggers
    if component_levels:
        for component, comp_level in component_levels.items():
            comp_logger = StructuredLogger(
                name=component,
                level=comp_level,
                structured=structured,
                file_path=file_path,
                file_rotation=file_rotation,
                max_bytes=max_bytes,
                backup_count=backup_count,
                console_output=console_output,
                syslog_enabled=syslog_enabled,
                syslog_address=syslog_address
            )
            _loggers[component] = comp_logger


def get_logger(name: str) -> StructuredLogger:
    """
    Get or create logger for component.
    
    Args:
        name: Logger name (typically component name)
    
    Returns:
        StructuredLogger instance
    """
    if name not in _loggers:
        # Create logger with root configuration
        root_config = _loggers.get("root")
        if root_config:
            # Inherit root configuration
            _loggers[name] = StructuredLogger(
                name=name,
                level=LogLevel.INFO,  # Default, can be overridden
                structured=True,
                console_output=True
            )
        else:
            # Create with defaults
            _loggers[name] = StructuredLogger(
                name=name,
                level=LogLevel.INFO,
                structured=True,
                console_output=True
            )
    
    return _loggers[name]


def read_logs(
    log_file: str,
    filter: Optional[LogFilter] = None,
    limit: int = 1000
) -> list:
    """
    Read and filter logs from file.
    
    Args:
        log_file: Path to log file
        filter: Optional log filter
        limit: Maximum number of logs to return
    
    Returns:
        List of log entries (as dicts if structured, strings otherwise)
    """
    logs = []
    
    try:
        with open(log_file, 'r') as f:
            for line in f:
                if len(logs) >= limit:
                    break
                
                try:
                    # Try to parse as JSON (structured log)
                    log_entry = json.loads(line.strip())
                    
                    # Apply filter if provided
                    if filter:
                        # Create a mock LogRecord for filtering
                        record = logging.LogRecord(
                            name=log_entry.get('logger', ''),
                            level=getattr(logging, log_entry.get('level', 'INFO')),
                            pathname='',
                            lineno=log_entry.get('line', 0),
                            msg=log_entry.get('message', ''),
                            args=(),
                            exc_info=None
                        )
                        record.created = datetime.fromisoformat(
                            log_entry.get('timestamp', datetime.now().isoformat())
                        ).timestamp()
                        
                        if not filter.filter(record):
                            continue
                    
                    logs.append(log_entry)
                    
                except json.JSONDecodeError:
                    # Not a JSON log, treat as plain text
                    if not filter:
                        logs.append({"message": line.strip()})
    
    except FileNotFoundError:
        pass
    
    return logs


def rotate_logs_manually(log_file: str):
    """
    Manually trigger log rotation.
    
    Args:
        log_file: Path to log file to rotate
    """
    try:
        # Find the handler for this file
        for logger in _loggers.values():
            for handler in logger.logger.handlers:
                if isinstance(handler, logging.handlers.RotatingFileHandler):
                    if handler.baseFilename == os.path.abspath(log_file):
                        handler.doRollover()
                        return
        
        # If no handler found, do manual rotation
        log_path = Path(log_file)
        if log_path.exists():
            # Rotate existing backups
            for i in range(4, 0, -1):
                old_file = log_path.with_suffix(f'.log.{i}')
                new_file = log_path.with_suffix(f'.log.{i+1}')
                if old_file.exists():
                    old_file.rename(new_file)
            
            # Move current log to .1
            log_path.rename(log_path.with_suffix('.log.1'))
    
    except Exception as e:
        logging.error(f"Failed to rotate logs: {e}")
