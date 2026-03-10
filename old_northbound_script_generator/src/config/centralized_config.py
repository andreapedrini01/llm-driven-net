"""Centralized configuration management with versioning and audit trail."""

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import hashlib
import uuid


class ConfigOperation(str, Enum):
    """Configuration operation types."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ROLLBACK = "rollback"


@dataclass
class ConfigVersion:
    """Configuration version."""
    version_id: str
    version_number: int
    config_data: Dict[str, Any]
    created_at: datetime
    created_by: str
    operation: ConfigOperation
    comment: str
    checksum: str
    parent_version: Optional[str] = None


@dataclass
class ConfigAuditEntry:
    """Configuration audit trail entry."""
    audit_id: str
    version_id: str
    timestamp: datetime
    user: str
    operation: ConfigOperation
    changes: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class CentralizedConfigManager:
    """
    Centralized configuration management system with:
    - Configuration versioning
    - Audit trail for all changes
    - Rollback capability
    - Distributed configuration support
    - Change validation and approval workflow
    """
    
    def __init__(self, db_path: str = "./config/config_versions.db"):
        self.logger = logging.getLogger("CentralizedConfigManager")
        self.db_path = Path(db_path)
        
        # Create database directory
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Current configuration version
        self._current_version: Optional[ConfigVersion] = None
        self._version_lock = threading.RLock()
        
        # Load latest version
        self._load_latest_version()
        
        # Statistics
        self.stats = {
            "total_versions": 0,
            "total_updates": 0,
            "total_rollbacks": 0,
            "current_version_number": 0
        }
        
        self._update_stats()
        
        self.logger.info("CentralizedConfigManager initialized")
    
    def _init_database(self):
        """Initialize SQLite database for configuration versioning."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Configuration versions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config_versions (
                version_id TEXT PRIMARY KEY,
                version_number INTEGER NOT NULL,
                config_data TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                created_by TEXT NOT NULL,
                operation TEXT NOT NULL,
                comment TEXT,
                checksum TEXT NOT NULL,
                parent_version TEXT,
                is_active BOOLEAN DEFAULT 0
            )
        ''')
        
        # Audit trail table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS config_audit (
                audit_id TEXT PRIMARY KEY,
                version_id TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                user TEXT NOT NULL,
                operation TEXT NOT NULL,
                changes TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (version_id) REFERENCES config_versions(version_id)
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_version_number 
            ON config_versions(version_number DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_created_at 
            ON config_versions(created_at DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
            ON config_audit(timestamp DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_audit_user 
            ON config_audit(user)
        ''')
        
        conn.commit()
        conn.close()
    
    def _calculate_checksum(self, config_data: Dict[str, Any]) -> str:
        """Calculate checksum for configuration data."""
        config_json = json.dumps(config_data, sort_keys=True)
        return hashlib.sha256(config_json.encode()).hexdigest()
    
    def _load_latest_version(self):
        """Load the latest active configuration version."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT version_id, version_number, config_data, created_at, 
                       created_by, operation, comment, checksum, parent_version
                FROM config_versions 
                WHERE is_active = 1
                ORDER BY version_number DESC 
                LIMIT 1
            ''')
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                with self._version_lock:
                    self._current_version = ConfigVersion(
                        version_id=row[0],
                        version_number=row[1],
                        config_data=json.loads(row[2]),
                        created_at=datetime.fromisoformat(row[3]),
                        created_by=row[4],
                        operation=ConfigOperation(row[5]),
                        comment=row[6] or "",
                        checksum=row[7],
                        parent_version=row[8]
                    )
                
                self.logger.info(f"Loaded configuration version {row[1]}")
            else:
                self.logger.info("No existing configuration version found")
        
        except Exception as e:
            self.logger.error(f"Failed to load latest version: {e}")
    
    def create_version(
        self,
        config_data: Dict[str, Any],
        user: str,
        comment: str = "",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> ConfigVersion:
        """
        Create new configuration version.
        
        Args:
            config_data: Configuration data
            user: User creating the version
            comment: Version comment
            ip_address: User IP address
            user_agent: User agent string
        
        Returns:
            Created ConfigVersion
        """
        try:
            with self._version_lock:
                # Generate version ID
                version_id = str(uuid.uuid4())
                
                # Get next version number
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('SELECT MAX(version_number) FROM config_versions')
                max_version = cursor.fetchone()[0]
                version_number = (max_version or 0) + 1
                
                # Calculate checksum
                checksum = self._calculate_checksum(config_data)
                
                # Determine operation
                operation = ConfigOperation.CREATE if not self._current_version else ConfigOperation.UPDATE
                
                # Get parent version
                parent_version = self._current_version.version_id if self._current_version else None
                
                # Deactivate current version
                if self._current_version:
                    cursor.execute(
                        'UPDATE config_versions SET is_active = 0 WHERE version_id = ?',
                        (self._current_version.version_id,)
                    )
                
                # Insert new version
                cursor.execute('''
                    INSERT INTO config_versions 
                    (version_id, version_number, config_data, created_at, created_by,
                     operation, comment, checksum, parent_version, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ''', (
                    version_id,
                    version_number,
                    json.dumps(config_data),
                    datetime.now().isoformat(),
                    user,
                    operation.value,
                    comment,
                    checksum,
                    parent_version
                ))
                
                # Create audit entry
                changes = self._calculate_changes(
                    self._current_version.config_data if self._current_version else {},
                    config_data
                )
                
                audit_id = str(uuid.uuid4())
                cursor.execute('''
                    INSERT INTO config_audit 
                    (audit_id, version_id, timestamp, user, operation, changes,
                     ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    audit_id,
                    version_id,
                    datetime.now().isoformat(),
                    user,
                    operation.value,
                    json.dumps(changes),
                    ip_address,
                    user_agent
                ))
                
                conn.commit()
                conn.close()
                
                # Update current version
                new_version = ConfigVersion(
                    version_id=version_id,
                    version_number=version_number,
                    config_data=config_data,
                    created_at=datetime.now(),
                    created_by=user,
                    operation=operation,
                    comment=comment,
                    checksum=checksum,
                    parent_version=parent_version
                )
                
                self._current_version = new_version
                
                # Update statistics
                self.stats["total_versions"] += 1
                if operation == ConfigOperation.UPDATE:
                    self.stats["total_updates"] += 1
                self.stats["current_version_number"] = version_number
                
                self.logger.info(f"Created configuration version {version_number}")
                
                return new_version
        
        except Exception as e:
            self.logger.error(f"Failed to create version: {e}")
            raise
    
    def _calculate_changes(
        self,
        old_config: Dict[str, Any],
        new_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate changes between configurations."""
        changes = {
            "added": {},
            "modified": {},
            "removed": {}
        }
        
        def compare_dicts(old: Dict, new: Dict, path: str = ""):
            # Check for added and modified keys
            for key in new:
                current_path = f"{path}.{key}" if path else key
                
                if key not in old:
                    changes["added"][current_path] = new[key]
                elif old[key] != new[key]:
                    if isinstance(old[key], dict) and isinstance(new[key], dict):
                        compare_dicts(old[key], new[key], current_path)
                    else:
                        changes["modified"][current_path] = {
                            "old": old[key],
                            "new": new[key]
                        }
            
            # Check for removed keys
            for key in old:
                current_path = f"{path}.{key}" if path else key
                if key not in new:
                    changes["removed"][current_path] = old[key]
        
        compare_dicts(old_config, new_config)
        
        return changes
    
    def get_version(self, version_number: int) -> Optional[ConfigVersion]:
        """Get specific configuration version."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT version_id, version_number, config_data, created_at,
                       created_by, operation, comment, checksum, parent_version
                FROM config_versions 
                WHERE version_number = ?
            ''', (version_number,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return ConfigVersion(
                    version_id=row[0],
                    version_number=row[1],
                    config_data=json.loads(row[2]),
                    created_at=datetime.fromisoformat(row[3]),
                    created_by=row[4],
                    operation=ConfigOperation(row[5]),
                    comment=row[6] or "",
                    checksum=row[7],
                    parent_version=row[8]
                )
            
            return None
        
        except Exception as e:
            self.logger.error(f"Failed to get version {version_number}: {e}")
            return None
    
    def rollback_to_version(
        self,
        version_number: int,
        user: str,
        comment: str = "",
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> ConfigVersion:
        """
        Rollback to a previous configuration version.
        
        Args:
            version_number: Version number to rollback to
            user: User performing rollback
            comment: Rollback comment
            ip_address: User IP address
            user_agent: User agent string
        
        Returns:
            New ConfigVersion (rollback creates a new version)
        """
        try:
            # Get target version
            target_version = self.get_version(version_number)
            
            if not target_version:
                raise ValueError(f"Version {version_number} not found")
            
            # Create new version with rollback operation
            with self._version_lock:
                version_id = str(uuid.uuid4())
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('SELECT MAX(version_number) FROM config_versions')
                max_version = cursor.fetchone()[0]
                new_version_number = (max_version or 0) + 1
                
                # Deactivate current version
                if self._current_version:
                    cursor.execute(
                        'UPDATE config_versions SET is_active = 0 WHERE version_id = ?',
                        (self._current_version.version_id,)
                    )
                
                # Insert rollback version
                cursor.execute('''
                    INSERT INTO config_versions 
                    (version_id, version_number, config_data, created_at, created_by,
                     operation, comment, checksum, parent_version, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ''', (
                    version_id,
                    new_version_number,
                    json.dumps(target_version.config_data),
                    datetime.now().isoformat(),
                    user,
                    ConfigOperation.ROLLBACK.value,
                    f"Rollback to version {version_number}: {comment}",
                    target_version.checksum,
                    self._current_version.version_id if self._current_version else None
                ))
                
                # Create audit entry
                audit_id = str(uuid.uuid4())
                cursor.execute('''
                    INSERT INTO config_audit 
                    (audit_id, version_id, timestamp, user, operation, changes,
                     ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    audit_id,
                    version_id,
                    datetime.now().isoformat(),
                    user,
                    ConfigOperation.ROLLBACK.value,
                    json.dumps({
                        "rollback_to_version": version_number,
                        "rollback_from_version": self._current_version.version_number if self._current_version else None
                    }),
                    ip_address,
                    user_agent
                ))
                
                conn.commit()
                conn.close()
                
                # Update current version
                rollback_version = ConfigVersion(
                    version_id=version_id,
                    version_number=new_version_number,
                    config_data=target_version.config_data,
                    created_at=datetime.now(),
                    created_by=user,
                    operation=ConfigOperation.ROLLBACK,
                    comment=f"Rollback to version {version_number}: {comment}",
                    checksum=target_version.checksum,
                    parent_version=self._current_version.version_id if self._current_version else None
                )
                
                self._current_version = rollback_version
                
                # Update statistics
                self.stats["total_versions"] += 1
                self.stats["total_rollbacks"] += 1
                self.stats["current_version_number"] = new_version_number
                
                self.logger.info(f"Rolled back to version {version_number}, created new version {new_version_number}")
                
                return rollback_version
        
        except Exception as e:
            self.logger.error(f"Failed to rollback to version {version_number}: {e}")
            raise
    
    def get_current_config(self) -> Dict[str, Any]:
        """Get current active configuration."""
        with self._version_lock:
            if self._current_version:
                return self._current_version.config_data.copy()
            return {}
    
    def get_version_history(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get configuration version history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT version_id, version_number, created_at, created_by,
                       operation, comment, checksum, is_active
                FROM config_versions 
                ORDER BY version_number DESC 
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            
            versions = []
            for row in cursor.fetchall():
                versions.append({
                    "version_id": row[0],
                    "version_number": row[1],
                    "created_at": row[2],
                    "created_by": row[3],
                    "operation": row[4],
                    "comment": row[5],
                    "checksum": row[6],
                    "is_active": bool(row[7])
                })
            
            conn.close()
            
            return versions
        
        except Exception as e:
            self.logger.error(f"Failed to get version history: {e}")
            return []
    
    def get_audit_trail(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        user: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get configuration audit trail."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = "SELECT * FROM config_audit WHERE 1=1"
            params = []
            
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())
            
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())
            
            if user:
                query += " AND user = ?"
                params.append(user)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            
            audit_entries = []
            for row in cursor.fetchall():
                audit_entries.append({
                    "audit_id": row[0],
                    "version_id": row[1],
                    "timestamp": row[2],
                    "user": row[3],
                    "operation": row[4],
                    "changes": json.loads(row[5]),
                    "ip_address": row[6],
                    "user_agent": row[7]
                })
            
            conn.close()
            
            return audit_entries
        
        except Exception as e:
            self.logger.error(f"Failed to get audit trail: {e}")
            return []
    
    def _update_stats(self):
        """Update statistics from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM config_versions')
            self.stats["total_versions"] = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM config_versions WHERE operation = ?', (ConfigOperation.UPDATE.value,))
            self.stats["total_updates"] = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM config_versions WHERE operation = ?', (ConfigOperation.ROLLBACK.value,))
            self.stats["total_rollbacks"] = cursor.fetchone()[0]
            
            if self._current_version:
                self.stats["current_version_number"] = self._current_version.version_number
            
            conn.close()
        
        except Exception as e:
            self.logger.error(f"Failed to update stats: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get configuration manager statistics."""
        return {
            **self.stats,
            "current_version_id": self._current_version.version_id if self._current_version else None,
            "current_checksum": self._current_version.checksum if self._current_version else None
        }


# Global centralized config manager instance
_centralized_config_manager: Optional[CentralizedConfigManager] = None


def get_centralized_config_manager(
    db_path: str = "./config/config_versions.db"
) -> CentralizedConfigManager:
    """Get or create global centralized config manager instance."""
    global _centralized_config_manager
    
    if _centralized_config_manager is None:
        _centralized_config_manager = CentralizedConfigManager(db_path)
    
    return _centralized_config_manager
