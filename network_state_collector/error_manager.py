"""
ErrorManager - Gestione centralizzata degli errori

Implementa la gestione centralizzata degli errori del sistema con retry logic,
categorizzazione degli errori e notifiche per errori critici.
"""

import time
import logging
import traceback
from typing import Dict, List, Any, Optional, Callable, Type
from enum import Enum
from dataclasses import dataclass, field
from llm_integration_module.models.health import HealthStatus, ComponentType


class ErrorSeverity(Enum):
    """Livelli di severità degli errori"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Categorie di errori"""
    CONNECTION = "connection"
    DATA_VALIDATION = "data_validation"
    PROCESSING = "processing"
    CONFIGURATION = "configuration"
    SYSTEM = "system"


@dataclass
class ErrorInfo:
    """Informazioni dettagliate su un errore"""
    timestamp: float
    category: ErrorCategory
    severity: ErrorSeverity
    component: str
    message: str
    exception_type: str
    traceback_info: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    resolved: bool = False


@dataclass
class RetryPolicy:
    """Politica di retry per gestione errori"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


class ErrorManager:
    """
    Gestore centralizzato degli errori del sistema
    
    Fornisce:
    - Gestione centralizzata di tutti gli errori
    - Retry logic configurabile con backoff esponenziale
    - Categorizzazione e prioritizzazione errori
    - Notifiche per errori critici
    - Statistiche e monitoraggio errori
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Inizializza l'ErrorManager
        
        Args:
            logger: Logger personalizzato (opzionale)
        """
        self.logger = logger or logging.getLogger(__name__)
        
        # Storico errori
        self._error_history: List[ErrorInfo] = []
        self._max_history_size = 1000
        
        # Statistiche errori
        self._error_stats: Dict[str, int] = {
            'total_errors': 0,
            'critical_errors': 0,
            'resolved_errors': 0,
            'retry_attempts': 0
        }
        
        # Politiche di retry per categoria
        self._retry_policies: Dict[ErrorCategory, RetryPolicy] = {
            ErrorCategory.CONNECTION: RetryPolicy(max_attempts=5, base_delay=1.0),
            ErrorCategory.DATA_VALIDATION: RetryPolicy(max_attempts=2, base_delay=0.5),
            ErrorCategory.PROCESSING: RetryPolicy(max_attempts=3, base_delay=1.0),
            ErrorCategory.CONFIGURATION: RetryPolicy(max_attempts=1, base_delay=0.0),
            ErrorCategory.SYSTEM: RetryPolicy(max_attempts=2, base_delay=2.0)
        }
        
        # Callback per notifiche errori critici
        self._critical_error_callbacks: List[Callable[[ErrorInfo], None]] = []
        
        self.logger.info("ErrorManager initialized")
    
    def handle_error(
        self,
        exception: Exception,
        category: ErrorCategory,
        severity: ErrorSeverity,
        component: str,
        context: Optional[Dict[str, Any]] = None,
        should_retry: bool = True
    ) -> ErrorInfo:
        """
        Gestisce un errore del sistema
        
        Args:
            exception: L'eccezione da gestire
            category: Categoria dell'errore
            severity: Severità dell'errore
            component: Componente che ha generato l'errore
            context: Contesto aggiuntivo (opzionale)
            should_retry: Se l'errore dovrebbe essere soggetto a retry
            
        Returns:
            ErrorInfo: Informazioni sull'errore gestito
        """
        error_info = ErrorInfo(
            timestamp=time.time(),
            category=category,
            severity=severity,
            component=component,
            message=str(exception),
            exception_type=type(exception).__name__,
            traceback_info=traceback.format_exc(),
            context=context or {}
        )
        
        # Registra l'errore
        self._record_error(error_info)
        
        # Log dell'errore
        self._log_error(error_info)
        
        # Gestione errori critici
        if severity == ErrorSeverity.CRITICAL:
            self._handle_critical_error(error_info)
        
        return error_info
    
    def retry_with_backoff(
        self,
        operation: Callable[[], Any],
        category: ErrorCategory,
        component: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Esegue un'operazione con retry e backoff esponenziale
        
        Args:
            operation: Funzione da eseguire
            category: Categoria dell'operazione
            component: Componente che esegue l'operazione
            context: Contesto aggiuntivo
            
        Returns:
            Risultato dell'operazione
            
        Raises:
            Exception: L'ultima eccezione se tutti i tentativi falliscono
        """
        policy = self._retry_policies.get(category, RetryPolicy())
        last_exception = None
        
        for attempt in range(policy.max_attempts):
            try:
                result = operation()
                
                # Se c'erano stati errori precedenti, segna come risolto
                if attempt > 0:
                    self._error_stats['resolved_errors'] += 1
                    self.logger.info(
                        f"Operation succeeded after {attempt} retries",
                        extra={
                            'component': component,
                            'category': category.value,
                            'attempt': attempt + 1
                        }
                    )
                
                return result
                
            except Exception as e:
                last_exception = e
                self._error_stats['retry_attempts'] += 1
                
                # Se è l'ultimo tentativo, gestisci l'errore
                if attempt == policy.max_attempts - 1:
                    self.handle_error(
                        e, category, ErrorSeverity.HIGH, component, context, False
                    )
                    break
                
                # Calcola delay per il prossimo tentativo
                delay = self._calculate_backoff_delay(policy, attempt)
                
                self.logger.warning(
                    f"Operation failed, retrying in {delay:.1f}s (attempt {attempt + 1}/{policy.max_attempts})",
                    extra={
                        'component': component,
                        'category': category.value,
                        'error': str(e),
                        'attempt': attempt + 1,
                        'delay': delay
                    }
                )
                
                time.sleep(delay)
        
        # Se arriviamo qui, tutti i tentativi sono falliti
        raise last_exception
    
    def set_retry_policy(self, category: ErrorCategory, policy: RetryPolicy) -> None:
        """
        Imposta la politica di retry per una categoria
        
        Args:
            category: Categoria di errori
            policy: Nuova politica di retry
        """
        self._retry_policies[category] = policy
        self.logger.info(f"Updated retry policy for {category.value}: {policy}")
    
    def add_critical_error_callback(self, callback: Callable[[ErrorInfo], None]) -> None:
        """
        Aggiunge un callback per errori critici
        
        Args:
            callback: Funzione da chiamare per errori critici
        """
        self._critical_error_callbacks.append(callback)
        self.logger.info("Added critical error callback")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Restituisce statistiche sugli errori
        
        Returns:
            Dizionario con statistiche errori
        """
        recent_errors = [
            e for e in self._error_history 
            if time.time() - e.timestamp < 3600  # Ultime ore
        ]
        
        error_by_category = {}
        error_by_severity = {}
        
        for error in recent_errors:
            category = error.category.value
            severity = error.severity.value
            
            error_by_category[category] = error_by_category.get(category, 0) + 1
            error_by_severity[severity] = error_by_severity.get(severity, 0) + 1
        
        return {
            'total_errors': self._error_stats['total_errors'],
            'critical_errors': self._error_stats['critical_errors'],
            'resolved_errors': self._error_stats['resolved_errors'],
            'retry_attempts': self._error_stats['retry_attempts'],
            'recent_errors_count': len(recent_errors),
            'errors_by_category': error_by_category,
            'errors_by_severity': error_by_severity,
            'history_size': len(self._error_history)
        }
    
    def get_recent_errors(self, hours: int = 1) -> List[ErrorInfo]:
        """
        Restituisce errori recenti
        
        Args:
            hours: Numero di ore da considerare
            
        Returns:
            Lista di errori recenti
        """
        cutoff_time = time.time() - (hours * 3600)
        return [e for e in self._error_history if e.timestamp >= cutoff_time]
    
    def clear_error_history(self) -> None:
        """Pulisce lo storico degli errori"""
        self._error_history.clear()
        self._error_stats = {
            'total_errors': 0,
            'critical_errors': 0,
            'resolved_errors': 0,
            'retry_attempts': 0
        }
        self.logger.info("Error history cleared")
    
    def _record_error(self, error_info: ErrorInfo) -> None:
        """Registra un errore nello storico"""
        self._error_history.append(error_info)
        
        # Mantieni dimensione storico sotto controllo
        if len(self._error_history) > self._max_history_size:
            self._error_history = self._error_history[-self._max_history_size:]
        
        # Aggiorna statistiche
        self._error_stats['total_errors'] += 1
        if error_info.severity == ErrorSeverity.CRITICAL:
            self._error_stats['critical_errors'] += 1
    
    def _log_error(self, error_info: ErrorInfo) -> None:
        """Logga un errore con il livello appropriato"""
        log_data = {
            'component': error_info.component,
            'category': error_info.category.value,
            'severity': error_info.severity.value,
            'exception_type': error_info.exception_type,
            'context': error_info.context
        }
        
        if error_info.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(
                f"CRITICAL ERROR in {error_info.component}: {error_info.message}",
                extra=log_data
            )
        elif error_info.severity == ErrorSeverity.HIGH:
            self.logger.error(
                f"ERROR in {error_info.component}: {error_info.message}",
                extra=log_data
            )
        elif error_info.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(
                f"WARNING in {error_info.component}: {error_info.message}",
                extra=log_data
            )
        else:
            self.logger.info(
                f"INFO in {error_info.component}: {error_info.message}",
                extra=log_data
            )
    
    def _handle_critical_error(self, error_info: ErrorInfo) -> None:
        """Gestisce errori critici con notifiche"""
        # Chiama tutti i callback registrati
        for callback in self._critical_error_callbacks:
            try:
                callback(error_info)
            except Exception as e:
                self.logger.error(f"Error in critical error callback: {e}")
    
    def _calculate_backoff_delay(self, policy: RetryPolicy, attempt: int) -> float:
        """
        Calcola il delay per il backoff esponenziale
        
        Args:
            policy: Politica di retry
            attempt: Numero del tentativo (0-based)
            
        Returns:
            Delay in secondi
        """
        delay = policy.base_delay * (policy.exponential_base ** attempt)
        delay = min(delay, policy.max_delay)
        
        # Aggiungi jitter se abilitato
        if policy.jitter:
            jitter_range = delay * 0.1  # 10% di jitter
            delay += (2 * jitter_range * (0.5 - time.time() % 1))
        
        return max(0, delay)