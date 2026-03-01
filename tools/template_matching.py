"""Template matching using OpenCV.

Provides single-best-match and multi-match template search against game
screenshots.  Uses ``cv2.matchTemplate`` with normalised cross-correlation
(``TM_CCOEFF_NORMED``) which is robust to brightness variation common in
game UIs.

Typical usage::

    from PIL import Image
    from tools.template_matching import template_match, template_match_all

    screenshot: Image.Image = ...   # from adb_screenshot
    template: Image.Image = ...     # loaded from assets/
    result = template_match(screenshot, template, confidence_threshold=0.85)
    if result["found"]:
        print(f"Found at {result['center']} with {result['confidence']:.2f}")
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image as PILImage


def _pil_to_cv2(image: PILImage.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV BGR array."""
    arr = np.array(image)
    if arr.ndim == 3 and arr.shape[2] >= 3:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    return arr


def template_match(
    screenshot: PILImage.Image,
    template: PILImage.Image,
    confidence_threshold: float = 0.8,
) -> dict:
    """Find the best match of *template* within *screenshot*.

    Args:
        screenshot: The full-screen PIL Image to search in.
        template: The reference PIL Image to search for.
        confidence_threshold: Minimum normalised correlation to count as
            a match (0.0–1.0, default 0.8).

    Returns:
        Dict with keys:

        - ``found`` (bool): whether the best match exceeds the threshold.
        - ``confidence`` (float): peak correlation value in [0.0, 1.0].
        - ``location`` (tuple[int, int]): top-left ``(x, y)`` of the
          best-match bounding box (or ``(-1, -1)`` if not found).
        - ``center`` (tuple[int, int]): centre point of the match
          (or ``(-1, -1)``).

    Raises:
        ValueError: If the template is larger than the screenshot in
            either dimension.
    """
    ss = _pil_to_cv2(screenshot)
    tmpl = _pil_to_cv2(template)

    sh, sw = ss.shape[:2]
    th, tw = tmpl.shape[:2]

    if th > sh or tw > sw:
        raise ValueError(
            f"Template ({tw}x{th}) is larger than screenshot ({sw}x{sh})"
        )

    result = cv2.matchTemplate(ss, tmpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    # Clamp to [0, 1] — TM_CCOEFF_NORMED can occasionally produce tiny
    # negative values for terrible matches.
    confidence = float(max(0.0, min(1.0, max_val)))
    found = confidence >= confidence_threshold

    if found:
        top_left = (int(max_loc[0]), int(max_loc[1]))
        center = (top_left[0] + tw // 2, top_left[1] + th // 2)
    else:
        top_left = (-1, -1)
        center = (-1, -1)

    return {
        "found": found,
        "confidence": confidence,
        "location": top_left,
        "center": center,
    }


def template_match_all(
    screenshot: PILImage.Image,
    template: PILImage.Image,
    confidence_threshold: float = 0.8,
    min_distance: int = 10,
) -> dict:
    """Find **all** matches of *template* within *screenshot*.

    Uses non-maximum suppression to eliminate overlapping detections.

    Args:
        screenshot: The full-screen PIL Image.
        template: The reference PIL Image.
        confidence_threshold: Minimum correlation (0.0–1.0, default 0.8).
        min_distance: Minimum pixel distance between match centres to
            consider them distinct (default 10).

    Returns:
        Dict with keys:

        - ``count`` (int): number of distinct matches found.
        - ``matches`` (list[dict]): each entry has ``location``,
          ``center``, and ``confidence``.
    """
    ss = _pil_to_cv2(screenshot)
    tmpl = _pil_to_cv2(template)

    sh, sw = ss.shape[:2]
    th, tw = tmpl.shape[:2]

    if th > sh or tw > sw:
        raise ValueError(
            f"Template ({tw}x{th}) is larger than screenshot ({sw}x{sh})"
        )

    result = cv2.matchTemplate(ss, tmpl, cv2.TM_CCOEFF_NORMED)

    # Find all locations above the threshold
    locations = np.where(result >= confidence_threshold)
    matches_raw: list[dict] = []
    for pt_y, pt_x in zip(*locations):
        conf = float(result[pt_y, pt_x])
        matches_raw.append({
            "location": (int(pt_x), int(pt_y)),
            "center": (int(pt_x) + tw // 2, int(pt_y) + th // 2),
            "confidence": conf,
        })

    # Sort by confidence descending for NMS
    matches_raw.sort(key=lambda m: m["confidence"], reverse=True)

    # Non-maximum suppression: keep only matches whose centres are far
    # enough apart.
    kept: list[dict] = []
    for m in matches_raw:
        cx, cy = m["center"]
        too_close = False
        for k in kept:
            kx, ky = k["center"]
            if abs(cx - kx) < min_distance and abs(cy - ky) < min_distance:
                too_close = True
                break
        if not too_close:
            kept.append(m)

    return {"count": len(kept), "matches": kept}
