"""
Test per ErrorManager - Gestione centralizzata degli errori
"""

import pytest
import time
import logging
from unittest.mock import Mock, patch
from network_state_collector.error_manager import (
    ErrorManager, ErrorSeverity, ErrorCategory, ErrorInfo, RetryPolicy
)


class TestErrorManager:
    """Test per la classe ErrorManager"""
    
    def setup_method(self):
        """Setup per ogni test"""
        self.error_manager = ErrorManager()
    
    def test_initialization(self):
        """Test inizializzazione ErrorManager"""
        assert self.error_manager is not None
        assert len(self.error_manager._error_history) == 0
        assert self.error_manager._error_stats['total_errors'] == 0
        assert ErrorCategory.CONNECTION in self.error_manager._retry_policies
    
    def test_handle_error_basic(self):
        """Test gestione errore base"""
        exception = ValueError("Test error")
        
        error_info = self.error_manager.handle_error(
            exception=exception,
            category=ErrorCategory.DATA_VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            component="test_component"
        )
        
        assert error_info.message == "Test error"
        assert error_info.category == ErrorCategory.DATA_VALIDATION
        assert error_info.severity == ErrorSeverity.MEDIUM
        assert error_info.component == "test_component"
        assert error_info.exception_type == "ValueError"
        assert error_info.timestamp > 0
        
        # Verifica che l'errore sia stato registrato
        assert len(self.error_manager._error_history) == 1
        assert self.error_manager._error_stats['total_errors'] == 1
    
    def test_handle_critical_error(self):
        """Test gestione errore critico"""
        callback_called = False
        error_received = None
        
        def critical_callback(error_info: ErrorInfo):
            nonlocal callback_called, error_received
            callback_called = True
            error_received = error_info
        
        self.error_manager.add_critical_error_callback(critical_callback)
        
        exception = RuntimeError("Critical error")
        error_info = self.error_manager.handle_error(
            exception=exception,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            component="critical_component"
        )
        
        assert callback_called
        assert error_received == error_info
        assert self.error_manager._error_stats['critical_errors'] == 1
    
    def test_retry_with_backoff_success(self):
        """Test retry con successo al secondo tentativo"""
        call_count = 0
        
        def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("First attempt fails")
            return "success"
        
        result = self.error_manager.retry_with_backoff(
            operation=failing_operation,
            category=ErrorCategory.CONNECTION,
            component="test_component"
        )
        
        assert result == "success"
        assert call_count == 2
        assert self.error_manager._error_stats['resolved_errors'] == 1
    
    def test_retry_with_backoff_all_fail(self):
        """Test retry con tutti i tentativi falliti"""
        call_count = 0
        
        def always_failing_operation():
            nonlocal call_count
            call_count += 1
            raise ConnectionError(f"Attempt {call_count} failed")
        
        with pytest.raises(ConnectionError):
            self.error_manager.retry_with_backoff(
                operation=always_failing_operation,
                category=ErrorCategory.CONNECTION,
                component="test_component"
            )
        
        # Verifica che siano stati fatti tutti i tentativi
        policy = self.error_manager._retry_policies[ErrorCategory.CONNECTION]
        assert call_count == policy.max_attempts
        
        # Verifica che l'errore finale sia stato registrato
        assert len(self.error_manager._error_history) == 1
        assert self.error_manager._error_stats['total_errors'] == 1
    
    @patch('time.sleep')
    def test_backoff_delay_calculation(self, mock_sleep):
        """Test calcolo delay per backoff esponenziale"""
        def always_failing():
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError):
            self.error_manager.retry_with_backoff(
                operation=always_failing,
                category=ErrorCategory.CONNECTION,
                component="test"
            )
        
        # Verifica che sleep sia stato chiamato con delay crescenti
        assert mock_sleep.call_count > 0
        
        # Il primo delay dovrebbe essere circa 1.0 (base_delay)
        first_delay = mock_sleep.call_args_list[0][0][0]
        assert 0.9 <= first_delay <= 1.1  # Con jitter può variare
    
    def test_set_retry_policy(self):
        """Test impostazione politica retry personalizzata"""
        custom_policy = RetryPolicy(
            max_attempts=10,
            base_delay=0.5,
            max_delay=30.0
        )
        
        self.error_manager.set_retry_policy(ErrorCategory.PROCESSING, custom_policy)
        
        stored_policy = self.error_manager._retry_policies[ErrorCategory.PROCESSING]
        assert stored_policy.max_attempts == 10
        assert stored_policy.base_delay == 0.5
        assert stored_policy.max_delay == 30.0
    
    def test_error_statistics(self):
        """Test statistiche errori"""
        # Genera alcuni errori
        self.error_manager.handle_error(
            ValueError("Error 1"), ErrorCategory.DATA_VALIDATION, 
            ErrorSeverity.LOW, "comp1"
        )
        self.error_manager.handle_error(
            RuntimeError("Error 2"), ErrorCategory.SYSTEM, 
            ErrorSeverity.CRITICAL, "comp2"
        )
        self.error_manager.handle_error(
            ConnectionError("Error 3"), ErrorCategory.CONNECTION, 
            ErrorSeverity.HIGH, "comp3"
        )
        
        stats = self.error_manager.get_error_statistics()
        
        assert stats['total_errors'] == 3
        assert stats['critical_errors'] == 1
        assert stats['recent_errors_count'] == 3
        assert 'data_validation' in stats['errors_by_category']
        assert 'critical' in stats['errors_by_severity']
    
    def test_recent_errors(self):
        """Test recupero errori recenti"""
        # Errore recente
        self.error_manager.handle_error(
            ValueError("Recent error"), ErrorCategory.DATA_VALIDATION,
            ErrorSeverity.MEDIUM, "comp1"
        )
        
        # Simula errore vecchio modificando timestamp
        old_error = ErrorInfo(
            timestamp=time.time() - 7200,  # 2 ore fa
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.LOW,
            component="comp2",
            message="Old error",
            exception_type="RuntimeError"
        )
        self.error_manager._error_history.append(old_error)
        
        recent_errors = self.error_manager.get_recent_errors(hours=1)
        
        assert len(recent_errors) == 1
        assert recent_errors[0].message == "Recent error"
    
    def test_clear_error_history(self):
        """Test pulizia storico errori"""
        # Genera alcuni errori
        for i in range(3):
            self.error_manager.handle_error(
                ValueError(f"Error {i}"), ErrorCategory.DATA_VALIDATION,
                ErrorSeverity.LOW, f"comp{i}"
            )
        
        assert len(self.error_manager._error_history) == 3
        assert self.error_manager._error_stats['total_errors'] == 3
        
        self.error_manager.clear_error_history()
        
        assert len(self.error_manager._error_history) == 0
        assert self.error_manager._error_stats['total_errors'] == 0
    
    def test_error_history_size_limit(self):
        """Test limite dimensione storico errori"""
        # Imposta limite basso per il test
        self.error_manager._max_history_size = 5
        
        # Genera più errori del limite
        for i in range(10):
            self.error_manager.handle_error(
                ValueError(f"Error {i}"), ErrorCategory.DATA_VALIDATION,
                ErrorSeverity.LOW, f"comp{i}"
            )
        
        # Verifica che lo storico sia limitato
        assert len(self.error_manager._error_history) == 5
        
        # Verifica che siano mantenuti gli errori più recenti
        messages = [e.message for e in self.error_manager._error_history]
        assert "Error 9" in messages
        assert "Error 0" not in messages
    
    def test_error_context(self):
        """Test contesto aggiuntivo negli errori"""
        context = {
            'user_id': 'test_user',
            'operation': 'data_processing',
            'input_size': 1024
        }
        
        error_info = self.error_manager.handle_error(
            exception=ValueError("Context test"),
            category=ErrorCategory.PROCESSING,
            severity=ErrorSeverity.MEDIUM,
            component="processor",
            context=context
        )
        
        assert error_info.context == context
        assert error_info.context['user_id'] == 'test_user'
    
    def test_multiple_critical_callbacks(self):
        """Test multipli callback per errori critici"""
        callback1_called = False
        callback2_called = False
        
        def callback1(error_info):
            nonlocal callback1_called
            callback1_called = True
        
        def callback2(error_info):
            nonlocal callback2_called
            callback2_called = True
        
        self.error_manager.add_critical_error_callback(callback1)
        self.error_manager.add_critical_error_callback(callback2)
        
        self.error_manager.handle_error(
            RuntimeError("Critical test"),
            ErrorCategory.SYSTEM,
            ErrorSeverity.CRITICAL,
            "test_component"
        )
        
        assert callback1_called
        assert callback2_called


class TestRetryPolicy:
    """Test per la classe RetryPolicy"""
    
    def test_default_values(self):
        """Test valori di default RetryPolicy"""
        policy = RetryPolicy()
        
        assert policy.max_attempts == 3
        assert policy.base_delay == 1.0
        assert policy.max_delay == 60.0
        assert policy.exponential_base == 2.0
        assert policy.jitter is True
    
    def test_custom_values(self):
        """Test valori personalizzati RetryPolicy"""
        policy = RetryPolicy(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=1.5,
            jitter=False
        )
        
        assert policy.max_attempts == 5
        assert policy.base_delay == 0.5
        assert policy.max_delay == 30.0
        assert policy.exponential_base == 1.5
        assert policy.jitter is False


class TestErrorInfo:
    """Test per la classe ErrorInfo"""
    
    def test_error_info_creation(self):
        """Test creazione ErrorInfo"""
        timestamp = time.time()
        context = {'key': 'value'}
        
        error_info = ErrorInfo(
            timestamp=timestamp,
            category=ErrorCategory.CONNECTION,
            severity=ErrorSeverity.HIGH,
            component="test_component",
            message="Test message",
            exception_type="ConnectionError",
            context=context,
            retry_count=2
        )
        
        assert error_info.timestamp == timestamp
        assert error_info.category == ErrorCategory.CONNECTION
        assert error_info.severity == ErrorSeverity.HIGH
        assert error_info.component == "test_component"
        assert error_info.message == "Test message"
        assert error_info.exception_type == "ConnectionError"
        assert error_info.context == context
        assert error_info.retry_count == 2
        assert error_info.resolved is False
    
    def test_error_info_defaults(self):
        """Test valori di default ErrorInfo"""
        error_info = ErrorInfo(
            timestamp=time.time(),
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.MEDIUM,
            component="test",
            message="test",
            exception_type="Exception"
        )
        
        assert error_info.traceback_info is None
        assert error_info.context == {}
        assert error_info.retry_count == 0
        assert error_info.resolved is False