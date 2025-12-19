"""Browser session manager."""

import asyncio
import os
from pathlib import Path

from src.browser.cdp import CDPClient
from src.browser.chrome import ChromeProcess, chrome_launcher
from src.browser.resource_pool import port_pool
from src.config import settings
from src.models import SessionConfig
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BrowserSession:
    """Manages a single browser session with CDP connection."""

    def __init__(
        self,
        session_id: str,
        config: SessionConfig,
    ) -> None:
        self.session_id = session_id
        self.config = config
        self.chrome_process: ChromeProcess | None = None
        self.cdp_client: CDPClient | None = None
        self._devtools_port: int | None = None

    async def start(self) -> None:
        """Start the browser session."""
        # Get the display from environment (set by entrypoint)
        display = os.environ.get("DISPLAY", ":99")
        display_num = int(display.lstrip(":"))

        # Acquire DevTools port
        self._devtools_port = await port_pool.acquire()
        if self._devtools_port is None:
            raise RuntimeError("No DevTools port available")

        try:
            # Launch Chrome
            self.chrome_process = await chrome_launcher.launch(
                session_id=self.session_id,
                display_num=display_num,
                devtools_port=self._devtools_port,
                proxy_server=self.config.proxy_server,
            )

            # Connect CDP client
            self.cdp_client = CDPClient(self._devtools_port)
            await self.cdp_client.connect()

            logger.info(
                "Browser session started",
                session_id=self.session_id,
                display=display_num,
                port=self._devtools_port,
            )

        except Exception as e:
            await self.stop()
            raise RuntimeError(f"Failed to start browser session: {e}") from e

    async def stop(self) -> None:
        """Stop the browser session and release resources."""
        logger.info("Stopping browser session", session_id=self.session_id)

        # Disconnect CDP
        if self.cdp_client:
            try:
                await self.cdp_client.disconnect()
            except Exception as e:
                logger.error("Error disconnecting CDP", error=str(e))
            self.cdp_client = None

        # Terminate Chrome
        await chrome_launcher.terminate(self.session_id)
        self.chrome_process = None

        # Release port
        if self._devtools_port is not None:
            await port_pool.release(self._devtools_port)
            self._devtools_port = None

        logger.info("Browser session stopped", session_id=self.session_id)

    async def navigate_and_get_content(self, url: str, delay: int = 0) -> str:
        """
        Navigate to URL and get page content.

        Args:
            url: URL to navigate to
            delay: Delay in seconds after navigation before getting content

        Returns:
            HTML content of the page
        """
        if not self.cdp_client:
            raise RuntimeError("CDP client not connected")

        # Navigate
        await self.cdp_client.navigate(url)

        # Wait for page to load
        await self.cdp_client.wait_for_load()

        # Apply delay if configured
        if delay > 0:
            logger.debug("Waiting after page load", delay=delay)
            await asyncio.sleep(delay)

        # Get content
        content = await self.cdp_client.get_content()
        return content


class BrowserManager:
    """Manages all browser sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the browser manager."""
        # Ensure chrome profile base directory exists
        profile_dir = Path(settings.chrome_user_data_base)
        profile_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Browser manager initialized",
            max_sessions=settings.max_concurrent_sessions,
        )

    async def create_session(
        self,
        session_id: str,
        config: SessionConfig,
    ) -> BrowserSession:
        """
        Create and start a new browser session.

        Args:
            session_id: Unique session identifier
            config: Session configuration

        Returns:
            Started BrowserSession instance
        """
        async with self._lock:
            if session_id in self._sessions:
                raise ValueError(f"Session already exists: {session_id}")

            session = BrowserSession(session_id, config)
            await session.start()
            self._sessions[session_id] = session
            return session

    async def get_session(self, session_id: str) -> BrowserSession | None:
        """Get an existing browser session."""
        return self._sessions.get(session_id)

    async def close_session(self, session_id: str) -> None:
        """Close and remove a browser session."""
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                await session.stop()

    async def cleanup(self) -> None:
        """Cleanup all sessions."""
        logger.info("Cleaning up all browser sessions")
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            await self.close_session(session_id)

    @property
    def active_session_count(self) -> int:
        """Number of active browser sessions."""
        return len(self._sessions)


# Global browser manager instance
browser_manager = BrowserManager()
