"""Security middleware for API endpoints.

This module provides:
- Rate limiting middleware
- Input sanitization middleware
- Security headers middleware
"""

import logging
from typing import Callable, Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..utils.input_sanitization import (
    get_input_sanitizer,
    get_rate_limiter,
    RateLimitConfig,
    ThreatLevel
)
from ..config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting requests."""
    
    def __init__(self, app: ASGIApp, config: Optional[RateLimitConfig] = None):
        """Initialize rate limit middleware.
        
        Args:
            app: ASGI application
            config: Rate limit configuration
        """
        super().__init__(app)
        
        # Use config from settings if not provided
        if config is None:
            config = RateLimitConfig(
                requests_per_minute=settings.rate_limit_requests_per_minute,
                requests_per_hour=settings.rate_limit_requests_per_minute * 60,
                requests_per_day=settings.rate_limit_requests_per_minute * 60 * 24,
                burst_size=10,
                block_duration_minutes=15
            )
        
        self.rate_limiter = get_rate_limiter(config)
        logger.info("Rate limit middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response
        """
        # Skip rate limiting for health checks
        if request.url.path.startswith("/health"):
            return await call_next(request)
        
        # Get client identifier (IP address or user ID from auth)
        client_id = request.client.host if request.client else "unknown"
        
        # Extract user ID from headers if available
        user_id = request.headers.get("X-User-ID")
        
        # Check rate limit
        is_allowed, reason = await self.rate_limiter.check_rate_limit(
            client_id=client_id,
            user_id=user_id
        )
        
        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded for {client_id}",
                extra={
                    "client_id": client_id,
                    "user_id": user_id,
                    "path": request.url.path,
                    "reason": reason
                }
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "rate_limit_exceeded",
                    "message": reason,
                    "retry_after": settings.rate_limit_requests_per_minute
                },
                headers={
                    "Retry-After": str(settings.rate_limit_requests_per_minute * 60)
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        stats = await self.rate_limiter.get_client_stats(client_id)
        if stats:
            response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(
                max(0, settings.rate_limit_requests_per_minute - stats["requests_last_minute"])
            )
        
        return response


class InputSanitizationMiddleware(BaseHTTPMiddleware):
    """Middleware for input sanitization and security checks."""
    
    def __init__(
        self,
        app: ASGIApp,
        max_length: Optional[int] = None,
        strict_mode: bool = False
    ):
        """Initialize input sanitization middleware.
        
        Args:
            app: ASGI application
            max_length: Maximum allowed input length
            strict_mode: If True, apply stricter validation rules
        """
        super().__init__(app)
        
        # Use config from settings if not provided
        if max_length is None:
            max_length = settings.max_intent_length
        
        self.sanitizer = get_input_sanitizer(
            max_length=max_length,
            strict_mode=strict_mode,
            allow_html=False
        )
        self.enabled = settings.enable_input_sanitization
        logger.info(
            f"Input sanitization middleware initialized: "
            f"enabled={self.enabled}, max_length={max_length}"
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with input sanitization.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response
        """
        # Skip sanitization if disabled or for health checks
        if not self.enabled or request.url.path.startswith("/health"):
            return await call_next(request)
        
        # Only sanitize POST/PUT/PATCH requests with JSON body
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Get request body
                body = await request.body()
                
                # Skip if no body
                if not body:
                    return await call_next(request)
                
                # Parse JSON body
                import json
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON in request body")
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "error": "invalid_json",
                            "message": "Request body must be valid JSON"
                        }
                    )
                
                # Sanitize text fields
                client_id = request.client.host if request.client else "unknown"
                user_id = request.headers.get("X-User-ID")
                
                violations_found = []
                
                # Check common text fields
                text_fields = ["text", "intent", "query", "message", "description"]
                for field in text_fields:
                    if field in data and isinstance(data[field], str):
                        result = self.sanitizer.sanitize(
                            data[field],
                            context="intent" if field in ["text", "intent"] else "general",
                            user_id=user_id,
                            source_ip=client_id
                        )
                        
                        # Block if critical or high threat
                        if result.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]:
                            violations_found.extend(result.violations)
                            logger.error(
                                f"Security threat detected in field '{field}': "
                                f"threat_level={result.threat_level.value}",
                                extra={
                                    "client_id": client_id,
                                    "user_id": user_id,
                                    "field": field,
                                    "violations": [v.attack_type.value for v in result.violations]
                                }
                            )
                
                # Block request if violations found
                if violations_found:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={
                            "error": "security_violation",
                            "message": "Input contains potentially malicious content",
                            "violations": [
                                {
                                    "type": v.attack_type.value,
                                    "description": v.description,
                                    "threat_level": v.threat_level.value
                                }
                                for v in violations_found
                            ]
                        }
                    )
                
                # Reconstruct request with original body
                # (We don't modify the body, just validate it)
                async def receive():
                    return {"type": "http.request", "body": body}
                
                request._receive = receive
                
            except Exception as e:
                logger.error(f"Error in input sanitization middleware: {e}")
                # Continue processing on middleware error
                pass
        
        # Process request
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware for adding security headers to responses."""
    
    def __init__(self, app: ASGIApp):
        """Initialize security headers middleware.
        
        Args:
            app: ASGI application
        """
        super().__init__(app)
        logger.info("Security headers middleware initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
            
        Returns:
            Response with security headers
        """
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )
        
        return response


def setup_security_middleware(app: ASGIApp) -> None:
    """Setup all security middleware for the application.
    
    Args:
        app: FastAPI application
    """
    # Add middleware in reverse order (last added is executed first)
    
    # Security headers (outermost)
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Input sanitization
    app.add_middleware(
        InputSanitizationMiddleware,
        max_length=settings.max_intent_length,
        strict_mode=False
    )
    
    # Rate limiting (innermost, before request processing)
    app.add_middleware(RateLimitMiddleware)
    
    logger.info("Security middleware setup complete")
