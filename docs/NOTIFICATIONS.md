# Notification and Alerting System

The LLM Integration Module includes a comprehensive notification and alerting system that sends alerts to administrators through multiple channels.

## Features

### Alert Severity Classification

Alerts are classified into four severity levels:

- **INFO**: Informational messages
- **WARNING**: Warning conditions that require attention
- **ERROR**: Error conditions that need immediate attention
- **CRITICAL**: Critical conditions requiring urgent action

### Alert Categories

Alerts are categorized by type:

- **ANOMALY**: Network anomaly detection alerts
- **SYSTEM_ERROR**: System-level errors
- **API_ERROR**: External API errors (ChatGPT, RYU, etc.)
- **BUDGET**: Budget threshold alerts for API costs
- **SECURITY**: Security-related alerts
- **PERFORMANCE**: Performance degradation alerts
- **NETWORK_STATE**: Network state issues

### Notification Channels

The system supports multiple notification channels:

#### 1. Email Notifications

Send alerts via email using SMTP.

**Configuration:**
```env
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=llm-module@example.com
SMTP_TO_EMAILS=admin1@example.com,admin2@example.com
SMTP_USE_TLS=true
```

**Features:**
- HTML-formatted emails with color-coded severity
- Includes all alert metadata
- Supports multiple recipients

#### 2. Slack Notifications

Send alerts to Slack channels using webhooks.

**Configuration:**
```env
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SLACK_CHANNEL=#alerts
SLACK_USERNAME=LLM Integration Module
```

**Features:**
- Rich message formatting with attachments
- Color-coded by severity
- Includes all alert details as fields

#### 3. Generic Webhook Notifications

Send alerts to any webhook endpoint.

**Configuration:**
```env
WEBHOOK_ENABLED=true
WEBHOOK_URL=https://your-webhook-endpoint.com/alerts
WEBHOOK_HEADERS={"Authorization": "Bearer your-token"}
```

**Features:**
- Sends alert as JSON payload
- Supports custom headers for authentication
- Compatible with any webhook-based system

### Budget Alerts

The system includes automatic budget monitoring for ChatGPT API costs.

**Configuration:**
```env
BUDGET_ALERTS_ENABLED=true
BUDGET_DAILY_WARNING=10.0
BUDGET_DAILY_CRITICAL=20.0
BUDGET_WEEKLY_WARNING=50.0
BUDGET_WEEKLY_CRITICAL=100.0
BUDGET_MONTHLY_WARNING=200.0
BUDGET_MONTHLY_CRITICAL=500.0
```

**Features:**
- Tracks API usage in real-time
- Monitors daily, weekly, and monthly spending
- Sends alerts when warning or critical thresholds are exceeded
- Automatic period rollover with usage summaries
- Prevents duplicate alerts within the same period

## Usage

### Sending Alerts Programmatically

The system provides helper functions for sending different types of alerts:

```python
from src.utils.alert_helpers import (
    send_anomaly_alert,
    send_system_error_alert,
    send_api_error_alert,
    send_security_alert,
    send_performance_alert,
    send_network_state_alert
)

# Send an anomaly alert
await send_anomaly_alert(
    anomaly_id="anomaly-123",
    anomaly_type="traffic_spike",
    severity="warning",
    message="Unusual traffic spike detected on switch sw1",
    metadata={"switch_id": "sw1", "traffic_rate": "1000 Mbps"}
)

# Send a system error alert
await send_system_error_alert(
    error_type="DatabaseError",
    error_message="Failed to connect to database",
    component="state_cache",
    metadata={"retry_count": 3}
)

# Send a security alert
await send_security_alert(
    threat_type="SQL Injection",
    message="Malicious input detected in intent",
    source="192.168.1.100",
    metadata={"intent_id": "intent-456"}
)
```

### Recording API Usage for Budget Tracking

```python
from src.utils.budget_alerts import budget_alert_manager

# Record ChatGPT API usage
await budget_alert_manager.record_usage(
    model="gpt-4-turbo",
    tokens=1500,
    cost=0.045,
    correlation_id="corr-123"
)

# Get current usage statistics
daily_usage = budget_alert_manager.get_current_usage("daily")
print(f"Daily cost: ${daily_usage['total_cost']:.2f}")

# Update budget thresholds
budget_alert_manager.update_thresholds(
    period="daily",
    warning_threshold=15.0,
    critical_threshold=30.0
)
```

### Custom Alert Creation

```python
from src.utils.notifications import (
    Alert,
    AlertSeverity,
    AlertCategory,
    notification_manager
)

# Create a custom alert
alert = Alert(
    id="custom-alert-123",
    severity=AlertSeverity.WARNING,
    category=AlertCategory.PERFORMANCE,
    title="High Memory Usage",
    message="Memory usage exceeded 80% threshold",
    metadata={
        "current_usage": "85%",
        "threshold": "80%",
        "component": "intent_parser"
    }
)

# Send through all configured channels
results = await notification_manager.send_alert(alert)
```

## Severity Filtering

You can configure channels to only receive alerts of specific severities:

```python
from src.utils.notifications import (
    EmailNotificationChannel,
    AlertSeverity,
    notification_manager
)

# Create email channel that only receives ERROR and CRITICAL alerts
email_channel = EmailNotificationChannel(
    smtp_host="smtp.example.com",
    smtp_port=587,
    smtp_username="user@example.com",
    smtp_password="password",
    from_email="alerts@example.com",
    to_emails=["admin@example.com"],
    enabled=True
)

notification_manager.add_channel(
    email_channel,
    "critical_email",
    severity_filter=[AlertSeverity.ERROR, AlertSeverity.CRITICAL]
)
```

## Integration with Existing Components

The notification system is automatically initialized on application startup and integrates with:

- **Logging System**: All alerts are also logged with appropriate severity
- **ChatGPT Usage Logger**: Budget alerts are logged to the ChatGPT usage logger
- **Audit Logger**: Critical alerts are recorded in the audit trail
- **Performance Logger**: Performance-related alerts include metrics

## Testing

The notification system includes comprehensive unit tests:

```bash
# Run notification tests
python -m pytest tests/test_notifications.py -v

# Run with coverage
python -m pytest tests/test_notifications.py --cov=src.utils.notifications --cov=src.utils.budget_alerts --cov=src.utils.alert_helpers
```

## Best Practices

1. **Use Appropriate Severity Levels**: Reserve CRITICAL for truly urgent situations
2. **Include Context**: Always provide relevant metadata with alerts
3. **Avoid Alert Fatigue**: Use severity filtering to prevent overwhelming administrators
4. **Monitor Budget Alerts**: Regularly review and adjust budget thresholds
5. **Test Notification Channels**: Verify all channels are working before production deployment
6. **Secure Credentials**: Store SMTP passwords and webhook tokens securely
7. **Rate Limiting**: Consider implementing rate limiting for high-frequency alerts

## Troubleshooting

### Email Notifications Not Working

- Verify SMTP credentials are correct
- Check if SMTP_USE_TLS is set correctly for your provider
- Ensure firewall allows outbound connections on SMTP port
- For Gmail, use an App Password instead of your regular password

### Slack Notifications Not Working

- Verify webhook URL is correct and active
- Check Slack workspace permissions
- Ensure the webhook has not been revoked

### Budget Alerts Not Triggering

- Verify BUDGET_ALERTS_ENABLED=true
- Check that thresholds are set appropriately
- Ensure API usage is being recorded correctly
- Review logs for any errors in budget tracking

### Missing Alerts

- Check notification channel is enabled
- Verify severity filters are not too restrictive
- Review application logs for notification errors
- Ensure notification system was initialized on startup

## Future Enhancements

Potential improvements for the notification system:

- SMS notifications via Twilio
- PagerDuty integration for on-call management
- Microsoft Teams webhook support
- Alert aggregation to reduce notification volume
- Alert acknowledgment and resolution tracking
- Custom alert templates
- Alert escalation policies
- Notification scheduling (quiet hours)
