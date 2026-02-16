"""Standalone ADB MCP server for Azur Lane automation.

Provides screenshot, tap, and swipe tools using adbutils directly.
No dependency on ALAS internals.

Usage:
    python server.py --serial 127.0.0.1:21503
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
import adbutils
from fastmcp import FastMCP
from fastmcp.utilities.types import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP("azurlane-agent", version="0.1.0")


# ---------------------------------------------------------------------------
# Device connection holder
# ---------------------------------------------------------------------------

class DeviceConnection:
    """Holds a reusable ADB device connection.

    Connects once at startup; all tool calls reuse the same handle.
    """

    def __init__(self, serial: str = "127.0.0.1:21503"):
        self.serial = serial
        self._device: adbutils.AdbDevice | None = None

    def connect(self) -> adbutils.AdbDevice:
        """Connect to the ADB device and return the handle.

        Raises:
            RuntimeError: If the device cannot be reached.
        """
        client = adbutils.AdbClient()
        try:
            client.connect(self.serial, timeout=5.0)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to connect to ADB device at {self.serial}: {exc}"
            ) from exc

        self._device = client.device(serial=self.serial)
        # Verify the connection is alive
        try:
            self._device.get_state()
        except Exception as exc:
            self._device = None
            raise RuntimeError(
                f"ADB device {self.serial} is not responding: {exc}"
            ) from exc

        logger.info("Connected to ADB device %s", self.serial)
        return self._device

    @property
    def device(self) -> adbutils.AdbDevice:
        """Return the cached device handle, raising if not connected."""
        if self._device is None:
            raise RuntimeError(
                "ADB device not connected. Call connect() first."
            )
        return self._device


# Module-level connection, initialised in main().
conn = DeviceConnection()


# ---------------------------------------------------------------------------
# Tool implementations (plain functions, easily testable)
# ---------------------------------------------------------------------------

def adb_screenshot() -> Image:
    """Take a screenshot from the connected Android device.

    Returns the screenshot as a FastMCP Image (PNG) that MCP clients can
    display directly.
    """
    device = conn.device
    pil_image = device.screenshot()

    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    return Image(data=png_bytes, format="png")


def adb_tap(x: int, y: int) -> str:
    """Tap a coordinate on the Android device.

    Uses ``adb shell input tap``.

    Args:
        x: X coordinate (pixels).
        y: Y coordinate (pixels).
    """
    device = conn.device
    device.click(x, y)
    return f"tapped {x},{y}"


def adb_swipe(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    duration_ms: int = 300,
) -> str:
    """Swipe between two coordinates on the Android device.

    Uses ``adb shell input swipe``.

    Args:
        x1: Starting X coordinate.
        y1: Starting Y coordinate.
        x2: Ending X coordinate.
        y2: Ending Y coordinate.
        duration_ms: Duration of the swipe in milliseconds (default 300).
    """
    device = conn.device
    # adbutils swipe() expects duration in seconds (float).
    device.swipe(x1, y1, x2, y2, duration=duration_ms / 1000.0)
    return f"swiped {x1},{y1}->{x2},{y2}"


# ---------------------------------------------------------------------------
# Register tools with the MCP server
# ---------------------------------------------------------------------------

mcp.tool(adb_screenshot)
mcp.tool(adb_tap)
mcp.tool(adb_swipe)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Standalone ADB MCP server for Azur Lane automation."
    )
    parser.add_argument(
        "--serial",
        default="127.0.0.1:21503",
        help="ADB device serial (default: 127.0.0.1:21503)",
    )
    args = parser.parse_args()

    # Configure logging to stderr so it doesn't corrupt MCP stdio transport.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    # Initialise the global connection.
    conn.serial = args.serial
    conn.connect()

    # Run MCP server on stdio.
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
