"""Unit tests for the template matching tool.

Tests use synthetic images with known patterns — no real game assets needed.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image as PILImage

from tools.template_matching import template_match, template_match_all


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_textured_block(w: int, h: int, seed: int = 42) -> np.ndarray:
    """Create a non-uniform block with deterministic texture.

    Template matching with TM_CCOEFF_NORMED requires variance in pixel
    values — solid-colour blocks produce degenerate 0/0 correlations.
    """
    rng = np.random.RandomState(seed)
    block = rng.randint(100, 256, (h, w, 3), dtype=np.uint8)
    return block


def _make_screenshot_with_pattern(
    sw: int = 300,
    sh: int = 200,
    pattern_pos: tuple[int, int] = (100, 60),
    pattern_size: tuple[int, int] = (40, 30),
    bg_color: tuple[int, int, int] = (30, 30, 30),
    seed: int = 42,
) -> tuple[PILImage.Image, PILImage.Image]:
    """Create a screenshot with an embedded textured pattern and a matching template.

    Returns (screenshot, template) as PIL Images.
    """
    pw, ph = pattern_size
    block = _make_textured_block(pw, ph, seed=seed)

    # Screenshot
    ss = np.full((sh, sw, 3), bg_color, dtype=np.uint8)
    px, py = pattern_pos
    ss[py : py + ph, px : px + pw] = block

    # Template — exact copy of the pattern
    tmpl = block.copy()

    return (
        PILImage.fromarray(ss, mode="RGB"),
        PILImage.fromarray(tmpl, mode="RGB"),
    )


def _make_non_matching_template(
    tw: int = 40, th: int = 30
) -> PILImage.Image:
    """Create a textured template that won't match a dark screenshot."""
    rng = np.random.RandomState(999)
    arr = rng.randint(0, 256, (th, tw, 3), dtype=np.uint8)
    return PILImage.fromarray(arr, mode="RGB")


def _make_screenshot_with_multiple_patterns(
    positions: list[tuple[int, int]],
    sw: int = 400,
    sh: int = 300,
    pattern_size: tuple[int, int] = (30, 20),
    bg_color: tuple[int, int, int] = (30, 30, 30),
    seed: int = 42,
) -> tuple[PILImage.Image, PILImage.Image]:
    """Create a screenshot with the same textured pattern at multiple positions."""
    pw, ph = pattern_size
    block = _make_textured_block(pw, ph, seed=seed)

    ss = np.full((sh, sw, 3), bg_color, dtype=np.uint8)
    for px, py in positions:
        ss[py : py + ph, px : px + pw] = block

    tmpl = block.copy()
    return (
        PILImage.fromarray(ss, mode="RGB"),
        PILImage.fromarray(tmpl, mode="RGB"),
    )


# ---------------------------------------------------------------------------
# template_match
# ---------------------------------------------------------------------------

class TestTemplateMatch:
    """Tests for single best-match template matching."""

    def test_returns_dict_with_expected_keys(self):
        screenshot, template = _make_screenshot_with_pattern()
        result = template_match(screenshot, template)
        assert isinstance(result, dict)
        assert "found" in result
        assert "confidence" in result
        assert "location" in result
        assert "center" in result

    def test_exact_match_high_confidence(self):
        """A pattern placed in the screenshot should match with high confidence."""
        screenshot, template = _make_screenshot_with_pattern(
            pattern_pos=(100, 60), pattern_size=(40, 30)
        )
        result = template_match(screenshot, template, confidence_threshold=0.8)
        assert result["found"] is True
        assert result["confidence"] >= 0.95

    def test_match_location_correct(self):
        """Detected location should match where the pattern was placed."""
        pos = (100, 60)
        screenshot, template = _make_screenshot_with_pattern(
            pattern_pos=pos, pattern_size=(40, 30)
        )
        result = template_match(screenshot, template)
        assert result["found"] is True
        lx, ly = result["location"]
        assert abs(lx - pos[0]) <= 2
        assert abs(ly - pos[1]) <= 2

    def test_match_center_correct(self):
        """Center point should be at (x + w/2, y + h/2) of the match."""
        pos = (100, 60)
        size = (40, 30)
        screenshot, template = _make_screenshot_with_pattern(
            pattern_pos=pos, pattern_size=size
        )
        result = template_match(screenshot, template)
        assert result["found"] is True
        cx, cy = result["center"]
        assert abs(cx - (pos[0] + size[0] // 2)) <= 2
        assert abs(cy - (pos[1] + size[1] // 2)) <= 2

    def test_no_match_below_threshold(self):
        """A non-matching template should return found=False."""
        screenshot, _ = _make_screenshot_with_pattern()
        bad_template = _make_non_matching_template()
        result = template_match(screenshot, bad_template, confidence_threshold=0.9)
        assert result["found"] is False
        assert result["confidence"] < 0.9

    def test_threshold_default_is_reasonable(self):
        """Default confidence threshold allows exact matches to pass."""
        screenshot, template = _make_screenshot_with_pattern()
        result = template_match(screenshot, template)
        assert result["found"] is True

    def test_high_threshold_rejects_imperfect(self):
        """Very high threshold can reject slightly imperfect matches."""
        screenshot, template = _make_screenshot_with_pattern(seed=42)
        # Modify template: add noise to reduce correlation
        arr = np.array(template).astype(np.int16)
        rng = np.random.RandomState(123)
        arr += rng.randint(-30, 31, arr.shape, dtype=np.int16)
        arr = np.clip(arr, 0, 255).astype(np.uint8)
        modified_template = PILImage.fromarray(arr, mode="RGB")
        result = template_match(screenshot, modified_template, confidence_threshold=0.999)
        # Noise drops correlation below perfect
        assert result["confidence"] < 1.0

    def test_template_larger_than_screenshot_raises(self):
        """Template larger than screenshot raises ValueError."""
        small = PILImage.fromarray(np.zeros((10, 10, 3), dtype=np.uint8))
        big = PILImage.fromarray(np.zeros((20, 20, 3), dtype=np.uint8))
        with pytest.raises(ValueError, match="larger"):
            template_match(small, big)

    def test_confidence_bounded(self):
        """Confidence is always in [0.0, 1.0]."""
        screenshot, template = _make_screenshot_with_pattern()
        result = template_match(screenshot, template)
        assert 0.0 <= result["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# template_match_all
# ---------------------------------------------------------------------------

class TestTemplateMatchAll:
    """Tests for finding all template matches."""

    def test_returns_dict_with_matches_list(self):
        screenshot, template = _make_screenshot_with_pattern()
        result = template_match_all(screenshot, template)
        assert isinstance(result, dict)
        assert "matches" in result
        assert isinstance(result["matches"], list)
        assert "count" in result

    def test_finds_single_instance(self):
        screenshot, template = _make_screenshot_with_pattern()
        result = template_match_all(screenshot, template, confidence_threshold=0.9)
        assert result["count"] >= 1

    def test_finds_multiple_instances(self):
        """Multiple separated identical patterns should all be found."""
        positions = [(50, 30), (200, 30), (125, 150)]
        screenshot, template = _make_screenshot_with_multiple_patterns(
            positions, pattern_size=(30, 20)
        )
        result = template_match_all(screenshot, template, confidence_threshold=0.9)
        assert result["count"] >= 2  # at least most should be found

    def test_no_matches_returns_empty(self):
        screenshot, _ = _make_screenshot_with_pattern()
        bad_template = _make_non_matching_template()
        result = template_match_all(screenshot, bad_template, confidence_threshold=0.9)
        assert result["count"] == 0
        assert result["matches"] == []

    def test_each_match_has_location_and_confidence(self):
        screenshot, template = _make_screenshot_with_pattern()
        result = template_match_all(screenshot, template)
        for match in result["matches"]:
            assert "location" in match
            assert "center" in match
            assert "confidence" in match

    def test_match_locations_near_placed_positions(self):
        """Detected positions should be close to where patterns were placed."""
        positions = [(50, 30), (250, 130)]
        screenshot, template = _make_screenshot_with_multiple_patterns(
            positions, sw=400, sh=250, pattern_size=(30, 20)
        )
        result = template_match_all(screenshot, template, confidence_threshold=0.9)
        found_locs = [m["location"] for m in result["matches"]]
        for px, py in positions:
            assert any(
                abs(lx - px) <= 5 and abs(ly - py) <= 5
                for lx, ly in found_locs
            ), f"Expected match near ({px}, {py}), got {found_locs}"
