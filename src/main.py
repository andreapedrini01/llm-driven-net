"""Main application entry point."""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .utils.logging import configure_logging, get_logger
from .utils.monitoring import start_metrics_server, health_checker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    settings = get_settings()
    logger = get_logger(__name__)
    
    # Configure logging
    configure_logging(
        log_level=settings.log_level,
        json_logs=settings.json_logs
    )
    
    logger.info("Starting LLM Integration Module", version=settings.app_version)
    
    # Start metrics server if enabled
    if settings.enable_metrics:
        start_metrics_server(settings.metrics_port)
        logger.info("Metrics server started", port=settings.metrics_port)
    
    # Register health checks
    health_checker.register_check("api", lambda: True)
    
    logger.info("Application startup complete")
    
    yield
    
    logger.info("Application shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add security middleware (rate limiting, input sanitization, security headers)
    from .api.security_middleware import setup_security_middleware
    setup_security_middleware(app)
    
    # Add API routers
    from .api.routes import intent_router, health_router
    from .api.auth_routes import auth_router
    
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(intent_router, prefix=settings.api_prefix)
    app.include_router(health_router)
    
    return app


# Create the application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_config=None,  # We handle logging ourselves
    )