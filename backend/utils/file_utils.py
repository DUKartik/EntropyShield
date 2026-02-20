"""
file_utils.py
Filesystem helper utilities for the EntropyShield backend.
"""
import shutil
from pathlib import Path

from utils.debug_logger import get_logger

logger = get_logger()


def cleanup_stale_files(directory: Path, max_age_seconds: int = 300) -> None:
    """
    Background task: remove files/directories in *directory* that are older
    than *max_age_seconds*.  Runs non-blocking so it should be scheduled via
    FastAPI BackgroundTasks and never awaited directly.
    """
    import time

    try:
        if not directory.exists():
            return

        current_time = time.time()
        for item in directory.iterdir():
            try:
                if item.stat().st_mtime < current_time - max_age_seconds:
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                        logger.info(f"Background cleanup: removed file {item.name}")
                    elif item.is_dir():
                        shutil.rmtree(item)
                        logger.info(f"Background cleanup: removed dir {item.name}")
            except Exception as e:
                logger.warning(f"Cleanup skipped {item.name}: {e}")
    except Exception as e:
        logger.error(f"Background cleanup process failed: {e}")
