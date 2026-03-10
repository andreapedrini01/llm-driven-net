"""
Simple Configuration Loader
Loads configuration from a single YAML file without complex distributed config systems
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SystemConfig:
    """System configuration data structure."""
    comnetsemu_host: str = "localhost"
    comnetsemu_port: int = 6653
    max_retries: int = 3
    retry_delay: float = 2.0
    timeout_seconds: int = 30
    log_level: str = "INFO"
    history_dir: str = "data/history"
    actions_file: str = "logs/actions.jsonl"


class ConfigLoader:
    """
    Simple configuration loader for YAML files.
    
    Responsibilities:
    - Load configuration from YAML file
    - Validate configuration parameters
    - Provide default values
    
    Does NOT depend on:
    - Distributed configuration systems
    - Redis or etcd
    - Complex configuration management
    """
    
    def __init__(self, config_path: str = "config.yaml"):
        """
        Initialize configuration loader.
        
        Args:
            config_path: Path to configuration file
        """
        self.logger = logging.getLogger("ConfigLoader")
        self.config_path = Path(config_path)
        self.config = None
    
    def load(self) -> SystemConfig:
        """
        Load configuration from file.
        
        Returns:
            SystemConfig object with loaded configuration
        """
        try:
            if not self.config_path.exists():
                self.logger.warning(f"Config file {self.config_path} not found, using defaults")
                return SystemConfig()
            
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            if not config_data:
                self.logger.warning("Empty config file, using defaults")
                return SystemConfig()
            
            # Extract configuration values with defaults
            self.config = SystemConfig(
                comnetsemu_host=config_data.get("comnetsemu_host", "localhost"),
                comnetsemu_port=config_data.get("comnetsemu_port", 6653),
                max_retries=config_data.get("max_retries", 3),
                retry_delay=config_data.get("retry_delay", 2.0),
                timeout_seconds=config_data.get("timeout_seconds", 30),
                log_level=config_data.get("log_level", "INFO"),
                history_dir=config_data.get("history_dir", "data/history"),
                actions_file=config_data.get("actions_file", "logs/actions.jsonl")
            )
            
            # Validate configuration
            validation_result = self.validate(self.config)
            if not validation_result["is_valid"]:
                self.logger.error(f"Invalid configuration: {validation_result['errors']}")
                raise ValueError(f"Configuration validation failed: {validation_result['errors']}")
            
            if validation_result["warnings"]:
                for warning in validation_result["warnings"]:
                    self.logger.warning(warning)
            
            self.logger.info(f"Configuration loaded successfully from {self.config_path}")
            return self.config
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise
    
    def validate(self, config: SystemConfig) -> Dict[str, Any]:
        """
        Validate configuration parameters.
        
        Args:
            config: SystemConfig to validate
            
        Returns:
            Dictionary with validation results
        """
        errors = []
        warnings = []
        
        # Validate ComnetsEMU host
        if not config.comnetsemu_host:
            errors.append("comnetsemu_host cannot be empty")
        
        # Validate ComnetsEMU port
        if not isinstance(config.comnetsemu_port, int) or config.comnetsemu_port < 1 or config.comnetsemu_port > 65535:
            errors.append("comnetsemu_port must be between 1 and 65535")
        
        # Validate max_retries
        if not isinstance(config.max_retries, int) or config.max_retries < 0:
            errors.append("max_retries must be a non-negative integer")
        
        if config.max_retries > 10:
            warnings.append("max_retries > 10 may cause long delays")
        
        # Validate retry_delay
        if not isinstance(config.retry_delay, (int, float)) or config.retry_delay < 0:
            errors.append("retry_delay must be a non-negative number")
        
        # Validate timeout_seconds
        if not isinstance(config.timeout_seconds, int) or config.timeout_seconds < 1:
            errors.append("timeout_seconds must be a positive integer")
        
        # Validate log_level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if config.log_level.upper() not in valid_log_levels:
            errors.append(f"log_level must be one of {valid_log_levels}")
        
        # Validate paths
        if not config.history_dir:
            errors.append("history_dir cannot be empty")
        
        if not config.actions_file:
            errors.append("actions_file cannot be empty")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Dictionary representation of configuration
        """
        if not self.config:
            return {}
        
        return {
            "comnetsemu_host": self.config.comnetsemu_host,
            "comnetsemu_port": self.config.comnetsemu_port,
            "max_retries": self.config.max_retries,
            "retry_delay": self.config.retry_delay,
            "timeout_seconds": self.config.timeout_seconds,
            "log_level": self.config.log_level,
            "history_dir": self.config.history_dir,
            "actions_file": self.config.actions_file
        }
    
    def save_example_config(self, output_path: str = "config.example.yaml"):
        """
        Save an example configuration file.
        
        Args:
            output_path: Path to save example config
        """
        try:
            example_config = {
                "comnetsemu_host": "localhost",
                "comnetsemu_port": 6653,
                "max_retries": 3,
                "retry_delay": 2.0,
                "timeout_seconds": 30,
                "log_level": "INFO",
                "history_dir": "data/history",
                "actions_file": "logs/actions.jsonl"
            }
            
            with open(output_path, 'w') as f:
                yaml.dump(example_config, f, default_flow_style=False, sort_keys=False)
            
            self.logger.info(f"Example configuration saved to {output_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save example config: {e}")
            raise
