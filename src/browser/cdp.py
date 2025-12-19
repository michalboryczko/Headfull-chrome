"""Chrome DevTools Protocol (CDP) client."""

import asyncio
import json
from typing import Any

import httpx
import websockets
from websockets import ClientConnection

from src.utils.logging import get_logger

logger = get_logger(__name__)


class CDPError(Exception):
    """CDP protocol error."""

    pass


class CDPClient:
    """Client for Chrome DevTools Protocol communication."""

    def __init__(self, devtools_port: int) -> None:
        self.devtools_port = devtools_port
        self._ws: ClientConnection | None = None
        self._message_id = 0
        self._pending_responses: dict[int, asyncio.Future[Any]] = {}
        self._receive_task: asyncio.Task[None] | None = None

    @property
    def base_url(self) -> str:
        """Base URL for DevTools HTTP endpoints."""
        return f"http://localhost:{self.devtools_port}"

    async def connect(self, timeout: float = 10.0) -> None:
        """
        Connect to Chrome DevTools page target.

        Args:
            timeout: Connection timeout in seconds
        """
        ws_url = None

        async with httpx.AsyncClient() as client:
            for _attempt in range(int(timeout)):
                try:
                    # Get list of targets (pages)
                    response = await client.get(f"{self.base_url}/json/list")
                    if response.status_code == 200:
                        targets = response.json()
                        # Find a page target
                        for target in targets:
                            if target.get("type") == "page":
                                ws_url = target.get("webSocketDebuggerUrl")
                                if ws_url:
                                    break
                        if ws_url:
                            break

                    # If no page target found, try to create one or wait
                    if not ws_url:
                        # Check if browser endpoint exists at least
                        version_resp = await client.get(f"{self.base_url}/json/version")
                        if version_resp.status_code == 200:
                            logger.debug("Browser connected but no page target yet, waiting...")

                except httpx.ConnectError:
                    pass
                await asyncio.sleep(1)
            else:
                raise CDPError(f"Failed to connect to DevTools page after {timeout}s")

        logger.debug("Connecting to page WebSocket", url=ws_url)

        # Connect to WebSocket
        self._ws = await websockets.connect(ws_url, max_size=100 * 1024 * 1024)

        # Start message receiver
        self._receive_task = asyncio.create_task(self._receive_messages())

        logger.info("CDP connected", port=self.devtools_port)

    async def disconnect(self) -> None:
        """Disconnect from Chrome DevTools."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        logger.debug("CDP disconnected")

    async def _receive_messages(self) -> None:
        """Background task to receive WebSocket messages."""
        if not self._ws:
            return

        try:
            async for message in self._ws:
                data = json.loads(message)

                # Handle response to our command
                if "id" in data:
                    msg_id = data["id"]
                    if msg_id in self._pending_responses:
                        future = self._pending_responses.pop(msg_id)
                        if "error" in data:
                            error_msg = data["error"].get("message", "Unknown error")
                            future.set_exception(CDPError(error_msg))
                        else:
                            future.set_result(data.get("result", {}))

                # Handle events (optional, for future use)
                elif "method" in data:
                    logger.debug("CDP event", method=data["method"])

        except websockets.ConnectionClosed:
            logger.debug("WebSocket connection closed")
        except Exception as e:
            logger.error("Error receiving CDP messages", error=str(e))

    async def send(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """
        Send a CDP command and wait for response.

        Args:
            method: CDP method name (e.g., "Page.navigate")
            params: Method parameters

        Returns:
            Command result
        """
        if not self._ws:
            raise CDPError("Not connected to DevTools")

        self._message_id += 1
        msg_id = self._message_id

        message = {
            "id": msg_id,
            "method": method,
            "params": params or {},
        }

        # Create future for response
        future: asyncio.Future[Any] = asyncio.Future()
        self._pending_responses[msg_id] = future

        # Send message
        await self._ws.send(json.dumps(message))
        logger.debug("CDP command sent", method=method, id=msg_id)

        # Wait for response
        try:
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except TimeoutError as e:
            self._pending_responses.pop(msg_id, None)
            raise CDPError(f"Timeout waiting for response to {method}") from e

    async def navigate(self, url: str) -> dict[str, Any]:
        """
        Navigate to a URL.

        Args:
            url: URL to navigate to

        Returns:
            Navigation result
        """
        logger.info("Navigating to URL", url=url)
        result: dict[str, Any] = await self.send("Page.navigate", {"url": url})
        return result

    async def wait_for_load(self, timeout: float = 30.0) -> None:
        """
        Wait for page to finish loading.

        Args:
            timeout: Maximum wait time in seconds
        """
        # Enable Page events
        await self.send("Page.enable")

        # Wait for load event using simple polling approach
        start_time = asyncio.get_event_loop().time()

        while True:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise CDPError("Timeout waiting for page load")

            try:
                # Check document ready state
                result = await self.send("Runtime.evaluate", {"expression": "document.readyState"})
                state = result.get("result", {}).get("value", "")
                if state == "complete":
                    break
            except CDPError:
                pass

            await asyncio.sleep(0.5)

        logger.debug("Page loaded")

    async def get_content(self) -> str:
        """
        Get page HTML content.

        Returns:
            HTML content of the page
        """
        result = await self.send(
            "Runtime.evaluate", {"expression": "document.documentElement.outerHTML"}
        )
        content: str = result.get("result", {}).get("value", "")
        logger.debug("Got page content", length=len(content))
        return content

    async def get_title(self) -> str:
        """Get page title."""
        result = await self.send("Runtime.evaluate", {"expression": "document.title"})
        title: str = result.get("result", {}).get("value", "")
        return title

    async def screenshot(self, format: str = "png", quality: int = 80) -> bytes:
        """
        Take a screenshot of the page.

        Args:
            format: Image format ("png" or "jpeg")
            quality: JPEG quality (0-100)

        Returns:
            Screenshot as bytes
        """
        import base64

        params: dict[str, Any] = {"format": format}
        if format == "jpeg":
            params["quality"] = quality

        result = await self.send("Page.captureScreenshot", params)
        data = result.get("data", "")
        return base64.b64decode(data)

    async def create_new_target(self, url: str = "about:blank") -> str:
        """
        Create a new browser target (tab).

        Args:
            url: Initial URL for the new tab

        Returns:
            Target ID
        """
        result = await self.send("Target.createTarget", {"url": url})
        target_id: str = result.get("targetId", "")
        logger.debug("Created new target", target_id=target_id)
        return target_id
