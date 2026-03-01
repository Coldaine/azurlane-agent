"""Unit tests for the screen state classifier.

Tests verify that the classifier identifies game screens (menu, battle, dock)
using template matching + OCR signals.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image as PILImage

from tools.screen_state import (
    ScreenTemplate,
    classify_screen,
    build_screen_templates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_solid_image(
    width: int = 300,
    height: int = 200,
    color: tuple[int, int, int] = (30, 30, 30),
) -> PILImage.Image:
    arr = np.full((height, width, 3), color, dtype=np.uint8)
    return PILImage.fromarray(arr, mode="RGB")


def _make_textured_block(
    w: int, h: int, seed: int = 0
) -> np.ndarray:
    """Create a textured block with deterministic content for template matching."""
    rng = np.random.RandomState(seed)
    return rng.randint(80, 256, (h, w, 3), dtype=np.uint8)


def _make_screen_with_marker(
    sw: int = 300,
    sh: int = 200,
    marker_pos: tuple[int, int] = (50, 30),
    marker_size: tuple[int, int] = (40, 25),
    marker_seed: int = 0,
    bg_color: tuple[int, int, int] = (30, 30, 30),
) -> PILImage.Image:
    """Create a screenshot with a textured marker at a known position."""
    arr = np.full((sh, sw, 3), bg_color, dtype=np.uint8)
    mx, my = marker_pos
    mw, mh = marker_size
    arr[my : my + mh, mx : mx + mw] = _make_textured_block(mw, mh, seed=marker_seed)
    return PILImage.fromarray(arr, mode="RGB")


def _make_template(
    tw: int = 40,
    th: int = 25,
    seed: int = 0,
) -> PILImage.Image:
    arr = _make_textured_block(tw, th, seed=seed)
    return PILImage.fromarray(arr, mode="RGB")


def _build_test_templates() -> dict[str, ScreenTemplate]:
    """Build a set of screen templates for testing.

    Three screens: menu (seed 10), battle (seed 20), dock (seed 30).
    Each has a unique textured pattern.
    """
    return {
        "menu": ScreenTemplate(
            name="menu",
            template=_make_template(40, 25, seed=10),
            region=None,
        ),
        "battle": ScreenTemplate(
            name="battle",
            template=_make_template(40, 25, seed=20),
            region=None,
        ),
        "dock": ScreenTemplate(
            name="dock",
            template=_make_template(40, 25, seed=30),
            region=None,
        ),
    }


# ---------------------------------------------------------------------------
# ScreenTemplate
# ---------------------------------------------------------------------------

class TestScreenTemplate:
    """Tests for the ScreenTemplate data class."""

    def test_has_required_fields(self):
        tmpl = _make_template()
        st = ScreenTemplate(name="test", template=tmpl, region=None)
        assert st.name == "test"
        assert st.template is tmpl
        assert st.region is None

    def test_optional_region(self):
        tmpl = _make_template()
        st = ScreenTemplate(name="test", template=tmpl, region=(10, 20, 100, 50))
        assert st.region == (10, 20, 100, 50)


# ---------------------------------------------------------------------------
# classify_screen
# ---------------------------------------------------------------------------

class TestClassifyScreen:
    """Tests for the screen state classifier."""

    def test_returns_tool_contract_envelope(self):
        """Result must follow the tool contract envelope."""
        screenshot = _make_solid_image()
        templates = _build_test_templates()
        result = classify_screen(screenshot, templates)
        assert isinstance(result, dict)
        assert "success" in result
        assert "data" in result
        assert "error" in result
        assert "observed_state" in result
        assert "expected_state" in result

    def test_identifies_menu_screen(self):
        """A screenshot with the menu marker is classified as 'menu'."""
        screenshot = _make_screen_with_marker(
            marker_pos=(50, 30), marker_seed=10
        )
        templates = _build_test_templates()
        result = classify_screen(screenshot, templates)
        assert result["success"] is True
        assert result["observed_state"] == "menu"

    def test_identifies_battle_screen(self):
        """A screenshot with the battle marker is classified as 'battle'."""
        screenshot = _make_screen_with_marker(
            marker_pos=(50, 30), marker_seed=20
        )
        templates = _build_test_templates()
        result = classify_screen(screenshot, templates)
        assert result["success"] is True
        assert result["observed_state"] == "battle"

    def test_identifies_dock_screen(self):
        """A screenshot with the dock marker is classified as 'dock'."""
        screenshot = _make_screen_with_marker(
            marker_pos=(50, 30), marker_seed=30
        )
        templates = _build_test_templates()
        result = classify_screen(screenshot, templates)
        assert result["success"] is True
        assert result["observed_state"] == "dock"

    def test_unknown_screen(self):
        """A screenshot matching no template returns observed_state='unknown'."""
        screenshot = _make_solid_image(color=(128, 128, 128))
        templates = _build_test_templates()
        result = classify_screen(screenshot, templates)
        assert result["success"] is True
        assert result["observed_state"] == "unknown"

    def test_expected_state_is_identify(self):
        """expected_state is always 'identify' for classification."""
        screenshot = _make_solid_image()
        templates = _build_test_templates()
        result = classify_screen(screenshot, templates)
        assert result["expected_state"] == "identify"

    def test_data_contains_scores(self):
        """Data includes match scores for each screen template."""
        screenshot = _make_screen_with_marker(marker_seed=10)
        templates = _build_test_templates()
        result = classify_screen(screenshot, templates)
        assert result["data"] is not None
        assert "scores" in result["data"]
        assert isinstance(result["data"]["scores"], dict)

    def test_data_scores_include_all_templates(self):
        """All template names appear in the scores dict."""
        screenshot = _make_solid_image()
        templates = _build_test_templates()
        result = classify_screen(screenshot, templates)
        for name in templates:
            assert name in result["data"]["scores"]

    def test_best_match_is_highest_scoring(self):
        """The observed_state is the template with the highest score."""
        screenshot = _make_screen_with_marker(marker_seed=10)
        templates = _build_test_templates()
        result = classify_screen(screenshot, templates)
        scores = result["data"]["scores"]
        if result["observed_state"] != "unknown":
            best_name = max(scores, key=scores.get)
            assert result["observed_state"] == best_name

    def test_empty_templates_returns_unknown(self):
        """With no templates, classification is always unknown."""
        screenshot = _make_solid_image()
        result = classify_screen(screenshot, {})
        assert result["observed_state"] == "unknown"

    def test_error_is_none_on_success(self):
        screenshot = _make_solid_image()
        templates = _build_test_templates()
        result = classify_screen(screenshot, templates)
        assert result["error"] is None


# ---------------------------------------------------------------------------
# build_screen_templates
# ---------------------------------------------------------------------------

class TestBuildScreenTemplates:
    """Tests for helper that builds templates from asset directory."""

    def test_returns_dict(self, tmp_path):
        """Returns a dict mapping screen names to ScreenTemplate objects."""
        # Create a minimal asset directory with one PNG
        marker = _make_template(20, 15, seed=99)
        asset_dir = tmp_path / "screens"
        asset_dir.mkdir()
        marker.save(str(asset_dir / "main_menu.png"))

        result = build_screen_templates(str(asset_dir))
        assert isinstance(result, dict)
        assert "main_menu" in result
        assert isinstance(result["main_menu"], ScreenTemplate)

    def test_empty_directory(self, tmp_path):
        """Empty asset directory produces empty dict."""
        asset_dir = tmp_path / "empty_screens"
        asset_dir.mkdir()
        result = build_screen_templates(str(asset_dir))
        assert result == {}

    def test_non_png_files_ignored(self, tmp_path):
        """Non-PNG files in the asset directory are ignored."""
        asset_dir = tmp_path / "screens"
        asset_dir.mkdir()
        (asset_dir / "readme.txt").write_text("not an image")
        marker = _make_template(20, 15)
        marker.save(str(asset_dir / "battle.png"))

        result = build_screen_templates(str(asset_dir))
        assert "battle" in result
        assert "readme" not in result
