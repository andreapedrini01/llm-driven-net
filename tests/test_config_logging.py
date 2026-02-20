"""Unit tests for configuration and logging systems."""

import unittest
import tempfile
import shutil
import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

from src.config.config_manager import ConfigManager, ConfigSource, ConfigChangeEvent
from src.config.models import SystemConfig, LogLevel
from src.config.centralized_config import CentralizedConfigManager, ConfigOperation
from src.logging.logger import StructuredLogger, LogFilter, setup_logging, read_logs
from src.logging.aggregator import LogAggregator


class TestConfigManager(unittest.TestCase):
    """Test configuration manager."""
    
    def setUp(self):
        """Setup test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.config_file = Path(self.test_dir) / "test_config.yaml"
    
    def tearDown(self):
        """Cleanup test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_default_configuration(self):
        """Test loading default configuration."""
        manager = ConfigManager(config_file=str(self.config_file), enable_hot_reload=False)
        config = manager.get_config()
        
        self.assertIsInstance(config, SystemConfig)
        self.assertEqual(config.ryu.host, "localhost")
        self.assertEqual(config.ryu.port, 8080)
    
    def test_yaml_configuration(self):
        """Test loading configuration from YAML file."""
        # Create test config file
        config_data = {
            "ryu": {
                "host": "test-host",
                "port": 9090
            },
            "api": {
                "port": 9000
            }
        }
        
        import yaml
        with open(self.config_file, 'w') as f:
            yaml.dump(config_data, f)
        
        manager = ConfigManager(config_file=str(self.config_file), enable_hot_reload=False)
        config = manager.get_config()
        
        self.assertEqual(config.ryu.host, "test-host")
        self.assertEqual(config.ryu.port, 9090)
        self.assertEqual(config.api.port, 9000)
    
    def test_environment_variable_override(self):
        """Test environment variable override."""
        os.environ["NORTHBOUND_RYU_HOST"] = "env-host"
        os.environ["NORTHBOUND_RYU_PORT"] = "7070"
        
        try:
            manager = ConfigManager(config_file=str(self.config_file), enable_hot_reload=False)
            config = manager.get_config()
            
            self.assertEqual(config.ryu.host, "env-host")
            self.assertEqual(config.ryu.port, 7070)
        finally:
            del os.environ["NORTHBOUND_RYU_HOST"]
            del os.environ["NORTHBOUND_RYU_PORT"]
    
    def test_api_update(self):
        """Test configuration update via API."""
        manager = ConfigManager(config_file=str(self.config_file), enable_hot_reload=False)
        
        updates = {
            "ryu": {
                "host": "api-updated-host",
                "port": 8888
            }
        }
        
        event = manager.update_from_api(updates)
        
        self.assertTrue(event.applied)
        self.assertIn("ryu.host", event.changes)
        
        config = manager.get_config()
        self.assertEqual(config.ryu.host, "api-updated-host")
        self.assertEqual(config.ryu.port, 8888)
    
    def test_validation(self):
        """Test configuration validation."""
        manager = ConfigManager(config_file=str(self.config_file), enable_hot_reload=False)
        
        # Valid configuration
        valid_config = {"ryu": {"host": "localhost", "port": 8080}}
        is_valid, error = manager.validate_config(valid_config)
        self.assertTrue(is_valid)
        self.assertIsNone(error)
        
        # Invalid configuration (port out of range)
        invalid_config = {"ryu": {"host": "localhost", "port": 99999}}
        is_valid, error = manager.validate_config(invalid_config)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
    
    def test_change_history(self):
        """Test configuration change history."""
        manager = ConfigManager(config_file=str(self.config_file), enable_hot_reload=False)
        
        # Make some changes
        manager.update_from_api({"ryu": {"host": "host1"}})
        manager.update_from_api({"ryu": {"host": "host2"}})
        
        history = manager.get_history(limit=10)
        
        self.assertGreaterEqual(len(history), 2)
        self.assertEqual(history[0]["source"], ConfigSource.API.value)


class TestCentralizedConfigManager(unittest.TestCase):
    """Test centralized configuration manager."""
    
    def setUp(self):
        """Setup test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "config_versions.db"
    
    def tearDown(self):
        """Cleanup test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_create_version(self):
        """Test creating configuration version."""
        manager = CentralizedConfigManager(db_path=str(self.db_path))
        
        config_data = {"ryu": {"host": "localhost", "port": 8080}}
        version = manager.create_version(
            config_data=config_data,
            user="test_user",
            comment="Initial version"
        )
        
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.created_by, "test_user")
        self.assertEqual(version.operation, ConfigOperation.CREATE)
    
    def test_version_history(self):
        """Test version history."""
        manager = CentralizedConfigManager(db_path=str(self.db_path))
        
        # Create multiple versions
        manager.create_version({"version": 1}, "user1", "Version 1")
        manager.create_version({"version": 2}, "user2", "Version 2")
        manager.create_version({"version": 3}, "user3", "Version 3")
        
        history = manager.get_version_history(limit=10)
        
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["version_number"], 3)  # Most recent first
        self.assertEqual(history[2]["version_number"], 1)
    
    def test_rollback(self):
        """Test configuration rollback."""
        manager = CentralizedConfigManager(db_path=str(self.db_path))
        
        # Create versions
        v1 = manager.create_version({"value": "v1"}, "user", "Version 1")
        v2 = manager.create_version({"value": "v2"}, "user", "Version 2")
        v3 = manager.create_version({"value": "v3"}, "user", "Version 3")
        
        # Rollback to version 1
        rollback_version = manager.rollback_to_version(
            version_number=1,
            user="admin",
            comment="Rollback test"
        )
        
        self.assertEqual(rollback_version.operation, ConfigOperation.ROLLBACK)
        self.assertEqual(rollback_version.config_data["value"], "v1")
        self.assertEqual(rollback_version.version_number, 4)  # New version created
    
    def test_audit_trail(self):
        """Test audit trail."""
        manager = CentralizedConfigManager(db_path=str(self.db_path))
        
        # Create versions with different users
        manager.create_version({"v": 1}, "user1", "Change 1", ip_address="192.168.1.1")
        manager.create_version({"v": 2}, "user2", "Change 2", ip_address="192.168.1.2")
        
        # Get audit trail
        audit = manager.get_audit_trail(limit=10)
        
        self.assertEqual(len(audit), 2)
        self.assertEqual(audit[0]["user"], "user2")  # Most recent first
        self.assertEqual(audit[0]["ip_address"], "192.168.1.2")
        
        # Filter by user
        user1_audit = manager.get_audit_trail(user="user1")
        self.assertEqual(len(user1_audit), 1)
        self.assertEqual(user1_audit[0]["user"], "user1")


class TestStructuredLogger(unittest.TestCase):
    """Test structured logger."""
    
    def setUp(self):
        """Setup test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.log_file = Path(self.test_dir) / "test.log"
    
    def tearDown(self):
        """Cleanup test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_structured_logging(self):
        """Test structured JSON logging."""
        logger = StructuredLogger(
            name="test_logger",
            level=LogLevel.INFO,
            structured=True,
            file_path=str(self.log_file),
            file_rotation=False,
            console_output=False
        )
        
        logger.info("Test message", component="test", action="testing")
        
        # Read log file
        with open(self.log_file, 'r') as f:
            log_line = f.readline()
            log_data = json.loads(log_line)
        
        self.assertEqual(log_data["level"], "INFO")
        self.assertEqual(log_data["message"], "Test message")
        self.assertEqual(log_data["component"], "test")
        self.assertEqual(log_data["action"], "testing")
    
    def test_log_rotation(self):
        """Test log file rotation."""
        logger = StructuredLogger(
            name="test_logger",
            level=LogLevel.INFO,
            structured=False,
            file_path=str(self.log_file),
            file_rotation=True,
            max_bytes=100,  # Small size to trigger rotation
            backup_count=2,
            console_output=False
        )
        
        # Write enough logs to trigger rotation
        for i in range(20):
            logger.info(f"Test message {i}" * 10)
        
        # Check that backup files were created
        backup_files = list(Path(self.test_dir).glob("test.log.*"))
        self.assertGreater(len(backup_files), 0)
    
    def test_log_filter(self):
        """Test log filtering."""
        log_filter = LogFilter(
            min_level=LogLevel.WARNING,
            loggers=["test_logger"]
        )
        
        logger = StructuredLogger(
            name="test_logger",
            level=LogLevel.DEBUG,
            structured=False,
            file_path=str(self.log_file),
            console_output=False
        )
        
        logger.add_filter(log_filter)
        
        # These should be filtered out
        logger.debug("Debug message")
        logger.info("Info message")
        
        # These should pass
        logger.warning("Warning message")
        logger.error("Error message")
        
        # Read log file
        with open(self.log_file, 'r') as f:
            lines = f.readlines()
        
        # Only WARNING and ERROR should be logged
        self.assertEqual(len(lines), 2)
        self.assertIn("WARNING", lines[0])
        self.assertIn("ERROR", lines[1])


class TestLogAggregator(unittest.TestCase):
    """Test log aggregator."""
    
    def setUp(self):
        """Setup test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "aggregated_logs.db"
    
    def tearDown(self):
        """Cleanup test environment."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_add_and_query_logs(self):
        """Test adding and querying logs."""
        aggregator = LogAggregator(
            db_path=str(self.db_path),
            flush_interval=1
        )
        
        # Add logs
        aggregator.add_log("INFO", "test_logger", "Test message 1", "instance1")
        aggregator.add_log("ERROR", "test_logger", "Test message 2", "instance1")
        aggregator.add_log("WARNING", "other_logger", "Test message 3", "instance2")
        
        # Wait for flush
        time.sleep(2)
        
        # Query all logs
        logs = aggregator.query_logs(limit=10)
        self.assertEqual(len(logs), 3)
        
        # Query by level
        error_logs = aggregator.query_logs(levels=["ERROR"])
        self.assertEqual(len(error_logs), 1)
        self.assertEqual(error_logs[0]["level"], "ERROR")
        
        # Query by logger
        test_logs = aggregator.query_logs(loggers=["test_logger"])
        self.assertEqual(len(test_logs), 2)
    
    def test_log_statistics(self):
        """Test log statistics."""
        aggregator = LogAggregator(
            db_path=str(self.db_path),
            flush_interval=1
        )
        
        # Add logs
        aggregator.add_log("INFO", "logger1", "Message 1", "instance1")
        aggregator.add_log("INFO", "logger1", "Message 2", "instance1")
        aggregator.add_log("ERROR", "logger2", "Message 3", "instance2")
        
        # Wait for flush
        time.sleep(2)
        
        # Get statistics
        stats = aggregator.get_log_statistics()
        
        self.assertEqual(stats["total_logs"], 3)
        self.assertEqual(stats["logs_by_level"]["INFO"], 2)
        self.assertEqual(stats["logs_by_level"]["ERROR"], 1)
    
    def test_cleanup_old_logs(self):
        """Test cleanup of old logs."""
        aggregator = LogAggregator(
            db_path=str(self.db_path),
            retention_days=1,
            flush_interval=1
        )
        
        # Add logs
        aggregator.add_log("INFO", "test", "Recent log", "instance1")
        
        # Wait for flush
        time.sleep(2)
        
        # Manually insert old log
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        old_date = (datetime.now() - timedelta(days=2)).isoformat()
        cursor.execute('''
            INSERT INTO logs 
            (timestamp, level, logger, message, source_host, source_instance)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (old_date, "INFO", "test", "Old log", "host", "instance"))
        conn.commit()
        conn.close()
        
        # Cleanup
        deleted = aggregator.cleanup_old_logs()
        
        self.assertEqual(deleted, 1)
        
        # Verify only recent log remains
        logs = aggregator.query_logs()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["message"], "Recent log")


if __name__ == '__main__':
    unittest.main()
