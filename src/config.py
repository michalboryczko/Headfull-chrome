"""Application configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # Chrome/Chromium settings
    chrome_binary: str = "/usr/bin/chromium"
    chrome_user_data_base: str = "/tmp/chrome-profiles"

    # Display settings (Xvfb)
    display_base: int = 99
    display_width: int = 1920
    display_height: int = 1080
    display_depth: int = 24

    # DevTools settings
    devtools_port_base: int = 9222
    max_concurrent_sessions: int = 5

    # Job settings
    default_delay_between_requests: int = 0
    job_timeout_seconds: int = 60
    content_fetch_timeout_seconds: int = 30

    # Logging
    log_level: str = "INFO"
    access_log_path: str = "/var/log/headfull-chrome/access.log"
    session_log_path: str = "/var/log/headfull-chrome/sessions"

    class Config:
        env_prefix = "HFC_"
        env_file = ".env"


settings = Settings()
