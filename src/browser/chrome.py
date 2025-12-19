"""Chrome process management."""

import asyncio
import os
import shutil
import tempfile
from dataclasses import dataclass

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChromeProcess:
    """Represents a running Chrome process."""

    pid: int
    display_num: int
    devtools_port: int
    user_data_dir: str
    ws_url: str | None = None


class ChromeLauncher:
    """Manages Chrome process lifecycle."""

    def __init__(self) -> None:
        self._processes: dict[str, ChromeProcess] = {}

    def _build_chrome_args(
        self,
        display_num: int,
        devtools_port: int,
        user_data_dir: str,
        proxy_server: str | None = None,
    ) -> list[str]:
        """Build Chrome command line arguments."""
        args = [
            settings.chrome_binary,
            f"--remote-debugging-port={devtools_port}",
            f"--user-data-dir={user_data_dir}",
            # Window settings
            f"--window-size={settings.display_width},{settings.display_height}",
            "--start-maximized",
            # Disable features that interfere with automation
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-client-side-phishing-detection",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-hang-monitor",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--disable-sync",
            "--disable-translate",
            "--metrics-recording-only",
            "--safebrowsing-disable-auto-update",
            # Performance
            "--disable-dev-shm-usage",
            "--disable-gpu",
            # Don't run headless - we want real rendering
            "--disable-software-rasterizer",
            # Accept language
            "--lang=en-US",
        ]

        if proxy_server:
            args.append(f"--proxy-server={proxy_server}")
            logger.info("Chrome configured with proxy", proxy=proxy_server)

        return args

    async def launch(
        self,
        session_id: str,
        display_num: int,
        devtools_port: int,
        proxy_server: str | None = None,
    ) -> ChromeProcess:
        """
        Launch a new Chrome process.

        Args:
            session_id: Unique session identifier
            display_num: X display number to use
            devtools_port: Port for DevTools protocol
            proxy_server: Optional proxy server URL

        Returns:
            ChromeProcess instance with process details
        """
        # Create temporary user data directory
        user_data_dir = tempfile.mkdtemp(
            prefix=f"chrome_{session_id}_",
            dir=settings.chrome_user_data_base,
        )

        args = self._build_chrome_args(
            display_num=display_num,
            devtools_port=devtools_port,
            user_data_dir=user_data_dir,
            proxy_server=proxy_server,
        )

        # Set DISPLAY environment variable
        env = os.environ.copy()
        env["DISPLAY"] = f":{display_num}"

        logger.info(
            "Launching Chrome",
            session_id=session_id,
            display=display_num,
            devtools_port=devtools_port,
            user_data_dir=user_data_dir,
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                env=env,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait a bit for Chrome to start and open the DevTools port
            await asyncio.sleep(2)

            # Check if process is still running
            if process.returncode is not None:
                stderr = await process.stderr.read() if process.stderr else b""
                raise RuntimeError(
                    f"Chrome failed to start: exit code {process.returncode}, "
                    f"stderr: {stderr.decode()}"
                )

            chrome_process = ChromeProcess(
                pid=process.pid,
                display_num=display_num,
                devtools_port=devtools_port,
                user_data_dir=user_data_dir,
            )

            self._processes[session_id] = chrome_process

            logger.info(
                "Chrome launched successfully",
                session_id=session_id,
                pid=process.pid,
            )

            return chrome_process

        except Exception as e:
            # Cleanup on failure
            shutil.rmtree(user_data_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to launch Chrome: {e}") from e

    async def terminate(self, session_id: str) -> None:
        """
        Terminate a Chrome process.

        Args:
            session_id: Session identifier
        """
        chrome_process = self._processes.pop(session_id, None)

        if chrome_process is None:
            logger.warning("No Chrome process found for session", session_id=session_id)
            return

        logger.info(
            "Terminating Chrome",
            session_id=session_id,
            pid=chrome_process.pid,
        )

        try:
            # Send SIGTERM
            os.kill(chrome_process.pid, 15)

            # Wait a bit for graceful shutdown
            await asyncio.sleep(1)

            # Check if still running and force kill if necessary
            try:
                os.kill(chrome_process.pid, 0)  # Check if process exists
                os.kill(chrome_process.pid, 9)  # Force kill
                logger.warning("Chrome required force kill", pid=chrome_process.pid)
            except ProcessLookupError:
                pass  # Already terminated

        except ProcessLookupError:
            logger.debug("Chrome process already terminated", pid=chrome_process.pid)
        except Exception as e:
            logger.error("Error terminating Chrome", error=str(e))
        finally:
            # Cleanup user data directory
            shutil.rmtree(chrome_process.user_data_dir, ignore_errors=True)
            logger.debug("Cleaned up user data dir", path=chrome_process.user_data_dir)

    async def terminate_all(self) -> None:
        """Terminate all running Chrome processes."""
        session_ids = list(self._processes.keys())
        for session_id in session_ids:
            await self.terminate(session_id)

    def get_process(self, session_id: str) -> ChromeProcess | None:
        """Get Chrome process for a session."""
        return self._processes.get(session_id)


# Global Chrome launcher instance
chrome_launcher = ChromeLauncher()
