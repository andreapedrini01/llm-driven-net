"""
LoggingManager - Gestione centralizzata del logging

Implementa la configurazione e gestione centralizzata del logging del sistema
con livelli configurabili, formattazione strutturata e rotazione dei log.
"""

import os
import sys
import logging
import logging.handlers
import json
import time
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from pathlib import Path


class LogLevel(Enum):
    """Livelli di logging supportati"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class LogFormat(Enum):
    """Formati di logging supportati"""
    SIMPLE = "simple"
    DETAILED = "detailed"
    JSON = "json"


@dataclass
class LoggingConfig:
    """Configurazione del sistema di logging"""
    level: LogLevel = LogLevel.INFO
    format_type: LogFormat = LogFormat.DETAILED
    console_enabled: bool = True
    file_enabled: bool = True
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    structured_logging: bool = True
    include_traceback: bool = True


class StructuredFormatter(logging.Formatter):
    """Formatter per logging strutturato con JSON"""
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Formatta il record di log in formato JSON strutturato
        
        Args:
            record: Record di log da formattare
            
        Returns:
            Stringa JSON formattata
        """
        log_data = {
            'timestamp': time.time(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Aggiungi informazioni extra se presenti
        if hasattr(record, 'component'):
            log_data['component'] = record.component
        if hasattr(record, 'category'):
            log_data['category'] = record.category
        if hasattr(record, 'context'):
            log_data['context'] = record.context
        
        # Aggiungi traceback per errori
        if record.exc_info and record.exc_info != (None, None, None):
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }
        
        return json.dumps(log_data, default=str, ensure_ascii=False)


class LoggingManager:
    """
    Gestore centralizzato del logging del sistema
    
    Fornisce:
    - Configurazione centralizzata di tutti i logger
    - Formattazione strutturata dei log
    - Rotazione automatica dei file di log
    - Livelli di logging configurabili per componente
    - Metriche di logging per monitoraggio
    """
    
    def __init__(self, config: Optional[LoggingConfig] = None):
        """
        Inizializza il LoggingManager
        
        Args:
            config: Configurazione del logging (opzionale)
        """
        self.config = config or LoggingConfig()
        self._loggers: Dict[str, logging.Logger] = {}
        self._log_stats: Dict[str, int] = {
            'debug_messages': 0,
            'info_messages': 0,
            'warning_messages': 0,
            'error_messages': 0,
            'critical_messages': 0
        }
        
        # Configura il logging di base
        self._setup_root_logger()
        
        # Logger principale per il manager
        self.logger = self.get_logger(__name__)
        self.logger.info("LoggingManager initialized", extra={
            'component': 'LoggingManager',
            'config': {
                'level': self.config.level.name,
                'format': self.config.format_type.value,
                'console_enabled': self.config.console_enabled,
                'file_enabled': self.config.file_enabled
            }
        })
    
    def get_logger(self, name: str, level: Optional[LogLevel] = None) -> logging.Logger:
        """
        Ottiene o crea un logger configurato
        
        Args:
            name: Nome del logger
            level: Livello di logging specifico (opzionale)
            
        Returns:
            Logger configurato
        """
        if name not in self._loggers:
            logger = logging.getLogger(name)
            
            # Imposta il livello
            log_level = level or self.config.level
            logger.setLevel(log_level.value)
            
            # Aggiungi handler personalizzato per statistiche
            logger.addHandler(self._create_stats_handler())
            
            self._loggers[name] = logger
        
        return self._loggers[name]
    
    def set_level(self, logger_name: str, level: LogLevel) -> None:
        """
        Imposta il livello di logging per un logger specifico
        
        Args:
            logger_name: Nome del logger
            level: Nuovo livello di logging
        """
        if logger_name in self._loggers:
            self._loggers[logger_name].setLevel(level.value)
            self.logger.info(f"Updated log level for {logger_name} to {level.name}")
    
    def set_global_level(self, level: LogLevel) -> None:
        """
        Imposta il livello di logging globale
        
        Args:
            level: Nuovo livello di logging globale
        """
        self.config.level = level
        
        # Aggiorna tutti i logger esistenti
        for logger in self._loggers.values():
            logger.setLevel(level.value)
        
        # Aggiorna il root logger
        logging.getLogger().setLevel(level.value)
        
        self.logger.info(f"Updated global log level to {level.name}")
    
    def enable_file_logging(self, file_path: str) -> None:
        """
        Abilita il logging su file
        
        Args:
            file_path: Percorso del file di log
        """
        self.config.file_enabled = True
        self.config.file_path = file_path
        
        # Riconfigura il root logger
        self._setup_root_logger()
        
        self.logger.info(f"File logging enabled: {file_path}")
    
    def disable_file_logging(self) -> None:
        """Disabilita il logging su file"""
        self.config.file_enabled = False
        
        # Rimuovi handler file dal root logger
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            if isinstance(handler, (logging.FileHandler, logging.handlers.RotatingFileHandler)):
                root_logger.removeHandler(handler)
                handler.close()
        
        self.logger.info("File logging disabled")
    
    def get_log_statistics(self) -> Dict[str, Any]:
        """
        Restituisce statistiche sui log
        
        Returns:
            Dizionario con statistiche di logging
        """
        total_messages = sum(self._log_stats.values())
        
        return {
            'total_messages': total_messages,
            'by_level': self._log_stats.copy(),
            'active_loggers': len(self._loggers),
            'logger_names': list(self._loggers.keys()),
            'config': {
                'level': self.config.level.name,
                'format': self.config.format_type.value,
                'console_enabled': self.config.console_enabled,
                'file_enabled': self.config.file_enabled,
                'file_path': self.config.file_path
            }
        }
    
    def clear_statistics(self) -> None:
        """Pulisce le statistiche di logging"""
        self._log_stats = {
            'debug_messages': 0,
            'info_messages': 0,
            'warning_messages': 0,
            'error_messages': 0,
            'critical_messages': 0
        }
        self.logger.info("Log statistics cleared")
    
    def _setup_root_logger(self) -> None:
        """Configura il root logger del sistema"""
        root_logger = logging.getLogger()
        
        # Rimuovi handler esistenti
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Imposta livello
        root_logger.setLevel(self.config.level.value)
        
        # Configura formatter
        formatter = self._create_formatter()
        
        # Handler console
        if self.config.console_enabled:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(self.config.level.value)
            root_logger.addHandler(console_handler)
        
        # Handler file
        if self.config.file_enabled and self.config.file_path:
            self._setup_file_handler(root_logger, formatter)
    
    def _setup_file_handler(self, logger: logging.Logger, formatter: logging.Formatter) -> None:
        """
        Configura l'handler per il logging su file
        
        Args:
            logger: Logger da configurare
            formatter: Formatter da utilizzare
        """
        # Crea directory se non esiste
        file_path = Path(self.config.file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Usa RotatingFileHandler per gestire la rotazione
        file_handler = logging.handlers.RotatingFileHandler(
            filename=self.config.file_path,
            maxBytes=self.config.max_file_size,
            backupCount=self.config.backup_count,
            encoding='utf-8'
        )
        
        file_handler.setFormatter(formatter)
        file_handler.setLevel(self.config.level.value)
        logger.addHandler(file_handler)
    
    def _create_formatter(self) -> logging.Formatter:
        """
        Crea il formatter appropriato basato sulla configurazione
        
        Returns:
            Formatter configurato
        """
        if self.config.format_type == LogFormat.JSON:
            return StructuredFormatter()
        elif self.config.format_type == LogFormat.DETAILED:
            return logging.Formatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:  # SIMPLE
            return logging.Formatter(
                fmt='%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
    
    def _create_stats_handler(self) -> logging.Handler:
        """
        Crea un handler per raccogliere statistiche sui log
        
        Returns:
            Handler per statistiche
        """
        class StatsHandler(logging.Handler):
            def __init__(self, stats_dict: Dict[str, int]):
                super().__init__()
                self.stats = stats_dict
                self.setLevel(logging.DEBUG)  # Cattura tutti i livelli
            
            def emit(self, record: logging.LogRecord) -> None:
                level_name = record.levelname.lower()
                key = f"{level_name}_messages"
                if key in self.stats:
                    self.stats[key] += 1
        
        return StatsHandler(self._log_stats)


# Istanza globale del LoggingManager
_global_logging_manager: Optional[LoggingManager] = None


def get_logging_manager(config: Optional[LoggingConfig] = None) -> LoggingManager:
    """
    Ottiene l'istanza globale del LoggingManager
    
    Args:
        config: Configurazione del logging (solo al primo utilizzo)
        
    Returns:
        Istanza del LoggingManager
    """
    global _global_logging_manager
    
    if _global_logging_manager is None:
        _global_logging_manager = LoggingManager(config)
    elif config is not None:
        # Se viene passata una nuova config, aggiorna quella esistente
        _global_logging_manager.config = config
        _global_logging_manager._setup_root_logger()
    
    return _global_logging_manager


def setup_logging(
    level: LogLevel = LogLevel.INFO,
    format_type: LogFormat = LogFormat.DETAILED,
    file_path: Optional[str] = None,
    console_enabled: bool = True
) -> LoggingManager:
    """
    Configura il sistema di logging del progetto
    
    Args:
        level: Livello di logging
        format_type: Tipo di formattazione
        file_path: Percorso file di log (opzionale)
        console_enabled: Se abilitare output su console
        
    Returns:
        Istanza del LoggingManager configurato
    """
    config = LoggingConfig(
        level=level,
        format_type=format_type,
        console_enabled=console_enabled,
        file_enabled=file_path is not None,
        file_path=file_path
    )
    
    return get_logging_manager(config)