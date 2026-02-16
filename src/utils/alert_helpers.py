"""Helper functions for creating and sending alerts."""

import uuid
import json
from typing import Optional, Dict, Any
from datetime import datetime

from src.config import get_settings
from src.utils.logging import get_logger
from src.utils.notifications import (
    Alert,
    AlertSeverity,
    AlertCategory,
    EmailNotificationChannel,
    SlackNotificationChannel,
    WebhookNotificationChannel,
    notification_manager
)
from src.utils.budget_alerts import budget_alert_manager


logger = get_logger(__name__)


def initialize_notification_system() -> None:
    """Initialize the notification system with configured channels."""
    settings = get_settings()
    
    if not settings.notifications_enabled:
        logger.info("Notifications are disabled in configuration")
        return
    
    # Initialize email channel
    if settings.email_enabled and settings.smtp_host:
        try:
            to_emails = [
                email.strip()
                for email in settings.smtp_to_emails.split(",")
                if email.strip()
            ]
            
            if to_emails:
                email_channel = EmailNotificationChannel(
                    smtp_host=settings.smtp_host,
                    smtp_port=settings.smtp_port,
                    smtp_username=settings.smtp_username,
                    smtp_password=settings.smtp_password,
                    from_email=settings.smtp_from_email,
                    to_emails=to_emails,
                    use_tls=settings.smtp_use_tls,
                    enabled=True
                )
                notification_manager.add_channel(
                    email_channel,
                    "email",
                    severity_filter=[
                        AlertSeverity.WARNING,
                        AlertSeverity.ERROR,
                        AlertSeverity.CRITICAL
                    ]
                )
                logger.info("Email notification channel initialized", recipients=to_emails)
        except Exception as e:
            logger.error("Failed to initialize email channel", error=str(e))
    
    # Initialize Slack channel
    if settings.slack_enabled and settings.slack_webhook_url:
        try:
            slack_channel = SlackNotificationChannel(
                webhook_url=settings.slack_webhook_url,
                channel=settings.slack_channel,
                username=settings.slack_username,
                enabled=True
            )
            notification_manager.add_channel(slack_channel, "slack")
            logger.info("Slack notification channel initialized")
        except Exception as e:
            logger.error("Failed to initialize Slack channel", error=str(e))
    
    # Initialize webhook channel
    if settings.webhook_enabled and settings.webhook_url:
        try:
            headers = json.loads(settings.webhook_headers) if settings.webhook_headers else {}
            webhook_channel = WebhookNotificationChannel(
                webhook_url=settings.webhook_url,
                headers=headers,
                enabled=True
            )
            notification_manager.add_channel(webhook_channel, "webhook")
            logger.info("Webhook notification channel initialized")
        except Exception as e:
            logger.error("Failed to initialize webhook channel", error=str(e))
    
    # Initialize budget alert manager
    if settings.budget_alerts_enabled:
        try:
            budget_alert_manager.__init__(
                daily_warning=settings.budget_daily_warning,
                daily_critical=settings.budget_daily_critical,
                weekly_warning=settings.budget_weekly_warning,
                weekly_critical=settings.budget_weekly_critical,
                monthly_warning=settings.budget_monthly_warning,
                monthly_critical=settings.budget_monthly_critical
            )
            logger.info(
                "Budget alert manager initialized",
                daily_warning=settings.budget_daily_warning,
                daily_critical=settings.budget_daily_critical
            )
        except Exception as e:
            logger.error("Failed to initialize budget alert manager", error=str(e))
    
    enabled_channels = notification_manager.get_enabled_channels()
    logger.info(
        "Notification system initialized",
        enabled_channels=enabled_channels,
        budget_alerts_enabled=settings.budget_alerts_enabled
    )


async def send_anomaly_alert(
    anomaly_id: str,
    anomaly_type: str,
    severity: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
) -> None:
    """Send an anomaly detection alert.
    
    Args:
        anomaly_id: Unique anomaly identifier
        anomaly_type: Type of anomaly detected
        severity: Severity level (info, warning, error, critical)
        message: Alert message
        metadata: Additional metadata
        correlation_id: Optional correlation ID
    """
    severity_map = {
        "info": AlertSeverity.INFO,
        "warning": AlertSeverity.WARNING,
        "error": AlertSeverity.ERROR,
        "critical": AlertSeverity.CRITICAL
    }
    
    alert = Alert(
        id=str(uuid.uuid4()),
        severity=severity_map.get(severity.lower(), AlertSeverity.WARNING),
        category=AlertCategory.ANOMALY,
        title=f"Network Anomaly Detected: {anomaly_type}",
        message=message,
        correlation_id=correlation_id,
        metadata={
            "anomaly_id": anomaly_id,
            "anomaly_type": anomaly_type,
            **(metadata or {})
        }
    )
    
    await notification_manager.send_alert(alert)


async def send_system_error_alert(
    error_type: str,
    error_message: str,
    component: str,
    metadata: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
) -> None:
    """Send a system error alert.
    
    Args:
        error_type: Type of error
        error_message: Error message
        component: Component where error occurred
        metadata: Additional metadata
        correlation_id: Optional correlation ID
    """
    alert = Alert(
        id=str(uuid.uuid4()),
        severity=AlertSeverity.ERROR,
        category=AlertCategory.SYSTEM_ERROR,
        title=f"System Error in {component}",
        message=f"{error_type}: {error_message}",
        correlation_id=correlation_id,
        metadata={
            "error_type": error_type,
            "component": component,
            **(metadata or {})
        }
    )
    
    await notification_manager.send_alert(alert)


async def send_api_error_alert(
    api_name: str,
    error_type: str,
    error_message: str,
    retry_attempt: int,
    metadata: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
) -> None:
    """Send an API error alert.
    
    Args:
        api_name: Name of the API (e.g., "ChatGPT", "RYU")
        error_type: Type of error
        error_message: Error message
        retry_attempt: Current retry attempt
        metadata: Additional metadata
        correlation_id: Optional correlation ID
    """
    # Only send alert on final retry attempt to avoid spam
    severity = AlertSeverity.CRITICAL if retry_attempt >= 3 else AlertSeverity.WARNING
    
    alert = Alert(
        id=str(uuid.uuid4()),
        severity=severity,
        category=AlertCategory.API_ERROR,
        title=f"{api_name} API Error",
        message=f"{error_type}: {error_message}\nRetry attempt: {retry_attempt}",
        correlation_id=correlation_id,
        metadata={
            "api_name": api_name,
            "error_type": error_type,
            "retry_attempt": retry_attempt,
            **(metadata or {})
        }
    )
    
    # Only send on final attempt
    if retry_attempt >= 3:
        await notification_manager.send_alert(alert)


async def send_security_alert(
    threat_type: str,
    message: str,
    source: str,
    metadata: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
) -> None:
    """Send a security alert.
    
    Args:
        threat_type: Type of security threat
        message: Alert message
        source: Source of the threat (IP, user, etc.)
        metadata: Additional metadata
        correlation_id: Optional correlation ID
    """
    alert = Alert(
        id=str(uuid.uuid4()),
        severity=AlertSeverity.CRITICAL,
        category=AlertCategory.SECURITY,
        title=f"Security Alert: {threat_type}",
        message=message,
        correlation_id=correlation_id,
        metadata={
            "threat_type": threat_type,
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
            **(metadata or {})
        }
    )
    
    await notification_manager.send_alert(alert)


async def send_performance_alert(
    metric_name: str,
    current_value: float,
    threshold: float,
    message: str,
    metadata: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
) -> None:
    """Send a performance alert.
    
    Args:
        metric_name: Name of the performance metric
        current_value: Current value
        threshold: Threshold that was exceeded
        message: Alert message
        metadata: Additional metadata
        correlation_id: Optional correlation ID
    """
    alert = Alert(
        id=str(uuid.uuid4()),
        severity=AlertSeverity.WARNING,
        category=AlertCategory.PERFORMANCE,
        title=f"Performance Alert: {metric_name}",
        message=message,
        correlation_id=correlation_id,
        metadata={
            "metric_name": metric_name,
            "current_value": current_value,
            "threshold": threshold,
            **(metadata or {})
        }
    )
    
    await notification_manager.send_alert(alert)


async def send_network_state_alert(
    state_issue: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None
) -> None:
    """Send a network state alert.
    
    Args:
        state_issue: Type of state issue
        message: Alert message
        metadata: Additional metadata
        correlation_id: Optional correlation ID
    """
    alert = Alert(
        id=str(uuid.uuid4()),
        severity=AlertSeverity.WARNING,
        category=AlertCategory.NETWORK_STATE,
        title=f"Network State Issue: {state_issue}",
        message=message,
        correlation_id=correlation_id,
        metadata={
            "state_issue": state_issue,
            **(metadata or {})
        }
    )
    
    await notification_manager.send_alert(alert)

