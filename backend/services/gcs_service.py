"""
gcs_service.py
Google Cloud Storage helpers for the EntropyShield backend.
"""
import os
from typing import Optional

from google.cloud import storage

from utils.debug_logger import get_logger

logger = get_logger()

GCS_BUCKET_NAME: str = os.getenv("GCS_BUCKET_NAME", "veridoc-uploads")


def upload_to_gcs(source_file_name: str, destination_blob_name: str) -> Optional[str]:
    """
    Upload a local file to the configured GCS bucket.

    Returns the ``gs://`` URI on success, or ``None`` on failure.
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)
        uri = f"gs://{GCS_BUCKET_NAME}/{destination_blob_name}"
        logger.info(f"GCS upload succeeded: {uri}")
        return uri
    except Exception as e:
        logger.error(f"GCS upload failed for {source_file_name}: {e}")
        return None
