"""Tests for notification and alerting system."""

import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import smtplib
import requests

from src.utils.notifications import (
    Alert,
    AlertSeverity,
    AlertCategory,
    EmailNotificationChannel,
    SlackNotificationChannel,
    WebhookNotificationChannel,
    NotificationManager,
    notification_manager
)
from src.utils.budget_alerts import (
    BudgetThreshold,
    UsageStats,
    BudgetAlertManager,
    budget_alert_manager
)
from src.utils.alert_helpers import (
    initialize_notification_system,
    send_anomaly_alert,
    send_system_error_alert,
    send_api_error_alert,
    send_security_alert,
    send_performance_alert,
    send_network_state_alert
)


class TestAlert:
    """Tests for Alert class."""
    
    def test_alert_creation(self):
        """Test creating an alert."""
        alert = Alert(
            id="alert-123",
            severity=AlertSeverity.WARNING,
            category=AlertCategory.ANOMALY,
            title="Test Alert",
            message="This is a test alert"
        )
        
        assert alert.id == "alert-123"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.category == AlertCategory.ANOMALY
        assert alert.title == "Test Alert"
        assert alert.message == "This is a test alert"
        assert isinstance(alert.timestamp, datetime)
    
    def test_alert_to_dict(self):
        """Test converting alert to dictionary."""
        alert = Alert(
            id="alert-123",
            severity=AlertSeverity.ERROR,
            category=AlertCategory.SYSTEM_ERROR,
            title="System Error",
            message="An error occurred",
            correlation_id="corr-456",
            metadata={"component": "parser"}
        )
        
        alert_dict = alert.to_dict()
        
        assert alert_dict["id"] == "alert-123"
        assert alert_dict["severity"] == "error"
        assert alert_dict["category"] == "system_error"
        assert alert_dict["correlation_id"] == "corr-456"
        assert alert_dict["metadata"]["component"] == "parser"
    
    def test_alert_severity_emoji(self):
        """Test getting severity emoji."""
        info_alert = Alert(
            id="1", severity=AlertSeverity.INFO,
            category=AlertCategory.ANOMALY, title="Info", message="Info"
        )
        warning_alert = Alert(
            id="2", severity=AlertSeverity.WARNING,
            category=AlertCategory.ANOMALY, title="Warning", message="Warning"
        )
        error_alert = Alert(
            id="3", severity=AlertSeverity.ERROR,
            category=AlertCategory.ANOMALY, title="Error", message="Error"
        )
        critical_alert = Alert(
            id="4", severity=AlertSeverity.CRITICAL,
            category=AlertCategory.ANOMALY, title="Critical", message="Critical"
        )
        
        assert info_alert.get_severity_emoji() == "ℹ️"
        assert warning_alert.get_severity_emoji() == "⚠️"
        assert error_alert.get_severity_emoji() == "❌"
        assert critical_alert.get_severity_emoji() == "🚨"


class TestEmailNotificationChannel:
    """Tests for EmailNotificationChannel."""
    
    @pytest.mark.asyncio
    async def test_email_channel_send_success(self):
        """Test sending email notification successfully."""
        channel = EmailNotificationChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user@example.com",
            smtp_password="password",
            from_email="sender@example.com",
            to_emails=["admin@example.com"],
            enabled=True
        )
        
        alert = Alert(
            id="alert-123",
            severity=AlertSeverity.WARNING,
            category=AlertCategory.ANOMALY,
            title="Test Alert",
            message="Test message"
        )
        
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            
            result = await channel.send(alert)
            
            assert result is True
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once()
            mock_server.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_email_channel_send_failure(self):
        """Test email notification failure."""
        channel = EmailNotificationChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user@example.com",
            smtp_password="password",
            from_email="sender@example.com",
            to_emails=["admin@example.com"],
            enabled=True
        )
        
        alert = Alert(
            id="alert-123",
            severity=AlertSeverity.ERROR,
            category=AlertCategory.SYSTEM_ERROR,
            title="Test Alert",
            message="Test message"
        )
        
        with patch('smtplib.SMTP') as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP error")
            
            result = await channel.send(alert)
            
            assert result is False
    
    def test_email_channel_is_enabled(self):
        """Test checking if email channel is enabled."""
        enabled_channel = EmailNotificationChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="pass",
            from_email="from@example.com",
            to_emails=["to@example.com"],
            enabled=True
        )
        
        disabled_channel = EmailNotificationChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="pass",
            from_email="from@example.com",
            to_emails=["to@example.com"],
            enabled=False
        )
        
        assert enabled_channel.is_enabled() is True
        assert disabled_channel.is_enabled() is False


class TestSlackNotificationChannel:
    """Tests for SlackNotificationChannel."""
    
    @pytest.mark.asyncio
    async def test_slack_channel_send_success(self):
        """Test sending Slack notification successfully."""
        channel = SlackNotificationChannel(
            webhook_url="https://hooks.slack.com/test",
            enabled=True
        )
        
        alert = Alert(
            id="alert-123",
            severity=AlertSeverity.CRITICAL,
            category=AlertCategory.SECURITY,
            title="Security Alert",
            message="Security breach detected"
        )
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            result = await channel.send(alert)
            
            assert result is True
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://hooks.slack.com/test"
    
    @pytest.mark.asyncio
    async def test_slack_channel_send_failure(self):
        """Test Slack notification failure."""
        channel = SlackNotificationChannel(
            webhook_url="https://hooks.slack.com/test",
            enabled=True
        )
        
        alert = Alert(
            id="alert-123",
            severity=AlertSeverity.ERROR,
            category=AlertCategory.API_ERROR,
            title="API Error",
            message="API request failed"
        )
        
        with patch('requests.post') as mock_post:
            mock_post.side_effect = Exception("Network error")
            
            result = await channel.send(alert)
            
            assert result is False
    
    def test_slack_channel_is_enabled(self):
        """Test checking if Slack channel is enabled."""
        enabled_channel = SlackNotificationChannel(
            webhook_url="https://hooks.slack.com/test",
            enabled=True
        )
        
        disabled_channel = SlackNotificationChannel(
            webhook_url="https://hooks.slack.com/test",
            enabled=False
        )
        
        assert enabled_channel.is_enabled() is True
        assert disabled_channel.is_enabled() is False


class TestWebhookNotificationChannel:
    """Tests for WebhookNotificationChannel."""
    
    @pytest.mark.asyncio
    async def test_webhook_channel_send_success(self):
        """Test sending webhook notification successfully."""
        channel = WebhookNotificationChannel(
            webhook_url="https://example.com/webhook",
            headers={"Authorization": "Bearer token"},
            enabled=True
        )
        
        alert = Alert(
            id="alert-123",
            severity=AlertSeverity.INFO,
            category=AlertCategory.PERFORMANCE,
            title="Performance Alert",
            message="High latency detected"
        )
        
        with patch('requests.post') as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response
            
            result = await channel.send(alert)
            
            assert result is True
            mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_webhook_channel_send_failure(self):
        """Test webhook notification failure."""
        channel = WebhookNotificationChannel(
            webhook_url="https://example.com/webhook",
            enabled=True
        )
        
        alert = Alert(
            id="alert-123",
            severity=AlertSeverity.WARNING,
            category=AlertCategory.NETWORK_STATE,
            title="State Alert",
            message="State update failed"
        )
        
        with patch('requests.post') as mock_post:
            mock_post.side_effect = Exception("Connection error")
            
            result = await channel.send(alert)
            
            assert result is False


class TestNotificationManager:
    """Tests for NotificationManager."""
    
    @pytest.mark.asyncio
    async def test_add_channel(self):
        """Test adding notification channel."""
        manager = NotificationManager()
        channel = Mock(spec=EmailNotificationChannel)
        
        manager.add_channel(channel, "test_email")
        
        assert len(manager.channels) == 1
    
    @pytest.mark.asyncio
    async def test_send_alert_to_all_channels(self):
        """Test sending alert to all channels."""
        manager = NotificationManager()
        
        channel1 = AsyncMock(spec=EmailNotificationChannel)
        channel1.send = AsyncMock(return_value=True)
        channel1.is_enabled = Mock(return_value=True)
        
        channel2 = AsyncMock(spec=SlackNotificationChannel)
        channel2.send = AsyncMock(return_value=True)
        channel2.is_enabled = Mock(return_value=True)
        
        manager.add_channel(channel1, "email")
        manager.add_channel(channel2, "slack")
        
        alert = Alert(
            id="alert-123",
            severity=AlertSeverity.ERROR,
            category=AlertCategory.SYSTEM_ERROR,
            title="Test",
            message="Test"
        )
        
        results = await manager.send_alert(alert)
        
        assert len(results) == 2
        channel1.send.assert_called_once_with(alert)
        channel2.send.assert_called_once_with(alert)
    
    @pytest.mark.asyncio
    async def test_severity_filter(self):
        """Test severity filtering for channels."""
        manager = NotificationManager()
        
        channel = AsyncMock(spec=EmailNotificationChannel)
        channel.send = AsyncMock(return_value=True)
        channel.is_enabled = Mock(return_value=True)
        
        # Only send ERROR and CRITICAL alerts
        manager.add_channel(
            channel,
            "email",
            severity_filter=[AlertSeverity.ERROR, AlertSeverity.CRITICAL]
        )
        
        # INFO alert should be filtered out
        info_alert = Alert(
            id="1",
            severity=AlertSeverity.INFO,
            category=AlertCategory.ANOMALY,
            title="Info",
            message="Info"
        )
        
        await manager.send_alert(info_alert)
        channel.send.assert_not_called()
        
        # ERROR alert should be sent
        error_alert = Alert(
            id="2",
            severity=AlertSeverity.ERROR,
            category=AlertCategory.SYSTEM_ERROR,
            title="Error",
            message="Error"
        )
        
        await manager.send_alert(error_alert)
        channel.send.assert_called_once_with(error_alert)


class TestBudgetAlertManager:
    """Tests for BudgetAlertManager."""
    
    @pytest.mark.asyncio
    async def test_record_usage(self):
        """Test recording API usage."""
        manager = BudgetAlertManager(
            daily_warning=10.0,
            daily_critical=20.0
        )
        
        await manager.record_usage(
            model="gpt-4-turbo",
            tokens=1000,
            cost=0.05
        )
        
        assert manager.daily_stats.total_requests == 1
        assert manager.daily_stats.total_tokens == 1000
        assert manager.daily_stats.total_cost == 0.05
    
    @pytest.mark.asyncio
    async def test_warning_threshold_alert(self):
        """Test warning threshold alert."""
        manager = BudgetAlertManager(
            daily_warning=1.0,
            daily_critical=2.0
        )
        
        with patch('src.utils.budget_alerts.notification_manager.send_alert') as mock_send:
            mock_send.return_value = {}
            
            # Exceed warning threshold
            await manager.record_usage(
                model="gpt-4-turbo",
                tokens=10000,
                cost=1.5
            )
            
            # Should trigger warning alert
            assert manager.alert_states["daily"]["warning"] is True
            assert manager.alert_states["daily"]["critical"] is False
            mock_send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_critical_threshold_alert(self):
        """Test critical threshold alert."""
        manager = BudgetAlertManager(
            daily_warning=1.0,
            daily_critical=2.0
        )
        
        with patch('src.utils.budget_alerts.notification_manager.send_alert') as mock_send:
            mock_send.return_value = {}
            
            # Exceed critical threshold
            await manager.record_usage(
                model="gpt-4-turbo",
                tokens=20000,
                cost=2.5
            )
            
            # Should trigger critical alert
            assert manager.alert_states["daily"]["critical"] is True
            mock_send.assert_called()
    
    def test_get_current_usage(self):
        """Test getting current usage statistics."""
        manager = BudgetAlertManager()
        
        usage = manager.get_current_usage("daily")
        
        assert usage is not None
        assert "period" in usage
        assert "total_requests" in usage
        assert "total_cost" in usage
        assert usage["period"] == "daily"
    
    def test_update_thresholds(self):
        """Test updating budget thresholds."""
        manager = BudgetAlertManager()
        
        result = manager.update_thresholds(
            period="daily",
            warning_threshold=15.0,
            critical_threshold=30.0
        )
        
        assert result is True
        assert manager.thresholds["daily"].warning_threshold == 15.0
        assert manager.thresholds["daily"].critical_threshold == 30.0


class TestAlertHelpers:
    """Tests for alert helper functions."""
    
    @pytest.mark.asyncio
    async def test_send_anomaly_alert(self):
        """Test sending anomaly alert."""
        with patch('src.utils.alert_helpers.notification_manager.send_alert') as mock_send:
            mock_send.return_value = {}
            
            await send_anomaly_alert(
                anomaly_id="anomaly-123",
                anomaly_type="traffic_spike",
                severity="warning",
                message="Traffic spike detected"
            )
            
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0][0]
            assert call_args.category == AlertCategory.ANOMALY
            assert call_args.severity == AlertSeverity.WARNING
    
    @pytest.mark.asyncio
    async def test_send_system_error_alert(self):
        """Test sending system error alert."""
        with patch('src.utils.alert_helpers.notification_manager.send_alert') as mock_send:
            mock_send.return_value = {}
            
            await send_system_error_alert(
                error_type="DatabaseError",
                error_message="Connection failed",
                component="database"
            )
            
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0][0]
            assert call_args.category == AlertCategory.SYSTEM_ERROR
            assert call_args.severity == AlertSeverity.ERROR
    
    @pytest.mark.asyncio
    async def test_send_api_error_alert_final_retry(self):
        """Test sending API error alert on final retry."""
        with patch('src.utils.alert_helpers.notification_manager.send_alert') as mock_send:
            mock_send.return_value = {}
            
            # Should send alert on final retry (attempt 3)
            await send_api_error_alert(
                api_name="ChatGPT",
                error_type="TimeoutError",
                error_message="Request timed out",
                retry_attempt=3
            )
            
            mock_send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_api_error_alert_early_retry(self):
        """Test not sending API error alert on early retry."""
        with patch('src.utils.alert_helpers.notification_manager.send_alert') as mock_send:
            mock_send.return_value = {}
            
            # Should not send alert on early retry (attempt 1)
            await send_api_error_alert(
                api_name="ChatGPT",
                error_type="TimeoutError",
                error_message="Request timed out",
                retry_attempt=1
            )
            
            mock_send.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_send_security_alert(self):
        """Test sending security alert."""
        with patch('src.utils.alert_helpers.notification_manager.send_alert') as mock_send:
            mock_send.return_value = {}
            
            await send_security_alert(
                threat_type="SQL Injection",
                message="Malicious input detected",
                source="192.168.1.100"
            )
            
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0][0]
            assert call_args.category == AlertCategory.SECURITY
            assert call_args.severity == AlertSeverity.CRITICAL
    
    @pytest.mark.asyncio
    async def test_send_performance_alert(self):
        """Test sending performance alert."""
        with patch('src.utils.alert_helpers.notification_manager.send_alert') as mock_send:
            mock_send.return_value = {}
            
            await send_performance_alert(
                metric_name="response_time",
                current_value=5000.0,
                threshold=1000.0,
                message="Response time exceeded threshold"
            )
            
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0][0]
            assert call_args.category == AlertCategory.PERFORMANCE
    
    @pytest.mark.asyncio
    async def test_send_network_state_alert(self):
        """Test sending network state alert."""
        with patch('src.utils.alert_helpers.notification_manager.send_alert') as mock_send:
            mock_send.return_value = {}
            
            await send_network_state_alert(
                state_issue="stale_data",
                message="Network state data is stale"
            )
            
            mock_send.assert_called_once()
            call_args = mock_send.call_args[0][0]
            assert call_args.category == AlertCategory.NETWORK_STATE

