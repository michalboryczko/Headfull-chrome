"""Job queue and session orchestration."""

import asyncio
import uuid
from datetime import datetime

from src.config import settings
from src.jobs.store import job_store, session_store
from src.jobs.worker import SessionWorker
from src.models import Job, JobStatus, PageJob, Session, SessionConfig, SessionStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)


class JobQueue:
    """
    Manages session creation and job processing.

    Sessions are processed in parallel (up to max_concurrent_sessions).
    Jobs within a session are processed sequentially.
    """

    def __init__(self) -> None:
        self._running = False
        self._session_queue: asyncio.Queue[Session] = asyncio.Queue()
        self._active_workers: dict[str, asyncio.Task[None]] = {}
        self._processor_task: asyncio.Task[None] | None = None
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_sessions)

    async def start(self) -> None:
        """Start the job queue processor."""
        if self._running:
            return

        self._running = True
        self._processor_task = asyncio.create_task(self._process_sessions())
        logger.info(
            "Job queue started",
            max_concurrent=settings.max_concurrent_sessions,
        )

    async def stop(self) -> None:
        """Stop the job queue processor."""
        self._running = False

        # Cancel processor task
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None

        # Wait for active workers to complete
        if self._active_workers:
            logger.info("Waiting for active workers to complete...")
            await asyncio.gather(*self._active_workers.values(), return_exceptions=True)
            self._active_workers.clear()

        logger.info("Job queue stopped")

    async def create_session(
        self,
        pages: list[str],
        config: SessionConfig,
    ) -> Session:
        """
        Create a new session with jobs for each page.

        Args:
            pages: List of URLs to fetch
            config: Session configuration

        Returns:
            Created Session with job IDs
        """
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # Create jobs for each page
        page_jobs: list[PageJob] = []
        for url in pages:
            job_id = str(uuid.uuid4())

            job = Job(
                id=job_id,
                session_id=session_id,
                url=url,
                status=JobStatus.QUEUED,
                queued_at=now,
            )
            await job_store.add(job)

            page_jobs.append(PageJob(url=url, id=job_id))

        # Create session
        session = Session(
            id=session_id,
            status=SessionStatus.CREATED,
            config=config,
            pages=page_jobs,
            created_at=now,
        )
        await session_store.add(session)

        # Queue session for processing
        await self._session_queue.put(session)

        logger.info(
            "Session created",
            session_id=session_id,
            pages_count=len(pages),
            proxy=config.proxy_server,
        )

        return session

    async def _process_sessions(self) -> None:
        """Background task that processes queued sessions."""
        while self._running:
            try:
                # Get next session (with timeout to check _running flag)
                try:
                    session = await asyncio.wait_for(
                        self._session_queue.get(),
                        timeout=1.0,
                    )
                except TimeoutError:
                    continue

                # Acquire semaphore slot (limits concurrency)
                await self._semaphore.acquire()

                # Start worker for this session
                worker = SessionWorker(session)
                task = asyncio.create_task(self._run_worker_with_cleanup(session.id, worker))
                self._active_workers[session.id] = task

                logger.debug(
                    "Session worker started",
                    session_id=session.id,
                    active_workers=len(self._active_workers),
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error processing session", error=str(e))

    async def _run_worker_with_cleanup(
        self,
        session_id: str,
        worker: SessionWorker,
    ) -> None:
        """Run a worker and clean up when done."""
        try:
            await worker.run()
        except Exception as e:
            logger.error("Worker error", session_id=session_id, error=str(e))
        finally:
            # Release semaphore slot
            self._semaphore.release()

            # Remove from active workers
            self._active_workers.pop(session_id, None)

            logger.debug(
                "Session worker finished",
                session_id=session_id,
                active_workers=len(self._active_workers),
            )

    def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        return job_store.get(job_id)

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        return session_store.get(session_id)

    @property
    def pending_sessions(self) -> int:
        """Number of sessions waiting to be processed."""
        return self._session_queue.qsize()

    @property
    def active_sessions(self) -> int:
        """Number of sessions currently being processed."""
        return len(self._active_workers)


# Global job queue instance
job_queue = JobQueue()
