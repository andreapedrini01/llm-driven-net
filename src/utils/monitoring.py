"""Monitoring and metrics utilities."""

import time
from typing import Any, Dict, Optional
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from functools import wraps


# Prometheus metrics
INTENT_COUNTER = Counter(
    'llm_module_intents_total',
    'Total number of intents processed',
    ['intent_type', 'status']
)

ACTION_COUNTER = Counter(
    'llm_module_actions_total',
    'Total number of actions generated',
    ['action_type', 'status']
)

PROCESSING_TIME = Histogram(
    'llm_module_processing_seconds',
    'Time spent processing intents',
    ['component']
)

ANOMALY_COUNTER = Counter(
    'llm_module_anomalies_total',
    'Total number of anomalies detected',
    ['anomaly_type', 'severity']
)

NETWORK_STATE_AGE = Gauge(
    'llm_module_network_state_age_seconds',
    'Age of the current network state in seconds'
)

LLM_REQUEST_COUNTER = Counter(
    'llm_module_llm_requests_total',
    'Total number of LLM API requests',
    ['model', 'status']
)

LLM_REQUEST_DURATION = Histogram(
    'llm_module_llm_request_seconds',
    'Duration of LLM API requests',
    ['model']
)


class MetricsCollector:
    """Centralized metrics collection."""
    
    def __init__(self):
        self.start_time = time.time()
    
    def record_intent_processed(self, intent_type: str, success: bool) -> None:
        """Record an intent processing event."""
        status = "success" if success else "failure"
        INTENT_COUNTER.labels(intent_type=intent_type, status=status).inc()
    
    def record_action_generated(self, action_type: str, success: bool) -> None:
        """Record an action generation event."""
        status = "success" if success else "failure"
        ACTION_COUNTER.labels(action_type=action_type, status=status).inc()
    
    def record_anomaly_detected(self, anomaly_type: str, severity: str) -> None:
        """Record an anomaly detection event."""
        ANOMALY_COUNTER.labels(anomaly_type=anomaly_type, severity=severity).inc()
    
    def update_network_state_age(self, age_seconds: float) -> None:
        """Update the network state age metric."""
        NETWORK_STATE_AGE.set(age_seconds)
    
    def record_llm_request(self, model: str, duration: float, success: bool) -> None:
        """Record an LLM API request."""
        status = "success" if success else "failure"
        LLM_REQUEST_COUNTER.labels(model=model, status=status).inc()
        if success:
            LLM_REQUEST_DURATION.labels(model=model).observe(duration)


def timed_operation(component: str):
    """Decorator to time operations and record metrics."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                PROCESSING_TIME.labels(component=component).observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                PROCESSING_TIME.labels(component=f"{component}_error").observe(duration)
                raise
        return wrapper
    return decorator


class HealthChecker:
    """Health check utilities."""
    
    def __init__(self):
        self.checks = {}
    
    def register_check(self, name: str, check_func) -> None:
        """Register a health check function."""
        self.checks[name] = check_func
    
    def run_checks(self) -> Dict[str, Any]:
        """Run all registered health checks."""
        results = {}
        overall_healthy = True
        
        for name, check_func in self.checks.items():
            try:
                result = check_func()
                results[name] = {
                    "status": "healthy" if result else "unhealthy",
                    "details": result if isinstance(result, dict) else {}
                }
                if not result:
                    overall_healthy = False
            except Exception as e:
                results[name] = {
                    "status": "error",
                    "error": str(e)
                }
                overall_healthy = False
        
        results["overall"] = "healthy" if overall_healthy else "unhealthy"
        return results


def start_metrics_server(port: int = 8000) -> None:
    """Start the Prometheus metrics server."""
    start_http_server(port)


# Global instances
metrics_collector = MetricsCollector()
health_checker = HealthChecker()