"""JSON file reader for network state with error handling, validation, and file watching."""

import json
import os
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from src.models.network import NetworkState


@dataclass
class FileReadResult:
    """Result of a file read operation."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    attempts: int = 1
    read_time: Optional[datetime] = None


class NetworkStateFileHandler(FileSystemEventHandler):
    """File system event handler for network state file changes."""

    def __init__(self, file_path: str, callback: Callable[[str], None]):
        """
        Initialize file handler.
        
        Args:
            file_path: Path to the file to watch
            callback: Callback function to call when file is modified
        """
        self.file_path = os.path.abspath(file_path)
        self.callback = callback
        self._logger = logging.getLogger(__name__)
        self._last_modified = 0
        self._debounce_seconds = 1.0  # Debounce to avoid multiple triggers

    def on_modified(self, event):
        """Handle file modification event."""
        if event.is_directory:
            return
        
        # Check if this is the file we're watching
        event_path = os.path.abspath(event.src_path)
        if event_path != self.file_path:
            return
        
        # Debounce: ignore if modified too recently
        current_time = time.time()
        if current_time - self._last_modified < self._debounce_seconds:
            return
        
        self._last_modified = current_time
        self._logger.info(f"Network state file modified: {self.file_path}")
        
        try:
            self.callback(self.file_path)
        except Exception as e:
            self._logger.error(f"Error in file modification callback: {e}")


class StateFileReader:
    """
    JSON file reader for network state with comprehensive error handling,
    validation, retry logic, and file watching capabilities.
    """

    def __init__(
        self,
        cache_folder: str = "./cache",
        state_file_name: str = "network_state.json",
        max_retries: int = 5,
        initial_backoff: float = 1.0,
        max_backoff: float = 32.0,
        enable_file_watching: bool = False,
        file_change_callback: Optional[Callable[[NetworkState], None]] = None
    ):
        """
        Initialize state file reader.
        
        Args:
            cache_folder: Path to cache folder containing state files
            state_file_name: Name of the state JSON file
            max_retries: Maximum number of retry attempts for file operations
            initial_backoff: Initial backoff delay in seconds
            max_backoff: Maximum backoff delay in seconds
            enable_file_watching: Whether to enable automatic file watching
            file_change_callback: Callback function when file changes (receives NetworkState)
        """
        self.cache_folder = cache_folder
        self.state_file_name = state_file_name
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.enable_file_watching = enable_file_watching
        self.file_change_callback = file_change_callback
        
        self._logger = logging.getLogger(__name__)
        self._file_observer: Optional[Observer] = None
        self._watch_thread: Optional[threading.Thread] = None
        self._is_watching = False
        self._lock = threading.RLock()
        
        # Ensure cache folder exists
        self._ensure_cache_folder()
        
        # Start file watching if enabled
        if self.enable_file_watching and self.file_change_callback:
            self.start_file_watching()

    def _ensure_cache_folder(self) -> None:
        """Ensure cache folder exists."""
        try:
            Path(self.cache_folder).mkdir(parents=True, exist_ok=True)
            self._logger.debug(f"Cache folder ensured: {self.cache_folder}")
        except Exception as e:
            self._logger.error(f"Failed to create cache folder: {e}")
            raise

    def get_file_path(self, file_name: Optional[str] = None) -> str:
        """
        Get full path to state file.
        
        Args:
            file_name: Optional file name, uses default if None
            
        Returns:
            Full path to state file
        """
        name = file_name or self.state_file_name
        return os.path.join(self.cache_folder, name)

    def read_json_file(self, file_path: Optional[str] = None) -> FileReadResult:
        """
        Read and parse JSON file with retry logic and exponential backoff.
        
        Args:
            file_path: Path to JSON file, uses default if None
            
        Returns:
            FileReadResult with success status and data or error
        """
        if file_path is None:
            file_path = self.get_file_path()
        
        retry_count = 0
        backoff_delay = self.initial_backoff
        last_error = None
        last_error_type = None
        
        while retry_count < self.max_retries:
            try:
                # Check if file exists
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"State file not found: {file_path}")
                
                # Check if file is readable
                if not os.access(file_path, os.R_OK):
                    raise PermissionError(f"No read permission for file: {file_path}")
                
                # Read file content
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check if file is empty
                if not content.strip():
                    raise ValueError(f"State file is empty: {file_path}")
                
                # Parse JSON
                data = json.loads(content)
                
                # Validate JSON structure
                validation_result = self._validate_json_structure(data)
                if not validation_result["is_valid"]:
                    raise ValueError(f"Invalid JSON structure: {validation_result['errors']}")
                
                self._logger.info(f"Successfully read state file: {file_path} (attempt {retry_count + 1})")
                
                return FileReadResult(
                    success=True,
                    data=data,
                    attempts=retry_count + 1,
                    read_time=datetime.now()
                )
                
            except FileNotFoundError as e:
                last_error = str(e)
                last_error_type = "FileNotFoundError"
                self._logger.warning(
                    f"File not found (attempt {retry_count + 1}/{self.max_retries}): {file_path}"
                )
                
            except PermissionError as e:
                last_error = str(e)
                last_error_type = "PermissionError"
                self._logger.error(
                    f"Permission error (attempt {retry_count + 1}/{self.max_retries}): {e}"
                )
                
            except json.JSONDecodeError as e:
                last_error = f"JSON decode error at line {e.lineno}, column {e.colno}: {e.msg}"
                last_error_type = "JSONDecodeError"
                self._logger.error(
                    f"JSON decode error (attempt {retry_count + 1}/{self.max_retries}): {last_error}"
                )
                
            except ValueError as e:
                last_error = str(e)
                last_error_type = "ValueError"
                self._logger.error(
                    f"Validation error (attempt {retry_count + 1}/{self.max_retries}): {e}"
                )
                
            except Exception as e:
                last_error = str(e)
                last_error_type = type(e).__name__
                self._logger.error(
                    f"Unexpected error (attempt {retry_count + 1}/{self.max_retries}): {e}"
                )
            
            # Increment retry count
            retry_count += 1
            
            # If not last attempt, wait with exponential backoff
            if retry_count < self.max_retries:
                self._logger.info(f"Retrying in {backoff_delay:.1f} seconds...")
                time.sleep(backoff_delay)
                
                # Exponential backoff with cap
                backoff_delay = min(backoff_delay * 2, self.max_backoff)
        
        # All retries failed
        self._logger.error(
            f"Failed to read state file after {self.max_retries} attempts: {last_error}"
        )
        
        return FileReadResult(
            success=False,
            error=last_error,
            error_type=last_error_type,
            attempts=retry_count
        )

    def _validate_json_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate JSON structure for network state.
        
        Args:
            data: Parsed JSON data
            
        Returns:
            Dictionary with validation result
        """
        errors = []
        
        # Check required top-level fields
        required_fields = ["timestamp", "topology", "flows", "metrics"]
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        # Validate topology structure
        if "topology" in data:
            topology = data["topology"]
            if not isinstance(topology, dict):
                errors.append("'topology' must be a dictionary")
            else:
                topology_fields = ["switches", "links", "hosts"]
                for field in topology_fields:
                    if field not in topology:
                        errors.append(f"Missing topology field: {field}")
                    elif not isinstance(topology[field], list):
                        errors.append(f"'topology.{field}' must be a list")
        
        # Validate flows
        if "flows" in data:
            if not isinstance(data["flows"], list):
                errors.append("'flows' must be a list")
        
        # Validate metrics
        if "metrics" in data:
            if not isinstance(data["metrics"], dict):
                errors.append("'metrics' must be a dictionary")
            else:
                metrics = data["metrics"]
                metrics_fields = ["bandwidth", "latency", "utilization"]
                for field in metrics_fields:
                    if field not in metrics:
                        errors.append(f"Missing metrics field: {field}")
        
        # Validate timestamp format
        if "timestamp" in data:
            try:
                # Try to parse timestamp
                datetime.fromisoformat(data["timestamp"].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                errors.append(f"Invalid timestamp format: {data.get('timestamp')}")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors
        }

    def parse_to_network_state(self, data: Dict[str, Any]) -> NetworkState:
        """
        Parse JSON data to NetworkState object.
        
        Args:
            data: Validated JSON data
            
        Returns:
            NetworkState object
            
        Raises:
            ValueError: If data cannot be parsed to NetworkState
        """
        try:
            # Use Pydantic's model_validate to create NetworkState
            state = NetworkState.model_validate(data)
            self._logger.debug(f"Successfully parsed NetworkState with {len(state.topology.switches)} switches")
            return state
            
        except Exception as e:
            self._logger.error(f"Failed to parse JSON to NetworkState: {e}")
            raise ValueError(f"Failed to parse JSON to NetworkState: {e}")

    def load_network_state(self, file_path: Optional[str] = None) -> Optional[NetworkState]:
        """
        Load network state from JSON file with full error handling and retry logic.
        
        Args:
            file_path: Path to JSON file, uses default if None
            
        Returns:
            NetworkState object or None if loading failed
        """
        # Read JSON file with retry logic
        result = self.read_json_file(file_path)
        
        if not result.success:
            self._logger.error(f"Failed to read state file: {result.error}")
            return None
        
        # Parse to NetworkState
        try:
            state = self.parse_to_network_state(result.data)
            self._logger.info(
                f"Successfully loaded NetworkState from file "
                f"(read time: {result.read_time}, attempts: {result.attempts})"
            )
            return state
            
        except ValueError as e:
            self._logger.error(f"Failed to parse NetworkState: {e}")
            return None

    def start_file_watching(self) -> bool:
        """
        Start watching the state file for changes.
        
        Returns:
            True if watching started successfully
        """
        with self._lock:
            if self._is_watching:
                self._logger.warning("File watching is already active")
                return True
            
            if not self.file_change_callback:
                self._logger.error("Cannot start file watching: no callback provided")
                return False
            
            try:
                file_path = self.get_file_path()
                
                # Create event handler
                event_handler = NetworkStateFileHandler(
                    file_path=file_path,
                    callback=self._handle_file_change
                )
                
                # Create observer
                self._file_observer = Observer()
                self._file_observer.schedule(
                    event_handler,
                    path=self.cache_folder,
                    recursive=False
                )
                
                # Start observer
                self._file_observer.start()
                self._is_watching = True
                
                self._logger.info(f"Started watching file: {file_path}")
                return True
                
            except Exception as e:
                self._logger.error(f"Failed to start file watching: {e}")
                return False

    def stop_file_watching(self) -> bool:
        """
        Stop watching the state file.
        
        Returns:
            True if watching stopped successfully
        """
        with self._lock:
            if not self._is_watching:
                self._logger.warning("File watching is not active")
                return True
            
            try:
                if self._file_observer:
                    self._file_observer.stop()
                    self._file_observer.join(timeout=5.0)
                    self._file_observer = None
                
                self._is_watching = False
                self._logger.info("Stopped file watching")
                return True
                
            except Exception as e:
                self._logger.error(f"Failed to stop file watching: {e}")
                return False

    def _handle_file_change(self, file_path: str) -> None:
        """
        Handle file change event.
        
        Args:
            file_path: Path to changed file
        """
        self._logger.info(f"Handling file change: {file_path}")
        
        try:
            # Load updated network state
            state = self.load_network_state(file_path)
            
            if state and self.file_change_callback:
                # Call callback with new state
                self.file_change_callback(state)
                self._logger.info("File change callback executed successfully")
            elif not state:
                self._logger.warning("Failed to load state after file change")
                
        except Exception as e:
            self._logger.error(f"Error handling file change: {e}")

    def is_watching(self) -> bool:
        """
        Check if file watching is active.
        
        Returns:
            True if watching is active
        """
        with self._lock:
            return self._is_watching

    def get_file_info(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about the state file.
        
        Args:
            file_path: Path to file, uses default if None
            
        Returns:
            Dictionary with file information
        """
        if file_path is None:
            file_path = self.get_file_path()
        
        info = {
            "path": file_path,
            "exists": False,
            "readable": False,
            "size_bytes": None,
            "modified_time": None,
            "age_seconds": None
        }
        
        try:
            if os.path.exists(file_path):
                info["exists"] = True
                info["readable"] = os.access(file_path, os.R_OK)
                
                stat = os.stat(file_path)
                info["size_bytes"] = stat.st_size
                
                modified_time = datetime.fromtimestamp(stat.st_mtime)
                info["modified_time"] = modified_time.isoformat()
                info["age_seconds"] = (datetime.now() - modified_time).total_seconds()
                
        except Exception as e:
            self._logger.error(f"Error getting file info: {e}")
            info["error"] = str(e)
        
        return info

    def __del__(self):
        """Cleanup when object is destroyed."""
        if self._is_watching:
            self.stop_file_watching()
