"""
Configuration Manager per Network State Collector

Gestisce il caricamento, la validazione e la gestione delle configurazioni
per diversi ambienti (development, staging, production).
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field

from src.models.config import CollectorConfig, RyuConfig, RetryConfig, OutputConfig, CollectionConfig, LoggingConfig
from .error_manager import ErrorManager, ErrorCategory, ErrorSeverity


@dataclass
class ValidationResult:
    """Risultato della validazione della configurazione"""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_error(self, message: str) -> None:
        """Aggiunge un errore di validazione"""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str) -> None:
        """Aggiunge un warning di validazione"""
        self.warnings.append(message)


class ConfigurationManager:
    """
    Gestisce la configurazione del Network State Collector
    
    Supporta:
    - Caricamento da file YAML/JSON
    - Validazione della configurazione
    - Override tramite variabili d'ambiente
    - Configurazioni multiple per ambienti diversi
    - Hot reload della configurazione
    """
    
    def __init__(self, config_dir: str = "config", error_manager: Optional[ErrorManager] = None):
        """
        Inizializza il Configuration Manager
        
        Args:
            config_dir: Directory contenente i file di configurazione
            error_manager: Manager per la gestione degli errori
        """
        self.config_dir = Path(config_dir)
        self.error_manager = error_manager or ErrorManager()
        self.logger = logging.getLogger(__name__)
        
        # Configurazione corrente
        self._current_config: Optional[CollectorConfig] = None
        self._config_file_path: Optional[Path] = None
        self._last_modified: Optional[float] = None
        
        # Cache delle configurazioni per ambiente
        self._config_cache: Dict[str, CollectorConfig] = {}
        
        # Mapping delle variabili d'ambiente
        self._env_mappings = {
            "NSC_RYU_HOST": ("ryu", "host"),
            "NSC_RYU_PORT": ("ryu", "port"),
            "NSC_RYU_TIMEOUT": ("ryu", "timeout"),
            "NSC_RYU_USE_HTTPS": ("ryu", "use_https"),
            "NSC_OUTPUT_DIR": ("output", "directory"),
            "NSC_COLLECTION_INTERVAL": ("collection", "interval"),
            "NSC_COLLECTION_CONTINUOUS": ("collection", "continuous_mode"),
            "NSC_LOG_LEVEL": ("logging", "level"),
            "NSC_LOG_FILE": ("logging", "file_path"),
            "NSC_RETRY_MAX_ATTEMPTS": ("retry", "max_attempts"),
            "NSC_RETRY_INITIAL_DELAY": ("retry", "initial_delay"),
        }
    
    def load_config(self, config_path: Optional[str] = None, environment: str = "development") -> CollectorConfig:
        """
        Carica la configurazione da file
        
        Args:
            config_path: Path specifico del file di configurazione
            environment: Ambiente per cui caricare la configurazione
            
        Returns:
            CollectorConfig: Configurazione caricata e validata
            
        Raises:
            FileNotFoundError: Se il file di configurazione non esiste
            ValueError: Se la configurazione non è valida
        """
        try:
            # Determina il path del file di configurazione
            if config_path:
                file_path = Path(config_path)
            else:
                file_path = self._find_config_file(environment)
            
            if not file_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {file_path}")
            
            # Carica la configurazione dal file
            config = CollectorConfig.load_from_file(str(file_path))
            
            # Applica override dalle variabili d'ambiente
            config = self._apply_environment_overrides(config)
            
            # Valida la configurazione
            validation_result = self.validate_config(config)
            if not validation_result.is_valid:
                error_msg = f"Invalid configuration: {'; '.join(validation_result.errors)}"
                self.error_manager.handle_error(
                    ValueError(error_msg),
                    ErrorCategory.CONFIGURATION,
                    ErrorSeverity.HIGH,
                    "ConfigurationManager",
                    {"config_path": str(file_path), "errors": validation_result.errors}
                )
                raise ValueError(error_msg)
            
            # Log warnings se presenti
            for warning in validation_result.warnings:
                self.logger.warning(f"Configuration warning: {warning}")
            
            # Aggiorna lo stato interno
            self._current_config = config
            self._config_file_path = file_path
            self._last_modified = file_path.stat().st_mtime
            self._config_cache[environment] = config
            
            self.logger.info(f"Configuration loaded successfully from {file_path}")
            return config
            
        except Exception as e:
            self.error_manager.handle_error(
                e,
                ErrorCategory.CONFIGURATION,
                ErrorSeverity.HIGH,
                "ConfigurationManager",
                {"config_path": config_path, "environment": environment}
            )
            raise
    
    def validate_config(self, config: CollectorConfig) -> ValidationResult:
        """
        Valida la configurazione
        
        Args:
            config: Configurazione da validare
            
        Returns:
            ValidationResult: Risultato della validazione
        """
        result = ValidationResult(is_valid=True)
        
        # Validazione configurazione Ryu
        self._validate_ryu_config(config.ryu, result)
        
        # Validazione configurazione retry
        self._validate_retry_config(config.retry, result)
        
        # Validazione configurazione output
        self._validate_output_config(config.output, result)
        
        # Validazione configurazione collection
        self._validate_collection_config(config.collection, result)
        
        # Validazione configurazione logging
        self._validate_logging_config(config.logging, result)
        
        # Validazione generale
        self._validate_general_config(config, result)
        
        return result
    
    def get_ryu_endpoint(self) -> str:
        """
        Restituisce l'endpoint del controller Ryu
        
        Returns:
            str: URL base del controller Ryu
        """
        if not self._current_config:
            raise ValueError("No configuration loaded")
        return self._current_config.ryu.base_url
    
    def get_output_directory(self) -> Path:
        """
        Restituisce la directory di output
        
        Returns:
            Path: Directory di output configurata
        """
        if not self._current_config:
            raise ValueError("No configuration loaded")
        return self._current_config.output.get_output_path()
    
    def get_collection_interval(self) -> float:
        """
        Restituisce l'intervallo di raccolta dati
        
        Returns:
            float: Intervallo in secondi
        """
        if not self._current_config:
            raise ValueError("No configuration loaded")
        return self._current_config.collection.interval
    
    def get_current_config(self) -> CollectorConfig:
        """
        Restituisce la configurazione corrente
        
        Returns:
            CollectorConfig: Configurazione corrente
        """
        if not self._current_config:
            raise ValueError("No configuration loaded")
        return self._current_config
    
    def reload_config(self) -> bool:
        """
        Ricarica la configurazione se il file è stato modificato
        
        Returns:
            bool: True se la configurazione è stata ricaricata
        """
        if not self._config_file_path or not self._last_modified:
            return False
        
        try:
            current_mtime = self._config_file_path.stat().st_mtime
            if current_mtime > self._last_modified:
                self.logger.info("Configuration file changed, reloading...")
                environment = self._current_config.environment if self._current_config else "development"
                self.load_config(str(self._config_file_path), environment)
                return True
        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {e}")
            self.error_manager.handle_error(
                e,
                ErrorCategory.CONFIGURATION,
                ErrorSeverity.MEDIUM,
                "ConfigurationManager",
                {"config_path": str(self._config_file_path)}
            )
        
        return False
    
    def list_available_environments(self) -> List[str]:
        """
        Lista gli ambienti disponibili nella directory di configurazione
        
        Returns:
            List[str]: Lista degli ambienti disponibili
        """
        environments = []
        
        if not self.config_dir.exists():
            return environments
        
        # Cerca file di configurazione
        for file_path in self.config_dir.glob("*.yaml"):
            env_name = file_path.stem
            if env_name not in ["example", "template"]:
                environments.append(env_name)
        
        for file_path in self.config_dir.glob("*.yml"):
            env_name = file_path.stem
            if env_name not in ["example", "template"] and env_name not in environments:
                environments.append(env_name)
        
        for file_path in self.config_dir.glob("*.json"):
            env_name = file_path.stem
            if env_name not in ["example", "template"] and env_name not in environments:
                environments.append(env_name)
        
        return sorted(environments)
    
    def create_environment_config(self, environment: str, base_config: Optional[CollectorConfig] = None) -> CollectorConfig:
        """
        Crea una nuova configurazione per un ambiente
        
        Args:
            environment: Nome dell'ambiente
            base_config: Configurazione base da cui partire
            
        Returns:
            CollectorConfig: Nuova configurazione per l'ambiente
        """
        if base_config is None:
            base_config = CollectorConfig()
        
        # Crea una copia della configurazione base
        config_dict = base_config.to_dict()
        config_dict["environment"] = environment
        
        # Applica modifiche specifiche per ambiente
        if environment == "production":
            config_dict["logging"]["level"] = "INFO"
            config_dict["logging"]["console_output"] = False
            config_dict["collection"]["continuous_mode"] = True
            config_dict["collection"]["interval"] = 10.0
            config_dict["output"]["pretty_print"] = False
            config_dict["output"]["compress_old_files"] = True
        elif environment == "development":
            config_dict["logging"]["level"] = "DEBUG"
            config_dict["logging"]["console_output"] = True
            config_dict["collection"]["continuous_mode"] = False
            config_dict["collection"]["interval"] = 30.0
            config_dict["output"]["pretty_print"] = True
        elif environment == "testing":
            config_dict["logging"]["level"] = "WARNING"
            config_dict["logging"]["file_path"] = None
            config_dict["collection"]["interval"] = 5.0
            config_dict["output"]["directory"] = "test_data"
        
        return CollectorConfig.from_dict(config_dict)
    
    def save_environment_config(self, environment: str, config: CollectorConfig) -> None:
        """
        Salva la configurazione per un ambiente
        
        Args:
            environment: Nome dell'ambiente
            config: Configurazione da salvare
        """
        self.config_dir.mkdir(parents=True, exist_ok=True)
        config_path = self.config_dir / f"{environment}.yaml"
        config.save_to_file(str(config_path), "yaml")
        self.logger.info(f"Configuration saved for environment '{environment}' to {config_path}")
    
    def _find_config_file(self, environment: str) -> Path:
        """Trova il file di configurazione per l'ambiente specificato"""
        # Prova diversi formati di file
        for extension in [".yaml", ".yml", ".json"]:
            config_path = self.config_dir / f"{environment}{extension}"
            if config_path.exists():
                return config_path
        
        # Se non trova il file specifico, prova con development come fallback
        if environment != "development":
            for extension in [".yaml", ".yml", ".json"]:
                config_path = self.config_dir / f"development{extension}"
                if config_path.exists():
                    self.logger.warning(f"Using development config as fallback for environment '{environment}'")
                    return config_path
        
        # Come ultima risorsa, crea il path per il file YAML
        return self.config_dir / f"{environment}.yaml"
    
    def _apply_environment_overrides(self, config: CollectorConfig) -> CollectorConfig:
        """Applica override dalle variabili d'ambiente"""
        config_dict = config.to_dict()
        
        for env_var, (section, key) in self._env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Converti il valore nel tipo appropriato
                converted_value = self._convert_env_value(value, section, key, config_dict)
                if converted_value is not None:
                    config_dict[section][key] = converted_value
                    self.logger.info(f"Applied environment override: {env_var} -> {section}.{key} = {converted_value}")
        
        return CollectorConfig.from_dict(config_dict)
    
    def _convert_env_value(self, value: str, section: str, key: str, config_dict: Dict[str, Any]) -> Any:
        """Converte il valore della variabile d'ambiente nel tipo appropriato"""
        try:
            # Ottieni il tipo del valore originale
            original_value = config_dict.get(section, {}).get(key)
            
            if isinstance(original_value, bool):
                return value.lower() in ("true", "1", "yes", "on")
            elif isinstance(original_value, int):
                return int(value)
            elif isinstance(original_value, float):
                return float(value)
            else:
                return value
        except (ValueError, TypeError) as e:
            self.logger.warning(f"Failed to convert environment variable {section}.{key}={value}: {e}")
            return None
    
    def _validate_ryu_config(self, ryu_config: RyuConfig, result: ValidationResult) -> None:
        """Valida la configurazione Ryu"""
        if not ryu_config.host:
            result.add_error("Ryu host cannot be empty")
        
        if not (1 <= ryu_config.port <= 65535):
            result.add_error(f"Ryu port must be between 1 and 65535, got {ryu_config.port}")
        
        if ryu_config.timeout <= 0:
            result.add_error(f"Ryu timeout must be positive, got {ryu_config.timeout}")
        
        if ryu_config.use_https and not ryu_config.verify_ssl:
            result.add_warning("HTTPS is enabled but SSL verification is disabled")
    
    def _validate_retry_config(self, retry_config: RetryConfig, result: ValidationResult) -> None:
        """Valida la configurazione retry"""
        if retry_config.max_attempts < 1:
            result.add_error(f"Max retry attempts must be at least 1, got {retry_config.max_attempts}")
        
        if retry_config.initial_delay <= 0:
            result.add_error(f"Initial retry delay must be positive, got {retry_config.initial_delay}")
        
        if retry_config.max_delay <= retry_config.initial_delay:
            result.add_error("Max retry delay must be greater than initial delay")
        
        if retry_config.backoff_factor <= 1:
            result.add_error(f"Backoff factor must be greater than 1, got {retry_config.backoff_factor}")
    
    def _validate_output_config(self, output_config: OutputConfig, result: ValidationResult) -> None:
        """Valida la configurazione output"""
        if not output_config.directory:
            result.add_error("Output directory cannot be empty")
        
        if not output_config.filename_pattern:
            result.add_error("Filename pattern cannot be empty")
        
        if "{timestamp}" not in output_config.filename_pattern:
            result.add_warning("Filename pattern should include {timestamp} placeholder")
        
        if output_config.max_history_files < 1:
            result.add_error(f"Max history files must be at least 1, got {output_config.max_history_files}")
        
        # Verifica che la directory sia scrivibile (se esiste)
        output_path = Path(output_config.directory)
        if output_path.exists() and not os.access(output_path, os.W_OK):
            result.add_error(f"Output directory is not writable: {output_path}")
    
    def _validate_collection_config(self, collection_config: CollectionConfig, result: ValidationResult) -> None:
        """Valida la configurazione collection"""
        if collection_config.interval <= 0:
            result.add_error(f"Collection interval must be positive, got {collection_config.interval}")
        
        if collection_config.interval < 1:
            result.add_warning("Collection interval less than 1 second may cause high load")
        
        if collection_config.max_workers < 1:
            result.add_error(f"Max workers must be at least 1, got {collection_config.max_workers}")
        
        if collection_config.max_workers > 20:
            result.add_warning(f"High number of workers ({collection_config.max_workers}) may cause resource issues")
    
    def _validate_logging_config(self, logging_config: LoggingConfig, result: ValidationResult) -> None:
        """Valida la configurazione logging"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if logging_config.level.upper() not in valid_levels:
            result.add_error(f"Invalid log level: {logging_config.level}. Must be one of {valid_levels}")
        
        if logging_config.file_path:
            log_path = Path(logging_config.file_path)
            log_dir = log_path.parent
            if not log_dir.exists():
                try:
                    log_dir.mkdir(parents=True, exist_ok=True)
                except OSError:
                    result.add_error(f"Cannot create log directory: {log_dir}")
            elif not os.access(log_dir, os.W_OK):
                result.add_error(f"Log directory is not writable: {log_dir}")
        
        if logging_config.max_file_size <= 0:
            result.add_error(f"Max file size must be positive, got {logging_config.max_file_size}")
        
        if logging_config.backup_count < 0:
            result.add_error(f"Backup count cannot be negative, got {logging_config.backup_count}")
    
    def _validate_general_config(self, config: CollectorConfig, result: ValidationResult) -> None:
        """Valida la configurazione generale"""
        if not config.environment:
            result.add_error("Environment cannot be empty")
        
        if not config.version:
            result.add_error("Version cannot be empty")
        
        # Verifica compatibilità tra configurazioni
        if config.collection.continuous_mode and config.collection.interval > 300:
            result.add_warning("Long collection interval with continuous mode may not be optimal")
        
        if config.output.compress_old_files and not config.collection.continuous_mode:
            result.add_warning("File compression is enabled but continuous mode is disabled")