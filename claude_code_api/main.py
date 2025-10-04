"""
Claude Code API Gateway

A FastAPI-based service that provides OpenAI-compatible endpoints
while leveraging Claude Code's powerful workflow capabilities.
"""

import os
import logging
import signal
import asyncio
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import json
import structlog

from claude_code_api.core.config import settings
from claude_code_api.core.database import create_tables, close_database
from claude_code_api.core.session_manager import SessionManager
from claude_code_api.core.claude_manager import ClaudeManager
from claude_code_api.api.chat import router as chat_router
from claude_code_api.api.models import router as models_router
from claude_code_api.api.projects import router as projects_router
from claude_code_api.api.sessions import router as sessions_router
from claude_code_api.core.auth import auth_middleware
from claude_code_api.utils.claude_patcher import auto_patch_claude


# Configure structured logging with both console and JSON output
import sys
from structlog.stdlib import add_log_level, add_logger_name, PositionalArgumentsFormatter
from structlog.processors import TimeStamper, StackInfoRenderer, format_exc_info, UnicodeDecoder
from structlog.dev import ConsoleRenderer

# Configure console logging for real-time output
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
console_handler.setFormatter(console_formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)

# Configure structlog for both console and JSON
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        add_logger_name,
        add_log_level,
        PositionalArgumentsFormatter(),
        TimeStamper(fmt="iso"),
        StackInfoRenderer(),
        format_exc_info,
        UnicodeDecoder(),
        # Use ConsoleRenderer for real-time console output
        ConsoleRenderer(colors=True) if settings.log_format == "console" else structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Global reference to managers for signal handling
_managers = {}


class UnicodeJSONResponse(JSONResponse):
    """Custom JSONResponse that preserves Unicode characters without escaping."""
    
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting Claude Code API Gateway", version="1.0.0")

    # Auto-patch Claude CLI to remove root user restriction
    try:
        logger.info("检查 Claude CLI root 权限限制...")
        patch_success = auto_patch_claude(settings.claude_binary_path)
        if patch_success:
            logger.info("✓ Claude CLI root 权限检查已处理")
        else:
            logger.warning("⚠ Claude CLI 修补失败或跳过，可能在 root 用户下无法使用 --dangerously-skip-permissions")
    except Exception as e:
        logger.warning(f"Claude CLI 修补过程出错: {e}")

    # Initialize database
    await create_tables()
    logger.info("Database initialized")

    # Initialize managers
    app.state.session_manager = SessionManager()
    app.state.claude_manager = ClaudeManager()
    _managers['session_manager'] = app.state.session_manager
    _managers['claude_manager'] = app.state.claude_manager
    logger.info("Managers initialized")

    # Verify Claude Code availability
    try:
        claude_version = await app.state.claude_manager.get_version()
        logger.info("Claude Code available", version=claude_version)
    except Exception as e:
        logger.error("Claude Code not available", error=str(e))
        raise HTTPException(
            status_code=503,
            detail="Claude Code CLI not available. Please ensure Claude Code is installed and accessible."
        )
    
    yield
    
    # Cleanup
    logger.info("Shutting down Claude Code API Gateway")
    try:
        await app.state.session_manager.cleanup_all()
    except Exception as e:
        logger.error("Error during session manager cleanup", error=str(e))
    
    try:
        await app.state.claude_manager.cleanup_all()
    except Exception as e:
        logger.error("Error during claude manager cleanup", error=str(e))
    
    try:
        await close_database()
    except Exception as e:
        logger.error("Error during database cleanup", error=str(e))
    
    logger.info("Shutdown complete")


app = FastAPI(
    title="Claude Code API Gateway",
    description="OpenAI-compatible API for Claude Code with enhanced project management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    default_response_class=UnicodeJSONResponse
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication middleware
app.middleware("http")(auth_middleware)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler with structured logging."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    return UnicodeJSONResponse(
        status_code=500,
        content={
            "error": {
                "message": "Internal server error",
                "type": "internal_error",
                "code": "internal_error"
            }
        }
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check Claude Code availability
        claude_version = await app.state.claude_manager.get_version()
        
        # Check for zombie processes
        zombie_count = await app.state.claude_manager.check_zombie_processes()
        
        return {
            "status": "healthy",
            "version": "1.0.0",
            "claude_version": claude_version,
            "active_sessions": len(app.state.session_manager.active_sessions),
            "claude_processes": len(app.state.claude_manager.get_active_sessions()),
            "zombie_processes_cleaned": zombie_count
        }
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Claude Code API Gateway",
        "version": "1.0.0",
        "description": "OpenAI-compatible API for Claude Code",
        "endpoints": {
            "chat": "/v1/chat/completions",
            "models": "/v1/models",
            "projects": "/v1/projects",
            "sessions": "/v1/sessions"
        },
        "docs": "/docs",
        "health": "/health"
    }


# Include API routers
app.include_router(chat_router, prefix="/v1", tags=["chat"])
app.include_router(models_router, prefix="/v1", tags=["models"])
app.include_router(projects_router, prefix="/v1", tags=["projects"])
app.include_router(sessions_router, prefix="/v1", tags=["sessions"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "claude_code_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
