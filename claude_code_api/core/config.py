"""Configuration management for Claude Code API Gateway."""

import os
import shutil
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_claude_binary() -> str:
    """Find Claude binary path automatically."""
    # First check environment variable
    if 'CLAUDE_BINARY_PATH' in os.environ:
        claude_path = os.environ['CLAUDE_BINARY_PATH']
        if os.path.exists(claude_path):
            return claude_path

    # Try to find claude in PATH - this should work for npm global installs
    claude_path = shutil.which("claude")
    if claude_path:
        return claude_path

    # Import npm environment if needed
    try:
        import subprocess
        # Try to get npm global bin path
        result = subprocess.run(['npm', 'bin', '-g'], capture_output=True, text=True)
        if result.returncode == 0:
            npm_bin_path = result.stdout.strip()
            claude_npm_path = os.path.join(npm_bin_path, 'claude')
            if os.path.exists(claude_npm_path):
                return claude_npm_path
    except Exception:
        pass

    # Fallback to common npm/nvm locations
    import glob
    common_patterns = [
        "/usr/local/bin/claude",
        "/usr/local/share/nvm/versions/node/*/bin/claude",
        "~/.nvm/versions/node/*/bin/claude",
    ]

    for pattern in common_patterns:
        expanded_pattern = os.path.expanduser(pattern)
        matches = glob.glob(expanded_pattern)
        if matches:
            # Return the most recent version
            return sorted(matches)[-1]

    return "claude"  # Final fallback


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # 重要：不要尝试将字符串解析为 JSON
        json_schema_extra={
            "env_parse_none_str": ""
        }
    )

    # API Configuration
    api_title: str = "Claude Code API Gateway"
    api_version: str = "1.0.0"
    api_description: str = "OpenAI-compatible API for Claude Code"

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Authentication
    api_keys: List[str] = Field(default_factory=list)
    require_auth: bool = False

    @field_validator('api_keys', mode='before')
    @classmethod
    def parse_api_keys(cls, v):
        """Parse API keys from string or list, handle empty values gracefully."""
        # Handle None or empty string
        if v is None or v == "":
            return []
        # Handle string input (comma-separated)
        if isinstance(v, str):
            return [x.strip() for x in v.split(',') if x.strip()]
        # Handle list input
        if isinstance(v, list):
            return v
        # Fallback to empty list
        return []

    # Claude Configuration
    claude_binary_path: str = find_claude_binary()
    claude_base_url: str = "https://api.moonshot.cn/anthropic/"
    claude_api_key: str = "sk-JyiveXJh4jfKp73ZbdSkZ6FycuOSaluwAnXFAZcYFbcHzVDL"
    default_model: str = "kimi-k2-turbo-preview"
    fallback_model: str = "kimi-k2-0905-preview"  # Fallback model for better reliability
    max_concurrent_sessions: int = 10
    session_timeout_minutes: int = 30
    enable_partial_messages: bool = True  # Enable partial message streaming
    enable_session_continuity: bool = True  # Enable session ID continuity

    # Project Configuration
    project_root: str = "/tmp/claude_projects"
    max_project_size_mb: int = 1000
    cleanup_interval_minutes: int = 60

    # Database Configuration
    database_url: str = "sqlite:///./claude_api.db"

    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "console"  # "console" for real-time output, "json" for structured logs
    enable_console_logs: bool = True  # Enable real-time console output
    enable_file_logs: bool = False  # Enable file logging
    log_file_path: str = "claude_api.log"  # Log file path

    # CORS Configuration
    allowed_origins: List[str] = Field(default=["*"])
    allowed_methods: List[str] = Field(default=["*"])
    allowed_headers: List[str] = Field(default=["*"])

    @field_validator('allowed_origins', 'allowed_methods', 'allowed_headers', mode='before')
    def parse_cors_lists(cls, v):
        """Parse CORS lists from string, handle empty values gracefully."""
        # Handle None or empty string
        if not v or v == "":
            return ["*"]
        # Handle string input (comma-separated)
        if isinstance(v, str):
            parsed = [x.strip() for x in v.split(',') if x.strip()]
            return parsed if parsed else ["*"]
        # Handle list input
        if isinstance(v, list):
            return v if v else ["*"]
        # Fallback to wildcard
        return ["*"]

    # Rate Limiting
    rate_limit_requests_per_minute: int = 100
    rate_limit_burst: int = 10

    # Streaming Configuration
    streaming_chunk_size: int = 1024
    streaming_timeout_seconds: int = 30  # Reduced from 300 to 30 seconds


# Create global settings instance
settings = Settings()

# Ensure project root exists
os.makedirs(settings.project_root, exist_ok=True)
