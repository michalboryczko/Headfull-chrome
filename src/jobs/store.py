"""In-memory job and session storage."""

import asyncio
from collections.abc import Iterator

from src.models import Job, Session, SessionStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)


class JobStore:
    """Thread-safe in-memory store for jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def add(self, job: Job) -> None:
        """Add a job to the store."""
        async with self._lock:
            self._jobs[job.id] = job
            logger.debug("Job added to store", job_id=job.id)

    def get(self, job_id: str) -> Job | None:
        """Get a job by ID (no lock needed for read)."""
        return self._jobs.get(job_id)

    async def update(self, job: Job) -> None:
        """Update an existing job."""
        async with self._lock:
            if job.id in self._jobs:
                self._jobs[job.id] = job
                logger.debug("Job updated", job_id=job.id, status=job.status)

    def get_by_session(self, session_id: str) -> list[Job]:
        """Get all jobs for a session."""
        return [job for job in self._jobs.values() if job.session_id == session_id]

    def get_all(self) -> list[Job]:
        """Get all jobs."""
        return list(self._jobs.values())

    @property
    def count(self) -> int:
        """Total number of jobs."""
        return len(self._jobs)


class SessionStore:
    """Thread-safe in-memory store for sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def add(self, session: Session) -> None:
        """Add a session to the store."""
        async with self._lock:
            self._sessions[session.id] = session
            logger.debug("Session added to store", session_id=session.id)

    def get(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    async def update(self, session: Session) -> None:
        """Update an existing session."""
        async with self._lock:
            if session.id in self._sessions:
                self._sessions[session.id] = session
                logger.debug("Session updated", session_id=session.id, status=session.status)

    async def remove(self, session_id: str) -> Session | None:
        """Remove a session from the store."""
        async with self._lock:
            return self._sessions.pop(session_id, None)

    def get_all(self) -> list[Session]:
        """Get all sessions."""
        return list(self._sessions.values())

    def get_pending(self) -> Iterator[Session]:
        """Get sessions waiting to be processed."""
        for session in self._sessions.values():
            if session.status == SessionStatus.CREATED:
                yield session

    @property
    def count(self) -> int:
        """Total number of sessions."""
        return len(self._sessions)


# Global store instances
job_store = JobStore()
session_store = SessionStore()
