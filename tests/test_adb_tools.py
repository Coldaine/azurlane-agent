"""Unit tests for the standalone ADB MCP server tools.

All adbutils interactions are mocked — no real device needed.
"""

from __future__ import annotations

import io
from unittest import mock

import pytest
from PIL import Image as PILImage

# We need to patch the module-level `conn` object inside server.py.
from mcp_server import server
from mcp_server.server import DeviceConnection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pil_image(width: int = 64, height: int = 48) -> PILImage.Image:
    """Create a small solid-colour PIL image for testing."""
    return PILImage.new("RGB", (width, height), color=(128, 64, 32))


def _make_mock_device() -> mock.Mock:
    """Return a Mock that behaves like an adbutils.AdbDevice."""
    device = mock.Mock()
    device.screenshot.return_value = _make_pil_image()
    device.click.return_value = None
    device.swipe.return_value = None
    device.get_state.return_value = "device"
    return device


@pytest.fixture()
def mock_device(monkeypatch):
    """Patch ``server.conn`` so tools use a mocked ADB device."""
    device = _make_mock_device()
    fake_conn = DeviceConnection(serial="127.0.0.1:99999")
    fake_conn._device = device  # bypass connect()
    monkeypatch.setattr(server, "conn", fake_conn)
    return device


# ---------------------------------------------------------------------------
# adb_screenshot
# ---------------------------------------------------------------------------

class TestAdbScreenshot:
    def test_returns_fastmcp_image(self, mock_device):
        """Tool returns a FastMCP Image with PNG data."""
        from fastmcp.utilities.types import Image

        result = server.adb_screenshot()
        assert isinstance(result, Image)

    def test_png_bytes_are_valid(self, mock_device):
        """The PNG bytes inside the Image can be decoded back to PIL."""
        result = server.adb_screenshot()
        # Access the raw bytes stored in the Image helper.
        assert result.data is not None
        img = PILImage.open(io.BytesIO(result.data))
        assert img.format == "PNG"
        assert img.size == (64, 48)

    def test_calls_device_screenshot(self, mock_device):
        """Underlying device.screenshot() is invoked exactly once."""
        server.adb_screenshot()
        mock_device.screenshot.assert_called_once()

    def test_screenshot_device_error(self, mock_device):
        """RuntimeError propagates when device.screenshot() fails."""
        mock_device.screenshot.side_effect = RuntimeError("screen off")
        with pytest.raises(RuntimeError, match="screen off"):
            server.adb_screenshot()


# ---------------------------------------------------------------------------
# adb_tap
# ---------------------------------------------------------------------------

class TestAdbTap:
    def test_tap_returns_message(self, mock_device):
        result = server.adb_tap(100, 200)
        assert result == "tapped 100,200"

    def test_tap_calls_device_click(self, mock_device):
        server.adb_tap(300, 400)
        mock_device.click.assert_called_once_with(300, 400)

    def test_tap_various_coordinates(self, mock_device):
        """Coordinates are forwarded exactly as given."""
        server.adb_tap(0, 0)
        mock_device.click.assert_called_with(0, 0)

        server.adb_tap(1280, 720)
        mock_device.click.assert_called_with(1280, 720)

    def test_tap_device_error(self, mock_device):
        mock_device.click.side_effect = RuntimeError("ADB gone")
        with pytest.raises(RuntimeError, match="ADB gone"):
            server.adb_tap(50, 50)


# ---------------------------------------------------------------------------
# adb_swipe
# ---------------------------------------------------------------------------

class TestAdbSwipe:
    def test_swipe_returns_message(self, mock_device):
        result = server.adb_swipe(10, 20, 30, 40, duration_ms=500)
        assert result == "swiped 10,20->30,40"

    def test_swipe_calls_device_swipe_with_duration(self, mock_device):
        """Duration is converted from ms to seconds."""
        server.adb_swipe(100, 200, 300, 400, duration_ms=600)
        mock_device.swipe.assert_called_once_with(
            100, 200, 300, 400, duration=0.6
        )

    def test_swipe_default_duration(self, mock_device):
        """Default duration_ms=300 becomes 0.3 s."""
        server.adb_swipe(0, 0, 100, 100)
        mock_device.swipe.assert_called_once_with(
            0, 0, 100, 100, duration=0.3
        )

    def test_swipe_device_error(self, mock_device):
        mock_device.swipe.side_effect = RuntimeError("swipe failed")
        with pytest.raises(RuntimeError, match="swipe failed"):
            server.adb_swipe(0, 0, 10, 10)


# ---------------------------------------------------------------------------
# DeviceConnection
# ---------------------------------------------------------------------------

class TestDeviceConnection:
    def test_device_raises_when_not_connected(self):
        """Accessing .device before connect() raises RuntimeError."""
        dc = DeviceConnection(serial="127.0.0.1:12345")
        with pytest.raises(RuntimeError, match="not connected"):
            _ = dc.device

    def test_connect_failure_raises(self):
        """connect() wraps adbutils errors in RuntimeError."""
        dc = DeviceConnection(serial="192.168.1.999:5555")
        with mock.patch("mcp_server.server.adbutils") as mock_adb:
            mock_client = mock.Mock()
            mock_adb.AdbClient.return_value = mock_client
            mock_client.connect.side_effect = Exception("connection refused")

            with pytest.raises(RuntimeError, match="Failed to connect"):
                dc.connect()

    def test_connect_success(self):
        """connect() stores the device handle on success."""
        dc = DeviceConnection(serial="127.0.0.1:21503")
        with mock.patch("mcp_server.server.adbutils") as mock_adb:
            mock_client = mock.Mock()
            mock_adb.AdbClient.return_value = mock_client
            mock_device = mock.Mock()
            mock_client.device.return_value = mock_device
            mock_device.get_state.return_value = "device"

            result = dc.connect()

            mock_client.connect.assert_called_once_with(
                "127.0.0.1:21503", timeout=5.0
            )
            assert result is mock_device
            assert dc.device is mock_device

    def test_connect_device_not_responding(self):
        """connect() raises when device is reachable but not responding."""
        dc = DeviceConnection(serial="127.0.0.1:21503")
        with mock.patch("mcp_server.server.adbutils") as mock_adb:
            mock_client = mock.Mock()
            mock_adb.AdbClient.return_value = mock_client
            mock_device = mock.Mock()
            mock_client.device.return_value = mock_device
            mock_device.get_state.side_effect = Exception("offline")

            with pytest.raises(RuntimeError, match="not responding"):
                dc.connect()

            # Device handle should NOT be cached on failure.
            assert dc._device is None
