"""OCR preprocessing and text-region detection using OpenCV.

This module provides the deterministic OCR pipeline for the azurlane-agent
toolchain.  It uses OpenCV for image preprocessing (crop, grayscale,
denoise, threshold) and contour analysis to locate text-like regions in
game screenshots.

The actual character recognition is intentionally kept as a separate
concern — this module provides the *preprocessing* and *region detection*
layers that any OCR backend (PaddleOCR, Tesseract, etc.) can build on.

Typical usage::

    from PIL import Image
    from tools.ocr import ocr_extract_text

    screenshot: Image.Image = ...  # from adb_screenshot
    result = ocr_extract_text(screenshot, region=(100, 50, 200, 40))
    print(result["text_regions_found"])
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image as PILImage


def pil_to_cv2(image: PILImage.Image) -> np.ndarray:
    """Convert a PIL Image to an OpenCV-compatible numpy array.

    RGB images are converted to BGR (OpenCV convention).
    Grayscale images are returned as-is.
    """
    arr = np.array(image)
    if arr.ndim == 3 and arr.shape[2] >= 3:
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    return arr


def preprocess_for_ocr(
    image: np.ndarray,
    region: tuple[int, int, int, int] | None = None,
) -> np.ndarray:
    """Crop and preprocess an image for OCR text extraction.

    The pipeline: optional crop → grayscale → bilateral denoise → Otsu
    binarisation.  The output is a clean binary image suitable for contour
    analysis or downstream OCR engines.

    Args:
        image: Input image as a numpy array (BGR 3-channel or grayscale).
        region: Optional ``(x, y, w, h)`` crop region.

    Returns:
        2-D uint8 array with values in {0, 255}.
    """
    if region is not None:
        x, y, w, h = region
        image = image[y : y + h, x : x + w]

    # Grayscale
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Bilateral filter preserves edges while removing noise
    denoised = cv2.bilateralFilter(gray, 9, 75, 75)

    # Otsu's binarisation picks the threshold automatically
    _, binary = cv2.threshold(
        denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    return binary


def _detect_text_regions(
    binary: np.ndarray,
) -> list[tuple[int, int, int, int]]:
    """Find bounding boxes of text-like regions in a binary image.

    Filters contours by minimum area and aspect ratio to discard noise
    while keeping character-shaped blobs.

    Returns a list of ``(x, y, w, h)`` tuples sorted in approximate
    reading order (top-to-bottom, left-to-right).
    """
    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    h_img, w_img = binary.shape[:2]
    min_area = max(4, int((h_img * w_img) * 0.0001))

    regions: list[tuple[int, int, int, int]] = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        aspect = w / max(h, 1)
        if 0.1 <= aspect <= 10:
            regions.append((int(x), int(y), int(w), int(h)))

    # Sort: top-to-bottom (group by row), then left-to-right
    row_height = max(h_img // 10, 1)
    regions.sort(key=lambda r: (r[1] // row_height, r[0]))
    return regions


def ocr_extract_text(
    image: PILImage.Image,
    region: tuple[int, int, int, int] | None = None,
) -> dict:
    """Extract text-region information from a screenshot.

    Uses OpenCV preprocessing and contour analysis to locate text-like
    regions.  The returned dict contains region bounding boxes and a
    heuristic confidence score based on how many text-like contours were
    found.

    Args:
        image: PIL Image (e.g. from ``adb_screenshot``).
        region: Optional ``(x, y, w, h)`` sub-region to analyse.

    Returns:
        Dict with keys:

        - ``text_regions_found`` (int): number of detected text-like regions.
        - ``confidence`` (float): heuristic in [0.0, 1.0].
        - ``region``: the *region* argument (echoed back).
        - ``preprocessed_shape`` (tuple): shape of the preprocessed image.
        - ``text_region_bounds`` (list): list of ``(x, y, w, h)`` tuples.

    Raises:
        ValueError: If *region* extends beyond the image boundaries.
    """
    img_w, img_h = image.size  # PIL uses (width, height)

    if region is not None:
        rx, ry, rw, rh = region
        if rx + rw > img_w or ry + rh > img_h or rx < 0 or ry < 0:
            raise ValueError(
                f"region {region} extends beyond image bounds "
                f"({img_w}x{img_h})"
            )

    cv_image = pil_to_cv2(image)
    preprocessed = preprocess_for_ocr(cv_image, region=region)
    regions = _detect_text_regions(preprocessed)

    has_text = len(regions) > 0
    confidence = min(1.0, len(regions) / 5.0) if has_text else 0.0

    return {
        "text_regions_found": len(regions),
        "confidence": confidence,
        "region": region,
        "preprocessed_shape": preprocessed.shape,
        "text_region_bounds": regions,
    }
