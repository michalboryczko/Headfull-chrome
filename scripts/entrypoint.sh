#!/bin/bash
set -e

# Headfull Chrome Entrypoint Script
# Manages Xvfb display and starts the FastAPI application

echo "Starting Headfull Chrome API..."

# Default display configuration
DISPLAY_NUM=${HFC_DISPLAY_BASE:-99}
DISPLAY_WIDTH=${HFC_DISPLAY_WIDTH:-1920}
DISPLAY_HEIGHT=${HFC_DISPLAY_HEIGHT:-1080}
DISPLAY_DEPTH=${HFC_DISPLAY_DEPTH:-24}

export DISPLAY=":${DISPLAY_NUM}"

# Clean up any stale lock files from previous runs
LOCK_FILE="/tmp/.X${DISPLAY_NUM}-lock"
if [ -f "$LOCK_FILE" ]; then
    echo "Removing stale X lock file: $LOCK_FILE"
    rm -f "$LOCK_FILE"
fi

# Also clean up socket
SOCKET_DIR="/tmp/.X11-unix"
SOCKET_FILE="${SOCKET_DIR}/X${DISPLAY_NUM}"
if [ -e "$SOCKET_FILE" ]; then
    echo "Removing stale X socket: $SOCKET_FILE"
    rm -f "$SOCKET_FILE"
fi

# Start Xvfb with the configured display
echo "Starting Xvfb on display ${DISPLAY} with resolution ${DISPLAY_WIDTH}x${DISPLAY_HEIGHT}x${DISPLAY_DEPTH}..."
Xvfb ${DISPLAY} -screen 0 ${DISPLAY_WIDTH}x${DISPLAY_HEIGHT}x${DISPLAY_DEPTH} -ac &
XVFB_PID=$!

# Wait for Xvfb to be ready
sleep 2

# Verify Xvfb is running
if ! kill -0 $XVFB_PID 2>/dev/null; then
    echo "ERROR: Xvfb failed to start"
    exit 1
fi

echo "Xvfb started successfully (PID: $XVFB_PID)"

# Function to cleanup on exit
cleanup() {
    echo "Shutting down..."
    kill $XVFB_PID 2>/dev/null || true
    rm -f "$LOCK_FILE" "$SOCKET_FILE" 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT EXIT

# Start the FastAPI application
echo "Starting FastAPI application..."

# Convert log level to lowercase for uvicorn
LOG_LEVEL=$(echo "${HFC_LOG_LEVEL:-info}" | tr '[:upper:]' '[:lower:]')

exec python -m uvicorn src.api.main:app \
    --host ${HFC_API_HOST:-0.0.0.0} \
    --port ${HFC_API_PORT:-8000} \
    --log-level ${LOG_LEVEL}
