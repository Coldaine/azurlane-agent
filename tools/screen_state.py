"""Screen state classifier for Azur Lane game screens.

Identifies the current game screen (menu, battle, dock, etc.) by running
template matching against a library of known screen markers.  Returns
results in the tool contract envelope defined in CLAUDE.md::

    {
        "success": bool,
        "data": {"scores": {...}, "best_match": str, "best_score": float},
        "error": str | None,
        "observed_state": str | None,
        "expected_state": "identify"
    }

Templates are loaded from an asset directory where each PNG file
represents a unique screen marker.  The filename (minus extension)
becomes the screen name.

Typical usage::

    from tools.screen_state import classify_screen, build_screen_templates

    templates = build_screen_templates("assets/screens/")
    result = classify_screen(screenshot, templates)
    print(result["observed_state"])  # e.g. "menu", "battle", "unknown"
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image as PILImage


# Default confidence threshold below which a match is considered
# too weak to identify a screen.
_CLASSIFY_THRESHOLD = 0.8


@dataclass
class ScreenTemplate:
    """A reference template for identifying a game screen.

    Attributes:
        name: Identifier for the screen (e.g. ``"menu"``, ``"battle"``).
        template: PIL Image of the screen marker.
        region: Optional ``(x, y, w, h)`` region-of-interest on the
            screenshot where this marker is expected.  If ``None``, the
            whole screenshot is searched.
    """

    name: str
    template: PILImage.Image
    region: tuple[int, int, int, int] | None = None


def _pil_to_cv2(image: PILImage.Image) -> np.ndarray:
    arr = np.array(image)
    if arr.ndim == 3 and arr.shape[2] >= 3:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    return arr


def _match_score(
    screenshot_cv: np.ndarray,
    template_cv: np.ndarray,
    region: tuple[int, int, int, int] | None = None,
) -> float:
    """Return the peak TM_CCOEFF_NORMED score for *template_cv* in *screenshot_cv*.

    If *region* is given, the search is restricted to that sub-image.
    """
    if region is not None:
        rx, ry, rw, rh = region
        search_area = screenshot_cv[ry : ry + rh, rx : rx + rw]
    else:
        search_area = screenshot_cv

    th, tw = template_cv.shape[:2]
    sh, sw = search_area.shape[:2]

    if th > sh or tw > sw:
        return 0.0

    result = cv2.matchTemplate(search_area, template_cv, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return float(max(0.0, min(1.0, max_val)))


def classify_screen(
    screenshot: PILImage.Image,
    screen_templates: dict[str, ScreenTemplate],
    threshold: float = _CLASSIFY_THRESHOLD,
) -> dict:
    """Classify the current game screen based on template matching.

    Runs each template in *screen_templates* against *screenshot* and
    returns the best match (if above *threshold*) as the observed screen
    state.

    Args:
        screenshot: PIL Image of the game screen.
        screen_templates: Mapping of screen name → ``ScreenTemplate``.
        threshold: Minimum match score to accept (default 0.8).

    Returns:
        Tool-contract envelope dict.
    """
    ss_cv = _pil_to_cv2(screenshot)

    scores: dict[str, float] = {}
    for name, st in screen_templates.items():
        tmpl_cv = _pil_to_cv2(st.template)
        scores[name] = _match_score(ss_cv, tmpl_cv, region=st.region)

    if scores:
        best_name = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_name]
    else:
        best_name = "unknown"
        best_score = 0.0

    observed = best_name if best_score >= threshold else "unknown"

    return {
        "success": True,
        "data": {
            "scores": scores,
            "best_match": best_name,
            "best_score": best_score,
        },
        "error": None,
        "observed_state": observed,
        "expected_state": "identify",
    }


def build_screen_templates(
    asset_dir: str,
) -> dict[str, ScreenTemplate]:
    """Load screen templates from a directory of PNG files.

    Each ``.png`` file becomes a ``ScreenTemplate`` whose name is the
    file stem (e.g. ``main_menu.png`` → name ``"main_menu"``).

    Args:
        asset_dir: Path to the directory containing template PNGs.

    Returns:
        Dict mapping screen names to ``ScreenTemplate`` instances.
    """
    templates: dict[str, ScreenTemplate] = {}
    asset_path = Path(asset_dir)

    if not asset_path.is_dir():
        return templates

    for entry in sorted(asset_path.iterdir()):
        if entry.suffix.lower() != ".png":
            continue
        img = PILImage.open(str(entry)).convert("RGB")
        templates[entry.stem] = ScreenTemplate(
            name=entry.stem,
            template=img,
            region=None,
        )

    return templates
