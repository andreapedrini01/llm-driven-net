"""Data models for backup and recovery system."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BackupType(str, Enum):
    """Type of backup operation."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class BackupStatus(str, Enum):
    """Status of backup operation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackupInfo(BaseModel):
    """Information about a backup."""
    backup_id: str = Field(..., description="Unique backup identifier")
    backup_type: BackupType = Field(..., description="Type of backup")
    status: BackupStatus = Field(..., description="Backup status")
    created_at: datetime = Field(..., description="Backup creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Backup completion timestamp")
    file_path: str = Field(..., description="Path to backup file")
    file_size: int = Field(..., description="Backup file size in bytes")
    compressed_size: int = Field(..., description="Compressed file size in bytes")
    is_encrypted: bool = Field(..., description="Whether backup is encrypted")
    checksum: str = Field(..., description="Backup file checksum")
    database_name: str = Field(..., description="Name of backed up database")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BackupResult(BaseModel):
    """Result of backup operation."""
    backup_id: str = Field(..., description="Backup identifier")
    status: BackupStatus = Field(..., description="Operation status")
    message: str = Field(..., description="Result message")
    backup_info: Optional[BackupInfo] = Field(None, description="Backup information if successful")
    error_details: Optional[str] = Field(None, description="Error details if failed")
    duration_seconds: float = Field(..., description="Operation duration in seconds")


class RestoreResult(BaseModel):
    """Result of restore operation."""
    restore_id: str = Field(..., description="Restore operation identifier")
    backup_id: str = Field(..., description="Source backup identifier")
    status: str = Field(..., description="Restore status")
    message: str = Field(..., description="Result message")
    restored_at: datetime = Field(..., description="Restore timestamp")
    duration_seconds: float = Field(..., description="Restore duration in seconds")
    error_details: Optional[str] = Field(None, description="Error details if failed")


class BackupConfig(BaseModel):
    """Configuration for backup operations."""
    database_url: str = Field(..., description="PostgreSQL database URL")
    backup_directory: str = Field(..., description="Directory for storing backups")
    compression_enabled: bool = Field(default=True, description="Enable backup compression")
    encryption_enabled: bool = Field(default=True, description="Enable backup encryption")
    encryption_key: Optional[str] = Field(None, description="Encryption key for backups")
    retention_days: int = Field(default=7, ge=1, description="Backup retention period in days")
    max_backup_size_mb: int = Field(default=1000, ge=1, description="Maximum backup size in MB")
    pg_dump_path: str = Field(default="pg_dump", description="Path to pg_dump executable")
    psql_path: str = Field(default="psql", description="Path to psql executable")
    notification_email: Optional[str] = Field(None, description="Email for backup notifications")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for notifications")


class BackupFilters(BaseModel):
    """Filters for backup listing."""
    backup_type: Optional[BackupType] = Field(None, description="Filter by backup type")
    status: Optional[BackupStatus] = Field(None, description="Filter by status")
    created_after: Optional[datetime] = Field(None, description="Filter by creation date")
    created_before: Optional[datetime] = Field(None, description="Filter by creation date")
    database_name: Optional[str] = Field(None, description="Filter by database name")


class BackupSchedule(BaseModel):
    """Schedule configuration for automatic backups."""
    schedule_id: str = Field(..., description="Schedule identifier")
    backup_type: BackupType = Field(..., description="Type of scheduled backup")
    cron_expression: str = Field(..., description="Cron expression for scheduling")
    is_enabled: bool = Field(default=True, description="Whether schedule is enabled")
    database_name: str = Field(..., description="Database to backup")
    retention_days: int = Field(default=7, ge=1, description="Retention period for scheduled backups")
    notification_on_failure: bool = Field(default=True, description="Send notification on failure")
    notification_on_success: bool = Field(default=False, description="Send notification on success")


class VerificationResult(BaseModel):
    """Result of backup verification."""
    backup_id: str = Field(..., description="Backup identifier")
    is_valid: bool = Field(..., description="Whether backup is valid")
    checksum_match: bool = Field(..., description="Whether checksum matches")
    file_exists: bool = Field(..., description="Whether backup file exists")
    file_readable: bool = Field(..., description="Whether backup file is readable")
    size_match: bool = Field(..., description="Whether file size matches metadata")
    verification_time: datetime = Field(..., description="Verification timestamp")
    error_details: Optional[str] = Field(None, description="Error details if verification failed")


class CleanupResult(BaseModel):
    """Result of backup cleanup operation."""
    cleanup_id: str = Field(..., description="Cleanup operation identifier")
    deleted_backups: List[str] = Field(..., description="List of deleted backup IDs")
    freed_space_bytes: int = Field(..., description="Amount of space freed in bytes")
    cleanup_time: datetime = Field(..., description="Cleanup timestamp")
    error_details: Optional[str] = Field(None, description="Error details if cleanup failed")


class DatabaseConfig(BaseModel):
    """PostgreSQL database configuration."""
    host: str = Field(..., description="Database host")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    ssl_mode: str = Field(default="prefer", description="SSL mode")
    connection_timeout: int = Field(default=30, ge=1, description="Connection timeout in seconds")
    
    @property
    def connection_url(self) -> str:
        """Generate PostgreSQL connection URL."""
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}?sslmode={self.ssl_mode}"


class BackupMetrics(BaseModel):
    """Metrics for backup operations."""
    total_backups: int = Field(..., description="Total number of backups")
    successful_backups: int = Field(..., description="Number of successful backups")
    failed_backups: int = Field(..., description="Number of failed backups")
    total_size_bytes: int = Field(..., description="Total size of all backups")
    average_backup_time_seconds: float = Field(..., description="Average backup time")
    last_backup_time: Optional[datetime] = Field(None, description="Last backup timestamp")
    next_scheduled_backup: Optional[datetime] = Field(None, description="Next scheduled backup")
    retention_compliance: float = Field(..., description="Percentage of backups within retention policy")