"""State persistence and recovery module for LLM Integration Module."""

import json
import os
import shutil
import threading
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
import logging

from src.models.network import NetworkState
from src.models.intent import IntentObject


@dataclass
class PersistenceMetadata:
    """Metadata for persisted state."""
    version: str
    timestamp: datetime
    component: str
    checksum: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "component": self.component,
            "checksum": self.checksum
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PersistenceMetadata':
        """Create from dictionary."""
        return cls(
            version=data["version"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            component=data["component"],
            checksum=data.get("checksum")
        )


@dataclass
class RecoveryResult:
    """Result of a recovery operation."""
    success: bool
    component: str
    data: Optional[Any] = None
    error: Optional[str] = None
    recovered_at: Optional[datetime] = None
    metadata: Optional[PersistenceMetadata] = None


class StatePersistenceManager:
    """Manager for state persistence and recovery operations."""

    def __init__(
        self,
        persistence_folder: str = "./persistence",
        backup_folder: str = "./persistence/backups",
        max_backups: int = 5,
        auto_backup: bool = True,
        backup_interval: int = 3600,
        enable_checksums: bool = True
    ):
        """Initialize state persistence manager."""
        self.persistence_folder = persistence_folder
        self.backup_folder = backup_folder
        self.max_backups = max_backups
        self.auto_backup = auto_backup
        self.backup_interval = backup_interval
        self.enable_checksums = enable_checksums
        
        self._logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._backup_thread: Optional[threading.Thread] = None
        self._stop_backup = threading.Event()
        self._version = "1.0.0"
        
        self._ensure_folders()
        
        if self.auto_backup:
            self.start_auto_backup()

    def _ensure_folders(self) -> None:
        """Ensure persistence and backup folders exist."""
        try:
            Path(self.persistence_folder).mkdir(parents=True, exist_ok=True)
            Path(self.backup_folder).mkdir(parents=True, exist_ok=True)
            self._logger.debug(f"Persistence folders ensured: {self.persistence_folder}")
        except Exception as e:
            self._logger.error(f"Failed to create persistence folders: {e}")
            raise

    def _calculate_checksum(self, data: str) -> str:
        """Calculate SHA-256 checksum of data."""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def _get_state_file_path(self, component: str) -> str:
        """Get path to state file for component."""
        return os.path.join(self.persistence_folder, f"{component}_state.json")

    def _get_backup_file_path(self, component: str, timestamp: datetime) -> str:
        """Get path to backup file for component."""
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.backup_folder, f"{component}_backup_{timestamp_str}.json")

    def persist_state(
        self,
        component: str,
        state_data: Dict[str, Any],
        create_backup: bool = True
    ) -> bool:
        """Persist state data to disk."""
        with self._lock:
            try:
                file_path = self._get_state_file_path(component)
                
                # Create backup of existing state before overwriting
                if create_backup and os.path.exists(file_path):
                    self._create_backup(component, file_path)
                
                metadata = PersistenceMetadata(
                    version=self._version,
                    timestamp=datetime.now(),
                    component=component
                )
                
                full_state = {
                    "metadata": metadata.to_dict(),
                    "data": state_data
                }
                
                json_data = json.dumps(full_state, indent=2, default=str)
                
                if self.enable_checksums:
                    checksum = self._calculate_checksum(json_data)
                    full_state["metadata"]["checksum"] = checksum
                    json_data = json.dumps(full_state, indent=2, default=str)
                
                temp_file = file_path + ".tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(json_data)
                
                if os.path.exists(file_path):
                    os.replace(temp_file, file_path)
                else:
                    os.rename(temp_file, file_path)
                
                # Also create a backup after writing if requested and this was a new file
                # This ensures we always have at least one backup
                if create_backup:
                    self._create_backup(component, file_path)
                
                self._logger.info(f"Successfully persisted state for component: {component}")
                return True
                
            except Exception as e:
                self._logger.error(f"Failed to persist state for {component}: {e}")
                return False

    def recover_state(self, component: str) -> RecoveryResult:
        """Recover state data from disk."""
        with self._lock:
            try:
                file_path = self._get_state_file_path(component)
                
                if not os.path.exists(file_path):
                    self._logger.warning(f"No persisted state found for component: {component}")
                    return RecoveryResult(
                        success=False,
                        component=component,
                        error="State file not found",
                        recovered_at=datetime.now()
                    )
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                full_state = json.loads(content)
                
                if "metadata" not in full_state:
                    raise ValueError("State file missing metadata")
                
                metadata = PersistenceMetadata.from_dict(full_state["metadata"])
                
                if self.enable_checksums and metadata.checksum:
                    temp_state = full_state.copy()
                    temp_state["metadata"] = temp_state["metadata"].copy()
                    temp_state["metadata"]["checksum"] = None
                    temp_json = json.dumps(temp_state, indent=2, default=str)
                    calculated_checksum = self._calculate_checksum(temp_json)
                    
                    if calculated_checksum != metadata.checksum:
                        self._logger.warning(f"Checksum mismatch for {component}, attempting backup recovery")
                        return self._recover_from_backup(component)
                
                state_data = full_state.get("data", {})
                
                self._logger.info(f"Successfully recovered state for component: {component}")
                
                return RecoveryResult(
                    success=True,
                    component=component,
                    data=state_data,
                    recovered_at=datetime.now(),
                    metadata=metadata
                )
                
            except Exception as e:
                self._logger.error(f"Failed to recover state for {component}: {e}, attempting backup recovery")
                return self._recover_from_backup(component)

    def _create_backup(self, component: str, source_file: str) -> bool:
        """Create backup of state file."""
        try:
            timestamp = datetime.now()
            backup_path = self._get_backup_file_path(component, timestamp)
            
            shutil.copy2(source_file, backup_path)
            
            self._logger.info(f"Created backup for {component}: {backup_path}")
            
            self._cleanup_old_backups(component)
            
            return True
            
        except Exception as e:
            self._logger.error(f"Failed to create backup for {component}: {e}")
            return False

    def _cleanup_old_backups(self, component: str) -> None:
        """Remove old backups exceeding max_backups limit."""
        try:
            backup_files = []
            
            for file in os.listdir(self.backup_folder):
                if file.startswith(f"{component}_backup_") and file.endswith(".json"):
                    file_path = os.path.join(self.backup_folder, file)
                    backup_files.append((file_path, os.path.getmtime(file_path)))
            
            backup_files.sort(key=lambda x: x[1], reverse=True)
            
            if len(backup_files) > self.max_backups:
                for file_path, _ in backup_files[self.max_backups:]:
                    os.remove(file_path)
                    self._logger.debug(f"Removed old backup: {file_path}")
                    
        except Exception as e:
            self._logger.error(f"Failed to cleanup old backups for {component}: {e}")

    def _recover_from_backup(self, component: str) -> RecoveryResult:
        """Attempt to recover state from most recent backup."""
        recovery_time = datetime.now()
        
        try:
            backup_files = []
            
            for file in os.listdir(self.backup_folder):
                if file.startswith(f"{component}_backup_") and file.endswith(".json"):
                    file_path = os.path.join(self.backup_folder, file)
                    backup_files.append((file_path, os.path.getmtime(file_path)))
            
            if not backup_files:
                self._logger.error(f"No backups found for component: {component}")
                return RecoveryResult(
                    success=False,
                    component=component,
                    error="No backups available",
                    recovered_at=recovery_time
                )
            
            # Sort backups by modification time (most recent first)
            backup_files.sort(key=lambda x: x[1], reverse=True)
            
            # Try each backup in order until one succeeds
            last_error = None
            for backup_path, _ in backup_files:
                try:
                    self._logger.info(f"Attempting recovery from backup: {backup_path}")
                    
                    with open(backup_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    full_state = json.loads(content)
                    
                    if "metadata" not in full_state:
                        self._logger.warning(f"Backup missing metadata: {backup_path}")
                        continue
                    
                    metadata = PersistenceMetadata.from_dict(full_state["metadata"])
                    state_data = full_state.get("data", {})
                    
                    # Restore the backup to the primary state file
                    state_file = self._get_state_file_path(component)
                    shutil.copy2(backup_path, state_file)
                    
                    self._logger.info(f"Successfully recovered {component} from backup: {backup_path}")
                    
                    return RecoveryResult(
                        success=True,
                        component=component,
                        data=state_data,
                        recovered_at=recovery_time,
                        metadata=metadata
                    )
                    
                except Exception as backup_error:
                    self._logger.warning(f"Failed to recover from backup {backup_path}: {backup_error}")
                    last_error = backup_error
                    continue
            
            # All backups failed
            error_msg = f"All backup recovery attempts failed. Last error: {str(last_error)}"
            self._logger.error(error_msg)
            return RecoveryResult(
                success=False,
                component=component,
                error=error_msg,
                recovered_at=recovery_time
            )
            
        except Exception as e:
            self._logger.error(f"Failed to recover from backup for {component}: {e}")
            return RecoveryResult(
                success=False,
                component=component,
                error=f"Backup recovery failed: {str(e)}",
                recovered_at=recovery_time
            )

    def create_manual_backup(self, component: str) -> bool:
        """Create manual backup of component state."""
        with self._lock:
            file_path = self._get_state_file_path(component)
            
            if not os.path.exists(file_path):
                self._logger.warning(f"No state file to backup for component: {component}")
                return False
            
            return self._create_backup(component, file_path)

    def restore_from_backup(self, component: str, backup_timestamp: Optional[datetime] = None) -> bool:
        """Restore state from specific backup."""
        with self._lock:
            try:
                if backup_timestamp:
                    backup_path = self._get_backup_file_path(component, backup_timestamp)
                    if not os.path.exists(backup_path):
                        self._logger.error(f"Backup not found: {backup_path}")
                        return False
                else:
                    backup_files = []
                    for file in os.listdir(self.backup_folder):
                        if file.startswith(f"{component}_backup_") and file.endswith(".json"):
                            file_path = os.path.join(self.backup_folder, file)
                            backup_files.append((file_path, os.path.getmtime(file_path)))
                    
                    if not backup_files:
                        self._logger.error(f"No backups found for component: {component}")
                        return False
                    
                    backup_files.sort(key=lambda x: x[1], reverse=True)
                    backup_path = backup_files[0][0]
                
                state_file = self._get_state_file_path(component)
                shutil.copy2(backup_path, state_file)
                
                self._logger.info(f"Successfully restored {component} from backup: {backup_path}")
                return True
                
            except Exception as e:
                self._logger.error(f"Failed to restore from backup for {component}: {e}")
                return False

    def list_backups(self, component: str) -> List[Dict[str, Any]]:
        """List all available backups for component."""
        backups = []
        
        try:
            for file in os.listdir(self.backup_folder):
                if file.startswith(f"{component}_backup_") and file.endswith(".json"):
                    file_path = os.path.join(self.backup_folder, file)
                    stat = os.stat(file_path)
                    
                    backups.append({
                        "file": file,
                        "path": file_path,
                        "size_bytes": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "age_seconds": time.time() - stat.st_mtime
                    })
            
            backups.sort(key=lambda x: x["created_at"], reverse=True)
            
        except Exception as e:
            self._logger.error(f"Failed to list backups for {component}: {e}")
        
        return backups

    def delete_state(self, component: str, delete_backups: bool = False) -> bool:
        """Delete persisted state for component."""
        with self._lock:
            try:
                state_file = self._get_state_file_path(component)
                if os.path.exists(state_file):
                    os.remove(state_file)
                    self._logger.info(f"Deleted state file for {component}")
                
                if delete_backups:
                    for file in os.listdir(self.backup_folder):
                        if file.startswith(f"{component}_backup_") and file.endswith(".json"):
                            file_path = os.path.join(self.backup_folder, file)
                            os.remove(file_path)
                            self._logger.debug(f"Deleted backup: {file_path}")
                
                return True
                
            except Exception as e:
                self._logger.error(f"Failed to delete state for {component}: {e}")
                return False

    def start_auto_backup(self) -> bool:
        """Start automatic periodic backup thread."""
        with self._lock:
            if self._backup_thread and self._backup_thread.is_alive():
                self._logger.warning("Auto-backup thread already running")
                return True
            
            try:
                self._stop_backup.clear()
                self._backup_thread = threading.Thread(
                    target=self._auto_backup_loop,
                    daemon=True,
                    name="StatePersistenceAutoBackup"
                )
                self._backup_thread.start()
                
                self._logger.info(f"Started auto-backup thread (interval: {self.backup_interval}s)")
                return True
                
            except Exception as e:
                self._logger.error(f"Failed to start auto-backup thread: {e}")
                return False

    def stop_auto_backup(self) -> bool:
        """Stop automatic periodic backup thread."""
        with self._lock:
            if not self._backup_thread or not self._backup_thread.is_alive():
                self._logger.warning("Auto-backup thread not running")
                return True
            
            try:
                self._stop_backup.set()
                self._backup_thread.join(timeout=10.0)
                
                self._logger.info("Stopped auto-backup thread")
                return True
                
            except Exception as e:
                self._logger.error(f"Failed to stop auto-backup thread: {e}")
                return False

    def _auto_backup_loop(self) -> None:
        """Auto-backup thread loop."""
        self._logger.info("Auto-backup thread started")
        
        while not self._stop_backup.is_set():
            try:
                if self._stop_backup.wait(timeout=self.backup_interval):
                    break
                
                for file in os.listdir(self.persistence_folder):
                    if file.endswith("_state.json"):
                        component = file.replace("_state.json", "")
                        file_path = os.path.join(self.persistence_folder, file)
                        self._create_backup(component, file_path)
                
            except Exception as e:
                self._logger.error(f"Error in auto-backup loop: {e}")
        
        self._logger.info("Auto-backup thread stopped")

    def get_persistence_info(self) -> Dict[str, Any]:
        """Get information about persistence system."""
        info = {
            "persistence_folder": self.persistence_folder,
            "backup_folder": self.backup_folder,
            "max_backups": self.max_backups,
            "auto_backup_enabled": self.auto_backup,
            "backup_interval": self.backup_interval,
            "checksums_enabled": self.enable_checksums,
            "auto_backup_running": self._backup_thread and self._backup_thread.is_alive(),
            "components": []
        }
        
        try:
            for file in os.listdir(self.persistence_folder):
                if file.endswith("_state.json"):
                    component = file.replace("_state.json", "")
                    file_path = os.path.join(self.persistence_folder, file)
                    stat = os.stat(file_path)
                    
                    backups = self.list_backups(component)
                    
                    info["components"].append({
                        "name": component,
                        "file": file,
                        "size_bytes": stat.st_size,
                        "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "backup_count": len(backups)
                    })
        
        except Exception as e:
            self._logger.error(f"Error getting persistence info: {e}")
            info["error"] = str(e)
        
        return info

    def __del__(self):
        """Cleanup when object is destroyed."""
        if self.auto_backup:
            self.stop_auto_backup()
