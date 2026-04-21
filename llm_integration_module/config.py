"""Configuration management for the LLM Integration Module."""

import os
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseModel):
    """Application settings."""
    
    # Application settings
    app_name: str = "LLM Integration Module"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_prefix: str = "/api/v1"
    
    # Logging settings
    log_level: str = "INFO"
    json_logs: bool = True
    
    # Monitoring settings
    metrics_port: int = 8000
    enable_metrics: bool = True
    
    # RYU Controller settings
    ryu_host: str = "localhost"
    ryu_port: int = 8080
    ryu_api_prefix: str = "/stats"
    ryu_timeout: int = 30
    ryu_retry_attempts: int = 3
    ryu_retry_backoff: float = 1.0
    
    # Northbound Script settings
    northbound_host: str = "localhost"
    northbound_port: int = 9090
    northbound_api_prefix: str = "/actions"
    northbound_timeout: int = 60
    
    # LLM settings
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.4-nano")
    openai_max_tokens: int = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
    openai_temperature: float = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
    
    # Local model settings (for transformers)
    local_model_name: str = "microsoft/DialoGPT-medium"
    local_model_device: str = "cpu"  # "cpu" or "cuda"
    
    # Network state settings
    state_cache_ttl: int = 300  # seconds
    state_refresh_interval: int = 60  # seconds
    
    # Intent processing settings
    intent_confidence_threshold: float = 0.7
    max_clarification_attempts: int = 3
    
    # Action validation settings
    enable_action_simulation: bool = True
    max_action_sequence_length: int = 50
    action_timeout: int = 300  # seconds
    
    # Anomaly detection settings
    anomaly_detection_enabled: bool = True
    anomaly_check_interval: int = 30  # seconds
    anomaly_threshold_multiplier: float = 2.0
    
    # Network slice settings
    max_slices_per_tenant: int = 10
    default_slice_bandwidth: int = 100  # Mbps
    slice_creation_timeout: int = 120  # seconds
    
    # Security settings
    enable_input_sanitization: bool = True
    max_intent_length: int = 1000
    rate_limit_requests_per_minute: int = 60
    
    class Config:
        """Pydantic configuration."""
        # Note: For production, consider using pydantic-settings package
        # This is a simplified version for the basic setup
        pass


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the application settings."""
    return settings