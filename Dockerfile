# Headfull Chrome - Browser Automation API
# Base image with Chromium and Xvfb for real display rendering

FROM python:3.11-slim-bookworm

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies and Chromium in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Xvfb for virtual display
    xvfb \
    # X11 utilities
    x11-utils \
    # Chromium browser (works on both amd64 and arm64)
    chromium \
    chromium-driver \
    # Fonts
    fonts-liberation \
    fonts-noto-color-emoji \
    # For debugging (optional, can remove in production)
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create application user (non-root for security)
RUN useradd -m -s /bin/bash chrome \
    && mkdir -p /var/log/headfull-chrome/sessions \
    && mkdir -p /tmp/chrome-profiles \
    && chown -R chrome:chrome /var/log/headfull-chrome \
    && chown -R chrome:chrome /tmp/chrome-profiles

# Set working directory
WORKDIR /app

# Copy project files needed for install
COPY pyproject.toml README.md ./

# Install Python dependencies (non-editable for Docker)
RUN pip install --no-cache-dir .

# Copy application code
COPY src/ ./src/

# Set ownership
RUN chown -R chrome:chrome /app

# Switch to non-root user
USER chrome

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV HFC_LOG_LEVEL=INFO
# Point to Chromium instead of Chrome
ENV HFC_CHROME_BINARY=/usr/bin/chromium

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start script will handle Xvfb and application
COPY --chown=chrome:chrome scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
