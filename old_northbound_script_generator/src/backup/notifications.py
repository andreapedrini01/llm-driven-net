"""Notification system for backup operations."""

import json
import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
import requests

from .models import BackupResult, BackupInfo

logger = logging.getLogger(__name__)


class NotificationConfig:
    """Configuration for backup notifications."""
    
    def __init__(
        self,
        email_enabled: bool = False,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_use_tls: bool = True,
        from_email: Optional[str] = None,
        to_emails: Optional[list] = None,
        webhook_enabled: bool = False,
        webhook_url: Optional[str] = None,
        webhook_timeout: int = 30
    ):
        """Initialize notification configuration.
        
        Args:
            email_enabled: Enable email notifications
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            smtp_username: SMTP username
            smtp_password: SMTP password
            smtp_use_tls: Use TLS for SMTP
            from_email: From email address
            to_emails: List of recipient email addresses
            webhook_enabled: Enable webhook notifications
            webhook_url: Webhook URL
            webhook_timeout: Webhook request timeout
        """
        self.email_enabled = email_enabled
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.smtp_use_tls = smtp_use_tls
        self.from_email = from_email
        self.to_emails = to_emails or []
        self.webhook_enabled = webhook_enabled
        self.webhook_url = webhook_url
        self.webhook_timeout = webhook_timeout


class BackupNotificationService:
    """Service for sending backup notifications."""
    
    def __init__(self, config: NotificationConfig):
        """Initialize notification service.
        
        Args:
            config: Notification configuration
        """
        self.config = config
        logger.info("Backup notification service initialized")
    
    def send_backup_success_notification(self, result: BackupResult):
        """Send notification for successful backup.
        
        Args:
            result: BackupResult from successful backup
        """
        try:
            subject = f"✅ Backup Completed Successfully - {result.backup_id}"
            
            message_data = {
                "type": "backup_success",
                "backup_id": result.backup_id,
                "status": result.status.value,
                "message": result.message,
                "duration_seconds": result.duration_seconds,
                "timestamp": datetime.utcnow().isoformat(),
                "backup_info": result.backup_info.dict() if result.backup_info else None
            }
            
            # Create email content
            email_body = self._create_success_email_body(result)
            
            # Send notifications
            self._send_email_notification(subject, email_body)
            self._send_webhook_notification(message_data)
            
            logger.info(f"Success notification sent for backup: {result.backup_id}")
            
        except Exception as e:
            logger.error(f"Failed to send success notification: {e}")
    
    def send_backup_failure_notification(self, result: BackupResult):
        """Send notification for failed backup.
        
        Args:
            result: BackupResult from failed backup
        """
        try:
            subject = f"❌ Backup Failed - {result.backup_id}"
            
            message_data = {
                "type": "backup_failure",
                "backup_id": result.backup_id,
                "status": result.status.value,
                "message": result.message,
                "error_details": result.error_details,
                "duration_seconds": result.duration_seconds,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Create email content
            email_body = self._create_failure_email_body(result)
            
            # Send notifications
            self._send_email_notification(subject, email_body)
            self._send_webhook_notification(message_data)
            
            logger.info(f"Failure notification sent for backup: {result.backup_id}")
            
        except Exception as e:
            logger.error(f"Failed to send failure notification: {e}")
    
    def send_cleanup_notification(self, cleanup_result: Dict[str, Any]):
        """Send notification for backup cleanup.
        
        Args:
            cleanup_result: Cleanup operation result
        """
        try:
            subject = f"🧹 Backup Cleanup Completed - {len(cleanup_result.get('deleted_backups', []))} backups removed"
            
            message_data = {
                "type": "backup_cleanup",
                "cleanup_id": cleanup_result.get("cleanup_id"),
                "deleted_backups": cleanup_result.get("deleted_backups", []),
                "freed_space_bytes": cleanup_result.get("freed_space_bytes", 0),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Create email content
            email_body = self._create_cleanup_email_body(cleanup_result)
            
            # Send notifications
            self._send_email_notification(subject, email_body)
            self._send_webhook_notification(message_data)
            
            logger.info(f"Cleanup notification sent: {cleanup_result.get('cleanup_id')}")
            
        except Exception as e:
            logger.error(f"Failed to send cleanup notification: {e}")
    
    def send_disk_space_warning(self, available_space_mb: int, threshold_mb: int):
        """Send notification for low disk space.
        
        Args:
            available_space_mb: Available disk space in MB
            threshold_mb: Warning threshold in MB
        """
        try:
            subject = f"⚠️ Low Disk Space Warning - {available_space_mb}MB available"
            
            message_data = {
                "type": "disk_space_warning",
                "available_space_mb": available_space_mb,
                "threshold_mb": threshold_mb,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Create email content
            email_body = f"""
            <h2>⚠️ Low Disk Space Warning</h2>
            <p><strong>Available Space:</strong> {available_space_mb} MB</p>
            <p><strong>Warning Threshold:</strong> {threshold_mb} MB</p>
            <p><strong>Time:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
            
            <p>Please free up disk space or adjust backup retention policies to prevent backup failures.</p>
            """
            
            # Send notifications
            self._send_email_notification(subject, email_body)
            self._send_webhook_notification(message_data)
            
            logger.info(f"Disk space warning sent: {available_space_mb}MB available")
            
        except Exception as e:
            logger.error(f"Failed to send disk space warning: {e}")
    
    def _create_success_email_body(self, result: BackupResult) -> str:
        """Create email body for successful backup.
        
        Args:
            result: BackupResult from successful backup
            
        Returns:
            HTML email body
        """
        backup_info = result.backup_info
        
        return f"""
        <h2>✅ Backup Completed Successfully</h2>
        
        <h3>Backup Details</h3>
        <ul>
            <li><strong>Backup ID:</strong> {result.backup_id}</li>
            <li><strong>Status:</strong> {result.status.value}</li>
            <li><strong>Duration:</strong> {result.duration_seconds:.2f} seconds</li>
            <li><strong>Message:</strong> {result.message}</li>
        </ul>
        
        {f'''
        <h3>Backup Information</h3>
        <ul>
            <li><strong>Type:</strong> {backup_info.backup_type.value}</li>
            <li><strong>Database:</strong> {backup_info.database_name}</li>
            <li><strong>File Size:</strong> {backup_info.file_size / (1024*1024):.2f} MB</li>
            <li><strong>Compressed Size:</strong> {backup_info.compressed_size / (1024*1024):.2f} MB</li>
            <li><strong>Compression Ratio:</strong> {(1 - backup_info.compressed_size / backup_info.file_size) * 100:.1f}%</li>
            <li><strong>Encrypted:</strong> {'Yes' if backup_info.is_encrypted else 'No'}</li>
            <li><strong>File Path:</strong> {backup_info.file_path}</li>
            <li><strong>Checksum:</strong> {backup_info.checksum[:16]}...</li>
        </ul>
        ''' if backup_info else ''}
        
        <p><strong>Timestamp:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
        """
    
    def _create_failure_email_body(self, result: BackupResult) -> str:
        """Create email body for failed backup.
        
        Args:
            result: BackupResult from failed backup
            
        Returns:
            HTML email body
        """
        return f"""
        <h2>❌ Backup Failed</h2>
        
        <h3>Failure Details</h3>
        <ul>
            <li><strong>Backup ID:</strong> {result.backup_id}</li>
            <li><strong>Status:</strong> {result.status.value}</li>
            <li><strong>Duration:</strong> {result.duration_seconds:.2f} seconds</li>
            <li><strong>Error Message:</strong> {result.message}</li>
        </ul>
        
        {f'''
        <h3>Error Details</h3>
        <pre style="background-color: #f5f5f5; padding: 10px; border-radius: 5px;">
{result.error_details}
        </pre>
        ''' if result.error_details else ''}
        
        <p><strong>Timestamp:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
        
        <p><em>Please investigate and resolve the issue to ensure backup continuity.</em></p>
        """
    
    def _create_cleanup_email_body(self, cleanup_result: Dict[str, Any]) -> str:
        """Create email body for cleanup notification.
        
        Args:
            cleanup_result: Cleanup operation result
            
        Returns:
            HTML email body
        """
        deleted_count = len(cleanup_result.get("deleted_backups", []))
        freed_space_mb = cleanup_result.get("freed_space_bytes", 0) / (1024 * 1024)
        
        return f"""
        <h2>🧹 Backup Cleanup Completed</h2>
        
        <h3>Cleanup Summary</h3>
        <ul>
            <li><strong>Cleanup ID:</strong> {cleanup_result.get('cleanup_id', 'N/A')}</li>
            <li><strong>Deleted Backups:</strong> {deleted_count}</li>
            <li><strong>Space Freed:</strong> {freed_space_mb:.2f} MB</li>
        </ul>
        
        {f'''
        <h3>Deleted Backup IDs</h3>
        <ul>
        {''.join(f'<li>{backup_id}</li>' for backup_id in cleanup_result.get('deleted_backups', []))}
        </ul>
        ''' if cleanup_result.get('deleted_backups') else ''}
        
        <p><strong>Timestamp:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
        """
    
    def _send_email_notification(self, subject: str, body: str):
        """Send email notification.
        
        Args:
            subject: Email subject
            body: Email body (HTML)
        """
        if not self.config.email_enabled or not self.config.to_emails:
            return
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.config.from_email
            msg['To'] = ', '.join(self.config.to_emails)
            
            # Add HTML body
            html_part = MIMEText(body, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                if self.config.smtp_use_tls:
                    server.starttls()
                
                if self.config.smtp_username and self.config.smtp_password:
                    server.login(self.config.smtp_username, self.config.smtp_password)
                
                server.send_message(msg)
            
            logger.info(f"Email notification sent: {subject}")
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
    
    def _send_webhook_notification(self, data: Dict[str, Any]):
        """Send webhook notification.
        
        Args:
            data: Notification data
        """
        if not self.config.webhook_enabled or not self.config.webhook_url:
            return
        
        try:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Northbound-Backup-Service/1.0'
            }
            
            response = requests.post(
                self.config.webhook_url,
                json=data,
                headers=headers,
                timeout=self.config.webhook_timeout
            )
            
            response.raise_for_status()
            logger.info(f"Webhook notification sent: {data.get('type', 'unknown')}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send webhook notification: {e}")
        except Exception as e:
            logger.error(f"Unexpected error sending webhook: {e}")
    
    def test_notifications(self) -> Dict[str, bool]:
        """Test notification systems.
        
        Returns:
            Dictionary with test results for each notification type
        """
        results = {}
        
        # Test email
        if self.config.email_enabled:
            try:
                test_subject = "🧪 Backup Notification Test"
                test_body = f"""
                <h2>🧪 Test Notification</h2>
                <p>This is a test notification from the Northbound Backup Service.</p>
                <p><strong>Timestamp:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
                <p>If you receive this email, email notifications are working correctly.</p>
                """
                
                self._send_email_notification(test_subject, test_body)
                results['email'] = True
                
            except Exception as e:
                logger.error(f"Email notification test failed: {e}")
                results['email'] = False
        else:
            results['email'] = None  # Not configured
        
        # Test webhook
        if self.config.webhook_enabled:
            try:
                test_data = {
                    "type": "test_notification",
                    "message": "This is a test notification from the Northbound Backup Service",
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                self._send_webhook_notification(test_data)
                results['webhook'] = True
                
            except Exception as e:
                logger.error(f"Webhook notification test failed: {e}")
                results['webhook'] = False
        else:
            results['webhook'] = None  # Not configured
        
        return results