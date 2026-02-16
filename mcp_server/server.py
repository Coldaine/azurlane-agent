"""Standalone ADB MCP server for Azur Lane automation.

This module provides an MCP (Model Context Protocol) server that exposes
three ADB-based tools for interacting with an Android device:

    adb_screenshot  -- Capture the device screen as a PNG image.
    adb_tap         -- Tap a pixel coordinate on the device.
    adb_swipe       -- Swipe between two pixel coordinates.

The server uses ``adbutils`` for ADB communication and ``fastmcp`` for the
MCP transport layer.  It has **no dependency on ALAS internals** -- it talks
directly to the ADB daemon and is intended to be the foundation of the
standalone azurlane-agent toolchain.

Running the server
------------------
::

    python -m mcp_server.server --serial 127.0.0.1:21503

Or from the repo root::

    python mcp_server/server.py --serial 127.0.0.1:21503

The ``--serial`` flag defaults to ``127.0.0.1:21503`` (MEmu default).  The
server communicates over **stdio** so it can be plugged directly into any
MCP-aware client (e.g. Claude Code, an LLM agent, or test harnesses).

Prerequisites
-------------
* An ADB daemon must be running and reachable (``adb start-server``).
* The target Android device / emulator must be booted and ADB-connectable.
* Python packages: ``fastmcp>=2.0``, ``adbutils>=2.0``, ``Pillow>=10.0``.

Tool details
------------
``adb_screenshot``
    Returns a ``fastmcp.utilities.types.Image`` wrapping raw PNG bytes.
    The MCP client receives this as base64-encoded image content.  The
    screenshot is captured via ``adb exec-out screencap`` under the hood.
    Passes ``error_ok=False`` to adbutils so a failed capture raises
    immediately rather than returning a silent black image.

``adb_tap(x, y)``
    Sends ``adb shell input tap <x> <y>``.  Coordinates are validated to
    be non-negative integers.

``adb_swipe(x1, y1, x2, y2, duration_ms=300)``
    Sends ``adb shell input swipe <x1> <y1> <x2> <y2> <ms>``.  Duration
    is converted from milliseconds (caller-friendly) to seconds (what
    ``adbutils.AdbDevice.swipe`` expects).  Coordinates must be
    non-negative; duration must be positive.
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
# Constants
# ---------------------------------------------------------------------------

#: Maximum reasonable coordinate value.  Android devices top out around 4K
#: (3840x2160).  Anything beyond this is almost certainly a caller mistake.
_MAX_COORD = 10_000

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

    Thread-safety note: this object is **not** thread-safe.  The current
    server runs on stdio (single-client), so concurrent access is not an
    issue.  If the transport is changed to SSE or HTTP (multi-client),
    add a lock around ``self._device`` access.
    """

    def __init__(self, serial: str = "127.0.0.1:21503"):
        self.serial = serial
        self._device: adbutils.AdbDevice | None = None

    def connect(self) -> adbutils.AdbDevice:
        """Connect to the ADB device and return the handle.

        Raises:
            RuntimeError: If the ADB server is unreachable, the device
                cannot be connected, or the device does not respond.
        """
        client = adbutils.AdbClient()
        try:
            response = client.connect(self.serial, timeout=5.0)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to connect to ADB device at {self.serial}: {exc}"
            ) from exc

        # adbutils.AdbClient.connect() returns a status string rather than
        # raising on soft failures.  Check for known failure prefixes.
        if response and ("unable to connect" in response
                         or "failed to connect" in response
                         or "cannot connect" in response):
            raise RuntimeError(
                f"ADB connect to {self.serial} failed: {response}"
            )

        self._device = client.device(serial=self.serial)
        # Verify the connection is alive by querying device state.
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
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_coordinate(name: str, value: int) -> None:
    """Raise ``ValueError`` if *value* is not a valid pixel coordinate."""
    if value < 0:
        raise ValueError(
            f"Coordinate {name}={value} is negative; "
            "pixel coordinates must be >= 0"
        )
    if value > _MAX_COORD:
        raise ValueError(
            f"Coordinate {name}={value} exceeds maximum ({_MAX_COORD}); "
            "this is almost certainly a mistake"
        )


# ---------------------------------------------------------------------------
# Tool implementations (plain functions, easily testable)
# ---------------------------------------------------------------------------

def adb_screenshot() -> Image:
    """Take a screenshot from the connected Android device.

    Returns the screenshot as a FastMCP Image (PNG) that MCP clients can
    display directly.

    Raises:
        RuntimeError: If the device is not connected.
        adbutils.AdbError: If the screenshot capture fails on the device.
    """
    device = conn.device
    # Pass error_ok=False so adbutils raises on capture failure instead
    # of silently returning a black image.
    pil_image = device.screenshot(error_ok=False)

    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    return Image(data=png_bytes, format="png")


def adb_tap(x: int, y: int) -> str:
    """Tap a coordinate on the Android device.

    Uses ``adb shell input tap``.

    Args:
        x: X coordinate (pixels, non-negative).
        y: Y coordinate (pixels, non-negative).

    Returns:
        Confirmation string, e.g. ``"tapped 100,200"``.

    Raises:
        ValueError: If coordinates are negative or unreasonably large.
        RuntimeError: If the device is not connected.
    """
    _validate_coordinate("x", x)
    _validate_coordinate("y", y)

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
        x1: Starting X coordinate (non-negative).
        y1: Starting Y coordinate (non-negative).
        x2: Ending X coordinate (non-negative).
        y2: Ending Y coordinate (non-negative).
        duration_ms: Duration of the swipe in milliseconds (default 300).
            Must be positive.

    Returns:
        Confirmation string, e.g. ``"swiped 10,20->30,40 (300ms)"``.

    Raises:
        ValueError: If coordinates are invalid or duration is non-positive.
        RuntimeError: If the device is not connected.
    """
    for name, val in [("x1", x1), ("y1", y1), ("x2", x2), ("y2", y2)]:
        _validate_coordinate(name, val)

    if duration_ms <= 0:
        raise ValueError(
            f"duration_ms={duration_ms} must be positive"
        )

    device = conn.device
    # adbutils swipe() expects duration in seconds (float).
    device.swipe(x1, y1, x2, y2, duration=duration_ms / 1000.0)
    return f"swiped {x1},{y1}->{x2},{y2} ({duration_ms}ms)"


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
