"""Session worker that processes jobs within a browser session."""

import asyncio
from datetime import datetime

from src.browser.manager import BrowserSession, browser_manager
from src.jobs.store import job_store, session_store
from src.models import Job, JobResult, JobStatus, Session, SessionStatus
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SessionWorker:
    """Worker that processes all jobs in a browser session."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._browser_session: BrowserSession | None = None

    async def run(self) -> None:
        """
        Process all jobs in the session.

        - Starts a browser session
        - Processes each job sequentially with configured delays
        - Handles errors gracefully
        - Cleans up resources
        """
        logger.info(
            "Starting session worker",
            session_id=self.session.id,
            job_count=len(self.session.pages),
        )

        # Update session status
        self.session.status = SessionStatus.RUNNING
        self.session.started_at = datetime.utcnow()
        await session_store.update(self.session)

        try:
            # Start browser session
            self._browser_session = await browser_manager.create_session(
                session_id=self.session.id,
                config=self.session.config,
            )

            # Process each job
            jobs = job_store.get_by_session(self.session.id)
            jobs.sort(key=lambda j: j.queued_at)  # Process in order

            for i, job in enumerate(jobs):
                await self._process_job(job)

                # Apply delay between requests (except after last job)
                if i < len(jobs) - 1 and self.session.config.delay_between_requests > 0:
                    delay = self.session.config.delay_between_requests
                    logger.debug("Applying delay between jobs", delay=delay)
                    await asyncio.sleep(delay)

            # Mark session as completed
            self.session.status = SessionStatus.COMPLETED
            self.session.completed_at = datetime.utcnow()
            await session_store.update(self.session)

            logger.info("Session completed", session_id=self.session.id)

        except Exception as e:
            logger.error(
                "Session failed",
                session_id=self.session.id,
                error=str(e),
            )
            self.session.status = SessionStatus.FAILED
            self.session.completed_at = datetime.utcnow()
            await session_store.update(self.session)

            # Mark remaining jobs as failed
            for job in job_store.get_by_session(self.session.id):
                if job.status in (JobStatus.QUEUED, JobStatus.IN_PROGRESS):
                    job.mark_failed(f"Session failed: {str(e)}")
                    await job_store.update(job)

        finally:
            # Cleanup browser session
            if self._browser_session:
                await browser_manager.close_session(self.session.id)
                self._browser_session = None

    async def _process_job(self, job: Job) -> None:
        """Process a single job."""
        logger.info(
            "Processing job",
            job_id=job.id,
            url=job.url,
        )

        # Mark job as started
        job.mark_started()
        await job_store.update(job)

        try:
            if not self._browser_session:
                raise RuntimeError("Browser session not available")

            # Navigate and get content
            content = await self._browser_session.navigate_and_get_content(
                url=job.url,
                delay=self.session.config.delay_between_requests,
            )

            # Mark job as completed
            result = JobResult(
                url=job.url,
                content=content,
                metadata={
                    "content_length": len(content),
                },
            )
            job.mark_completed(result)
            await job_store.update(job)

            logger.info(
                "Job completed",
                job_id=job.id,
                execution_time_ms=job.execution_time_ms,
                content_length=len(content),
            )

        except Exception as e:
            logger.error(
                "Job failed",
                job_id=job.id,
                error=str(e),
            )
            job.mark_failed(str(e))
            await job_store.update(job)
