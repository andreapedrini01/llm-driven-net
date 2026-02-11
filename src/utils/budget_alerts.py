"""Budget alerting system for ChatGPT API costs."""

import uuid
from typing import Dict, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from src.utils.logging import get_logger, chatgpt_usage_logger
from src.utils.notifications import (
    Alert,
    AlertSeverity,
    AlertCategory,
    notification_manager
)


logger = get_logger(__name__)


@dataclass
class BudgetThreshold:
    """Represents a budget threshold configuration."""
    
    warning_threshold: float  # USD
    critical_threshold: float  # USD
    period: str = "daily"  # daily, weekly, monthly
    enabled: bool = True


@dataclass
class UsageStats:
    """Tracks usage statistics for a time period."""
    
    period_start: datetime
    period_end: datetime
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    models_used: Dict[str, int] = field(default_factory=dict)
    
    def add_usage(
        self,
        model: str,
        tokens: int,
        cost: float
    ) -> None:
        """Add usage data to stats."""
        self.total_requests += 1
        self.total_tokens += tokens
        self.total_cost += cost
        self.models_used[model] = self.models_used.get(model, 0) + 1


class BudgetAlertManager:
    """Manages budget alerts for ChatGPT API usage."""
    
    def __init__(
        self,
        daily_warning: float = 10.0,
        daily_critical: float = 20.0,
        weekly_warning: float = 50.0,
        weekly_critical: float = 100.0,
        monthly_warning: float = 200.0,
        monthly_critical: float = 500.0
    ):
        """Initialize budget alert manager.
        
        Args:
            daily_warning: Daily warning threshold in USD
            daily_critical: Daily critical threshold in USD
            weekly_warning: Weekly warning threshold in USD
            weekly_critical: Weekly critical threshold in USD
            monthly_warning: Monthly warning threshold in USD
            monthly_critical: Monthly critical threshold in USD
        """
        self.thresholds = {
            "daily": BudgetThreshold(
                warning_threshold=daily_warning,
                critical_threshold=daily_critical,
                period="daily"
            ),
            "weekly": BudgetThreshold(
                warning_threshold=weekly_warning,
                critical_threshold=weekly_critical,
                period="weekly"
            ),
            "monthly": BudgetThreshold(
                warning_threshold=monthly_warning,
                critical_threshold=monthly_critical,
                period="monthly"
            )
        }
        
        # Track usage stats
        self.daily_stats: Optional[UsageStats] = None
        self.weekly_stats: Optional[UsageStats] = None
        self.monthly_stats: Optional[UsageStats] = None
        
        # Track alert states to avoid duplicate alerts
        self.alert_states: Dict[str, Dict[str, bool]] = {
            "daily": {"warning": False, "critical": False},
            "weekly": {"warning": False, "critical": False},
            "monthly": {"warning": False, "critical": False}
        }
        
        self._initialize_stats()
    
    def _initialize_stats(self) -> None:
        """Initialize usage stats for current periods."""
        now = datetime.utcnow()
        
        # Daily stats
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        self.daily_stats = UsageStats(period_start=day_start, period_end=day_end)
        
        # Weekly stats (Monday to Sunday)
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        self.weekly_stats = UsageStats(period_start=week_start, period_end=week_end)
        
        # Monthly stats
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            month_end = month_start.replace(year=now.year + 1, month=1)
        else:
            month_end = month_start.replace(month=now.month + 1)
        self.monthly_stats = UsageStats(period_start=month_start, period_end=month_end)
    
    def _check_period_rollover(self) -> None:
        """Check if any periods have rolled over and reset stats."""
        now = datetime.utcnow()
        
        # Check daily rollover
        if self.daily_stats and now >= self.daily_stats.period_end:
            logger.info(
                "Daily period rollover",
                old_period_start=self.daily_stats.period_start.isoformat(),
                total_cost=self.daily_stats.total_cost
            )
            # Log summary before reset
            chatgpt_usage_logger.log_usage_summary(
                period_start=self.daily_stats.period_start,
                period_end=self.daily_stats.period_end,
                total_requests=self.daily_stats.total_requests,
                total_tokens=self.daily_stats.total_tokens,
                total_cost=self.daily_stats.total_cost,
                models_used=self.daily_stats.models_used
            )
            # Reset
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            self.daily_stats = UsageStats(period_start=day_start, period_end=day_end)
            self.alert_states["daily"] = {"warning": False, "critical": False}
        
        # Check weekly rollover
        if self.weekly_stats and now >= self.weekly_stats.period_end:
            logger.info(
                "Weekly period rollover",
                old_period_start=self.weekly_stats.period_start.isoformat(),
                total_cost=self.weekly_stats.total_cost
            )
            chatgpt_usage_logger.log_usage_summary(
                period_start=self.weekly_stats.period_start,
                period_end=self.weekly_stats.period_end,
                total_requests=self.weekly_stats.total_requests,
                total_tokens=self.weekly_stats.total_tokens,
                total_cost=self.weekly_stats.total_cost,
                models_used=self.weekly_stats.models_used
            )
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
            week_end = week_start + timedelta(days=7)
            self.weekly_stats = UsageStats(period_start=week_start, period_end=week_end)
            self.alert_states["weekly"] = {"warning": False, "critical": False}
        
        # Check monthly rollover
        if self.monthly_stats and now >= self.monthly_stats.period_end:
            logger.info(
                "Monthly period rollover",
                old_period_start=self.monthly_stats.period_start.isoformat(),
                total_cost=self.monthly_stats.total_cost
            )
            chatgpt_usage_logger.log_usage_summary(
                period_start=self.monthly_stats.period_start,
                period_end=self.monthly_stats.period_end,
                total_requests=self.monthly_stats.total_requests,
                total_tokens=self.monthly_stats.total_tokens,
                total_cost=self.monthly_stats.total_cost,
                models_used=self.monthly_stats.models_used
            )
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if now.month == 12:
                month_end = month_start.replace(year=now.year + 1, month=1)
            else:
                month_end = month_start.replace(month=now.month + 1)
            self.monthly_stats = UsageStats(period_start=month_start, period_end=month_end)
            self.alert_states["monthly"] = {"warning": False, "critical": False}
    
    async def record_usage(
        self,
        model: str,
        tokens: int,
        cost: float,
        correlation_id: Optional[str] = None
    ) -> None:
        """Record API usage and check thresholds.
        
        Args:
            model: Model used
            tokens: Total tokens used
            cost: Cost in USD
            correlation_id: Optional correlation ID
        """
        # Check for period rollovers
        self._check_period_rollover()
        
        # Add usage to all periods
        if self.daily_stats:
            self.daily_stats.add_usage(model, tokens, cost)
        if self.weekly_stats:
            self.weekly_stats.add_usage(model, tokens, cost)
        if self.monthly_stats:
            self.monthly_stats.add_usage(model, tokens, cost)
        
        # Check thresholds for each period
        await self._check_thresholds("daily", self.daily_stats, correlation_id)
        await self._check_thresholds("weekly", self.weekly_stats, correlation_id)
        await self._check_thresholds("monthly", self.monthly_stats, correlation_id)
    
    async def _check_thresholds(
        self,
        period: str,
        stats: Optional[UsageStats],
        correlation_id: Optional[str]
    ) -> None:
        """Check if thresholds are exceeded and send alerts.
        
        Args:
            period: Period name (daily, weekly, monthly)
            stats: Usage stats for the period
            correlation_id: Optional correlation ID
        """
        if not stats:
            return
        
        threshold = self.thresholds.get(period)
        if not threshold or not threshold.enabled:
            return
        
        current_cost = stats.total_cost
        
        # Check critical threshold
        if current_cost >= threshold.critical_threshold:
            if not self.alert_states[period]["critical"]:
                await self._send_budget_alert(
                    period=period,
                    severity=AlertSeverity.CRITICAL,
                    current_cost=current_cost,
                    threshold=threshold.critical_threshold,
                    stats=stats,
                    correlation_id=correlation_id
                )
                self.alert_states[period]["critical"] = True
                
                # Log to ChatGPT usage logger
                chatgpt_usage_logger.log_budget_alert(
                    alert_type="critical",
                    current_cost=current_cost,
                    threshold=threshold.critical_threshold,
                    message=f"{period.capitalize()} critical budget threshold exceeded",
                    correlation_id=correlation_id
                )
        
        # Check warning threshold
        elif current_cost >= threshold.warning_threshold:
            if not self.alert_states[period]["warning"]:
                await self._send_budget_alert(
                    period=period,
                    severity=AlertSeverity.WARNING,
                    current_cost=current_cost,
                    threshold=threshold.warning_threshold,
                    stats=stats,
                    correlation_id=correlation_id
                )
                self.alert_states[period]["warning"] = True
                
                # Log to ChatGPT usage logger
                chatgpt_usage_logger.log_budget_alert(
                    alert_type="warning",
                    current_cost=current_cost,
                    threshold=threshold.warning_threshold,
                    message=f"{period.capitalize()} warning budget threshold exceeded",
                    correlation_id=correlation_id
                )
    
    async def _send_budget_alert(
        self,
        period: str,
        severity: AlertSeverity,
        current_cost: float,
        threshold: float,
        stats: UsageStats,
        correlation_id: Optional[str]
    ) -> None:
        """Send a budget alert notification.
        
        Args:
            period: Period name
            severity: Alert severity
            current_cost: Current cost
            threshold: Threshold that was exceeded
            stats: Usage statistics
            correlation_id: Optional correlation ID
        """
        percentage = (current_cost / threshold) * 100
        
        alert = Alert(
            id=str(uuid.uuid4()),
            severity=severity,
            category=AlertCategory.BUDGET,
            title=f"ChatGPT API Budget Alert - {period.capitalize()}",
            message=(
                f"The {period} ChatGPT API budget has reached {percentage:.1f}% "
                f"of the {severity.value} threshold.\n\n"
                f"Current cost: ${current_cost:.2f}\n"
                f"Threshold: ${threshold:.2f}\n"
                f"Total requests: {stats.total_requests}\n"
                f"Total tokens: {stats.total_tokens:,}\n"
                f"Period: {stats.period_start.strftime('%Y-%m-%d')} to "
                f"{stats.period_end.strftime('%Y-%m-%d')}"
            ),
            correlation_id=correlation_id,
            metadata={
                "period": period,
                "current_cost": f"${current_cost:.2f}",
                "threshold": f"${threshold:.2f}",
                "percentage": f"{percentage:.1f}%",
                "total_requests": stats.total_requests,
                "total_tokens": stats.total_tokens,
                "models_used": stats.models_used,
                "period_start": stats.period_start.isoformat(),
                "period_end": stats.period_end.isoformat()
            }
        )
        
        await notification_manager.send_alert(alert)
        
        logger.warning(
            "Budget alert sent",
            period=period,
            severity=severity.value,
            current_cost=current_cost,
            threshold=threshold
        )
    
    def get_current_usage(self, period: str = "daily") -> Optional[Dict[str, any]]:
        """Get current usage statistics for a period.
        
        Args:
            period: Period to get stats for (daily, weekly, monthly)
            
        Returns:
            Dictionary with usage statistics or None
        """
        stats_map = {
            "daily": self.daily_stats,
            "weekly": self.weekly_stats,
            "monthly": self.monthly_stats
        }
        
        stats = stats_map.get(period)
        if not stats:
            return None
        
        threshold = self.thresholds.get(period)
        
        return {
            "period": period,
            "period_start": stats.period_start.isoformat(),
            "period_end": stats.period_end.isoformat(),
            "total_requests": stats.total_requests,
            "total_tokens": stats.total_tokens,
            "total_cost": stats.total_cost,
            "models_used": stats.models_used,
            "warning_threshold": threshold.warning_threshold if threshold else None,
            "critical_threshold": threshold.critical_threshold if threshold else None,
            "warning_triggered": self.alert_states[period]["warning"],
            "critical_triggered": self.alert_states[period]["critical"]
        }
    
    def update_thresholds(
        self,
        period: str,
        warning_threshold: Optional[float] = None,
        critical_threshold: Optional[float] = None
    ) -> bool:
        """Update budget thresholds for a period.
        
        Args:
            period: Period to update (daily, weekly, monthly)
            warning_threshold: New warning threshold in USD
            critical_threshold: New critical threshold in USD
            
        Returns:
            True if updated successfully
        """
        if period not in self.thresholds:
            logger.error("Invalid period", period=period)
            return False
        
        threshold = self.thresholds[period]
        
        if warning_threshold is not None:
            threshold.warning_threshold = warning_threshold
        if critical_threshold is not None:
            threshold.critical_threshold = critical_threshold
        
        logger.info(
            "Budget thresholds updated",
            period=period,
            warning_threshold=threshold.warning_threshold,
            critical_threshold=threshold.critical_threshold
        )
        
        return True


# Global budget alert manager instance
budget_alert_manager = BudgetAlertManager()

