"""Unit tests for the OCR tool.

Tests use synthetic images — no real game screenshots or OCR engine needed.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image as PILImage

from tools.ocr import ocr_extract_text, preprocess_for_ocr, pil_to_cv2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_dark_image(width: int = 200, height: int = 100) -> PILImage.Image:
    """Create a dark image (simulating a game UI background)."""
    return PILImage.fromarray(
        np.zeros((height, width, 3), dtype=np.uint8), mode="RGB"
    )


def _make_image_with_white_block(
    width: int = 200,
    height: int = 100,
    block_rect: tuple[int, int, int, int] = (40, 20, 80, 40),
) -> PILImage.Image:
    """Create a dark image with a white rectangle (simulating text region).

    *block_rect* is (x, y, w, h) defining the white block position.
    """
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    bx, by, bw, bh = block_rect
    arr[by : by + bh, bx : bx + bw] = 255
    return PILImage.fromarray(arr, mode="RGB")


def _make_uniform_image(
    width: int = 200, height: int = 100, value: int = 128
) -> PILImage.Image:
    """Create a uniform gray image (no text-like features)."""
    arr = np.full((height, width, 3), value, dtype=np.uint8)
    return PILImage.fromarray(arr, mode="RGB")


# ---------------------------------------------------------------------------
# pil_to_cv2
# ---------------------------------------------------------------------------

class TestPilToCv2:
    """Tests for PIL → OpenCV conversion."""

    def test_rgb_to_bgr_conversion(self):
        """Red channel in PIL becomes blue channel in OpenCV."""
        img = PILImage.fromarray(
            np.array([[[255, 0, 0]]], dtype=np.uint8), mode="RGB"
        )
        cv2_img = pil_to_cv2(img)
        # OpenCV uses BGR: blue=255, green=0, red=0
        assert cv2_img[0, 0, 0] == 0    # B
        assert cv2_img[0, 0, 1] == 0    # G
        assert cv2_img[0, 0, 2] == 255  # R

    def test_output_shape_matches_input(self):
        img = _make_dark_image(64, 48)
        cv2_img = pil_to_cv2(img)
        assert cv2_img.shape == (48, 64, 3)

    def test_grayscale_input(self):
        """Grayscale PIL image passes through without error."""
        arr = np.zeros((10, 20), dtype=np.uint8)
        img = PILImage.fromarray(arr, mode="L")
        cv2_img = pil_to_cv2(img)
        assert cv2_img.shape == (10, 20)


# ---------------------------------------------------------------------------
# preprocess_for_ocr
# ---------------------------------------------------------------------------

class TestPreprocessForOcr:
    """Tests for the OpenCV preprocessing pipeline."""

    def test_returns_2d_array(self):
        """Preprocessing produces a single-channel (binary) image."""
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        result = preprocess_for_ocr(img)
        assert result.ndim == 2

    def test_output_is_binary(self):
        """Result contains only 0 and 255 values (binary threshold)."""
        arr = np.random.randint(0, 256, (100, 200, 3), dtype=np.uint8)
        result = preprocess_for_ocr(arr)
        unique = set(np.unique(result))
        assert unique <= {0, 255}

    def test_region_crop(self):
        """Specifying a region crops the image before processing."""
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        region = (10, 20, 50, 30)  # x, y, w, h
        result = preprocess_for_ocr(img, region=region)
        assert result.shape == (30, 50)

    def test_full_image_when_no_region(self):
        """Without a region, the full image dimensions are preserved."""
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        result = preprocess_for_ocr(img)
        assert result.shape == (100, 200)

    def test_grayscale_input_accepted(self):
        """Grayscale input (2D array) is handled correctly."""
        gray = np.zeros((50, 80), dtype=np.uint8)
        result = preprocess_for_ocr(gray)
        assert result.ndim == 2
        assert result.shape == (50, 80)

    def test_white_on_black_preserved(self):
        """White regions on a black background survive thresholding."""
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        img[30:60, 50:150] = 255  # white block
        result = preprocess_for_ocr(img)
        # The white block region should contain 255 values
        assert np.any(result[30:60, 50:150] == 255)


# ---------------------------------------------------------------------------
# ocr_extract_text
# ---------------------------------------------------------------------------

class TestOcrExtractText:
    """Tests for the main OCR extraction function."""

    def test_returns_dict(self):
        """Result is a dict with expected keys."""
        img = _make_dark_image()
        result = ocr_extract_text(img)
        assert isinstance(result, dict)
        assert "text_regions_found" in result
        assert "confidence" in result
        assert "region" in result
        assert "preprocessed_shape" in result

    def test_blank_image_finds_no_text(self):
        """A uniform image has no text-like regions."""
        img = _make_uniform_image(200, 100, value=0)
        result = ocr_extract_text(img)
        assert result["text_regions_found"] == 0
        assert result["confidence"] == 0.0

    def test_image_with_block_finds_regions(self):
        """An image with a white block on dark background detects regions."""
        img = _make_image_with_white_block(200, 100, (40, 20, 80, 40))
        result = ocr_extract_text(img)
        assert result["text_regions_found"] >= 1
        assert result["confidence"] > 0.0

    def test_region_parameter_crops_correctly(self):
        """OCR with a region parameter processes only that subimage."""
        img = _make_image_with_white_block(200, 100, (40, 20, 80, 40))
        region = (30, 10, 100, 60)  # x, y, w, h
        result = ocr_extract_text(img, region=region)
        assert result["region"] == region
        assert result["preprocessed_shape"] == (60, 100)

    def test_region_outside_text_finds_nothing(self):
        """A region that doesn't overlap text finds no text regions."""
        # White block at (40,20,80,40), search in bottom-right corner
        img = _make_image_with_white_block(200, 100, (40, 20, 80, 40))
        region = (150, 70, 40, 25)
        result = ocr_extract_text(img, region=region)
        assert result["text_regions_found"] == 0

    def test_confidence_bounded_zero_one(self):
        """Confidence is always in [0.0, 1.0]."""
        img = _make_image_with_white_block()
        result = ocr_extract_text(img)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_text_region_bounds_are_tuples(self):
        """Each detected text-region bound is a (x, y, w, h) tuple."""
        img = _make_image_with_white_block(200, 100, (40, 20, 80, 40))
        result = ocr_extract_text(img)
        for bound in result["text_region_bounds"]:
            assert len(bound) == 4
            assert all(isinstance(v, (int, np.integer)) for v in bound)

    def test_multiple_text_regions(self):
        """Multiple separated white blocks produce multiple regions."""
        arr = np.zeros((100, 300, 3), dtype=np.uint8)
        arr[20:40, 30:70] = 255   # block 1
        arr[20:40, 150:190] = 255  # block 2
        arr[60:80, 90:130] = 255   # block 3
        img = PILImage.fromarray(arr, mode="RGB")
        result = ocr_extract_text(img)
        assert result["text_regions_found"] >= 2

    def test_invalid_region_raises(self):
        """A region extending beyond image bounds raises ValueError."""
        img = _make_dark_image(100, 50)
        with pytest.raises(ValueError, match="region"):
            ocr_extract_text(img, region=(80, 30, 50, 30))  # overflows
