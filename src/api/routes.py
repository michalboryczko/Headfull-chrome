"""API route definitions."""

from fastapi import APIRouter, HTTPException, status

from src.models import ContentRequest, ContentResponse, JobResponse
from src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/contents",
    response_model=list[ContentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create content fetch sessions",
    description="Queue content fetching from URLs. Each request creates a browser session.",
)
async def create_contents(requests: list[ContentRequest]) -> list[ContentResponse]:
    """
    Create browser sessions and queue jobs to fetch content from URLs.

    Each item in the request list creates a separate browser session with its own
    configuration (proxy, delays, etc.). Each URL in the pages list becomes a
    separate job that can be tracked individually.
    """
    from src.jobs.queue import job_queue

    responses = []

    for request in requests:
        logger.info(
            "Creating content session",
            pages_count=len(request.pages),
            proxy=request.config.proxy_server,
        )

        try:
            session = await job_queue.create_session(
                pages=request.pages,
                config=request.config,
            )

            responses.append(
                ContentResponse(
                    id=session.id,
                    status=session.status,
                    pages=session.pages,
                )
            )
        except Exception as e:
            logger.error("Failed to create session", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create session: {str(e)}",
            ) from e

    return responses


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    summary="Get job status and result",
    description="Retrieve the status and result of a specific job.",
)
async def get_job(job_id: str) -> JobResponse:
    """
    Get the status and result of a specific job.

    Returns the job's current status, timing information, and result (if completed).
    """
    from src.jobs.store import job_store

    job = job_store.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    return JobResponse(
        id=job.id,
        status=job.status,
        execution_time_ms=job.execution_time_ms,
        queued_at=job.queued_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        result=job.result,
    )
