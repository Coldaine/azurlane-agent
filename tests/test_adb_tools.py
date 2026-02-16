"""Unit tests for the standalone ADB MCP server tools.

All adbutils interactions are mocked -- no real device needed.
"""

from __future__ import annotations

import io
from unittest import mock

import pytest
from PIL import Image as PILImage

# We need to patch the module-level `conn` object inside server.py.
from mcp_server import server
from mcp_server.server import DeviceConnection, _MAX_COORD, _validate_coordinate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pil_image(width: int = 64, height: int = 48) -> PILImage.Image:
    """Create a small solid-colour PIL image for testing."""
    return PILImage.new("RGB", (width, height), color=(128, 64, 32))


def _make_mock_device() -> mock.Mock:
    """Return a Mock that behaves like an adbutils.AdbDevice.

    Mocked methods match the real ``adbutils.AdbDevice`` signatures:
      - ``screenshot(display_id=None, error_ok=True) -> PIL.Image.Image``
      - ``click(x, y, display_id=None) -> None``
      - ``swipe(sx, sy, ex, ey, duration=1.0) -> None``
      - ``get_state() -> str``
    """
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
# _validate_coordinate
# ---------------------------------------------------------------------------

class TestValidateCoordinate:
    """Tests for the ``_validate_coordinate`` helper."""

    def test_zero_is_valid(self):
        """Zero is a valid coordinate (top-left corner)."""
        _validate_coordinate("x", 0)  # should not raise

    def test_typical_value_is_valid(self):
        _validate_coordinate("x", 640)  # should not raise

    def test_max_coord_is_valid(self):
        _validate_coordinate("x", _MAX_COORD)  # should not raise

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="negative"):
            _validate_coordinate("x", -1)

    def test_large_negative_raises(self):
        with pytest.raises(ValueError, match="negative"):
            _validate_coordinate("y", -9999)

    def test_exceeds_max_raises(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            _validate_coordinate("x", _MAX_COORD + 1)

    def test_very_large_raises(self):
        with pytest.raises(ValueError, match="exceeds maximum"):
            _validate_coordinate("y", 999_999)


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

    def test_calls_device_screenshot_with_error_ok_false(self, mock_device):
        """Underlying device.screenshot() is invoked with error_ok=False."""
        server.adb_screenshot()
        mock_device.screenshot.assert_called_once_with(error_ok=False)

    def test_screenshot_device_error(self, mock_device):
        """RuntimeError propagates when device.screenshot() fails."""
        mock_device.screenshot.side_effect = RuntimeError("screen off")
        with pytest.raises(RuntimeError, match="screen off"):
            server.adb_screenshot()

    def test_screenshot_format_is_png(self, mock_device):
        """The Image wrapper reports PNG format."""
        result = server.adb_screenshot()
        assert result._format == "png"

    def test_screenshot_with_large_image(self, mock_device):
        """Screenshot works with a typical 1280x720 device resolution."""
        mock_device.screenshot.return_value = _make_pil_image(1280, 720)
        result = server.adb_screenshot()
        img = PILImage.open(io.BytesIO(result.data))
        assert img.size == (1280, 720)


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

    def test_tap_origin(self, mock_device):
        """Tapping at (0, 0) is valid."""
        result = server.adb_tap(0, 0)
        mock_device.click.assert_called_with(0, 0)
        assert result == "tapped 0,0"

    def test_tap_typical_resolution(self, mock_device):
        """Tapping at the edge of a 1280x720 screen."""
        server.adb_tap(1280, 720)
        mock_device.click.assert_called_with(1280, 720)

    def test_tap_device_error(self, mock_device):
        mock_device.click.side_effect = RuntimeError("ADB gone")
        with pytest.raises(RuntimeError, match="ADB gone"):
            server.adb_tap(50, 50)

    def test_tap_negative_x_raises(self, mock_device):
        """Negative X coordinate is rejected before reaching ADB."""
        with pytest.raises(ValueError, match="negative"):
            server.adb_tap(-1, 100)
        mock_device.click.assert_not_called()

    def test_tap_negative_y_raises(self, mock_device):
        """Negative Y coordinate is rejected before reaching ADB."""
        with pytest.raises(ValueError, match="negative"):
            server.adb_tap(100, -50)
        mock_device.click.assert_not_called()

    def test_tap_huge_coordinate_raises(self, mock_device):
        """Absurdly large coordinates are rejected."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            server.adb_tap(99999, 100)
        mock_device.click.assert_not_called()

    def test_tap_validation_runs_before_device_access(self, monkeypatch):
        """Validation fires even when the device is not connected."""
        # Use a DeviceConnection with no device set (not connected).
        disconnected = DeviceConnection(serial="fake")
        monkeypatch.setattr(server, "conn", disconnected)
        with pytest.raises(ValueError, match="negative"):
            server.adb_tap(-10, 0)


# ---------------------------------------------------------------------------
# adb_swipe
# ---------------------------------------------------------------------------

class TestAdbSwipe:
    def test_swipe_returns_message(self, mock_device):
        result = server.adb_swipe(10, 20, 30, 40, duration_ms=500)
        assert result == "swiped 10,20->30,40 (500ms)"

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

    def test_swipe_negative_start_raises(self, mock_device):
        """Negative start coordinates are rejected."""
        with pytest.raises(ValueError, match="negative"):
            server.adb_swipe(-1, 0, 100, 100)
        mock_device.swipe.assert_not_called()

    def test_swipe_negative_end_raises(self, mock_device):
        """Negative end coordinates are rejected."""
        with pytest.raises(ValueError, match="negative"):
            server.adb_swipe(0, 0, -100, 100)
        mock_device.swipe.assert_not_called()

    def test_swipe_huge_coordinate_raises(self, mock_device):
        """Unreasonably large coordinates are rejected."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            server.adb_swipe(0, 0, 0, 99999)
        mock_device.swipe.assert_not_called()

    def test_swipe_zero_duration_raises(self, mock_device):
        """Zero duration_ms is rejected (must be positive)."""
        with pytest.raises(ValueError, match="must be positive"):
            server.adb_swipe(0, 0, 100, 100, duration_ms=0)
        mock_device.swipe.assert_not_called()

    def test_swipe_negative_duration_raises(self, mock_device):
        """Negative duration_ms is rejected."""
        with pytest.raises(ValueError, match="must be positive"):
            server.adb_swipe(0, 0, 100, 100, duration_ms=-200)
        mock_device.swipe.assert_not_called()

    def test_swipe_small_duration(self, mock_device):
        """1 ms duration is valid (minimum positive)."""
        server.adb_swipe(0, 0, 10, 10, duration_ms=1)
        mock_device.swipe.assert_called_once_with(
            0, 0, 10, 10, duration=0.001
        )

    def test_swipe_large_duration(self, mock_device):
        """Long swipe durations are allowed."""
        server.adb_swipe(0, 0, 100, 100, duration_ms=5000)
        mock_device.swipe.assert_called_once_with(
            0, 0, 100, 100, duration=5.0
        )

    def test_swipe_same_start_and_end(self, mock_device):
        """Swiping to the same point is valid (effectively a long-press)."""
        result = server.adb_swipe(500, 500, 500, 500, duration_ms=1000)
        assert "swiped 500,500->500,500" in result
        mock_device.swipe.assert_called_once()


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
            mock_client.connect.return_value = "already connected to 127.0.0.1:21503"
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
            mock_client.connect.return_value = "already connected to 127.0.0.1:21503"
            mock_device = mock.Mock()
            mock_client.device.return_value = mock_device
            mock_device.get_state.side_effect = Exception("offline")

            with pytest.raises(RuntimeError, match="not responding"):
                dc.connect()

            # Device handle should NOT be cached on failure.
            assert dc._device is None

    def test_connect_soft_failure_unable_to_connect(self):
        """connect() detects 'unable to connect' in the response string.

        adbutils.AdbClient.connect() does NOT raise on connection refusal;
        it returns a status string like "unable to connect to ...".  The
        server must check this string and raise accordingly.
        """
        dc = DeviceConnection(serial="192.168.1.100:5555")
        with mock.patch("mcp_server.server.adbutils") as mock_adb:
            mock_client = mock.Mock()
            mock_adb.AdbClient.return_value = mock_client
            mock_client.connect.return_value = (
                "unable to connect to 192.168.1.100:5555"
            )

            with pytest.raises(RuntimeError, match="ADB connect.*failed"):
                dc.connect()

    def test_connect_soft_failure_failed_to_connect(self):
        """connect() detects 'failed to connect' in the response string."""
        dc = DeviceConnection(serial="1.2.3.4:5555")
        with mock.patch("mcp_server.server.adbutils") as mock_adb:
            mock_client = mock.Mock()
            mock_adb.AdbClient.return_value = mock_client
            mock_client.connect.return_value = (
                "failed to connect to '1.2.3.4:5555': Operation timed out"
            )

            with pytest.raises(RuntimeError, match="ADB connect.*failed"):
                dc.connect()

    def test_connect_already_connected_succeeds(self):
        """'already connected to ...' is treated as success."""
        dc = DeviceConnection(serial="127.0.0.1:21503")
        with mock.patch("mcp_server.server.adbutils") as mock_adb:
            mock_client = mock.Mock()
            mock_adb.AdbClient.return_value = mock_client
            mock_client.connect.return_value = (
                "already connected to 127.0.0.1:21503"
            )
            mock_device = mock.Mock()
            mock_client.device.return_value = mock_device
            mock_device.get_state.return_value = "device"

            result = dc.connect()
            assert result is mock_device

    def test_serial_can_be_updated_before_connect(self):
        """The serial can be changed after construction (used by main())."""
        dc = DeviceConnection(serial="old:1234")
        dc.serial = "new:5678"
        assert dc.serial == "new:5678"


# ---------------------------------------------------------------------------
# MCP server tool registration
# ---------------------------------------------------------------------------

class TestMcpToolRegistration:
    """Verify that tools are correctly registered on the FastMCP instance."""

    def test_server_has_three_tools(self):
        """The mcp instance has exactly three tools registered."""
        tools = server.mcp._tool_manager._tools
        assert len(tools) == 3

    def test_adb_screenshot_registered(self):
        """adb_screenshot is registered by name."""
        tools = server.mcp._tool_manager._tools
        assert "adb_screenshot" in tools

    def test_adb_tap_registered(self):
        """adb_tap is registered by name."""
        tools = server.mcp._tool_manager._tools
        assert "adb_tap" in tools

    def test_adb_swipe_registered(self):
        """adb_swipe is registered by name."""
        tools = server.mcp._tool_manager._tools
        assert "adb_swipe" in tools

    def test_tool_names_match_functions(self):
        """Registered tool names match the function names exactly."""
        tools = server.mcp._tool_manager._tools
        expected = {"adb_screenshot", "adb_tap", "adb_swipe"}
        assert set(tools.keys()) == expected
