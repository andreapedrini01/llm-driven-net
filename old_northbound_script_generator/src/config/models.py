"""Configuration data models."""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class LogLevel(str, Enum):
    """Logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class RYUConfig(BaseModel):
    """RYU Controller configuration."""
    host: str = Field(default="localhost", description="RYU controller host")
    port: int = Field(default=8080, ge=1, le=65535, description="RYU controller port")
    api_version: str = Field(default="v1.0", description="API version")
    timeout_seconds: int = Field(default=30, ge=1, description="Connection timeout")
    max_retries: int = Field(default=3, ge=0, description="Maximum retry attempts")
    ssl_enabled: bool = Field(default=False, description="Enable SSL/TLS")
    ssl_verify: bool = Field(default=True, description="Verify SSL certificates")
    connection_pool_size: int = Field(default=10, ge=1, description="Connection pool size")
    
    class Config:
        extra = "forbid"


class ComnetsConfig(BaseModel):
    """ComnetsEMU configuration."""
    host: str = Field(default="localhost", description="ComnetsEMU host")
    port: int = Field(default=6653, ge=1, le=65535, description="ComnetsEMU port")
    protocol: str = Field(default="openflow", description="Protocol type")
    version: str = Field(default="1.3", description="Protocol version")
    connection_pool_size: int = Field(default=10, ge=1, description="Connection pool size")
    timeout_seconds: int = Field(default=30, ge=1, description="Connection timeout")
    
    @validator('protocol')
    def validate_protocol(cls, v):
        allowed = ['openflow', 'netconf']
        if v not in allowed:
            raise ValueError(f"Protocol must be one of {allowed}")
        return v
    
    class Config:
        extra = "forbid"


class MonitoringConfig(BaseModel):
    """Monitoring system configuration."""
    metrics_interval_seconds: int = Field(default=60, ge=1, description="Metrics collection interval")
    retention_days: int = Field(default=30, ge=1, description="Metrics retention period")
    alert_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "cpu_usage_percent": 90.0,
            "memory_usage_percent": 90.0,
            "error_rate_percent": 5.0,
            "response_time_p95_ms": 1000.0
        },
        description="Alert threshold values"
    )
    prometheus_enabled: bool = Field(default=True, description="Enable Prometheus export")
    prometheus_port: int = Field(default=9090, ge=1, le=65535, description="Prometheus port")
    influxdb_enabled: bool = Field(default=True, description="Enable InfluxDB storage")
    influxdb_url: str = Field(default="http://localhost:8086", description="InfluxDB URL")
    influxdb_token: Optional[str] = Field(default=None, description="InfluxDB authentication token")
    influxdb_org: str = Field(default="northbound", description="InfluxDB organization")
    influxdb_bucket: str = Field(default="metrics", description="InfluxDB bucket")
    
    class Config:
        extra = "forbid"


class APIConfig(BaseModel):
    """API Gateway configuration."""
    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=8000, ge=1, le=65535, description="API port")
    workers: int = Field(default=4, ge=1, description="Number of worker processes")
    reload: bool = Field(default=False, description="Enable auto-reload")
    cors_enabled: bool = Field(default=True, description="Enable CORS")
    cors_origins: List[str] = Field(default_factory=lambda: ["*"], description="Allowed CORS origins")
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")
    rate_limit_requests: int = Field(default=100, ge=1, description="Requests per minute")
    jwt_secret_key: str = Field(default="change-me-in-production", description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration_minutes: int = Field(default=30, ge=1, description="JWT expiration time")
    
    class Config:
        extra = "forbid"


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: LogLevel = Field(default=LogLevel.INFO, description="Default log level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string"
    )
    structured: bool = Field(default=True, description="Enable structured logging (JSON)")
    file_enabled: bool = Field(default=True, description="Enable file logging")
    file_path: str = Field(default="./logs/northbound.log", description="Log file path")
    file_rotation_enabled: bool = Field(default=True, description="Enable log rotation")
    file_max_bytes: int = Field(default=10485760, ge=1024, description="Max log file size (10MB)")
    file_backup_count: int = Field(default=5, ge=1, description="Number of backup files")
    console_enabled: bool = Field(default=True, description="Enable console logging")
    syslog_enabled: bool = Field(default=False, description="Enable syslog")
    syslog_host: str = Field(default="localhost", description="Syslog host")
    syslog_port: int = Field(default=514, ge=1, le=65535, description="Syslog port")
    filters: Dict[str, LogLevel] = Field(
        default_factory=dict,
        description="Per-component log level filters"
    )
    
    class Config:
        extra = "forbid"


class BackupConfig(BaseModel):
    """Backup system configuration."""
    enabled: bool = Field(default=True, description="Enable backup system")
    directory: str = Field(default="./backups", description="Backup directory")
    retention_days: int = Field(default=7, ge=1, description="Backup retention period")
    compression_enabled: bool = Field(default=True, description="Enable compression")
    encryption_enabled: bool = Field(default=False, description="Enable encryption")
    schedule_cron: str = Field(default="0 * * * *", description="Backup schedule (cron)")
    
    class Config:
        extra = "forbid"


class SystemConfig(BaseModel):
    """Complete system configuration."""
    version: str = Field(default="1.0.0", description="Configuration version")
    environment: str = Field(default="development", description="Environment name")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Component configurations
    ryu: RYUConfig = Field(default_factory=RYUConfig)
    comnets: ComnetsConfig = Field(default_factory=ComnetsConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    backup: BackupConfig = Field(default_factory=BackupConfig)
    
    # Retry and resilience
    max_retries: int = Field(default=3, ge=0, description="Global max retries")
    retry_delay: float = Field(default=2.0, ge=0, description="Retry delay in seconds")
    enable_rollback: bool = Field(default=True, description="Enable automatic rollback")
    
    # Performance
    connection_pool_size: int = Field(default=10, ge=1, description="Global connection pool size")
    request_timeout: int = Field(default=30, ge=1, description="Request timeout in seconds")
    
    class Config:
        extra = "forbid"
    
    @validator('environment')
    def validate_environment(cls, v):
        allowed = ['development', 'staging', 'production']
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    def dict_for_hot_reload(self) -> Dict[str, Any]:
        """Return configuration as dict with hot-reload compatible fields only."""
        # These fields can be changed without restart
        hot_reload_fields = {
            'logging': self.logging.dict(),
            'monitoring': {
                'metrics_interval_seconds': self.monitoring.metrics_interval_seconds,
                'alert_thresholds': self.monitoring.alert_thresholds,
            },
            'api': {
                'rate_limit_requests': self.api.rate_limit_requests,
                'cors_origins': self.api.cors_origins,
            },
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
        }
        return hot_reload_fields
