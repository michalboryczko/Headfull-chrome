"""Resource pool for managing DevTools ports."""

import asyncio

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ResourcePool:
    """Thread-safe pool for managing limited resources (ports, etc.)."""

    def __init__(self, name: str, start: int, count: int) -> None:
        """
        Initialize a resource pool.

        Args:
            name: Name for logging purposes
            start: Starting value (e.g., port 9222)
            count: Number of resources in the pool
        """
        self.name = name
        self._available: set[int] = set(range(start, start + count))
        self._in_use: set[int] = set()
        self._lock = asyncio.Lock()
        logger.info(
            f"Initialized {name} pool",
            start=start,
            count=count,
            available=list(self._available),
        )

    async def acquire(self) -> int | None:
        """
        Acquire a resource from the pool.

        Returns:
            The resource value, or None if pool is exhausted.
        """
        async with self._lock:
            if not self._available:
                logger.warning(f"{self.name} pool exhausted")
                return None

            resource = self._available.pop()
            self._in_use.add(resource)
            logger.debug(f"Acquired {self.name}", value=resource)
            return resource

    async def release(self, resource: int) -> None:
        """
        Release a resource back to the pool.

        Args:
            resource: The resource value to release.
        """
        async with self._lock:
            if resource in self._in_use:
                self._in_use.remove(resource)
                self._available.add(resource)
                logger.debug(f"Released {self.name}", value=resource)
            else:
                logger.warning(f"Attempted to release unknown {self.name}", value=resource)

    @property
    def available_count(self) -> int:
        """Number of available resources."""
        return len(self._available)

    @property
    def in_use_count(self) -> int:
        """Number of resources currently in use."""
        return len(self._in_use)


# Global port pool for DevTools
port_pool = ResourcePool(
    name="devtools_port",
    start=settings.devtools_port_base,
    count=settings.max_concurrent_sessions,
)
