"""Backup retention and cleanup management."""

import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from enum import Enum

from .models import (
    BackupInfo, BackupStatus, BackupType, CleanupResult, 
    BackupFilters, BackupMetrics
)
from .backup_service import BackupService
from .disk_monitor import DiskSpaceMonitor
from .notifications import BackupNotificationService

logger = logging.getLogger(__name__)


class RetentionPolicy(str, Enum):
    """Types of retention policies."""
    TIME_BASED = "time_based"
    COUNT_BASED = "count_based"
    SIZE_BASED = "size_based"
    HYBRID = "hybrid"


class CleanupTrigger(str, Enum):
    """Types of cleanup triggers."""
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    DISK_SPACE_LOW = "disk_space_low"
    RETENTION_POLICY = "retention_policy"
    EMERGENCY = "emergency"


class RetentionRule:
    """Defines a backup retention rule."""
    
    def __init__(
        self,
        rule_id: str,
        policy_type: RetentionPolicy,
        backup_type: Optional[BackupType] = None,
        max_age_days: Optional[int] = None,
        max_count: Optional[int] = None,
        max_size_mb: Optional[int] = None,
        priority: int = 100
    ):
        """Initialize retention rule.
        
        Args:
            rule_id: Unique rule identifier
            policy_type: Type of retention policy
            backup_type: Backup type this rule applies to (None for all)
            max_age_days: Maximum age in days
            max_count: Maximum number of backups to keep
            max_size_mb: Maximum total size in MB
            priority: Rule priority (lower number = higher priority)
        """
        self.rule_id = rule_id
        self.policy_type = policy_type
        self.backup_type = backup_type
        self.max_age_days = max_age_days
        self.max_count = max_count
        self.max_size_mb = max_size_mb
        self.priority = priority
    
    def applies_to_backup(self, backup: BackupInfo) -> bool:
        """Check if rule applies to a backup.
        
        Args:
            backup: Backup to check
            
        Returns:
            True if rule applies, False otherwise
        """
        if self.backup_type and backup.backup_type != self.backup_type:
            return False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'rule_id': self.rule_id,
            'policy_type': self.policy_type.value,
            'backup_type': self.backup_type.value if self.backup_type else None,
            'max_age_days': self.max_age_days,
            'max_count': self.max_count,
            'max_size_mb': self.max_size_mb,
            'priority': self.priority
        }


class RetentionManager:
    """Manages backup retention and cleanup operations."""
    
    def __init__(
        self,
        backup_service: BackupService,
        disk_monitor: Optional[DiskSpaceMonitor] = None,
        notification_service: Optional[BackupNotificationService] = None
    ):
        """Initialize retention manager.
        
        Args:
            backup_service: BackupService instance
            disk_monitor: Optional disk space monitor
            notification_service: Optional notification service
        """
        self.backup_service = backup_service
        self.disk_monitor = disk_monitor
        self.notification_service = notification_service
        
        # Retention rules
        self.retention_rules: List[RetentionRule] = []
        self._setup_default_rules()
        
        # Cleanup scheduling
        self.cleanup_enabled = False
        self.cleanup_interval_hours = 24  # Daily cleanup by default
        self.cleanup_thread: Optional[threading.Thread] = None
        self.cleanup_stop_event = threading.Event()
        
        # Emergency cleanup settings
        self.emergency_cleanup_enabled = True
        self.emergency_threshold_mb = 500  # Trigger emergency cleanup at 500MB free
        
        # Statistics
        self.last_cleanup_time: Optional[datetime] = None
        self.total_cleanups_performed = 0
        self.total_space_freed_mb = 0
        
        # Callbacks
        self.cleanup_started_callback: Optional[Callable[[str, CleanupTrigger], None]] = None
        self.cleanup_completed_callback: Optional[Callable[[CleanupResult], None]] = None
        
        logger.info("Retention manager initialized")
    
    def _setup_default_rules(self):
        """Setup default retention rules."""
        # Keep full backups for 30 days
        self.retention_rules.append(RetentionRule(
            rule_id="default_full_time",
            policy_type=RetentionPolicy.TIME_BASED,
            backup_type=BackupType.FULL,
            max_age_days=30,
            priority=100
        ))
        
        # Keep incremental backups for 7 days
        self.retention_rules.append(RetentionRule(
            rule_id="default_incremental_time",
            policy_type=RetentionPolicy.TIME_BASED,
            backup_type=BackupType.INCREMENTAL,
            max_age_days=7,
            priority=100
        ))
        
        # Keep at least 5 most recent backups regardless of age
        self.retention_rules.append(RetentionRule(
            rule_id="default_minimum_count",
            policy_type=RetentionPolicy.COUNT_BASED,
            max_count=5,
            priority=50  # Higher priority than time-based rules
        ))
    
    def add_retention_rule(self, rule: RetentionRule) -> bool:
        """Add a retention rule.
        
        Args:
            rule: RetentionRule to add
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            # Check if rule with same ID already exists
            existing_rule = next((r for r in self.retention_rules if r.rule_id == rule.rule_id), None)
            if existing_rule:
                logger.warning(f"Rule with ID {rule.rule_id} already exists")
                return False
            
            self.retention_rules.append(rule)
            
            # Sort rules by priority
            self.retention_rules.sort(key=lambda r: r.priority)
            
            logger.info(f"Added retention rule: {rule.rule_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add retention rule: {e}")
            return False
    
    def remove_retention_rule(self, rule_id: str) -> bool:
        """Remove a retention rule.
        
        Args:
            rule_id: Rule identifier
            
        Returns:
            True if removed successfully, False otherwise
        """
        try:
            original_count = len(self.retention_rules)
            self.retention_rules = [r for r in self.retention_rules if r.rule_id != rule_id]
            
            if len(self.retention_rules) < original_count:
                logger.info(f"Removed retention rule: {rule_id}")
                return True
            else:
                logger.warning(f"Rule not found: {rule_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove retention rule: {e}")
            return False
    
    def get_retention_rules(self) -> List[Dict[str, Any]]:
        """Get all retention rules.
        
        Returns:
            List of retention rule dictionaries
        """
        return [rule.to_dict() for rule in self.retention_rules]
    
    def analyze_retention_compliance(self) -> Dict[str, Any]:
        """Analyze current backup retention compliance.
        
        Returns:
            Dictionary with compliance analysis
        """
        try:
            all_backups = self.backup_service.list_backups()
            completed_backups = [b for b in all_backups if b.status == BackupStatus.COMPLETED]
            
            analysis = {
                'total_backups': len(completed_backups),
                'rules_analysis': [],
                'backups_to_delete': [],
                'compliance_score': 0.0,
                'recommendations': []
            }
            
            # Analyze each rule
            for rule in self.retention_rules:
                rule_analysis = self._analyze_rule_compliance(rule, completed_backups)
                analysis['rules_analysis'].append(rule_analysis)
                
                # Collect backups marked for deletion by this rule
                analysis['backups_to_delete'].extend(rule_analysis.get('backups_to_delete', []))
            
            # Remove duplicates from backups to delete
            unique_backups_to_delete = []
            seen_ids = set()
            for backup_id in analysis['backups_to_delete']:
                if backup_id not in seen_ids:
                    unique_backups_to_delete.append(backup_id)
                    seen_ids.add(backup_id)
            
            analysis['backups_to_delete'] = unique_backups_to_delete
            
            # Calculate compliance score
            total_rules = len(self.retention_rules)
            compliant_rules = len([r for r in analysis['rules_analysis'] if r.get('compliant', False)])
            analysis['compliance_score'] = (compliant_rules / total_rules * 100) if total_rules > 0 else 100
            
            # Generate recommendations
            analysis['recommendations'] = self._generate_retention_recommendations(analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze retention compliance: {e}")
            return {
                'total_backups': 0,
                'rules_analysis': [],
                'backups_to_delete': [],
                'compliance_score': 0.0,
                'recommendations': [f"Analysis failed: {str(e)}"],
                'error': str(e)
            }
    
    def _analyze_rule_compliance(self, rule: RetentionRule, backups: List[BackupInfo]) -> Dict[str, Any]:
        """Analyze compliance for a specific rule.
        
        Args:
            rule: RetentionRule to analyze
            backups: List of backups to analyze
            
        Returns:
            Dictionary with rule compliance analysis
        """
        # Filter backups that this rule applies to
        applicable_backups = [b for b in backups if rule.applies_to_backup(b)]
        
        analysis = {
            'rule_id': rule.rule_id,
            'policy_type': rule.policy_type.value,
            'applicable_backups': len(applicable_backups),
            'compliant': True,
            'backups_to_delete': [],
            'violations': []
        }
        
        if rule.policy_type == RetentionPolicy.TIME_BASED and rule.max_age_days:
            cutoff_date = datetime.utcnow() - timedelta(days=rule.max_age_days)
            old_backups = [b for b in applicable_backups if b.created_at < cutoff_date]
            
            if old_backups:
                analysis['compliant'] = False
                analysis['backups_to_delete'] = [b.backup_id for b in old_backups]
                analysis['violations'].append(f"{len(old_backups)} backups exceed {rule.max_age_days} day limit")
        
        elif rule.policy_type == RetentionPolicy.COUNT_BASED and rule.max_count:
            if len(applicable_backups) > rule.max_count:
                # Sort by creation time (newest first) and mark excess for deletion
                sorted_backups = sorted(applicable_backups, key=lambda b: b.created_at, reverse=True)
                excess_backups = sorted_backups[rule.max_count:]
                
                analysis['compliant'] = False
                analysis['backups_to_delete'] = [b.backup_id for b in excess_backups]
                analysis['violations'].append(f"{len(excess_backups)} backups exceed count limit of {rule.max_count}")
        
        elif rule.policy_type == RetentionPolicy.SIZE_BASED and rule.max_size_mb:
            total_size_mb = sum(b.compressed_size or b.file_size for b in applicable_backups) / (1024 * 1024)
            
            if total_size_mb > rule.max_size_mb:
                # Sort by creation time (oldest first) and mark for deletion until under limit
                sorted_backups = sorted(applicable_backups, key=lambda b: b.created_at)
                current_size_mb = total_size_mb
                backups_to_delete = []
                
                for backup in sorted_backups:
                    if current_size_mb <= rule.max_size_mb:
                        break
                    
                    backup_size_mb = (backup.compressed_size or backup.file_size) / (1024 * 1024)
                    backups_to_delete.append(backup.backup_id)
                    current_size_mb -= backup_size_mb
                
                if backups_to_delete:
                    analysis['compliant'] = False
                    analysis['backups_to_delete'] = backups_to_delete
                    analysis['violations'].append(f"Total size {total_size_mb:.1f}MB exceeds limit of {rule.max_size_mb}MB")
        
        return analysis
    
    def _generate_retention_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate retention recommendations based on analysis.
        
        Args:
            analysis: Retention compliance analysis
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        if analysis['compliance_score'] < 100:
            recommendations.append(f"Retention compliance is {analysis['compliance_score']:.1f}% - cleanup recommended")
        
        if analysis['backups_to_delete']:
            count = len(analysis['backups_to_delete'])
            recommendations.append(f"{count} backups can be safely deleted to improve compliance")
        
        # Check for potential issues
        total_backups = analysis['total_backups']
        if total_backups < 3:
            recommendations.append("Very few backups available - consider increasing backup frequency")
        elif total_backups > 100:
            recommendations.append("Large number of backups - consider tightening retention policies")
        
        # Disk space recommendations
        if self.disk_monitor:
            try:
                disk_usage = self.disk_monitor.get_disk_usage()
                if disk_usage.get('is_warning', False):
                    recommendations.append("Low disk space detected - immediate cleanup recommended")
                elif disk_usage.get('free_mb', 0) < 2000:  # Less than 2GB
                    recommendations.append("Disk space getting low - proactive cleanup recommended")
            except Exception:
                pass
        
        return recommendations
    
    def perform_cleanup(self, trigger: CleanupTrigger = CleanupTrigger.MANUAL, dry_run: bool = False) -> CleanupResult:
        """Perform backup cleanup based on retention policies.
        
        Args:
            trigger: What triggered the cleanup
            dry_run: If True, only analyze what would be deleted without actually deleting
            
        Returns:
            CleanupResult with cleanup details
        """
        cleanup_id = f"cleanup_{int(time.time())}"
        start_time = datetime.utcnow()
        
        logger.info(f"Starting backup cleanup {cleanup_id} (trigger: {trigger.value}, dry_run: {dry_run})")
        
        if self.cleanup_started_callback:
            try:
                self.cleanup_started_callback(cleanup_id, trigger)
            except Exception as e:
                logger.error(f"Error in cleanup started callback: {e}")
        
        try:
            # Analyze retention compliance
            analysis = self.analyze_retention_compliance()
            backups_to_delete = analysis['backups_to_delete']
            
            if not backups_to_delete:
                logger.info("No backups need to be deleted")
                return CleanupResult(
                    cleanup_id=cleanup_id,
                    deleted_backups=[],
                    freed_space_bytes=0,
                    cleanup_time=start_time
                )
            
            deleted_backups = []
            freed_space_bytes = 0
            
            if not dry_run:
                # Actually delete the backups
                for backup_id in backups_to_delete:
                    try:
                        # Get backup info before deletion
                        backup_record = self.backup_service.db_manager.get_backup_record(backup_id)
                        if not backup_record:
                            logger.warning(f"Backup record not found: {backup_id}")
                            continue
                        
                        backup_path = Path(backup_record['file_path'])
                        file_size = 0
                        
                        # Delete backup file
                        if backup_path.exists():
                            file_size = backup_path.stat().st_size
                            backup_path.unlink()
                            logger.info(f"Deleted backup file: {backup_path}")
                        
                        # Delete backup record
                        if self.backup_service.db_manager.delete_backup_record(backup_id):
                            deleted_backups.append(backup_id)
                            freed_space_bytes += file_size
                            logger.info(f"Deleted backup record: {backup_id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to delete backup {backup_id}: {e}")
            else:
                # Dry run - just calculate what would be freed
                for backup_id in backups_to_delete:
                    backup_record = self.backup_service.db_manager.get_backup_record(backup_id)
                    if backup_record:
                        backup_path = Path(backup_record['file_path'])
                        if backup_path.exists():
                            freed_space_bytes += backup_path.stat().st_size
                
                deleted_backups = backups_to_delete
            
            # Update statistics
            if not dry_run:
                self.last_cleanup_time = start_time
                self.total_cleanups_performed += 1
                self.total_space_freed_mb += freed_space_bytes / (1024 * 1024)
            
            result = CleanupResult(
                cleanup_id=cleanup_id,
                deleted_backups=deleted_backups,
                freed_space_bytes=freed_space_bytes,
                cleanup_time=start_time
            )
            
            logger.info(f"Cleanup {cleanup_id} completed: deleted {len(deleted_backups)} backups, freed {freed_space_bytes / (1024 * 1024):.1f}MB")
            
            # Send notifications
            if not dry_run and self.notification_service:
                try:
                    self.notification_service.send_cleanup_notification(result.dict())
                except Exception as e:
                    logger.error(f"Failed to send cleanup notification: {e}")
            
            if self.cleanup_completed_callback:
                try:
                    self.cleanup_completed_callback(result)
                except Exception as e:
                    logger.error(f"Error in cleanup completed callback: {e}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Cleanup {cleanup_id} failed: {error_msg}")
            
            return CleanupResult(
                cleanup_id=cleanup_id,
                deleted_backups=[],
                freed_space_bytes=0,
                cleanup_time=start_time,
                error_details=error_msg
            )
    
    def start_scheduled_cleanup(self):
        """Start scheduled cleanup process."""
        if self.cleanup_enabled:
            logger.warning("Scheduled cleanup is already running")
            return
        
        self.cleanup_enabled = True
        self.cleanup_stop_event.clear()
        
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name="RetentionCleanup",
            daemon=True
        )
        self.cleanup_thread.start()
        
        logger.info("Scheduled cleanup started")
    
    def stop_scheduled_cleanup(self):
        """Stop scheduled cleanup process."""
        if not self.cleanup_enabled:
            logger.warning("Scheduled cleanup is not running")
            return
        
        self.cleanup_enabled = False
        self.cleanup_stop_event.set()
        
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=10)
            if self.cleanup_thread.is_alive():
                logger.warning("Cleanup thread did not stop gracefully")
        
        logger.info("Scheduled cleanup stopped")
    
    def _cleanup_loop(self):
        """Main cleanup loop."""
        logger.info("Retention cleanup loop started")
        
        while self.cleanup_enabled and not self.cleanup_stop_event.is_set():
            try:
                # Perform scheduled cleanup
                self.perform_cleanup(trigger=CleanupTrigger.SCHEDULED)
                
                # Check for emergency cleanup if disk monitor is available
                if self.emergency_cleanup_enabled and self.disk_monitor:
                    try:
                        disk_usage = self.disk_monitor.get_disk_usage()
                        free_mb = disk_usage.get('free_mb', float('inf'))
                        
                        if free_mb < self.emergency_threshold_mb:
                            logger.warning(f"Emergency cleanup triggered: {free_mb:.1f}MB free")
                            self.perform_cleanup(trigger=CleanupTrigger.EMERGENCY)
                    except Exception as e:
                        logger.error(f"Error checking disk space for emergency cleanup: {e}")
                
                # Wait for next cleanup
                wait_seconds = self.cleanup_interval_hours * 3600
                self.cleanup_stop_event.wait(wait_seconds)
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                self.cleanup_stop_event.wait(3600)  # Wait 1 hour before retry
        
        logger.info("Retention cleanup loop stopped")
    
    def get_retention_statistics(self) -> Dict[str, Any]:
        """Get retention and cleanup statistics.
        
        Returns:
            Dictionary with retention statistics
        """
        try:
            # Get backup metrics
            backup_metrics = self.backup_service.get_backup_metrics()
            
            # Get retention compliance
            compliance_analysis = self.analyze_retention_compliance()
            
            return {
                'total_backups': backup_metrics.total_backups,
                'successful_backups': backup_metrics.successful_backups,
                'failed_backups': backup_metrics.failed_backups,
                'total_size_mb': backup_metrics.total_size_bytes / (1024 * 1024),
                'retention_compliance_score': compliance_analysis['compliance_score'],
                'backups_pending_deletion': len(compliance_analysis['backups_to_delete']),
                'retention_rules_count': len(self.retention_rules),
                'last_cleanup_time': self.last_cleanup_time.isoformat() if self.last_cleanup_time else None,
                'total_cleanups_performed': self.total_cleanups_performed,
                'total_space_freed_mb': self.total_space_freed_mb,
                'cleanup_enabled': self.cleanup_enabled,
                'cleanup_interval_hours': self.cleanup_interval_hours,
                'emergency_cleanup_enabled': self.emergency_cleanup_enabled,
                'emergency_threshold_mb': self.emergency_threshold_mb
            }
            
        except Exception as e:
            logger.error(f"Failed to get retention statistics: {e}")
            return {
                'error': str(e)
            }
    
    def set_cleanup_callbacks(
        self,
        started_callback: Optional[Callable[[str, CleanupTrigger], None]] = None,
        completed_callback: Optional[Callable[[CleanupResult], None]] = None
    ):
        """Set callbacks for cleanup events.
        
        Args:
            started_callback: Called when cleanup starts
            completed_callback: Called when cleanup completes
        """
        self.cleanup_started_callback = started_callback
        self.cleanup_completed_callback = completed_callback