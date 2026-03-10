"""Integrated backup management service that coordinates all backup operations."""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from .backup_service import BackupService
from .database_manager import DatabaseManager
from .scheduler import BackupScheduler
from .recovery_service import RecoveryService
from .retention_manager import RetentionManager
from .notifications import BackupNotificationService, NotificationConfig
from .disk_monitor import DiskSpaceMonitor
from .models import (
    BackupConfig, DatabaseConfig, BackupSchedule, BackupType,
    BackupResult, RestoreResult, CleanupResult
)

logger = logging.getLogger(__name__)


class BackupManager:
    """Integrated backup management service."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize backup manager with configuration.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        
        # Initialize core services
        self._initialize_services()
        
        # Setup integrations
        self._setup_integrations()
        
        logger.info("Backup manager initialized successfully")
    
    def _initialize_services(self):
        """Initialize all backup services."""
        # Database configuration
        db_config_dict = self.config.get('database', {})
        self.db_config = DatabaseConfig(
            host=db_config_dict.get('host', 'localhost'),
            port=db_config_dict.get('port', 5432),
            database=db_config_dict.get('database', 'northbound'),
            username=db_config_dict.get('username', 'postgres'),
            password=db_config_dict.get('password', ''),
            ssl_mode=db_config_dict.get('ssl_mode', 'prefer'),
            connection_timeout=db_config_dict.get('connection_timeout', 30)
        )
        
        # Backup configuration
        backup_config_dict = self.config.get('backup', {})
        backup_dir = backup_config_dict.get('directory', './backups')
        
        self.backup_config = BackupConfig(
            database_url=self.db_config.connection_url,
            backup_directory=backup_dir,
            compression_enabled=backup_config_dict.get('compression_enabled', True),
            encryption_enabled=backup_config_dict.get('encryption_enabled', True),
            encryption_key=backup_config_dict.get('encryption_key'),
            retention_days=backup_config_dict.get('retention_days', 7),
            max_backup_size_mb=backup_config_dict.get('max_backup_size_mb', 1000),
            pg_dump_path=backup_config_dict.get('pg_dump_path', 'pg_dump'),
            psql_path=backup_config_dict.get('psql_path', 'psql'),
            notification_email=backup_config_dict.get('notification_email'),
            webhook_url=backup_config_dict.get('webhook_url')
        )
        
        # Initialize core backup service
        self.backup_service = BackupService(self.backup_config, self.db_config)
        
        # Initialize scheduler
        self.scheduler = BackupScheduler(self.backup_service)
        
        # Initialize recovery service
        recovery_config = self.config.get('recovery', {})
        self.recovery_service = RecoveryService(
            backup_service=self.backup_service,
            db_config=self.db_config,
            auto_recovery_enabled=recovery_config.get('auto_recovery_enabled', True),
            max_recovery_attempts=recovery_config.get('max_recovery_attempts', 3)
        )
        
        # Initialize disk monitor
        disk_config = self.config.get('disk_monitoring', {})
        self.disk_monitor = DiskSpaceMonitor(
            backup_directory=backup_dir,
            warning_threshold_mb=disk_config.get('warning_threshold_mb', 1000),
            critical_threshold_mb=disk_config.get('critical_threshold_mb', 500),
            check_interval_seconds=disk_config.get('check_interval_seconds', 300)
        )
        
        # Initialize notification service
        notification_config_dict = self.config.get('notifications', {})
        notification_config = NotificationConfig(
            email_enabled=notification_config_dict.get('email_enabled', False),
            smtp_host=notification_config_dict.get('smtp_host'),
            smtp_port=notification_config_dict.get('smtp_port', 587),
            smtp_username=notification_config_dict.get('smtp_username'),
            smtp_password=notification_config_dict.get('smtp_password'),
            smtp_use_tls=notification_config_dict.get('smtp_use_tls', True),
            from_email=notification_config_dict.get('from_email'),
            to_emails=notification_config_dict.get('to_emails', []),
            webhook_enabled=notification_config_dict.get('webhook_enabled', False),
            webhook_url=notification_config_dict.get('webhook_url'),
            webhook_timeout=notification_config_dict.get('webhook_timeout', 30)
        )
        self.notification_service = BackupNotificationService(notification_config)
        
        # Initialize retention manager
        self.retention_manager = RetentionManager(
            backup_service=self.backup_service,
            disk_monitor=self.disk_monitor,
            notification_service=self.notification_service
        )
    
    def _setup_integrations(self):
        """Setup integrations between services."""
        # Setup scheduler callbacks
        self.scheduler.set_success_callback(self._on_backup_success)
        self.scheduler.set_failure_callback(self._on_backup_failure)
        
        # Setup recovery callbacks
        self.recovery_service.set_recovery_callbacks(
            started_callback=self._on_recovery_started,
            completed_callback=self._on_recovery_completed,
            failed_callback=self._on_recovery_failed
        )
        
        # Setup disk monitor callbacks
        self.disk_monitor.set_warning_callback(self._on_disk_space_warning)
        self.disk_monitor.set_critical_callback(self._on_disk_space_critical)
        
        # Setup retention manager callbacks
        self.retention_manager.set_cleanup_callbacks(
            started_callback=self._on_cleanup_started,
            completed_callback=self._on_cleanup_completed
        )
    
    def start(self):
        """Start all backup services."""
        try:
            # Start scheduler
            self.scheduler.start()
            
            # Start disk monitoring
            self.disk_monitor.start_monitoring()
            
            # Start health monitoring for recovery
            self.recovery_service.start_health_monitoring()
            
            # Start scheduled cleanup
            self.retention_manager.start_scheduled_cleanup()
            
            # Setup default backup schedule if configured
            self._setup_default_schedules()
            
            logger.info("All backup services started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start backup services: {e}")
            raise
    
    def stop(self):
        """Stop all backup services."""
        try:
            # Stop scheduler
            self.scheduler.stop()
            
            # Stop disk monitoring
            self.disk_monitor.stop_monitoring()
            
            # Stop health monitoring
            self.recovery_service.stop_health_monitoring()
            
            # Stop scheduled cleanup
            self.retention_manager.stop_scheduled_cleanup()
            
            # Close backup service
            self.backup_service.close()
            
            logger.info("All backup services stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping backup services: {e}")
    
    def _setup_default_schedules(self):
        """Setup default backup schedules."""
        schedules_config = self.config.get('schedules', [])
        
        for schedule_config in schedules_config:
            try:
                schedule = BackupSchedule(
                    schedule_id=schedule_config['schedule_id'],
                    backup_type=BackupType(schedule_config['backup_type']),
                    cron_expression=schedule_config['cron_expression'],
                    is_enabled=schedule_config.get('is_enabled', True),
                    database_name=schedule_config.get('database_name', self.db_config.database),
                    retention_days=schedule_config.get('retention_days', 7),
                    notification_on_failure=schedule_config.get('notification_on_failure', True),
                    notification_on_success=schedule_config.get('notification_on_success', False)
                )
                
                if self.scheduler.add_schedule(schedule):
                    logger.info(f"Added default schedule: {schedule.schedule_id}")
                else:
                    logger.warning(f"Failed to add default schedule: {schedule.schedule_id}")
                    
            except Exception as e:
                logger.error(f"Failed to setup default schedule: {e}")
    
    # Callback methods
    def _on_backup_success(self, result: BackupResult):
        """Handle successful backup."""
        logger.info(f"Backup completed successfully: {result.backup_id}")
        self.notification_service.send_backup_success_notification(result)
    
    def _on_backup_failure(self, result: BackupResult):
        """Handle failed backup."""
        logger.error(f"Backup failed: {result.backup_id} - {result.error_details}")
        self.notification_service.send_backup_failure_notification(result)
    
    def _on_recovery_started(self, operation):
        """Handle recovery started."""
        logger.info(f"Recovery started: {operation.operation_id}")
    
    def _on_recovery_completed(self, operation):
        """Handle recovery completed."""
        logger.info(f"Recovery completed successfully: {operation.operation_id}")
    
    def _on_recovery_failed(self, operation):
        """Handle recovery failed."""
        logger.error(f"Recovery failed: {operation.operation_id} - {operation.error_message}")
    
    def _on_disk_space_warning(self, available_mb: int, threshold_mb: int):
        """Handle disk space warning."""
        logger.warning(f"Disk space warning: {available_mb}MB available")
        self.notification_service.send_disk_space_warning(available_mb, threshold_mb)
        
        # Trigger cleanup if enabled
        if self.retention_manager.cleanup_enabled:
            self.retention_manager.perform_cleanup(trigger="disk_space_low")
    
    def _on_disk_space_critical(self, available_mb: int, threshold_mb: int):
        """Handle critical disk space."""
        logger.critical(f"Critical disk space: {available_mb}MB available")
        self.notification_service.send_disk_space_warning(available_mb, threshold_mb)
        
        # Force emergency cleanup
        self.retention_manager.perform_cleanup(trigger="emergency")
    
    def _on_cleanup_started(self, cleanup_id: str, trigger):
        """Handle cleanup started."""
        logger.info(f"Cleanup started: {cleanup_id} (trigger: {trigger.value})")
    
    def _on_cleanup_completed(self, result: CleanupResult):
        """Handle cleanup completed."""
        logger.info(f"Cleanup completed: {result.cleanup_id} - freed {result.freed_space_bytes / (1024*1024):.1f}MB")
    
    # Public API methods
    def create_backup(self, backup_type: BackupType = BackupType.FULL) -> BackupResult:
        """Create a manual backup.
        
        Args:
            backup_type: Type of backup to create
            
        Returns:
            BackupResult with operation details
        """
        return self.backup_service.create_backup(backup_type)
    
    def get_recovery_points(self, max_age_days: int = 30):
        """Get available recovery points.
        
        Args:
            max_age_days: Maximum age of backups to consider
            
        Returns:
            List of recovery points
        """
        return self.recovery_service.get_recovery_points(max_age_days)
    
    def start_recovery(self, backup_id: str) -> str:
        """Start manual recovery.
        
        Args:
            backup_id: Backup ID to restore from
            
        Returns:
            Recovery operation ID
        """
        return self.recovery_service.start_manual_recovery(backup_id)
    
    def get_recovery_status(self, operation_id: str):
        """Get recovery operation status.
        
        Args:
            operation_id: Recovery operation ID
            
        Returns:
            Recovery operation status
        """
        return self.recovery_service.get_operation_status(operation_id)
    
    def perform_cleanup(self, dry_run: bool = False) -> CleanupResult:
        """Perform manual cleanup.
        
        Args:
            dry_run: If True, only analyze what would be deleted
            
        Returns:
            CleanupResult with cleanup details
        """
        return self.retention_manager.perform_cleanup(trigger="manual", dry_run=dry_run)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall backup system status.
        
        Returns:
            Dictionary with system status
        """
        try:
            # Get backup metrics
            backup_metrics = self.backup_service.get_backup_metrics()
            
            # Get disk usage
            disk_usage = self.disk_monitor.get_disk_usage()
            
            # Get retention statistics
            retention_stats = self.retention_manager.get_retention_statistics()
            
            # Get recovery status
            recovery_status = self.recovery_service.get_recovery_status()
            
            # Get scheduler status
            schedules = self.scheduler.list_schedules()
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'backup_metrics': {
                    'total_backups': backup_metrics.total_backups,
                    'successful_backups': backup_metrics.successful_backups,
                    'failed_backups': backup_metrics.failed_backups,
                    'total_size_mb': backup_metrics.total_size_bytes / (1024 * 1024),
                    'last_backup_time': backup_metrics.last_backup_time.isoformat() if backup_metrics.last_backup_time else None,
                    'average_backup_time_seconds': backup_metrics.average_backup_time_seconds
                },
                'disk_usage': {
                    'total_mb': disk_usage.get('total_mb', 0),
                    'used_mb': disk_usage.get('used_mb', 0),
                    'free_mb': disk_usage.get('free_mb', 0),
                    'usage_percent': disk_usage.get('usage_percent', 0),
                    'is_warning': disk_usage.get('is_warning', False),
                    'is_critical': disk_usage.get('is_critical', False)
                },
                'retention': {
                    'compliance_score': retention_stats.get('retention_compliance_score', 0),
                    'backups_pending_deletion': retention_stats.get('backups_pending_deletion', 0),
                    'last_cleanup_time': retention_stats.get('last_cleanup_time'),
                    'total_cleanups_performed': retention_stats.get('total_cleanups_performed', 0),
                    'total_space_freed_mb': retention_stats.get('total_space_freed_mb', 0)
                },
                'recovery': {
                    'auto_recovery_enabled': recovery_status.get('auto_recovery_enabled', False),
                    'health_monitoring_enabled': recovery_status.get('health_monitoring_enabled', False),
                    'recovery_attempts': recovery_status.get('recovery_attempts', 0),
                    'in_cooldown': recovery_status.get('in_cooldown', False),
                    'active_operations': recovery_status.get('active_operations', 0)
                },
                'scheduler': {
                    'active_schedules': len([s for s in schedules if s.is_enabled]),
                    'total_schedules': len(schedules),
                    'scheduler_running': self.scheduler.running
                },
                'services': {
                    'backup_service': 'running',
                    'scheduler': 'running' if self.scheduler.running else 'stopped',
                    'disk_monitor': 'running' if self.disk_monitor.running else 'stopped',
                    'recovery_service': 'running',
                    'retention_manager': 'running' if self.retention_manager.cleanup_enabled else 'stopped'
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'services': {
                    'backup_service': 'error',
                    'scheduler': 'error',
                    'disk_monitor': 'error',
                    'recovery_service': 'error',
                    'retention_manager': 'error'
                }
            }
    
    def test_notifications(self) -> Dict[str, bool]:
        """Test notification systems.
        
        Returns:
            Dictionary with test results
        """
        return self.notification_service.test_notifications()
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate backup system configuration.
        
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'checks': {}
        }
        
        try:
            # Check database connectivity
            try:
                db_connected = self.backup_service.db_manager.test_connection()
                validation_results['checks']['database_connection'] = db_connected
                if not db_connected:
                    validation_results['errors'].append("Cannot connect to database")
                    validation_results['valid'] = False
            except Exception as e:
                validation_results['errors'].append(f"Database connection test failed: {e}")
                validation_results['valid'] = False
            
            # Check backup directory
            backup_dir = Path(self.backup_config.backup_directory)
            try:
                backup_dir.mkdir(parents=True, exist_ok=True)
                validation_results['checks']['backup_directory'] = True
            except Exception as e:
                validation_results['errors'].append(f"Cannot create backup directory: {e}")
                validation_results['valid'] = False
            
            # Check PostgreSQL tools
            try:
                self.backup_service._verify_pg_tools()
                validation_results['checks']['postgresql_tools'] = True
            except Exception as e:
                validation_results['errors'].append(f"PostgreSQL tools not available: {e}")
                validation_results['valid'] = False
            
            # Check disk space
            try:
                disk_usage = self.disk_monitor.get_disk_usage()
                free_mb = disk_usage.get('free_mb', 0)
                validation_results['checks']['disk_space_mb'] = free_mb
                
                if free_mb < 100:
                    validation_results['errors'].append("Very low disk space (< 100MB)")
                    validation_results['valid'] = False
                elif free_mb < 500:
                    validation_results['warnings'].append("Low disk space (< 500MB)")
            except Exception as e:
                validation_results['warnings'].append(f"Could not check disk space: {e}")
            
            # Check notification configuration
            if self.backup_config.notification_email and not self.notification_service.config.email_enabled:
                validation_results['warnings'].append("Email notification configured but not enabled")
            
            if self.backup_config.webhook_url and not self.notification_service.config.webhook_enabled:
                validation_results['warnings'].append("Webhook URL configured but not enabled")
            
        except Exception as e:
            validation_results['errors'].append(f"Configuration validation failed: {e}")
            validation_results['valid'] = False
        
        return validation_results