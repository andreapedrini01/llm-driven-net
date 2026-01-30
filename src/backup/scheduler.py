"""Backup scheduler for automatic backup operations."""

import asyncio
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from croniter import croniter

from .models import BackupSchedule, BackupType, BackupResult
from .backup_service import BackupService

logger = logging.getLogger(__name__)


class BackupScheduler:
    """Scheduler for automatic backup operations."""
    
    def __init__(self, backup_service: BackupService):
        """Initialize backup scheduler.
        
        Args:
            backup_service: BackupService instance
        """
        self.backup_service = backup_service
        self.schedules: Dict[str, BackupSchedule] = {}
        self.running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Callbacks for notifications
        self.success_callback: Optional[Callable[[BackupResult], None]] = None
        self.failure_callback: Optional[Callable[[BackupResult], None]] = None
        
        logger.info("Backup scheduler initialized")
    
    def add_schedule(self, schedule: BackupSchedule) -> bool:
        """Add a backup schedule.
        
        Args:
            schedule: BackupSchedule configuration
            
        Returns:
            True if schedule added successfully, False otherwise
        """
        try:
            # Validate cron expression
            if not self._validate_cron_expression(schedule.cron_expression):
                logger.error(f"Invalid cron expression: {schedule.cron_expression}")
                return False
            
            self.schedules[schedule.schedule_id] = schedule
            logger.info(f"Added backup schedule: {schedule.schedule_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add schedule {schedule.schedule_id}: {e}")
            return False
    
    def remove_schedule(self, schedule_id: str) -> bool:
        """Remove a backup schedule.
        
        Args:
            schedule_id: Schedule identifier
            
        Returns:
            True if schedule removed successfully, False otherwise
        """
        try:
            if schedule_id in self.schedules:
                del self.schedules[schedule_id]
                logger.info(f"Removed backup schedule: {schedule_id}")
                return True
            else:
                logger.warning(f"Schedule not found: {schedule_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove schedule {schedule_id}: {e}")
            return False
    
    def update_schedule(self, schedule: BackupSchedule) -> bool:
        """Update an existing backup schedule.
        
        Args:
            schedule: Updated BackupSchedule configuration
            
        Returns:
            True if schedule updated successfully, False otherwise
        """
        try:
            if schedule.schedule_id not in self.schedules:
                logger.error(f"Schedule not found: {schedule.schedule_id}")
                return False
            
            # Validate cron expression
            if not self._validate_cron_expression(schedule.cron_expression):
                logger.error(f"Invalid cron expression: {schedule.cron_expression}")
                return False
            
            self.schedules[schedule.schedule_id] = schedule
            logger.info(f"Updated backup schedule: {schedule.schedule_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update schedule {schedule.schedule_id}: {e}")
            return False
    
    def get_schedule(self, schedule_id: str) -> Optional[BackupSchedule]:
        """Get a backup schedule by ID.
        
        Args:
            schedule_id: Schedule identifier
            
        Returns:
            BackupSchedule if found, None otherwise
        """
        return self.schedules.get(schedule_id)
    
    def list_schedules(self) -> List[BackupSchedule]:
        """List all backup schedules.
        
        Returns:
            List of BackupSchedule objects
        """
        return list(self.schedules.values())
    
    def get_next_run_time(self, schedule_id: str) -> Optional[datetime]:
        """Get next run time for a schedule.
        
        Args:
            schedule_id: Schedule identifier
            
        Returns:
            Next run datetime if schedule exists and is enabled, None otherwise
        """
        try:
            schedule = self.schedules.get(schedule_id)
            if not schedule or not schedule.is_enabled:
                return None
            
            cron = croniter(schedule.cron_expression, datetime.utcnow())
            return cron.get_next(datetime)
            
        except Exception as e:
            logger.error(f"Failed to get next run time for {schedule_id}: {e}")
            return None
    
    def start(self):
        """Start the backup scheduler."""
        if self.running:
            logger.warning("Backup scheduler is already running")
            return
        
        self.running = True
        self.stop_event.clear()
        
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="BackupScheduler",
            daemon=True
        )
        self.scheduler_thread.start()
        
        logger.info("Backup scheduler started")
    
    def stop(self):
        """Stop the backup scheduler."""
        if not self.running:
            logger.warning("Backup scheduler is not running")
            return
        
        self.running = False
        self.stop_event.set()
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=10)
            if self.scheduler_thread.is_alive():
                logger.warning("Scheduler thread did not stop gracefully")
        
        logger.info("Backup scheduler stopped")
    
    def set_success_callback(self, callback: Callable[[BackupResult], None]):
        """Set callback for successful backups.
        
        Args:
            callback: Function to call on successful backup
        """
        self.success_callback = callback
    
    def set_failure_callback(self, callback: Callable[[BackupResult], None]):
        """Set callback for failed backups.
        
        Args:
            callback: Function to call on failed backup
        """
        self.failure_callback = callback
    
    def _scheduler_loop(self):
        """Main scheduler loop."""
        logger.info("Backup scheduler loop started")
        
        while self.running and not self.stop_event.is_set():
            try:
                current_time = datetime.utcnow()
                
                # Check each schedule
                for schedule in self.schedules.values():
                    if not schedule.is_enabled:
                        continue
                    
                    try:
                        if self._should_run_backup(schedule, current_time):
                            logger.info(f"Triggering scheduled backup: {schedule.schedule_id}")
                            self._execute_scheduled_backup(schedule)
                    
                    except Exception as e:
                        logger.error(f"Error checking schedule {schedule.schedule_id}: {e}")
                
                # Sleep for 60 seconds before next check
                self.stop_event.wait(60)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                self.stop_event.wait(60)
        
        logger.info("Backup scheduler loop stopped")
    
    def _should_run_backup(self, schedule: BackupSchedule, current_time: datetime) -> bool:
        """Check if backup should run for given schedule.
        
        Args:
            schedule: BackupSchedule to check
            current_time: Current datetime
            
        Returns:
            True if backup should run, False otherwise
        """
        try:
            cron = croniter(schedule.cron_expression, current_time)
            
            # Get the previous scheduled time
            prev_time = cron.get_prev(datetime)
            
            # Check if we're within 1 minute of the scheduled time
            time_diff = abs((current_time - prev_time).total_seconds())
            
            # Run if we're within 60 seconds of scheduled time
            return time_diff <= 60
            
        except Exception as e:
            logger.error(f"Error checking schedule time for {schedule.schedule_id}: {e}")
            return False
    
    def _execute_scheduled_backup(self, schedule: BackupSchedule):
        """Execute a scheduled backup.
        
        Args:
            schedule: BackupSchedule to execute
        """
        try:
            logger.info(f"Executing scheduled backup: {schedule.schedule_id}")
            
            # Create backup
            result = self.backup_service.create_backup(schedule.backup_type)
            
            # Handle result
            if result.status.value == "completed":
                logger.info(f"Scheduled backup completed: {result.backup_id}")
                
                if schedule.notification_on_success and self.success_callback:
                    try:
                        self.success_callback(result)
                    except Exception as e:
                        logger.error(f"Error in success callback: {e}")
            
            else:
                logger.error(f"Scheduled backup failed: {result.error_details}")
                
                if schedule.notification_on_failure and self.failure_callback:
                    try:
                        self.failure_callback(result)
                    except Exception as e:
                        logger.error(f"Error in failure callback: {e}")
            
            # Clean up old backups if retention is configured
            if schedule.retention_days > 0:
                try:
                    cleanup_result = self.backup_service.cleanup_old_backups()
                    logger.info(f"Cleanup completed: freed {cleanup_result.freed_space_bytes} bytes")
                except Exception as e:
                    logger.error(f"Cleanup failed: {e}")
            
        except Exception as e:
            logger.error(f"Error executing scheduled backup {schedule.schedule_id}: {e}")
    
    def _validate_cron_expression(self, cron_expression: str) -> bool:
        """Validate cron expression.
        
        Args:
            cron_expression: Cron expression to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Test if croniter can parse the expression
            cron = croniter(cron_expression, datetime.utcnow())
            # Try to get next run time to validate
            cron.get_next(datetime)
            return True
        except Exception:
            return False
    
    def trigger_backup_now(self, schedule_id: str) -> Optional[BackupResult]:
        """Manually trigger a backup for a specific schedule.
        
        Args:
            schedule_id: Schedule identifier
            
        Returns:
            BackupResult if successful, None otherwise
        """
        try:
            schedule = self.schedules.get(schedule_id)
            if not schedule:
                logger.error(f"Schedule not found: {schedule_id}")
                return None
            
            logger.info(f"Manually triggering backup for schedule: {schedule_id}")
            result = self.backup_service.create_backup(schedule.backup_type)
            
            # Handle notifications
            if result.status.value == "completed" and self.success_callback:
                try:
                    self.success_callback(result)
                except Exception as e:
                    logger.error(f"Error in success callback: {e}")
            elif result.status.value != "completed" and self.failure_callback:
                try:
                    self.failure_callback(result)
                except Exception as e:
                    logger.error(f"Error in failure callback: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error triggering manual backup for {schedule_id}: {e}")
            return None