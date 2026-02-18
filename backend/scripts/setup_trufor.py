#!/usr/bin/env python3
"""
TruFor Model Weights Setup Script
Downloads model weights from the official TruFor repository.
"""

import os
import sys
import hashlib
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

# Configuration
WEIGHTS_URL = "https://www.grip.unina.it/download/prog/TruFor/TruFor_weights.zip"
EXPECTED_MD5 = "7bee48f3476c75616c3c5721ab256ff8"
WEIGHTS_DIR = Path("components/trufor/core/weights")
WEIGHTS_FILE = WEIGHTS_DIR / "trufor.pth.tar"
TEMP_ZIP = "TruFor_weights.zip"


def calculate_md5(filepath, chunk_size=8192):
    """Calculate MD5 hash of a file."""
    md5 = hashlib.md5()
    with open(filepath, 'rb') as f:
        while chunk := f.read(chunk_size):
            md5.update(chunk)
    return md5.hexdigest()


def download_file(url, output_path):
    """Download file with progress indication."""
    print(f"Downloading from: {url}")
    print("Size: ~249 MB")
    print("")
    
    try:
        # Create request with user agent to avoid blocks
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urlopen(req) as response:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Show progress
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        bar_length = 40
                        filled = int(bar_length * downloaded / total_size)
                        bar = '=' * filled + '-' * (bar_length - filled)
                        print(f'\r[{bar}] {percent:.1f}% ({downloaded}/{total_size} bytes)', end='')
                    else:
                        print(f'\rDownloaded: {downloaded} bytes', end='')
            
            print()  # New line after progress
            
    except URLError as e:
        print(f"\nError downloading file: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        sys.exit(1)


def main():
    print("=" * 42)
    print("TruFor Model Weights Setup")
    print("=" * 42)
    print()
    
    # Check if weights already exist
    if WEIGHTS_FILE.exists():
        print(f"✓ TruFor weights already exist at: {WEIGHTS_FILE}")
        print("  Skipping download. Delete the file to re-download.")
        return 0
    
    # Create weights directory
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Download weights
    print("Downloading TruFor weights from official source...")
    download_file(WEIGHTS_URL, TEMP_ZIP)
    
    # Verify MD5 checksum
    print("\nVerifying download integrity...")
    actual_md5 = calculate_md5(TEMP_ZIP)
    
    if actual_md5 != EXPECTED_MD5:
        print("Error: MD5 checksum mismatch!")
        print(f"Expected: {EXPECTED_MD5}")
        print(f"Got:      {actual_md5}")
        print("The download may be corrupted. Please try again.")
        os.remove(TEMP_ZIP)
        return 1
    
    print("✓ Checksum verified successfully")
    
    # Extract weights
    print("\nExtracting weights...")
    try:
        with zipfile.ZipFile(TEMP_ZIP, 'r') as zip_ref:
            zip_ref.extractall(WEIGHTS_DIR)
    except zipfile.BadZipFile:
        print("Error: Downloaded file is not a valid zip file.")
        os.remove(TEMP_ZIP)
        return 1
    
    # Handle nested weights directory (zip contains weights/trufor.pth.tar)
    nested_weights = WEIGHTS_DIR / "weights" / "trufor.pth.tar"
    if nested_weights.exists() and not WEIGHTS_FILE.exists():
        import shutil
        shutil.move(str(nested_weights), str(WEIGHTS_FILE))
        # Clean up empty nested directory
        try:
            (WEIGHTS_DIR / "weights").rmdir()
        except OSError:
            pass  # Directory not empty, leave it
    
    # Clean up
    os.remove(TEMP_ZIP)
    
    # Verify extraction
    if WEIGHTS_FILE.exists():
        file_size = WEIGHTS_FILE.stat().st_size / (1024 * 1024)  # Convert to MB
        print(f"✓ Successfully extracted weights to: {WEIGHTS_FILE}")
        print(f"  File size: {file_size:.1f} MB")
        print()
        print("=" * 42)
        print("Setup Complete!")
        print("=" * 42)
        return 0
    else:
        print(f"Error: Expected file not found after extraction: {WEIGHTS_FILE}")
        print("Please check the zip file contents.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
