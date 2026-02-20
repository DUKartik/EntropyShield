"""
image_analyzers.py
Pure CPU-bound image analysis functions (ELA, Noise, Quantization).
These are synchronous and should be dispatched via loop.run_in_executor
when called from async contexts.
"""
import os
# cv2 and numpy are lazy-imported inside each function to avoid loading
# OpenCV at server startup time.

from utils.debug_logger import get_logger

logger = get_logger()


def perform_ela(image_path: str, quality: int = 90) -> dict:
    """
    Error Level Analysis (ELA): re-saves the image at a fixed JPEG quality and
    computes the absolute difference to highlight manipulated regions.

    Returns a dict with ELA stats and the filename of the saved heatmap.
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    resaved_path = image_path + ".resaved.jpg"
    try:
        original = cv2.imread(image_path)
        if original is None:
            return {"status": "error", "message": "Could not read image"}

        # Re-save at target quality then compute per-pixel difference
        cv2.imwrite(resaved_path, original, [cv2.IMWRITE_JPEG_QUALITY, quality])
        resaved = cv2.imread(resaved_path)
        ela_image = cv2.absdiff(original, resaved)

        # Stats on grayscale channel
        gray_ela = cv2.cvtColor(ela_image, cv2.COLOR_BGR2GRAY)
        max_diff = float(np.max(gray_ela))
        mean_diff = float(np.mean(gray_ela))
        std_dev = float(np.std(gray_ela))

        # Adaptive threshold: keep only pixels significantly above mean noise
        thresh_val = mean_diff + 3 * std_dev
        _, mask = cv2.threshold(gray_ela, thresh_val, 255, cv2.THRESH_BINARY)

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        dilated = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=4)

        heatmap_density = cv2.GaussianBlur(dilated, (21, 21), 0)
        heatmap_norm = cv2.normalize(heatmap_density, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        amplified = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_TURBO)

        ela_filename = os.path.basename(image_path) + ".ela.png"
        ela_output_path = os.path.join(os.path.dirname(image_path), ela_filename)
        cv2.imwrite(ela_output_path, amplified)

        return {
            "status": "success",
            "max_difference": max_diff,
            "mean_difference": mean_diff,
            "std_deviation": std_dev,
            "ela_image_path": ela_filename,
        }
    except Exception as e:
        logger.error(f"ELA failed for {image_path}: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(resaved_path):
            os.remove(resaved_path)


def perform_noise_analysis(image_path: str) -> dict:
    """
    Block-wise noise variance map: highlights regions with inconsistent high-
    frequency noise — a common artefact of image splicing / compositing.
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"status": "error", "message": "Could not read image"}

        h, w = img.shape
        block_size = 8
        h_b = (h // block_size) * block_size
        w_b = (w // block_size) * block_size
        img_trunc = img[:h_b, :w_b]

        blocks = img_trunc.reshape(h_b // block_size, block_size, w_b // block_size, block_size)
        block_stds = blocks.std(axis=(1, 3))
        avg_noise_var = float(np.mean(block_stds))

        min_v, max_v = block_stds.min(), block_stds.max()
        norm_stds = (block_stds - min_v) / (max_v - min_v + 1e-5) * 255
        noise_map_resized = cv2.resize(norm_stds, (w_b, h_b), interpolation=cv2.INTER_NEAREST)
        colored_noise = cv2.applyColorMap(noise_map_resized.astype(np.uint8), cv2.COLORMAP_INFERNO)

        noise_filename = os.path.basename(image_path) + ".noise.png"
        noise_output_path = os.path.join(os.path.dirname(image_path), noise_filename)
        cv2.imwrite(noise_output_path, colored_noise)

        return {
            "status": "success",
            "noise_map_path": noise_filename,
            "average_diff": avg_noise_var,
        }
    except Exception as e:
        logger.error(f"Noise analysis failed for {image_path}: {e}")
        return {"status": "error", "message": str(e)}


def analyze_quantization(image_path: str) -> dict:
    """
    Simplified JPEG double-quantization detector: counts zero-bin gaps in the
    pixel-value histogram as a proxy for DCT quantization comb artefacts.
    """
    import cv2  # noqa: PLC0415
    try:
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return {"status": "error", "message": "Could not read image"}

        hist = cv2.calcHist([img], [0], None, [256], [0, 256])
        zeros = int(sum(1 for i in range(1, 255) if hist[i] == 0))
        is_suspicious = zeros > 10  # heuristic threshold for comb pattern

        return {
            "status": "success",
            "histogram_gaps": zeros,
            "suspicious": is_suspicious,
            "histogram_values": hist.flatten().tolist(),
        }
    except Exception as e:
        logger.error(f"Quantization analysis failed for {image_path}: {e}")
        return {"status": "error", "message": str(e)}
