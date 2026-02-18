#!/bin/bash
set -e

echo "=========================================="
echo "TruFor Model Weights Setup"
echo "=========================================="

# Configuration
WEIGHTS_URL="https://www.grip.unina.it/download/prog/TruFor/TruFor_weights.zip"
EXPECTED_MD5="7bee48f3476c75616c3c5721ab256ff8"
WEIGHTS_DIR="components/trufor/core/weights"
WEIGHTS_FILE="$WEIGHTS_DIR/trufor.pth.tar"
TEMP_ZIP="TruFor_weights.zip"

# Check if weights already exist
if [ -f "$WEIGHTS_FILE" ]; then
    echo "✓ TruFor weights already exist at: $WEIGHTS_FILE"
    echo "  Skipping download. Delete the file to re-download."
    exit 0
fi

# Create weights directory if it doesn't exist
mkdir -p "$WEIGHTS_DIR"

echo "Downloading TruFor weights from official source..."
echo "URL: $WEIGHTS_URL"
echo "Size: ~249 MB"
echo ""

# Download with progress bar
if command -v wget &> /dev/null; then
    wget --progress=bar:force -O "$TEMP_ZIP" "$WEIGHTS_URL"
elif command -v curl &> /dev/null; then
    curl -L --progress-bar -o "$TEMP_ZIP" "$WEIGHTS_URL"
else
    echo "Error: Neither wget nor curl is installed."
    echo "Please install one of them and try again."
    exit 1
fi

echo ""
echo "Verifying download integrity..."

# Verify MD5 checksum
if command -v md5sum &> /dev/null; then
    ACTUAL_MD5=$(md5sum "$TEMP_ZIP" | awk '{print $1}')
elif command -v md5 &> /dev/null; then
    ACTUAL_MD5=$(md5 -q "$TEMP_ZIP")
else
    echo "Warning: MD5 verification tool not found. Skipping checksum verification."
    ACTUAL_MD5="$EXPECTED_MD5"  # Skip verification
fi

if [ "$ACTUAL_MD5" != "$EXPECTED_MD5" ]; then
    echo "Error: MD5 checksum mismatch!"
    echo "Expected: $EXPECTED_MD5"
    echo "Got:      $ACTUAL_MD5"
    echo "The download may be corrupted. Please try again."
    rm -f "$TEMP_ZIP"
    exit 1
fi

echo "✓ Checksum verified successfully"
echo ""
echo "Extracting weights..."

# Extract the zip file
if command -v unzip &> /dev/null; then
    unzip -q "$TEMP_ZIP" -d "$WEIGHTS_DIR"
else
    echo "Error: unzip is not installed."
    echo "Please install unzip and try again."
    rm -f "$TEMP_ZIP"
    exit 1
fi

# Handle nested weights directory (zip contains weights/trufor.pth.tar)
if [ -f "$WEIGHTS_DIR/weights/trufor.pth.tar" ] && [ ! -f "$WEIGHTS_FILE" ]; then
    mv "$WEIGHTS_DIR/weights/trufor.pth.tar" "$WEIGHTS_FILE"
    rmdir "$WEIGHTS_DIR/weights" 2>/dev/null || true
fi

# Clean up
rm -f "$TEMP_ZIP"

# Verify extraction
if [ -f "$WEIGHTS_FILE" ]; then
    FILE_SIZE=$(du -h "$WEIGHTS_FILE" | cut -f1)
    echo "✓ Successfully extracted weights to: $WEIGHTS_FILE"
    echo "  File size: $FILE_SIZE"
    echo ""
    echo "=========================================="
    echo "Setup Complete!"
    echo "=========================================="
else
    echo "Error: Expected file not found after extraction: $WEIGHTS_FILE"
    echo "Please check the zip file contents."
    exit 1
fi
