# Headfull Chrome

[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://www.docker.com/)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A **cloud-native**, **containerized** browser automation API that runs Chrome with a real virtual display (Xvfb) for reliable web content fetching. Built for **scalability** and **stealth**.

## Why Headfull Chrome?

| Feature | Headfull Chrome | Headless Chrome | Playwright/Puppeteer |
|---------|----------------|-----------------|---------------------|
| Real display rendering | Yes | No | No |
| Anti-bot detection resistance | High | Low | Low |
| No automation JS artifacts | Yes | No | No |
| Container-ready | Yes | Yes | Partial |
| REST API out of the box | Yes | No | No |

### Key Benefits

- **Stealth-First Design** — Uses vanilla Chrome with Xvfb virtual display. No injected JavaScript, no `navigator.webdriver` flags, no Playwright/Puppeteer automation artifacts that anti-bot systems detect.
- **Production-Ready** — Dockerized microservice architecture with async job queue, health checks, and structured logging.
- **Horizontally Scalable** — Run multiple concurrent browser sessions with resource pooling and automatic cleanup.
- **Developer-Friendly** — Simple REST API + Python SDK with sync/async support. Zero browser automation knowledge required.
- **Proxy Support** — Per-session proxy configuration for IP rotation and geo-targeting.

## Current Limitations

> This project is in **early development**. Contributions welcome!

- **REST API only** — No WebSocket support, no real-time streaming
- **Basic functionality** — Fetches page HTML content only; no screenshots, PDF export, or custom JavaScript execution
- **No cookie/session persistence** — Each browser session starts fresh
- **Single-node only** — No distributed queue (Redis/RabbitMQ) for multi-node scaling
- **No authentication** — API is open; add your own auth layer in production

## Quick Start

### Prerequisites

- Docker and Docker Compose
- 4GB+ RAM recommended

### Running

```bash
# Build and start the container
docker-compose up --build

# The API is available at http://localhost:8000
```

### Using the Python SDK (Recommended)

```bash
# Install SDK
cd sdk && pip install -e .
```

```python
from headfull_chrome import HeadfullChrome

with HeadfullChrome() as client:
    result = client.fetch_content("https://example.com")
    print(result.content)
```

### Using cURL

```bash
# Fetch content from URLs
curl -X POST http://localhost:8000/contents \
  -H "Content-Type: application/json" \
  -d '[{
    "pages": ["https://example.com", "https://example.org"],
    "config": {
      "delay_between_requests": 2
    }
  }]'

# Check job status
curl http://localhost:8000/jobs/{job_id}
```

## API Reference

### `POST /contents`

Create browser sessions and queue content fetching jobs.

**Request Body:**
```json
[
  {
    "pages": ["https://example.com", "https://example.org"],
    "config": {
      "delay_between_requests": 5,
      "proxy_server": "http://proxy.example.com:8080"
    }
  }
]
```

**Response:**
```json
[
  {
    "id": "session-uuid",
    "status": "created",
    "pages": [
      {"url": "https://example.com", "id": "job-uuid-1"},
      {"url": "https://example.org", "id": "job-uuid-2"}
    ]
  }
]
```

### `GET /jobs/{job_id}`

Get the status and result of a specific job.

**Response:**
```json
{
  "id": "job-uuid",
  "status": "completed",
  "execution_time_ms": 1234,
  "queued_at": "2024-01-01T12:00:00Z",
  "started_at": "2024-01-01T12:00:01Z",
  "completed_at": "2024-01-01T12:00:03Z",
  "result": {
    "url": "https://example.com",
    "content": "<html>...</html>"
  }
}
```

**Job Statuses:**
- `queued` - Job is waiting to be processed
- `in_progress` - Job is currently being processed
- `completed` - Job finished successfully
- `failed` - Job failed (check `result.error`)

### `GET /health`

Health check endpoint for container orchestration and load balancers.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Container                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    FastAPI Application                   ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ ││
│  │  │  API Routes │  │  Job Queue  │  │ Browser Manager │ ││
│  │  └─────────────┘  └─────────────┘  └─────────────────┘ ││
│  └─────────────────────────────────────────────────────────┘│
│                              │                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    Xvfb (Virtual Display)                ││
│  │            :99 → 1920x1080x24                            ││
│  └─────────────────────────────────────────────────────────┘│
│                              │                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │ Chrome 1 │  │ Chrome 2 │  │ Chrome N │  (per session)   │
│  │ Port 9222│  │ Port 9223│  │ Port 922N│                   │
│  └──────────┘  └──────────┘  └──────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

1. **FastAPI Application** — High-performance async REST API server
2. **Job Queue** — In-memory async queue for session and job processing
3. **Browser Manager** — Controls Chrome processes via Chrome DevTools Protocol (CDP)
4. **Resource Pools** — Allocates display numbers and DevTools ports with automatic cleanup

### Session Processing

1. Each request item creates a separate browser session
2. Sessions run in parallel (limited by `max_concurrent_sessions`)
3. Jobs within a session run sequentially with configured delays
4. Each session has its own Chrome process and optional proxy

## Configuration

Environment variables (prefix: `HFC_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `HFC_API_PORT` | 8000 | API server port |
| `HFC_LOG_LEVEL` | INFO | Log level (DEBUG, INFO, WARNING, ERROR) |
| `HFC_MAX_CONCURRENT_SESSIONS` | 5 | Max parallel browser sessions |
| `HFC_DISPLAY_WIDTH` | 1920 | Virtual display width |
| `HFC_DISPLAY_HEIGHT` | 1080 | Virtual display height |
| `HFC_JOB_TIMEOUT_SECONDS` | 60 | Job timeout |
| `HFC_DEFAULT_DELAY_BETWEEN_REQUESTS` | 0 | Default delay between pages |

## Development

```bash
# Run with hot reload (development)
docker-compose --profile dev up headfull-chrome-dev

# View logs
docker-compose logs -f headfull-chrome

# Run tests (locally)
pip install -e ".[dev]"
pytest
```

## Troubleshooting

### Chrome fails to start

Ensure the container has sufficient shared memory:
```yaml
shm_size: "2gb"
```

### Jobs timing out

Increase timeouts in environment:
```bash
HFC_JOB_TIMEOUT_SECONDS=120
HFC_CONTENT_FETCH_TIMEOUT_SECONDS=60
```

### Out of memory

Reduce concurrent sessions:
```bash
HFC_MAX_CONCURRENT_SESSIONS=3
```

## Python SDK

A Python SDK is included for easier integration. See [sdk/README.md](sdk/README.md) for full documentation.

**Quick example:**
```python
from headfull_chrome import HeadfullChrome, SessionConfig

with HeadfullChrome() as client:
    # Fetch single page
    result = client.fetch_content("https://example.com")

    # Fetch multiple pages with delays
    results = client.fetch_contents(
        urls=["https://example.com", "https://example.org"],
        config=SessionConfig(delay_between_requests=2),
    )

    # Fetch in parallel (separate browser sessions)
    results = client.fetch_parallel(["https://site1.com", "https://site2.com"])
```

**Async support:**
```python
from headfull_chrome import AsyncHeadfullChrome

async with AsyncHeadfullChrome() as client:
    result = await client.fetch_content("https://example.com")
```

## Roadmap

- [ ] Screenshot and PDF capture
- [ ] Custom JavaScript execution
- [ ] Cookie/session persistence
- [ ] WebSocket support for real-time updates
- [ ] Redis/RabbitMQ queue backend for distributed scaling

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT