"""Disk space monitoring for backup system."""

import logging
import shutil
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)


class DiskSpaceMonitor:
    """Monitor disk space for backup operations."""
    
    def __init__(
        self,
        backup_directory: str,
        warning_threshold_mb: int = 1000,
        critical_threshold_mb: int = 500,
        check_interval_seconds: int = 300
    ):
        """Initialize disk space monitor.
        
        Args:
            backup_directory: Directory to monitor
            warning_threshold_mb: Warning threshold in MB
            critical_threshold_mb: Critical threshold in MB
            check_interval_seconds: Check interval in seconds
        """
        self.backup_directory = Path(backup_directory)
        self.warning_threshold_mb = warning_threshold_mb
        self.critical_threshold_mb = critical_threshold_mb
        self.check_interval_seconds = check_interval_seconds
        
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Callbacks for notifications
        self.warning_callback: Optional[Callable[[int, int], None]] = None
        self.critical_callback: Optional[Callable[[int, int], None]] = None
        
        # State tracking
        self.last_warning_time = 0
        self.last_critical_time = 0
        self.warning_cooldown = 3600  # 1 hour
        self.critical_cooldown = 1800  # 30 minutes
        
        logger.info(f"Disk space monitor initialized for {backup_directory}")
    
    def get_disk_usage(self) -> Dict[str, Any]:
        """Get current disk usage information.
        
        Returns:
            Dictionary with disk usage information
        """
        try:
            # Get disk usage for backup directory
            total, used, free = shutil.disk_usage(self.backup_directory)
            
            # Convert to MB
            total_mb = total / (1024 * 1024)
            used_mb = used / (1024 * 1024)
            free_mb = free / (1024 * 1024)
            
            # Calculate usage percentage
            usage_percent = (used / total) * 100 if total > 0 else 0
            
            return {
                'total_mb': total_mb,
                'used_mb': used_mb,
                'free_mb': free_mb,
                'usage_percent': usage_percent,
                'warning_threshold_mb': self.warning_threshold_mb,
                'critical_threshold_mb': self.critical_threshold_mb,
                'is_warning': free_mb < self.warning_threshold_mb,
                'is_critical': free_mb < self.critical_threshold_mb
            }
            
        except Exception as e:
            logger.error(f"Failed to get disk usage: {e}")
            return {
                'total_mb': 0,
                'used_mb': 0,
                'free_mb': 0,
                'usage_percent': 0,
                'warning_threshold_mb': self.warning_threshold_mb,
                'critical_threshold_mb': self.critical_threshold_mb,
                'is_warning': False,
                'is_critical': False,
                'error': str(e)
            }
    
    def check_disk_space(self) -> Dict[str, Any]:
        """Check disk space and trigger alerts if needed.
        
        Returns:
            Dictionary with check results
        """
        usage_info = self.get_disk_usage()
        current_time = time.time()
        
        free_mb = usage_info['free_mb']
        alerts_triggered = []
        
        # Check critical threshold
        if free_mb < self.critical_threshold_mb:
            # Only trigger if cooldown period has passed
            if current_time - self.last_critical_time > self.critical_cooldown:
                logger.critical(f"Critical disk space: {free_mb:.1f}MB available")
                
                if self.critical_callback:
                    try:
                        self.critical_callback(int(free_mb), self.critical_threshold_mb)
                        alerts_triggered.append('critical')
                        self.last_critical_time = current_time
                    except Exception as e:
                        logger.error(f"Error in critical callback: {e}")
        
        # Check warning threshold (only if not critical)
        elif free_mb < self.warning_threshold_mb:
            # Only trigger if cooldown period has passed
            if current_time - self.last_warning_time > self.warning_cooldown:
                logger.warning(f"Low disk space: {free_mb:.1f}MB available")
                
                if self.warning_callback:
                    try:
                        self.warning_callback(int(free_mb), self.warning_threshold_mb)
                        alerts_triggered.append('warning')
                        self.last_warning_time = current_time
                    except Exception as e:
                        logger.error(f"Error in warning callback: {e}")
        
        usage_info['alerts_triggered'] = alerts_triggered
        return usage_info
    
    def start_monitoring(self):
        """Start disk space monitoring."""
        if self.running:
            logger.warning("Disk space monitor is already running")
            return
        
        self.running = True
        self.stop_event.clear()
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="DiskSpaceMonitor",
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info("Disk space monitoring started")
    
    def stop_monitoring(self):
        """Stop disk space monitoring."""
        if not self.running:
            logger.warning("Disk space monitor is not running")
            return
        
        self.running = False
        self.stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10)
            if self.monitor_thread.is_alive():
                logger.warning("Monitor thread did not stop gracefully")
        
        logger.info("Disk space monitoring stopped")
    
    def set_warning_callback(self, callback: Callable[[int, int], None]):
        """Set callback for warning threshold.
        
        Args:
            callback: Function to call when warning threshold is reached
        """
        self.warning_callback = callback
    
    def set_critical_callback(self, callback: Callable[[int, int], None]):
        """Set callback for critical threshold.
        
        Args:
            callback: Function to call when critical threshold is reached
        """
        self.critical_callback = callback
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        logger.info("Disk space monitor loop started")
        
        while self.running and not self.stop_event.is_set():
            try:
                self.check_disk_space()
                
                # Wait for next check
                self.stop_event.wait(self.check_interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in disk space monitor loop: {e}")
                self.stop_event.wait(60)  # Wait 1 minute before retry
        
        logger.info("Disk space monitor loop stopped")
    
    def get_backup_directory_size(self) -> Dict[str, Any]:
        """Get size information for backup directory.
        
        Returns:
            Dictionary with backup directory size information
        """
        try:
            total_size = 0
            file_count = 0
            
            if self.backup_directory.exists():
                for file_path in self.backup_directory.rglob('*'):
                    if file_path.is_file():
                        try:
                            total_size += file_path.stat().st_size
                            file_count += 1
                        except (OSError, IOError):
                            # Skip files that can't be accessed
                            continue
            
            total_size_mb = total_size / (1024 * 1024)
            
            return {
                'total_size_bytes': total_size,
                'total_size_mb': total_size_mb,
                'file_count': file_count,
                'directory_path': str(self.backup_directory)
            }
            
        except Exception as e:
            logger.error(f"Failed to get backup directory size: {e}")
            return {
                'total_size_bytes': 0,
                'total_size_mb': 0,
                'file_count': 0,
                'directory_path': str(self.backup_directory),
                'error': str(e)
            }
    
    def estimate_backup_space_needed(self, database_size_mb: float) -> Dict[str, Any]:
        """Estimate space needed for backup.
        
        Args:
            database_size_mb: Database size in MB
            
        Returns:
            Dictionary with space estimation
        """
        try:
            # Estimate compressed size (assume 70% compression)
            compressed_size_mb = database_size_mb * 0.7
            
            # Add overhead for temporary files during backup (20%)
            overhead_mb = compressed_size_mb * 0.2
            
            # Total estimated space needed
            total_needed_mb = compressed_size_mb + overhead_mb
            
            # Get current free space
            usage_info = self.get_disk_usage()
            free_mb = usage_info['free_mb']
            
            # Check if there's enough space
            has_enough_space = free_mb > total_needed_mb
            
            # Calculate space after backup
            space_after_backup_mb = free_mb - total_needed_mb
            
            return {
                'database_size_mb': database_size_mb,
                'estimated_compressed_mb': compressed_size_mb,
                'estimated_overhead_mb': overhead_mb,
                'total_needed_mb': total_needed_mb,
                'current_free_mb': free_mb,
                'has_enough_space': has_enough_space,
                'space_after_backup_mb': space_after_backup_mb,
                'will_trigger_warning': space_after_backup_mb < self.warning_threshold_mb,
                'will_trigger_critical': space_after_backup_mb < self.critical_threshold_mb
            }
            
        except Exception as e:
            logger.error(f"Failed to estimate backup space: {e}")
            return {
                'database_size_mb': database_size_mb,
                'error': str(e)
            }
    
    def cleanup_space_if_needed(self, space_needed_mb: float) -> Dict[str, Any]:
        """Check if cleanup is needed and suggest actions.
        
        Args:
            space_needed_mb: Space needed in MB
            
        Returns:
            Dictionary with cleanup recommendations
        """
        try:
            usage_info = self.get_disk_usage()
            free_mb = usage_info['free_mb']
            
            cleanup_needed = free_mb < space_needed_mb
            
            if not cleanup_needed:
                return {
                    'cleanup_needed': False,
                    'current_free_mb': free_mb,
                    'space_needed_mb': space_needed_mb,
                    'surplus_mb': free_mb - space_needed_mb
                }
            
            # Calculate how much space needs to be freed
            space_to_free_mb = space_needed_mb - free_mb + 100  # Add 100MB buffer
            
            # Get backup directory size info
            backup_info = self.get_backup_directory_size()
            
            return {
                'cleanup_needed': True,
                'current_free_mb': free_mb,
                'space_needed_mb': space_needed_mb,
                'space_to_free_mb': space_to_free_mb,
                'backup_directory_size_mb': backup_info['total_size_mb'],
                'backup_file_count': backup_info['file_count'],
                'recommendations': [
                    f"Free at least {space_to_free_mb:.1f}MB of disk space",
                    "Consider running backup cleanup to remove old backups",
                    "Check if backup retention policy can be reduced",
                    "Consider moving old backups to external storage"
                ]
            }
            
        except Exception as e:
            logger.error(f"Failed to check cleanup needs: {e}")
            return {
                'cleanup_needed': False,
                'error': str(e)
            }