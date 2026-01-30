"""Recovery service for automatic and manual database recovery."""

import logging
import os
import signal
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from enum import Enum

from .models import (
    BackupInfo, BackupStatus, BackupType, RestoreResult, 
    VerificationResult, DatabaseConfig
)
from .backup_service import BackupService
from .database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class RecoveryTrigger(str, Enum):
    """Types of recovery triggers."""
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    SCHEDULED = "scheduled"
    HEALTH_CHECK_FAILURE = "health_check_failure"
    DATABASE_CORRUPTION = "database_corruption"
    CONNECTION_FAILURE = "connection_failure"


class RecoveryStatus(str, Enum):
    """Status of recovery operations."""
    PENDING = "pending"
    ANALYZING = "analyzing"
    SELECTING_BACKUP = "selecting_backup"
    PREPARING = "preparing"
    RESTORING = "restoring"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RecoveryPoint:
    """Represents a point-in-time recovery option."""
    
    def __init__(
        self,
        backup_info: BackupInfo,
        verification_result: VerificationResult,
        recovery_score: float,
        estimated_recovery_time_minutes: int
    ):
        """Initialize recovery point.
        
        Args:
            backup_info: Backup information
            verification_result: Backup verification result
            recovery_score: Score indicating recovery suitability (0-100)
            estimated_recovery_time_minutes: Estimated recovery time
        """
        self.backup_info = backup_info
        self.verification_result = verification_result
        self.recovery_score = recovery_score
        self.estimated_recovery_time_minutes = estimated_recovery_time_minutes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'backup_id': self.backup_info.backup_id,
            'backup_type': self.backup_info.backup_type.value,
            'created_at': self.backup_info.created_at.isoformat(),
            'completed_at': self.backup_info.completed_at.isoformat() if self.backup_info.completed_at else None,
            'file_size_mb': self.backup_info.file_size / (1024 * 1024),
            'compressed_size_mb': self.backup_info.compressed_size / (1024 * 1024),
            'is_encrypted': self.backup_info.is_encrypted,
            'database_name': self.backup_info.database_name,
            'is_valid': self.verification_result.is_valid,
            'verification_time': self.verification_result.verification_time.isoformat(),
            'recovery_score': self.recovery_score,
            'estimated_recovery_time_minutes': self.estimated_recovery_time_minutes,
            'recommendation': self._get_recommendation()
        }
    
    def _get_recommendation(self) -> str:
        """Get recovery recommendation."""
        if not self.verification_result.is_valid:
            return "❌ Not recommended - backup verification failed"
        elif self.recovery_score >= 90:
            return "✅ Highly recommended - recent, verified backup"
        elif self.recovery_score >= 70:
            return "✅ Recommended - good backup option"
        elif self.recovery_score >= 50:
            return "⚠️ Acceptable - older backup, use if newer options unavailable"
        else:
            return "❌ Not recommended - very old or problematic backup"


class RecoveryOperation:
    """Represents an ongoing recovery operation."""
    
    def __init__(
        self,
        operation_id: str,
        trigger: RecoveryTrigger,
        selected_backup_id: Optional[str] = None
    ):
        """Initialize recovery operation.
        
        Args:
            operation_id: Unique operation identifier
            trigger: What triggered the recovery
            selected_backup_id: ID of backup to restore from
        """
        self.operation_id = operation_id
        self.trigger = trigger
        self.selected_backup_id = selected_backup_id
        self.status = RecoveryStatus.PENDING
        self.started_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.error_message: Optional[str] = None
        self.progress_percentage = 0
        self.current_step = ""
        self.logs: List[str] = []
    
    def add_log(self, message: str):
        """Add log message to operation."""
        timestamp = datetime.utcnow().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        logger.info(f"Recovery {self.operation_id}: {message}")
    
    def update_progress(self, percentage: int, step: str):
        """Update operation progress."""
        self.progress_percentage = min(100, max(0, percentage))
        self.current_step = step
        self.add_log(f"Progress: {percentage}% - {step}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'operation_id': self.operation_id,
            'trigger': self.trigger.value,
            'selected_backup_id': self.selected_backup_id,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': (
                (self.completed_at or datetime.utcnow()) - self.started_at
            ).total_seconds(),
            'error_message': self.error_message,
            'progress_percentage': self.progress_percentage,
            'current_step': self.current_step,
            'logs': self.logs[-10:]  # Last 10 log entries
        }


class RecoveryService:
    """Service for database recovery operations."""
    
    def __init__(
        self,
        backup_service: BackupService,
        db_config: DatabaseConfig,
        auto_recovery_enabled: bool = True,
        max_recovery_attempts: int = 3
    ):
        """Initialize recovery service.
        
        Args:
            backup_service: BackupService instance
            db_config: Database configuration
            auto_recovery_enabled: Enable automatic recovery
            max_recovery_attempts: Maximum automatic recovery attempts
        """
        self.backup_service = backup_service
        self.db_config = db_config
        self.auto_recovery_enabled = auto_recovery_enabled
        self.max_recovery_attempts = max_recovery_attempts
        
        # Active operations
        self.active_operations: Dict[str, RecoveryOperation] = {}
        self.operation_lock = threading.Lock()
        
        # Health monitoring
        self.health_check_enabled = False
        self.health_check_interval = 300  # 5 minutes
        self.health_check_thread: Optional[threading.Thread] = None
        self.health_stop_event = threading.Event()
        
        # Recovery attempt tracking
        self.recovery_attempts = 0
        self.last_recovery_attempt = None
        self.recovery_cooldown_minutes = 30
        
        # Callbacks
        self.recovery_started_callback: Optional[Callable[[RecoveryOperation], None]] = None
        self.recovery_completed_callback: Optional[Callable[[RecoveryOperation], None]] = None
        self.recovery_failed_callback: Optional[Callable[[RecoveryOperation], None]] = None
        
        logger.info("Recovery service initialized")
    
    def get_recovery_points(self, max_age_days: int = 30) -> List[RecoveryPoint]:
        """Get available recovery points.
        
        Args:
            max_age_days: Maximum age of backups to consider
            
        Returns:
            List of RecoveryPoint objects sorted by recommendation score
        """
        try:
            # Get recent backups
            cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
            backups = self.backup_service.list_backups()
            
            # Filter to completed backups within age limit
            valid_backups = [
                b for b in backups 
                if b.status == BackupStatus.COMPLETED and b.created_at >= cutoff_date
            ]
            
            recovery_points = []
            
            for backup in valid_backups:
                # Verify backup integrity
                verification = self.backup_service.verify_backup(backup.backup_id)
                
                # Calculate recovery score
                score = self._calculate_recovery_score(backup, verification)
                
                # Estimate recovery time
                estimated_time = self._estimate_recovery_time(backup)
                
                recovery_point = RecoveryPoint(
                    backup_info=backup,
                    verification_result=verification,
                    recovery_score=score,
                    estimated_recovery_time_minutes=estimated_time
                )
                
                recovery_points.append(recovery_point)
            
            # Sort by recovery score (highest first)
            recovery_points.sort(key=lambda rp: rp.recovery_score, reverse=True)
            
            logger.info(f"Found {len(recovery_points)} recovery points")
            return recovery_points
            
        except Exception as e:
            logger.error(f"Failed to get recovery points: {e}")
            return []
    
    def _calculate_recovery_score(
        self, 
        backup: BackupInfo, 
        verification: VerificationResult
    ) -> float:
        """Calculate recovery score for a backup.
        
        Args:
            backup: Backup information
            verification: Verification result
            
        Returns:
            Recovery score (0-100)
        """
        score = 0.0
        
        # Base score for valid backup
        if verification.is_valid:
            score += 40
        else:
            return 0  # Invalid backups get 0 score
        
        # Age factor (newer is better)
        age_hours = (datetime.utcnow() - backup.created_at).total_seconds() / 3600
        if age_hours <= 24:
            score += 30  # Very recent
        elif age_hours <= 168:  # 1 week
            score += 20
        elif age_hours <= 720:  # 1 month
            score += 10
        
        # Backup type factor
        if backup.backup_type == BackupType.FULL:
            score += 20
        elif backup.backup_type == BackupType.DIFFERENTIAL:
            score += 15
        else:  # Incremental
            score += 10
        
        # Size factor (reasonable size is better)
        size_mb = backup.file_size / (1024 * 1024)
        if 10 <= size_mb <= 10000:  # 10MB to 10GB
            score += 10
        elif size_mb > 0:
            score += 5
        
        return min(100, score)
    
    def _estimate_recovery_time(self, backup: BackupInfo) -> int:
        """Estimate recovery time in minutes.
        
        Args:
            backup: Backup information
            
        Returns:
            Estimated recovery time in minutes
        """
        # Base time for setup and verification
        base_time = 5
        
        # Time based on backup size (assume 100MB/minute restore rate)
        size_mb = backup.compressed_size / (1024 * 1024)
        size_time = max(1, int(size_mb / 100))
        
        # Additional time for encryption/compression
        if backup.is_encrypted:
            size_time += 2
        
        # Additional time for backup type
        if backup.backup_type == BackupType.FULL:
            type_time = 5
        else:
            type_time = 2
        
        return base_time + size_time + type_time
    
    def start_manual_recovery(self, backup_id: str) -> str:
        """Start manual recovery from specific backup.
        
        Args:
            backup_id: ID of backup to restore from
            
        Returns:
            Recovery operation ID
        """
        operation_id = f"recovery_{int(time.time())}"
        
        with self.operation_lock:
            operation = RecoveryOperation(
                operation_id=operation_id,
                trigger=RecoveryTrigger.MANUAL,
                selected_backup_id=backup_id
            )
            self.active_operations[operation_id] = operation
        
        # Start recovery in background thread
        recovery_thread = threading.Thread(
            target=self._execute_recovery,
            args=(operation,),
            name=f"Recovery-{operation_id}",
            daemon=True
        )
        recovery_thread.start()
        
        logger.info(f"Started manual recovery: {operation_id}")
        return operation_id
    
    def start_automatic_recovery(self, trigger: RecoveryTrigger) -> Optional[str]:
        """Start automatic recovery.
        
        Args:
            trigger: What triggered the recovery
            
        Returns:
            Recovery operation ID if started, None if not eligible
        """
        if not self.auto_recovery_enabled:
            logger.info("Automatic recovery is disabled")
            return None
        
        # Check recovery cooldown
        if self._is_in_recovery_cooldown():
            logger.warning("Recovery is in cooldown period")
            return None
        
        # Check maximum attempts
        if self.recovery_attempts >= self.max_recovery_attempts:
            logger.error("Maximum recovery attempts reached")
            return None
        
        operation_id = f"auto_recovery_{int(time.time())}"
        
        with self.operation_lock:
            operation = RecoveryOperation(
                operation_id=operation_id,
                trigger=trigger
            )
            self.active_operations[operation_id] = operation
        
        # Start recovery in background thread
        recovery_thread = threading.Thread(
            target=self._execute_automatic_recovery,
            args=(operation,),
            name=f"AutoRecovery-{operation_id}",
            daemon=True
        )
        recovery_thread.start()
        
        logger.info(f"Started automatic recovery: {operation_id}")
        return operation_id
    
    def _execute_recovery(self, operation: RecoveryOperation):
        """Execute recovery operation.
        
        Args:
            operation: RecoveryOperation to execute
        """
        try:
            operation.status = RecoveryStatus.ANALYZING
            operation.update_progress(10, "Analyzing recovery requirements")
            
            if self.recovery_started_callback:
                self.recovery_started_callback(operation)
            
            # Verify backup exists and is valid
            if not operation.selected_backup_id:
                raise RuntimeError("No backup selected for recovery")
            
            operation.update_progress(20, "Verifying backup integrity")
            verification = self.backup_service.verify_backup(operation.selected_backup_id)
            
            if not verification.is_valid:
                raise RuntimeError(f"Backup verification failed: {verification.error_details}")
            
            operation.add_log("Backup verification successful")
            
            # Perform pre-recovery checks
            operation.update_progress(30, "Performing pre-recovery checks")
            self._perform_pre_recovery_checks(operation)
            
            # Execute restore
            operation.status = RecoveryStatus.RESTORING
            operation.update_progress(50, "Restoring database from backup")
            
            restore_result = self.backup_service.restore_backup(operation.selected_backup_id)
            
            if restore_result.status != "completed":
                raise RuntimeError(f"Restore failed: {restore_result.error_details}")
            
            operation.add_log("Database restore completed")
            
            # Verify recovery
            operation.status = RecoveryStatus.VERIFYING
            operation.update_progress(80, "Verifying recovery")
            
            if self._verify_recovery(operation):
                operation.status = RecoveryStatus.COMPLETED
                operation.update_progress(100, "Recovery completed successfully")
                operation.completed_at = datetime.utcnow()
                
                # Reset recovery attempt counter on success
                self.recovery_attempts = 0
                
                if self.recovery_completed_callback:
                    self.recovery_completed_callback(operation)
            else:
                raise RuntimeError("Recovery verification failed")
            
        except Exception as e:
            operation.status = RecoveryStatus.FAILED
            operation.error_message = str(e)
            operation.completed_at = datetime.utcnow()
            operation.add_log(f"Recovery failed: {e}")
            
            # Increment recovery attempts for automatic recovery
            if operation.trigger != RecoveryTrigger.MANUAL:
                self.recovery_attempts += 1
                self.last_recovery_attempt = datetime.utcnow()
            
            if self.recovery_failed_callback:
                self.recovery_failed_callback(operation)
            
            logger.error(f"Recovery {operation.operation_id} failed: {e}")
    
    def _execute_automatic_recovery(self, operation: RecoveryOperation):
        """Execute automatic recovery operation.
        
        Args:
            operation: RecoveryOperation to execute
        """
        try:
            operation.status = RecoveryStatus.SELECTING_BACKUP
            operation.update_progress(10, "Selecting best recovery point")
            
            # Get recovery points and select the best one
            recovery_points = self.get_recovery_points(max_age_days=7)  # Only recent backups for auto recovery
            
            if not recovery_points:
                raise RuntimeError("No valid recovery points available")
            
            # Select the highest scoring recovery point
            best_recovery_point = recovery_points[0]
            
            if best_recovery_point.recovery_score < 50:
                raise RuntimeError(f"Best available backup has low score: {best_recovery_point.recovery_score}")
            
            operation.selected_backup_id = best_recovery_point.backup_info.backup_id
            operation.add_log(f"Selected backup: {operation.selected_backup_id} (score: {best_recovery_point.recovery_score})")
            
            # Continue with normal recovery process
            self._execute_recovery(operation)
            
        except Exception as e:
            operation.status = RecoveryStatus.FAILED
            operation.error_message = str(e)
            operation.completed_at = datetime.utcnow()
            operation.add_log(f"Automatic recovery failed: {e}")
            
            self.recovery_attempts += 1
            self.last_recovery_attempt = datetime.utcnow()
            
            if self.recovery_failed_callback:
                self.recovery_failed_callback(operation)
            
            logger.error(f"Automatic recovery {operation.operation_id} failed: {e}")
    
    def _perform_pre_recovery_checks(self, operation: RecoveryOperation):
        """Perform pre-recovery checks.
        
        Args:
            operation: RecoveryOperation being executed
        """
        # Check disk space
        backup_record = self.backup_service.db_manager.get_backup_record(operation.selected_backup_id)
        if backup_record:
            # Estimate space needed (backup size + 50% overhead)
            space_needed_mb = (backup_record['file_size'] / (1024 * 1024)) * 1.5
            
            # This would integrate with disk monitor if available
            operation.add_log(f"Estimated space needed: {space_needed_mb:.1f}MB")
        
        # Check database connectivity (if database is running)
        try:
            if self.backup_service.db_manager.test_connection():
                operation.add_log("Database is currently accessible - will be restored")
            else:
                operation.add_log("Database is not accessible - recovery may help")
        except Exception:
            operation.add_log("Cannot test database connection - proceeding with recovery")
    
    def _verify_recovery(self, operation: RecoveryOperation) -> bool:
        """Verify recovery was successful.
        
        Args:
            operation: RecoveryOperation to verify
            
        Returns:
            True if recovery verification passed, False otherwise
        """
        try:
            # Test database connection
            if not self.backup_service.db_manager.test_connection():
                operation.add_log("❌ Database connection test failed")
                return False
            
            operation.add_log("✅ Database connection test passed")
            
            # Get database info to verify it's working
            db_info = self.backup_service.db_manager.get_database_info()
            if not db_info:
                operation.add_log("❌ Could not retrieve database information")
                return False
            
            operation.add_log(f"✅ Database info retrieved: {db_info.get('table_count', 0)} tables")
            
            # Additional verification could include:
            # - Check critical tables exist
            # - Verify data integrity
            # - Run application-specific health checks
            
            return True
            
        except Exception as e:
            operation.add_log(f"❌ Recovery verification failed: {e}")
            return False
    
    def _is_in_recovery_cooldown(self) -> bool:
        """Check if recovery is in cooldown period.
        
        Returns:
            True if in cooldown, False otherwise
        """
        if not self.last_recovery_attempt:
            return False
        
        cooldown_end = self.last_recovery_attempt + timedelta(minutes=self.recovery_cooldown_minutes)
        return datetime.utcnow() < cooldown_end
    
    def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get status of recovery operation.
        
        Args:
            operation_id: Recovery operation ID
            
        Returns:
            Operation status dictionary or None if not found
        """
        with self.operation_lock:
            operation = self.active_operations.get(operation_id)
            return operation.to_dict() if operation else None
    
    def list_operations(self, include_completed: bool = True) -> List[Dict[str, Any]]:
        """List recovery operations.
        
        Args:
            include_completed: Include completed operations
            
        Returns:
            List of operation status dictionaries
        """
        with self.operation_lock:
            operations = []
            for operation in self.active_operations.values():
                if include_completed or operation.status not in [RecoveryStatus.COMPLETED, RecoveryStatus.FAILED]:
                    operations.append(operation.to_dict())
            
            # Sort by start time (newest first)
            operations.sort(key=lambda op: op['started_at'], reverse=True)
            return operations
    
    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel recovery operation.
        
        Args:
            operation_id: Recovery operation ID
            
        Returns:
            True if cancelled successfully, False otherwise
        """
        with self.operation_lock:
            operation = self.active_operations.get(operation_id)
            if not operation:
                return False
            
            if operation.status in [RecoveryStatus.COMPLETED, RecoveryStatus.FAILED, RecoveryStatus.CANCELLED]:
                return False
            
            operation.status = RecoveryStatus.CANCELLED
            operation.completed_at = datetime.utcnow()
            operation.add_log("Recovery operation cancelled by user")
            
            logger.info(f"Recovery operation cancelled: {operation_id}")
            return True
    
    def start_health_monitoring(self):
        """Start database health monitoring for automatic recovery."""
        if self.health_check_enabled:
            logger.warning("Health monitoring is already running")
            return
        
        self.health_check_enabled = True
        self.health_stop_event.clear()
        
        self.health_check_thread = threading.Thread(
            target=self._health_check_loop,
            name="RecoveryHealthCheck",
            daemon=True
        )
        self.health_check_thread.start()
        
        logger.info("Database health monitoring started")
    
    def stop_health_monitoring(self):
        """Stop database health monitoring."""
        if not self.health_check_enabled:
            logger.warning("Health monitoring is not running")
            return
        
        self.health_check_enabled = False
        self.health_stop_event.set()
        
        if self.health_check_thread and self.health_check_thread.is_alive():
            self.health_check_thread.join(timeout=10)
            if self.health_check_thread.is_alive():
                logger.warning("Health check thread did not stop gracefully")
        
        logger.info("Database health monitoring stopped")
    
    def _health_check_loop(self):
        """Main health check loop."""
        logger.info("Database health check loop started")
        consecutive_failures = 0
        failure_threshold = 3
        
        while self.health_check_enabled and not self.health_stop_event.is_set():
            try:
                # Test database connection
                if self.backup_service.db_manager.test_connection():
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    logger.warning(f"Database health check failed ({consecutive_failures}/{failure_threshold})")
                    
                    # Trigger automatic recovery after threshold failures
                    if consecutive_failures >= failure_threshold:
                        logger.error("Database health check threshold reached, triggering automatic recovery")
                        self.start_automatic_recovery(RecoveryTrigger.HEALTH_CHECK_FAILURE)
                        consecutive_failures = 0  # Reset counter
                
                # Wait for next check
                self.health_stop_event.wait(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                self.health_stop_event.wait(60)  # Wait 1 minute before retry
        
        logger.info("Database health check loop stopped")
    
    def set_recovery_callbacks(
        self,
        started_callback: Optional[Callable[[RecoveryOperation], None]] = None,
        completed_callback: Optional[Callable[[RecoveryOperation], None]] = None,
        failed_callback: Optional[Callable[[RecoveryOperation], None]] = None
    ):
        """Set callbacks for recovery events.
        
        Args:
            started_callback: Called when recovery starts
            completed_callback: Called when recovery completes successfully
            failed_callback: Called when recovery fails
        """
        self.recovery_started_callback = started_callback
        self.recovery_completed_callback = completed_callback
        self.recovery_failed_callback = failed_callback
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """Get overall recovery system status.
        
        Returns:
            Dictionary with recovery system status
        """
        with self.operation_lock:
            active_count = len([
                op for op in self.active_operations.values()
                if op.status not in [RecoveryStatus.COMPLETED, RecoveryStatus.FAILED, RecoveryStatus.CANCELLED]
            ])
        
        return {
            'auto_recovery_enabled': self.auto_recovery_enabled,
            'health_monitoring_enabled': self.health_check_enabled,
            'recovery_attempts': self.recovery_attempts,
            'max_recovery_attempts': self.max_recovery_attempts,
            'last_recovery_attempt': self.last_recovery_attempt.isoformat() if self.last_recovery_attempt else None,
            'in_cooldown': self._is_in_recovery_cooldown(),
            'cooldown_minutes': self.recovery_cooldown_minutes,
            'active_operations': active_count,
            'total_operations': len(self.active_operations)
        }