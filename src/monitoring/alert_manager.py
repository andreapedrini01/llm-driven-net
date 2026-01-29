"""
Alert management system for Northbound Script Generator.

This module provides comprehensive alerting capabilities including:
- Configurable alert thresholds
- Multiple notification channels (email, webhook)
- Alert dashboard and history
- Alert suppression and escalation
"""

import asyncio
import smtplib
import json
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import threading
import logging
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class AlertStatus(Enum):
    """Alert status."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    ACKNOWLEDGED = "acknowledged"


@dataclass
class AlertThreshold:
    """Configuration for an alert threshold."""
    metric_name: str
    operator: str  # >, <, >=, <=, ==, !=
    value: float
    severity: AlertSeverity
    duration_seconds: int = 60  # How long condition must persist
    description: str = ""
    enabled: bool = True


@dataclass
class Alert:
    """Represents an active or historical alert."""
    id: str
    metric_name: str
    threshold: AlertThreshold
    current_value: float
    severity: AlertSeverity
    status: AlertStatus
    message: str
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    notification_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NotificationChannel:
    """Configuration for a notification channel."""
    name: str
    type: str  # email, webhook, slack
    config: Dict[str, Any]
    enabled: bool = True
    severity_filter: List[AlertSeverity] = field(default_factory=list)


class AlertManager:
    """
    Manages alerts, thresholds, and notifications.
    
    Monitors metrics against configured thresholds and sends notifications
    when alerts are triggered or resolved.
    """
    
    def __init__(self):
        """Initialize alert manager."""
        self._thresholds: Dict[str, AlertThreshold] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: deque = deque(maxlen=10000)
        self._notification_channels: Dict[str, NotificationChannel] = {}
        
        # Alert state tracking
        self._metric_violations: Dict[str, datetime] = {}
        self._last_notification: Dict[str, datetime] = {}
        self._suppressed_alerts: set = set()
        
        # Configuration
        self._check_interval = 30  # seconds
        self._notification_cooldown = 300  # 5 minutes between notifications
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Metrics callback
        self._metrics_callback: Optional[Callable] = None
        
        logger.info("AlertManager initialized")
    
    def set_metrics_callback(self, callback: Callable) -> None:
        """Set callback function to get current metrics."""
        self._metrics_callback = callback
    
    def add_threshold(self, threshold: AlertThreshold) -> None:
        """Add or update an alert threshold."""
        with self._lock:
            self._thresholds[threshold.metric_name] = threshold
        logger.info(f"Added alert threshold for {threshold.metric_name}")
    
    def remove_threshold(self, metric_name: str) -> None:
        """Remove an alert threshold."""
        with self._lock:
            if metric_name in self._thresholds:
                del self._thresholds[metric_name]
                logger.info(f"Removed alert threshold for {metric_name}")
    
    def add_notification_channel(self, channel: NotificationChannel) -> None:
        """Add or update a notification channel."""
        with self._lock:
            self._notification_channels[channel.name] = channel
        logger.info(f"Added notification channel: {channel.name}")
    
    def remove_notification_channel(self, channel_name: str) -> None:
        """Remove a notification channel."""
        with self._lock:
            if channel_name in self._notification_channels:
                del self._notification_channels[channel_name]
                logger.info(f"Removed notification channel: {channel_name}")
    
    def start(self) -> None:
        """Start the alert monitoring thread."""
        if self._running:
            logger.warning("AlertManager already running")
            return
            
        self._running = True
        self._thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._thread.start()
        logger.info("AlertManager started")
    
    def stop(self) -> None:
        """Stop the alert monitoring thread."""
        if not self._running:
            return
            
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("AlertManager stopped")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                self._check_alerts()
                asyncio.run(self._process_notifications())
                threading.Event().wait(self._check_interval)
            except Exception as e:
                logger.error(f"Error in alert monitoring loop: {e}")
                threading.Event().wait(self._check_interval)
    
    def _check_alerts(self) -> None:
        """Check all thresholds against current metrics."""
        if not self._metrics_callback:
            return
            
        try:
            # Get current metrics
            current_metrics = self._metrics_callback()
            if not current_metrics:
                return
                
            now = datetime.utcnow()
            
            with self._lock:
                for metric_name, threshold in self._thresholds.items():
                    if not threshold.enabled:
                        continue
                        
                    # Get metric value
                    metric_value = self._extract_metric_value(current_metrics, metric_name)
                    if metric_value is None:
                        continue
                    
                    # Check threshold
                    violation = self._evaluate_threshold(metric_value, threshold)
                    
                    if violation:
                        self._handle_threshold_violation(metric_name, threshold, metric_value, now)
                    else:
                        self._handle_threshold_resolution(metric_name, now)
                        
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
    
    def _extract_metric_value(self, metrics: Dict[str, Any], metric_name: str) -> Optional[float]:
        """Extract metric value from metrics dictionary."""
        try:
            # Handle nested metric names like "system.cpu_usage_percent"
            parts = metric_name.split('.')
            value = metrics
            
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                elif hasattr(value, part):
                    value = getattr(value, part)
                else:
                    return None
            
            return float(value) if value is not None else None
            
        except (ValueError, TypeError, AttributeError):
            return None
    
    def _evaluate_threshold(self, value: float, threshold: AlertThreshold) -> bool:
        """Evaluate if a metric value violates the threshold."""
        try:
            if threshold.operator == '>':
                return value > threshold.value
            elif threshold.operator == '<':
                return value < threshold.value
            elif threshold.operator == '>=':
                return value >= threshold.value
            elif threshold.operator == '<=':
                return value <= threshold.value
            elif threshold.operator == '==':
                return value == threshold.value
            elif threshold.operator == '!=':
                return value != threshold.value
            else:
                logger.warning(f"Unknown operator: {threshold.operator}")
                return False
        except Exception as e:
            logger.error(f"Error evaluating threshold: {e}")
            return False
    
    def _handle_threshold_violation(self, metric_name: str, threshold: AlertThreshold, 
                                  current_value: float, now: datetime) -> None:
        """Handle a threshold violation."""
        # Track violation start time
        if metric_name not in self._metric_violations:
            self._metric_violations[metric_name] = now
            return  # Wait for duration before triggering alert
        
        # Check if violation has persisted long enough
        violation_duration = (now - self._metric_violations[metric_name]).total_seconds()
        if violation_duration < threshold.duration_seconds:
            return
        
        # Check if alert already exists
        alert_id = f"{metric_name}_{threshold.severity.value}"
        if alert_id in self._active_alerts:
            # Update existing alert
            alert = self._active_alerts[alert_id]
            alert.current_value = current_value
            alert.updated_at = now
        else:
            # Create new alert
            alert = Alert(
                id=alert_id,
                metric_name=metric_name,
                threshold=threshold,
                current_value=current_value,
                severity=threshold.severity,
                status=AlertStatus.ACTIVE,
                message=self._generate_alert_message(metric_name, threshold, current_value),
                created_at=now,
                updated_at=now
            )
            
            self._active_alerts[alert_id] = alert
            self._alert_history.append(alert)
            
            logger.warning(f"Alert triggered: {alert.message}")
    
    def _handle_threshold_resolution(self, metric_name: str, now: datetime) -> None:
        """Handle threshold resolution."""
        # Clear violation tracking
        if metric_name in self._metric_violations:
            del self._metric_violations[metric_name]
        
        # Resolve active alerts for this metric
        alerts_to_resolve = [
            alert_id for alert_id, alert in self._active_alerts.items()
            if alert.metric_name == metric_name and alert.status == AlertStatus.ACTIVE
        ]
        
        for alert_id in alerts_to_resolve:
            alert = self._active_alerts[alert_id]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = now
            alert.updated_at = now
            
            # Move to history and remove from active
            self._alert_history.append(alert)
            del self._active_alerts[alert_id]
            
            logger.info(f"Alert resolved: {alert.message}")
    
    def _generate_alert_message(self, metric_name: str, threshold: AlertThreshold, 
                              current_value: float) -> str:
        """Generate alert message."""
        return (f"Alert: {metric_name} is {current_value} "
                f"({threshold.operator} {threshold.value}). "
                f"{threshold.description}")
    
    async def _process_notifications(self) -> None:
        """Process pending notifications."""
        now = datetime.utcnow()
        
        with self._lock:
            alerts_to_notify = []
            
            for alert in self._active_alerts.values():
                if alert.status != AlertStatus.ACTIVE:
                    continue
                    
                # Check notification cooldown
                last_notif = self._last_notification.get(alert.id)
                if last_notif and (now - last_notif).total_seconds() < self._notification_cooldown:
                    continue
                
                # Check if alert is suppressed
                if alert.id in self._suppressed_alerts:
                    continue
                
                alerts_to_notify.append(alert)
        
        # Send notifications
        for alert in alerts_to_notify:
            await self._send_notifications(alert)
            with self._lock:
                self._last_notification[alert.id] = now
                alert.notification_count += 1
    
    async def _send_notifications(self, alert: Alert) -> None:
        """Send notifications for an alert."""
        with self._lock:
            channels = list(self._notification_channels.values())
        
        for channel in channels:
            if not channel.enabled:
                continue
                
            # Check severity filter
            if channel.severity_filter and alert.severity not in channel.severity_filter:
                continue
            
            try:
                if channel.type == 'email':
                    await self._send_email_notification(channel, alert)
                elif channel.type == 'webhook':
                    await self._send_webhook_notification(channel, alert)
                elif channel.type == 'slack':
                    await self._send_slack_notification(channel, alert)
                else:
                    logger.warning(f"Unknown notification channel type: {channel.type}")
                    
            except Exception as e:
                logger.error(f"Error sending notification via {channel.name}: {e}")
    
    async def _send_email_notification(self, channel: NotificationChannel, alert: Alert) -> None:
        """Send email notification."""
        config = channel.config
        
        msg = MIMEMultipart()
        msg['From'] = config['from_email']
        msg['To'] = ', '.join(config['to_emails'])
        msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.metric_name} Alert"
        
        body = f"""
Alert Details:
- Metric: {alert.metric_name}
- Current Value: {alert.current_value}
- Threshold: {alert.threshold.operator} {alert.threshold.value}
- Severity: {alert.severity.value}
- Created: {alert.created_at}
- Message: {alert.message}

Alert ID: {alert.id}
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        with smtplib.SMTP(config['smtp_host'], config['smtp_port']) as server:
            if config.get('use_tls'):
                server.starttls()
            if config.get('username') and config.get('password'):
                server.login(config['username'], config['password'])
            server.send_message(msg)
        
        logger.info(f"Email notification sent for alert {alert.id}")
    
    async def _send_webhook_notification(self, channel: NotificationChannel, alert: Alert) -> None:
        """Send webhook notification."""
        config = channel.config
        
        payload = {
            'alert_id': alert.id,
            'metric_name': alert.metric_name,
            'current_value': alert.current_value,
            'threshold_value': alert.threshold.value,
            'threshold_operator': alert.threshold.operator,
            'severity': alert.severity.value,
            'status': alert.status.value,
            'message': alert.message,
            'created_at': alert.created_at.isoformat(),
            'updated_at': alert.updated_at.isoformat()
        }
        
        headers = {'Content-Type': 'application/json'}
        if 'headers' in config:
            headers.update(config['headers'])
        
        response = requests.post(
            config['url'],
            json=payload,
            headers=headers,
            timeout=config.get('timeout', 30)
        )
        response.raise_for_status()
        
        logger.info(f"Webhook notification sent for alert {alert.id}")
    
    async def _send_slack_notification(self, channel: NotificationChannel, alert: Alert) -> None:
        """Send Slack notification."""
        config = channel.config
        
        color_map = {
            AlertSeverity.INFO: 'good',
            AlertSeverity.WARNING: 'warning', 
            AlertSeverity.CRITICAL: 'danger',
            AlertSeverity.EMERGENCY: 'danger'
        }
        
        payload = {
            'text': f"Alert: {alert.metric_name}",
            'attachments': [{
                'color': color_map.get(alert.severity, 'warning'),
                'fields': [
                    {'title': 'Metric', 'value': alert.metric_name, 'short': True},
                    {'title': 'Current Value', 'value': str(alert.current_value), 'short': True},
                    {'title': 'Threshold', 'value': f"{alert.threshold.operator} {alert.threshold.value}", 'short': True},
                    {'title': 'Severity', 'value': alert.severity.value.upper(), 'short': True},
                    {'title': 'Message', 'value': alert.message, 'short': False}
                ],
                'ts': int(alert.created_at.timestamp())
            }]
        }
        
        response = requests.post(
            config['webhook_url'],
            json=payload,
            timeout=config.get('timeout', 30)
        )
        response.raise_for_status()
        
        logger.info(f"Slack notification sent for alert {alert.id}")
    
    # Public API methods
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acknowledge an alert."""
        with self._lock:
            if alert_id in self._active_alerts:
                alert = self._active_alerts[alert_id]
                alert.status = AlertStatus.ACKNOWLEDGED
                alert.acknowledged_at = datetime.utcnow()
                alert.acknowledged_by = acknowledged_by
                alert.updated_at = datetime.utcnow()
                logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
                return True
        return False
    
    def suppress_alert(self, alert_id: str) -> bool:
        """Suppress an alert."""
        with self._lock:
            if alert_id in self._active_alerts:
                self._suppressed_alerts.add(alert_id)
                alert = self._active_alerts[alert_id]
                alert.status = AlertStatus.SUPPRESSED
                alert.updated_at = datetime.utcnow()
                logger.info(f"Alert {alert_id} suppressed")
                return True
        return False
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts."""
        with self._lock:
            return list(self._active_alerts.values())
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get alert history."""
        with self._lock:
            return list(self._alert_history)[-limit:]
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """Get alert statistics."""
        with self._lock:
            active_count = len(self._active_alerts)
            severity_counts = defaultdict(int)
            
            for alert in self._active_alerts.values():
                severity_counts[alert.severity.value] += 1
            
            return {
                'active_alerts': active_count,
                'severity_breakdown': dict(severity_counts),
                'total_thresholds': len(self._thresholds),
                'notification_channels': len(self._notification_channels)
            }