"""Configuration manager with hot-reload, YAML, environment variables, and API support."""

import os
import yaml
import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from enum import Enum
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pydantic import ValidationError

from .models import SystemConfig


class ConfigSource(str, Enum):
    """Configuration sources."""
    YAML_FILE = "yaml_file"
    ENV_VARS = "env_vars"
    API = "api"
    DEFAULT = "default"


class ConfigChangeEvent:
    """Configuration change event."""
    
    def __init__(self, source: ConfigSource, changes: Dict[str, Any], timestamp: datetime):
        self.source = source
        self.changes = changes
        self.timestamp = timestamp
        self.applied = False
        self.error: Optional[str] = None


class ConfigFileWatcher(FileSystemEventHandler):
    """Watches configuration file for changes."""
    
    def __init__(self, config_manager: 'ConfigManager'):
        self.config_manager = config_manager
        self.logger = logging.getLogger("ConfigFileWatcher")
    
    def on_modified(self, event):
        """Handle file modification event."""
        if event.is_directory:
            return
        
        if event.src_path == str(self.config_manager.config_file_path):
            self.logger.info(f"Configuration file modified: {event.src_path}")
            self.config_manager.reload_from_file()


class ConfigManager:
    """
    Flexible configuration manager supporting:
    - YAML files
    - Environment variables
    - API updates
    - Hot-reload without restart
    - Configuration validation
    - Change auditing
    """
    
    def __init__(self, config_file: Optional[str] = None, enable_hot_reload: bool = True):
        self.logger = logging.getLogger("ConfigManager")
        
        # Configuration file
        self.config_file_path = Path(config_file) if config_file else Path("./config/system_config.yaml")
        
        # Current configuration
        self._config: SystemConfig = SystemConfig()
        self._config_lock = threading.RLock()
        
        # Hot-reload support
        self.enable_hot_reload = enable_hot_reload
        self.file_observer: Optional[Observer] = None
        
        # Change listeners
        self._change_listeners: List[Callable[[ConfigChangeEvent], None]] = []
        
        # Configuration history for audit trail
        self._config_history: List[ConfigChangeEvent] = []
        self._max_history_size = 100
        
        # Statistics
        self.stats = {
            "total_reloads": 0,
            "successful_reloads": 0,
            "failed_reloads": 0,
            "last_reload_time": None,
            "last_reload_source": None,
        }
        
        # Load initial configuration
        self._load_configuration()
        
        # Start file watcher if hot-reload enabled
        if self.enable_hot_reload:
            self._start_file_watcher()
        
        self.logger.info("ConfigManager initialized")
    
    def _load_configuration(self):
        """Load configuration from all sources in priority order."""
        try:
            # 1. Start with defaults
            config_dict = SystemConfig().dict()
            
            # 2. Load from YAML file if exists
            if self.config_file_path.exists():
                yaml_config = self._load_from_yaml()
                config_dict = self._deep_merge(config_dict, yaml_config)
                self.logger.info(f"Loaded configuration from {self.config_file_path}")
            else:
                self.logger.warning(f"Configuration file not found: {self.config_file_path}")
            
            # 3. Override with environment variables
            env_config = self._load_from_env()
            config_dict = self._deep_merge(config_dict, env_config)
            
            # 4. Validate and create config object
            with self._config_lock:
                self._config = SystemConfig(**config_dict)
            
            self.logger.info("Configuration loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            # Keep existing config or use defaults
            if not hasattr(self, '_config'):
                self._config = SystemConfig()
            raise
    
    def _load_from_yaml(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_file_path, 'r') as f:
                yaml_data = yaml.safe_load(f)
                return yaml_data or {}
        except Exception as e:
            self.logger.error(f"Failed to load YAML configuration: {e}")
            return {}
    
    def _load_from_env(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        env_config = {}
        
        # Map environment variables to config structure
        # Format: NORTHBOUND_<SECTION>_<KEY>=value
        prefix = "NORTHBOUND_"
        
        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue
            
            # Remove prefix and split into parts
            config_path = key[len(prefix):].lower().split('_')
            
            # Convert value to appropriate type
            parsed_value = self._parse_env_value(value)
            
            # Build nested dict
            current = env_config
            for part in config_path[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            current[config_path[-1]] = parsed_value
        
        if env_config:
            self.logger.info(f"Loaded {len(env_config)} configuration sections from environment variables")
        
        return env_config
    
    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value to appropriate type."""
        # Try to parse as JSON first (for complex types)
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
        
        # Try boolean
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
        
        # Try integer
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _start_file_watcher(self):
        """Start watching configuration file for changes."""
        try:
            if not self.config_file_path.exists():
                self.logger.warning("Configuration file doesn't exist, file watcher not started")
                return
            
            event_handler = ConfigFileWatcher(self)
            self.file_observer = Observer()
            self.file_observer.schedule(
                event_handler,
                str(self.config_file_path.parent),
                recursive=False
            )
            self.file_observer.start()
            
            self.logger.info(f"Started file watcher for {self.config_file_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to start file watcher: {e}")
    
    def reload_from_file(self):
        """Reload configuration from file (hot-reload)."""
        try:
            self.stats["total_reloads"] += 1
            
            # Load new configuration
            yaml_config = self._load_from_yaml()
            env_config = self._load_from_env()
            
            # Merge configurations
            config_dict = SystemConfig().dict()
            config_dict = self._deep_merge(config_dict, yaml_config)
            config_dict = self._deep_merge(config_dict, env_config)
            
            # Validate new configuration
            new_config = SystemConfig(**config_dict)
            
            # Detect changes
            changes = self._detect_changes(self._config, new_config)
            
            if not changes:
                self.logger.info("No configuration changes detected")
                return
            
            # Apply hot-reload compatible changes
            with self._config_lock:
                old_config = self._config
                self._config = new_config
            
            # Record change event
            event = ConfigChangeEvent(
                source=ConfigSource.YAML_FILE,
                changes=changes,
                timestamp=datetime.now()
            )
            event.applied = True
            
            self._add_to_history(event)
            
            # Notify listeners
            self._notify_listeners(event)
            
            # Update statistics
            self.stats["successful_reloads"] += 1
            self.stats["last_reload_time"] = datetime.now().isoformat()
            self.stats["last_reload_source"] = ConfigSource.YAML_FILE.value
            
            self.logger.info(f"Configuration reloaded successfully with {len(changes)} changes")
            
        except ValidationError as e:
            self.stats["failed_reloads"] += 1
            self.logger.error(f"Configuration validation failed: {e}")
            raise
        except Exception as e:
            self.stats["failed_reloads"] += 1
            self.logger.error(f"Failed to reload configuration: {e}")
            raise
    
    def update_from_api(self, updates: Dict[str, Any]) -> ConfigChangeEvent:
        """Update configuration via API."""
        try:
            self.stats["total_reloads"] += 1
            
            # Get current config as dict
            current_dict = self._config.dict()
            
            # Apply updates
            updated_dict = self._deep_merge(current_dict, updates)
            
            # Validate new configuration
            new_config = SystemConfig(**updated_dict)
            
            # Detect changes
            changes = self._detect_changes(self._config, new_config)
            
            # Apply changes
            with self._config_lock:
                self._config = new_config
            
            # Record change event
            event = ConfigChangeEvent(
                source=ConfigSource.API,
                changes=changes,
                timestamp=datetime.now()
            )
            event.applied = True
            
            self._add_to_history(event)
            
            # Notify listeners
            self._notify_listeners(event)
            
            # Update statistics
            self.stats["successful_reloads"] += 1
            self.stats["last_reload_time"] = datetime.now().isoformat()
            self.stats["last_reload_source"] = ConfigSource.API.value
            
            self.logger.info(f"Configuration updated via API with {len(changes)} changes")
            
            return event
            
        except ValidationError as e:
            self.stats["failed_reloads"] += 1
            error_msg = f"Configuration validation failed: {e}"
            self.logger.error(error_msg)
            
            event = ConfigChangeEvent(
                source=ConfigSource.API,
                changes=updates,
                timestamp=datetime.now()
            )
            event.error = error_msg
            
            raise ValueError(error_msg)
        except Exception as e:
            self.stats["failed_reloads"] += 1
            error_msg = f"Failed to update configuration: {e}"
            self.logger.error(error_msg)
            raise
    
    def _detect_changes(self, old_config: SystemConfig, new_config: SystemConfig) -> Dict[str, Any]:
        """Detect changes between configurations."""
        changes = {}
        
        old_dict = old_config.dict()
        new_dict = new_config.dict()
        
        def compare_dicts(old: Dict, new: Dict, path: str = ""):
            for key in set(list(old.keys()) + list(new.keys())):
                current_path = f"{path}.{key}" if path else key
                
                if key not in old:
                    changes[current_path] = {"action": "added", "new": new[key]}
                elif key not in new:
                    changes[current_path] = {"action": "removed", "old": old[key]}
                elif old[key] != new[key]:
                    if isinstance(old[key], dict) and isinstance(new[key], dict):
                        compare_dicts(old[key], new[key], current_path)
                    else:
                        changes[current_path] = {
                            "action": "modified",
                            "old": old[key],
                            "new": new[key]
                        }
        
        compare_dicts(old_dict, new_dict)
        
        return changes
    
    def _add_to_history(self, event: ConfigChangeEvent):
        """Add configuration change to history."""
        self._config_history.append(event)
        
        # Trim history if too large
        if len(self._config_history) > self._max_history_size:
            self._config_history = self._config_history[-self._max_history_size:]
    
    def register_change_listener(self, listener: Callable[[ConfigChangeEvent], None]):
        """Register a listener for configuration changes."""
        self._change_listeners.append(listener)
        self.logger.info(f"Registered configuration change listener: {listener.__name__}")
    
    def _notify_listeners(self, event: ConfigChangeEvent):
        """Notify all listeners of configuration change."""
        for listener in self._change_listeners:
            try:
                listener(event)
            except Exception as e:
                self.logger.error(f"Error notifying listener {listener.__name__}: {e}")
    
    def get_config(self) -> SystemConfig:
        """Get current configuration (thread-safe)."""
        with self._config_lock:
            return self._config.copy(deep=True)
    
    def get_config_dict(self) -> Dict[str, Any]:
        """Get current configuration as dictionary."""
        with self._config_lock:
            return self._config.dict()
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get configuration change history."""
        history = self._config_history[-limit:]
        
        return [
            {
                "source": event.source.value,
                "timestamp": event.timestamp.isoformat(),
                "changes": event.changes,
                "applied": event.applied,
                "error": event.error
            }
            for event in history
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get configuration manager statistics."""
        return {
            **self.stats,
            "hot_reload_enabled": self.enable_hot_reload,
            "config_file": str(self.config_file_path),
            "file_exists": self.config_file_path.exists(),
            "listeners_count": len(self._change_listeners),
            "history_size": len(self._config_history)
        }
    
    def validate_config(self, config_dict: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate configuration without applying it."""
        try:
            SystemConfig(**config_dict)
            return True, None
        except ValidationError as e:
            return False, str(e)
    
    def export_config(self, output_file: str, format: str = "yaml"):
        """Export current configuration to file."""
        try:
            config_dict = self.get_config_dict()
            
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format == "yaml":
                with open(output_path, 'w') as f:
                    yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
            elif format == "json":
                with open(output_path, 'w') as f:
                    json.dump(config_dict, f, indent=2)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            self.logger.info(f"Configuration exported to {output_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to export configuration: {e}")
            raise
    
    def close(self):
        """Stop file watcher and cleanup."""
        if self.file_observer:
            self.file_observer.stop()
            self.file_observer.join()
            self.logger.info("File watcher stopped")


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_file: Optional[str] = None, enable_hot_reload: bool = True) -> ConfigManager:
    """Get or create global configuration manager instance."""
    global _config_manager
    
    if _config_manager is None:
        _config_manager = ConfigManager(config_file, enable_hot_reload)
    
    return _config_manager


def get_config() -> SystemConfig:
    """Get current system configuration."""
    manager = get_config_manager()
    return manager.get_config()
