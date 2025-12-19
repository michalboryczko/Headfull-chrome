"""Browser management module."""

from src.browser.cdp import CDPClient, CDPError
from src.browser.chrome import ChromeLauncher, ChromeProcess, chrome_launcher
from src.browser.manager import BrowserManager, BrowserSession, browser_manager
from src.browser.resource_pool import ResourcePool, port_pool

__all__ = [
    "CDPClient",
    "CDPError",
    "ChromeLauncher",
    "ChromeProcess",
    "chrome_launcher",
    "BrowserManager",
    "BrowserSession",
    "browser_manager",
    "ResourcePool",
    "port_pool",
]
