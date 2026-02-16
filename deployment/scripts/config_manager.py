#!/usr/bin/env python3
"""
Configuration Manager for LLM Integration Module

Provides centralized configuration management with:
- Environment-specific configurations
- Configuration validation
- Dynamic configuration updates
- Configuration export/import
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict


@dataclass
class ConfigValidationRule:
    """Configuration validation rule"""
    key: str
    required: bool = False
    type: Optional[type] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[Any]] = None
    pattern: Optional[str] = None


class ConfigManager:
    """Manages application configuration"""
    
    VALIDATION_RULES = [
        # API Configuration
        ConfigValidationRule("API_HOST", required=True, type=str),
        ConfigValidationRule("API_PORT", required=True, type=int, min_value=1, max_value=65535),
        
        # ChatGPT API
        ConfigValidationRule("OPENAI_API_KEY", required=True, type=str),
        ConfigValidationRule("OPENAI_MODEL", required=True, type=str, 
                           allowed_values=["gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]),
        ConfigValidationRule("OPENAI_MAX_TOKENS", required=True, type=int, min_value=1, max_value=128000),
        ConfigValidationRule("OPENAI_TEMPERATURE", required=True, type=float, min_value=0.0, max_value=2.0),
        ConfigValidationRule("OPENAI_RATE_LIMIT_RPM", required=True, type=int, min_value=1),
        ConfigValidationRule("OPENAI_TIMEOUT", required=True, type=int, min_value=1),
        ConfigValidationRule("OPENAI_MAX_RETRIES", required=True, type=int, min_value=0, max_value=10),
        
        # State Management
        ConfigValidationRule("STATE_CACHE_TTL", required=True, type=int, min_value=1),
        ConfigValidationRule("STATE_REFRESH_INTERVAL", required=True, type=int, min_value=1),
        
        # Security
        ConfigValidationRule("JWT_SECRET_KEY", required=True, type=str),
        ConfigValidationRule("ENABLE_INPUT_SANITIZATION", required=True, type=bool),
        ConfigValidationRule("MAX_INTENT_LENGTH", required=True, type=int, min_value=1),
        ConfigValidationRule("RATE_LIMIT_REQUESTS_PER_MINUTE", required=True, type=int, min_value=1),
        
        # Logging
        ConfigValidationRule("LOG_LEVEL", required=True, type=str,
                           allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    ]
    
    def __init__(self, env_file: Optional[str] = None):
        self.env_file = env_file
        self.config: Dict[str, Any] = {}
        self._load_config()
        
    def _load_config(self):
        """Load configuration from environment file"""
        if self.env_file and Path(self.env_file).exists():
            self._load_env_file(self.env_file)
        else:
            # Load from environment variables
            self._load_from_env()
            
    def _load_env_file(self, file_path: str):
        """Load configuration from .env file"""
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        self.config[key.strip()] = value.strip()
                        
    def _load_from_env(self):
        """Load configuration from environment variables"""
        for rule in self.VALIDATION_RULES:
            value = os.getenv(rule.key)
            if value:
                self.config[rule.key] = value
                
    def validate(self) -> tuple[bool, List[str]]:
        """Validate configuration against rules"""
        errors = []
        
        for rule in self.VALIDATION_RULES:
            value = self.config.get(rule.key)
            
            # Check required
            if rule.required and value is None:
                errors.append(f"Missing required configuration: {rule.key}")
                continue
                
            if value is None:
                continue
                
            # Check type
            if rule.type:
                try:
                    if rule.type == bool:
                        if isinstance(value, str):
                            value = value.lower() in ('true', '1', 'yes')
                    elif rule.type == int:
                        value = int(value)
                    elif rule.type == float:
                        value = float(value)
                    else:
                        value = str(value)
                        
                    self.config[rule.key] = value
                except ValueError:
                    errors.append(f"Invalid type for {rule.key}: expected {rule.type.__name__}")
                    continue
                    
            # Check min/max values
            if rule.min_value is not None and isinstance(value, (int, float)):
                if value < rule.min_value:
                    errors.append(f"{rule.key} must be >= {rule.min_value}")
                    
            if rule.max_value is not None and isinstance(value, (int, float)):
                if value > rule.max_value:
                    errors.append(f"{rule.key} must be <= {rule.max_value}")
                    
            # Check allowed values
            if rule.allowed_values and value not in rule.allowed_values:
                errors.append(f"{rule.key} must be one of: {', '.join(map(str, rule.allowed_values))}")
                
        return len(errors) == 0, errors
        
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
        
    def set(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value
        
    def export_to_file(self, output_path: str):
        """Export configuration to file"""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            for key, value in sorted(self.config.items()):
                f.write(f"{key}={value}\n")
                
    def export_to_json(self, output_path: str):
        """Export configuration to JSON"""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.config, f, indent=2)
            
    def get_summary(self) -> Dict[str, Any]:
        """Get configuration summary (with secrets masked)"""
        summary = {}
        secret_keys = ["API_KEY", "PASSWORD", "SECRET", "TOKEN", "WEBHOOK"]
        
        for key, value in self.config.items():
            if any(secret in key for secret in secret_keys):
                summary[key] = "***MASKED***"
            else:
                summary[key] = value
                
        return summary


def validate_environment(env: str = "dev") -> bool:
    """Validate environment configuration"""
    print(f"Validating {env} environment configuration...\n")
    
    env_file = f"config/{env}.env"
    if not Path(env_file).exists():
        print(f"✗ Environment file not found: {env_file}")
        return False
        
    manager = ConfigManager(env_file)
    is_valid, errors = manager.validate()
    
    if is_valid:
        print("✓ Configuration is valid\n")
        print("Configuration summary:")
        summary = manager.get_summary()
        for key, value in sorted(summary.items()):
            print(f"  {key}: {value}")
        return True
    else:
        print("✗ Configuration validation failed:\n")
        for error in errors:
            print(f"  - {error}")
        return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        env = sys.argv[1]
        success = validate_environment(env)
        sys.exit(0 if success else 1)
    else:
        print("Usage: python config_manager.py <dev|staging|prod>")
        sys.exit(1)
