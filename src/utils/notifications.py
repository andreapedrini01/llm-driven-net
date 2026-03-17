"""Notification and alerting system for administrators."""

import smtplib
import json
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass, field
import requests
from pydantic import BaseModel, Field

from src.utils.logging import get_logger


logger = get_logger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertCategory(str, Enum):
    """Alert categories."""
    ANOMALY = "anomaly"
    SYSTEM_ERROR = "system_error"
    API_ERROR = "api_error"
    BUDGET = "budget"
    SECURITY = "security"
    PERFORMANCE = "performance"
    NETWORK_STATE = "network_state"


@dataclass
class Alert:
    """Represents an alert to be sent to administrators."""
    
    id: str
    severity: AlertSeverity
    category: AlertCategory
    title: str
    message: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "id": self.id,
            "severity": self.severity.value,
            "category": self.category.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "correlation_id": self.correlation_id,
            "metadata": self.metadata
        }
    
    def get_severity_emoji(self) -> str:
        """Get emoji for severity level."""
        emoji_map = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.ERROR: "❌",
            AlertSeverity.CRITICAL: "🚨"
        }
        return emoji_map.get(self.severity, "📢")


class NotificationChannel(ABC):
    """Abstract base class for notification channels."""
    
    @abstractmethod
    async def send(self, alert: Alert) -> bool:
        """Send an alert through this channel.
        
        Args:
            alert: Alert to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if this channel is enabled."""
        pass


class EmailNotificationChannel(NotificationChannel):
    """Email notification channel."""
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        from_email: str,
        to_emails: List[str],
        use_tls: bool = True,
        enabled: bool = True
    ):
        """Initialize email notification channel.
        
        Args:
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            smtp_username: SMTP username
            smtp_password: SMTP password
            from_email: Sender email address
            to_emails: List of recipient email addresses
            use_tls: Whether to use TLS
            enabled: Whether this channel is enabled
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.to_emails = to_emails
        self.use_tls = use_tls
        self.enabled = enabled
    
    async def send(self, alert: Alert) -> bool:
        """Send alert via email."""
        if not self.is_enabled():
            logger.warning("Email channel is disabled, skipping notification")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
            msg['From'] = self.from_email
            msg['To'] = ", ".join(self.to_emails)
            
            # Create HTML body
            html_body = self._create_html_body(alert)
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(
                "Email notification sent",
                alert_id=alert.id,
                severity=alert.severity.value,
                recipients=self.to_emails
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to send email notification",
                alert_id=alert.id,
                error=str(e)
            )
            return False
    
    def is_enabled(self) -> bool:
        """Check if email channel is enabled."""
        return self.enabled and bool(self.smtp_host and self.to_emails)
    
    def _create_html_body(self, alert: Alert) -> str:
        """Create HTML email body."""
        severity_colors = {
            AlertSeverity.INFO: "#0066cc",
            AlertSeverity.WARNING: "#ff9900",
            AlertSeverity.ERROR: "#cc0000",
            AlertSeverity.CRITICAL: "#990000"
        }
        color = severity_colors.get(alert.severity, "#333333")
        
        metadata_html = ""
        if alert.metadata:
            metadata_html = "<h3>Additional Details:</h3><ul>"
            for key, value in alert.metadata.items():
                metadata_html += f"<li><strong>{key}:</strong> {value}</li>"
            metadata_html += "</ul>"
        
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="border-left: 4px solid {color}; padding-left: 20px;">
                <h2 style="color: {color};">{alert.get_severity_emoji()} {alert.title}</h2>
                <p><strong>Severity:</strong> {alert.severity.value.upper()}</p>
                <p><strong>Category:</strong> {alert.category.value}</p>
                <p><strong>Time:</strong> {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                {f'<p><strong>Correlation ID:</strong> {alert.correlation_id}</p>' if alert.correlation_id else ''}
                <hr>
                <h3>Message:</h3>
                <p>{alert.message}</p>
                {metadata_html}
            </div>
        </body>
        </html>
        """


class SlackNotificationChannel(NotificationChannel):
    """Slack notification channel using webhooks."""
    
    def __init__(
        self,
        webhook_url: str,
        channel: Optional[str] = None,
        username: str = "LLM Integration Module",
        enabled: bool = True
    ):
        """Initialize Slack notification channel.
        
        Args:
            webhook_url: Slack webhook URL
            channel: Optional channel override
            username: Bot username
            enabled: Whether this channel is enabled
        """
        self.webhook_url = webhook_url
        self.channel = channel
        self.username = username
        self.enabled = enabled
    
    async def send(self, alert: Alert) -> bool:
        """Send alert via Slack."""
        if not self.is_enabled():
            logger.warning("Slack channel is disabled, skipping notification")
            return False
        
        try:
            # Create Slack message
            payload = self._create_slack_payload(alert)
            
            # Send to Slack
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            
            logger.info(
                "Slack notification sent",
                alert_id=alert.id,
                severity=alert.severity.value
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to send Slack notification",
                alert_id=alert.id,
                error=str(e)
            )
            return False
    
    def is_enabled(self) -> bool:
        """Check if Slack channel is enabled."""
        return self.enabled and bool(self.webhook_url)
    
    def _create_slack_payload(self, alert: Alert) -> Dict[str, Any]:
        """Create Slack message payload."""
        # Color based on severity
        color_map = {
            AlertSeverity.INFO: "#36a64f",
            AlertSeverity.WARNING: "#ff9900",
            AlertSeverity.ERROR: "#cc0000",
            AlertSeverity.CRITICAL: "#990000"
        }
        color = color_map.get(alert.severity, "#333333")
        
        # Build fields
        fields = [
            {
                "title": "Severity",
                "value": alert.severity.value.upper(),
                "short": True
            },
            {
                "title": "Category",
                "value": alert.category.value,
                "short": True
            },
            {
                "title": "Time",
                "value": alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'),
                "short": False
            }
        ]
        
        if alert.correlation_id:
            fields.append({
                "title": "Correlation ID",
                "value": alert.correlation_id,
                "short": False
            })
        
        # Add metadata fields
        for key, value in alert.metadata.items():
            fields.append({
                "title": key.replace("_", " ").title(),
                "value": str(value),
                "short": True
            })
        
        payload = {
            "username": self.username,
            "attachments": [
                {
                    "color": color,
                    "title": f"{alert.get_severity_emoji()} {alert.title}",
                    "text": alert.message,
                    "fields": fields,
                    "footer": "LLM Integration Module",
                    "ts": int(alert.timestamp.timestamp())
                }
            ]
        }
        
        if self.channel:
            payload["channel"] = self.channel
        
        return payload


class WebhookNotificationChannel(NotificationChannel):
    """Generic webhook notification channel."""
    
    def __init__(
        self,
        webhook_url: str,
        headers: Optional[Dict[str, str]] = None,
        enabled: bool = True
    ):
        """Initialize webhook notification channel.
        
        Args:
            webhook_url: Webhook URL
            headers: Optional HTTP headers
            enabled: Whether this channel is enabled
        """
        self.webhook_url = webhook_url
        self.headers = headers or {}
        self.enabled = enabled
    
    async def send(self, alert: Alert) -> bool:
        """Send alert via webhook."""
        if not self.is_enabled():
            logger.warning("Webhook channel is disabled, skipping notification")
            return False
        
        try:
            # Send alert as JSON
            response = requests.post(
                self.webhook_url,
                json=alert.to_dict(),
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            logger.info(
                "Webhook notification sent",
                alert_id=alert.id,
                severity=alert.severity.value
            )
            return True
            
        except Exception as e:
            logger.error(
                "Failed to send webhook notification",
                alert_id=alert.id,
                error=str(e)
            )
            return False
    
    def is_enabled(self) -> bool:
        """Check if webhook channel is enabled."""
        return self.enabled and bool(self.webhook_url)


class NotificationManager:
    """Manages notification channels and alert distribution."""
    
    def __init__(self):
        """Initialize notification manager."""
        self.channels: List[Tuple[str, NotificationChannel]] = []
        self.severity_filters: Dict[str, List[AlertSeverity]] = {}
    
    def add_channel(
        self,
        channel: NotificationChannel,
        channel_id: str,
        severity_filter: Optional[List[AlertSeverity]] = None
    ) -> None:
        """Add a notification channel.
        
        Args:
            channel: Notification channel to add
            channel_id: Unique identifier for the channel
            severity_filter: Optional list of severities to filter (only send these)
        """
        self.channels.append((channel_id, channel))
        if severity_filter:
            self.severity_filters[channel_id] = severity_filter
        
        logger.info(
            "Notification channel added",
            channel_id=channel_id,
            channel_type=type(channel).__name__,
            severity_filter=severity_filter
        )
    
    async def send_alert(self, alert: Alert) -> Dict[str, bool]:
        """Send alert through all enabled channels.
        
        Args:
            alert: Alert to send
            
        Returns:
            Dictionary mapping channel type to success status
        """
        results = {}
        
        for channel_id, channel in self.channels:
            # Check severity filter
            if channel_id in self.severity_filters:
                if alert.severity not in self.severity_filters[channel_id]:
                    logger.debug(
                        "Skipping channel due to severity filter",
                        channel_id=channel_id,
                        alert_severity=alert.severity.value
                    )
                    continue
            
            # Send through channel
            try:
                success = await channel.send(alert)
                results[channel_id] = success
            except Exception as e:
                logger.error(
                    "Error sending alert through channel",
                    channel_id=channel_id,
                    error=str(e)
                )
                results[channel_id] = False
        
        return results
    
    def get_enabled_channels(self) -> List[str]:
        """Get list of enabled channel types."""
        return [
            type(channel).__name__
            for _, channel in self.channels
            if channel.is_enabled()
        ]


# Global notification manager instance
notification_manager = NotificationManager()

