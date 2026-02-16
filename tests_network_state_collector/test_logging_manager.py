"""
Test per LoggingManager - Gestione centralizzata del logging
"""

import pytest
import logging
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch
from network_state_collector.logging_manager import (
    LoggingManager, LoggingConfig, LogLevel, LogFormat, 
    StructuredFormatter, get_logging_manager, setup_logging
)


class TestLoggingConfig:
    """Test per la classe LoggingConfig"""
    
    def test_default_values(self):
        """Test valori di default LoggingConfig"""
        config = LoggingConfig()
        
        assert config.level == LogLevel.INFO
        assert config.format_type == LogFormat.DETAILED
        assert config.console_enabled is True
        assert config.file_enabled is True
        assert config.file_path is None
        assert config.max_file_size == 10 * 1024 * 1024
        assert config.backup_count == 5
        assert config.structured_logging is True
        assert config.include_traceback is True
    
    def test_custom_values(self):
        """Test valori personalizzati LoggingConfig"""
        config = LoggingConfig(
            level=LogLevel.DEBUG,
            format_type=LogFormat.JSON,
            console_enabled=False,
            file_enabled=False,
            file_path="/tmp/test.log",
            max_file_size=5 * 1024 * 1024,
            backup_count=3
        )
        
        assert config.level == LogLevel.DEBUG
        assert config.format_type == LogFormat.JSON
        assert config.console_enabled is False
        assert config.file_enabled is False
        assert config.file_path == "/tmp/test.log"
        assert config.max_file_size == 5 * 1024 * 1024
        assert config.backup_count == 3


class TestStructuredFormatter:
    """Test per la classe StructuredFormatter"""
    
    def test_basic_formatting(self):
        """Test formattazione base"""
        formatter = StructuredFormatter()
        
        # Crea un record di log
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data['level'] == 'INFO'
        assert log_data['logger'] == 'test.logger'
        assert log_data['message'] == 'Test message'
        assert log_data['module'] == 'test_module'
        assert log_data['function'] == 'test_function'
        assert log_data['line'] == 42
        assert 'timestamp' in log_data
    
    def test_formatting_with_extra_fields(self):
        """Test formattazione con campi extra"""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="/test/path.py",
            lineno=42,
            msg="Warning message",
            args=(),
            exc_info=None
        )
        record.module = "test_module"
        record.funcName = "test_function"
        record.component = "test_component"
        record.category = "test_category"
        record.context = {"key": "value"}
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert log_data['component'] == 'test_component'
        assert log_data['category'] == 'test_category'
        assert log_data['context'] == {"key": "value"}
    
    def test_formatting_with_exception(self):
        """Test formattazione con eccezione"""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="/test/path.py",
                lineno=42,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info()  # Cattura l'eccezione corrente
            )
            record.module = "test_module"
            record.funcName = "test_function"
        
        formatted = formatter.format(record)
        log_data = json.loads(formatted)
        
        assert 'exception' in log_data
        assert log_data['exception']['type'] == 'ValueError'
        assert log_data['exception']['message'] == 'Test exception'
        assert 'traceback' in log_data['exception']


class TestLoggingManager:
    """Test per la classe LoggingManager"""
    
    def setup_method(self):
        """Setup per ogni test"""
        # Reset del logging globale
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)
        
        # Crea config di test
        self.config = LoggingConfig(
            level=LogLevel.DEBUG,
            console_enabled=True,
            file_enabled=False
        )
        self.logging_manager = LoggingManager(self.config)
    
    def test_initialization(self):
        """Test inizializzazione LoggingManager"""
        assert self.logging_manager.config == self.config
        # Il LoggingManager crea automaticamente un logger per se stesso
        assert len(self.logging_manager._loggers) >= 0
        assert self.logging_manager._log_stats['info_messages'] >= 0
    
    def test_get_logger(self):
        """Test ottenimento logger"""
        logger = self.logging_manager.get_logger("test.module")
        
        assert logger.name == "test.module"
        assert logger.level == LogLevel.DEBUG.value
        assert "test.module" in self.logging_manager._loggers
        
        # Verifica che ottenere lo stesso logger restituisca la stessa istanza
        logger2 = self.logging_manager.get_logger("test.module")
        assert logger is logger2
    
    def test_get_logger_with_custom_level(self):
        """Test ottenimento logger con livello personalizzato"""
        logger = self.logging_manager.get_logger("test.custom", LogLevel.ERROR)
        
        assert logger.level == LogLevel.ERROR.value
    
    def test_set_level(self):
        """Test impostazione livello logger specifico"""
        logger = self.logging_manager.get_logger("test.module")
        original_level = logger.level
        
        self.logging_manager.set_level("test.module", LogLevel.CRITICAL)
        
        assert logger.level == LogLevel.CRITICAL.value
        assert logger.level != original_level
    
    def test_set_global_level(self):
        """Test impostazione livello globale"""
        logger1 = self.logging_manager.get_logger("test.module1")
        logger2 = self.logging_manager.get_logger("test.module2")
        
        self.logging_manager.set_global_level(LogLevel.WARNING)
        
        assert logger1.level == LogLevel.WARNING.value
        assert logger2.level == LogLevel.WARNING.value
        assert self.logging_manager.config.level == LogLevel.WARNING
    
    def test_file_logging_enable_disable(self):
        """Test abilitazione/disabilitazione logging su file"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Abilita file logging
            self.logging_manager.enable_file_logging(tmp_path)
            
            assert self.logging_manager.config.file_enabled is True
            assert self.logging_manager.config.file_path == tmp_path
            
            # Verifica che il file handler sia stato aggiunto
            root_logger = logging.getLogger()
            file_handlers = [
                h for h in root_logger.handlers 
                if isinstance(h, (logging.FileHandler, logging.handlers.RotatingFileHandler))
            ]
            assert len(file_handlers) > 0
            
            # Disabilita file logging
            self.logging_manager.disable_file_logging()
            
            assert self.logging_manager.config.file_enabled is False
            
            # Verifica che il file handler sia stato rimosso
            file_handlers = [
                h for h in root_logger.handlers 
                if isinstance(h, (logging.FileHandler, logging.handlers.RotatingFileHandler))
            ]
            assert len(file_handlers) == 0
            
        finally:
            # Cleanup
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def test_log_statistics_collection(self):
        """Test raccolta statistiche log"""
        # Reset statistiche prima del test
        self.logging_manager.clear_statistics()
        
        logger = self.logging_manager.get_logger("test.stats")
        
        # Genera alcuni log
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")
        
        stats = self.logging_manager.get_log_statistics()
        
        assert stats['total_messages'] == 5
        assert stats['by_level']['debug_messages'] == 1
        assert stats['by_level']['info_messages'] == 1
        assert stats['by_level']['warning_messages'] == 1
        assert stats['by_level']['error_messages'] == 1
        assert stats['by_level']['critical_messages'] == 1
        assert stats['active_loggers'] >= 1
        assert "test.stats" in stats['logger_names']
    
    def test_clear_statistics(self):
        """Test pulizia statistiche"""
        logger = self.logging_manager.get_logger("test.clear")
        logger.info("Test message")
        
        # Verifica che ci siano statistiche
        stats = self.logging_manager.get_log_statistics()
        initial_total = stats['total_messages']
        
        # Pulisci statistiche
        self.logging_manager.clear_statistics()
        
        # Verifica che siano state pulite
        stats = self.logging_manager.get_log_statistics()
        assert stats['total_messages'] == 0
        assert all(count == 0 for count in stats['by_level'].values())
    
    def test_formatter_creation(self):
        """Test creazione formatter"""
        # Test formatter JSON
        config_json = LoggingConfig(format_type=LogFormat.JSON)
        manager_json = LoggingManager(config_json)
        formatter_json = manager_json._create_formatter()
        assert isinstance(formatter_json, StructuredFormatter)
        
        # Test formatter DETAILED
        config_detailed = LoggingConfig(format_type=LogFormat.DETAILED)
        manager_detailed = LoggingManager(config_detailed)
        formatter_detailed = manager_detailed._create_formatter()
        assert isinstance(formatter_detailed, logging.Formatter)
        assert "%(asctime)s" in formatter_detailed._fmt
        assert "%(funcName)s" in formatter_detailed._fmt
        
        # Test formatter SIMPLE
        config_simple = LoggingConfig(format_type=LogFormat.SIMPLE)
        manager_simple = LoggingManager(config_simple)
        formatter_simple = manager_simple._create_formatter()
        assert isinstance(formatter_simple, logging.Formatter)
        assert "%(asctime)s" in formatter_simple._fmt
        assert "%(funcName)s" not in formatter_simple._fmt


class TestGlobalFunctions:
    """Test per le funzioni globali del modulo"""
    
    def test_get_logging_manager_singleton(self):
        """Test comportamento singleton del LoggingManager globale"""
        # Reset del manager globale
        import network_state_collector.logging_manager as lm
        lm._global_logging_manager = None
        
        manager1 = get_logging_manager()
        manager2 = get_logging_manager()
        
        assert manager1 is manager2
    
    def test_setup_logging(self):
        """Test funzione setup_logging"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Reset del manager globale per il test
            import network_state_collector.logging_manager as lm
            lm._global_logging_manager = None
            
            manager = setup_logging(
                level=LogLevel.WARNING,
                format_type=LogFormat.JSON,
                file_path=tmp_path,
                console_enabled=False
            )
            
            assert manager.config.level == LogLevel.WARNING
            assert manager.config.format_type == LogFormat.JSON
            assert manager.config.file_path == tmp_path
            assert manager.config.console_enabled is False
            assert manager.config.file_enabled is True
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestIntegration:
    """Test di integrazione per LoggingManager"""
    
    def test_end_to_end_logging(self):
        """Test logging end-to-end con file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as tmp_file:
            tmp_path = tmp_file.name
        
        try:
            # Setup logging manager con file
            config = LoggingConfig(
                level=LogLevel.INFO,
                format_type=LogFormat.JSON,
                file_enabled=True,
                file_path=tmp_path,
                console_enabled=False
            )
            manager = LoggingManager(config)
            manager.clear_statistics()  # Reset statistiche
            
            # Ottieni logger e logga messaggi
            logger = manager.get_logger("test.integration")
            logger.info("Test info message", extra={
                'component': 'test_component',
                'context': {'key': 'value'}
            })
            logger.error("Test error message")
            
            # Forza flush dei handler
            for handler in logging.getLogger().handlers:
                handler.flush()
            
            # Verifica che i messaggi siano stati scritti nel file
            with open(tmp_path, 'r') as f:
                content = f.read()
                assert 'Test info message' in content
                assert 'Test error message' in content
                assert 'test_component' in content
            
            # Verifica statistiche
            stats = manager.get_log_statistics()
            assert stats['by_level']['info_messages'] >= 1
            assert stats['by_level']['error_messages'] >= 1
            
        finally:
            # Cleanup
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def test_multiple_loggers_coordination(self):
        """Test coordinamento di multipli logger"""
        manager = LoggingManager(LoggingConfig(level=LogLevel.DEBUG))
        manager.clear_statistics()  # Reset statistiche
        
        # Crea multipli logger
        logger1 = manager.get_logger("module1")
        logger2 = manager.get_logger("module2")
        logger3 = manager.get_logger("module3")
        
        # Logga da tutti i logger
        logger1.debug("Debug from module1")
        logger2.info("Info from module2")
        logger3.warning("Warning from module3")
        
        # Verifica statistiche aggregate
        stats = manager.get_log_statistics()
        assert stats['active_loggers'] >= 3  # Almeno i 3 logger creati
        assert stats['total_messages'] == 3
        assert 'module1' in stats['logger_names']
        assert 'module2' in stats['logger_names']
        assert 'module3' in stats['logger_names']
        
        # Cambia livello globale
        manager.set_global_level(LogLevel.WARNING)
        
        # Verifica che tutti i logger abbiano il nuovo livello
        assert logger1.level == LogLevel.WARNING.value
        assert logger2.level == LogLevel.WARNING.value
        assert logger3.level == LogLevel.WARNING.value