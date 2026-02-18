import os
from dotenv import load_dotenv

load_dotenv()

# Load Thresholds
SEG_MIN = float(os.getenv("SEGFORMER_MIN_CONFIDENCE", 0.50))
SEG_NEG = float(os.getenv("SEGFORMER_VALID_NEGATIVE_THRESHOLD", 0.70))
SEG_STRONG = float(os.getenv("SEGFORMER_STRONG_SIGNAL_THRESHOLD", 0.85))

FORENSIC_DECISION_TREE = {
    "segformer": {
        "description": "Visual Splicing Detection (ROI-based)",
        "rules": [
            {
                "condition": f"confidence_score < {SEG_MIN}",
                "action": "IGNORE_DETECTION",
                "reason": "Signal too weak. Treat as Compression Artifacts."
            },
            {
                "condition": f"is_tampered == False AND confidence_score < {SEG_NEG}",
                "action": "MARK_VALID_NEGATIVE",
                "reason": "Tool successfully confirmed no tampering found."
            },
            {
                "condition": "ROI_contents IS 'text' OR 'solid_color' OR 'ui_element'",
                "action": "IGNORE_DETECTION",
                "reason": "False Positive: Model hallucinates on sharp contrast edges."
            },
            {
                "condition": f"confidence_score >= {SEG_STRONG} AND ROI_contents IS 'natural_texture' OR 'face' OR 'complex_object'",
                "action": "MARK_VALID_POSITIVE",
                "reason": "Strong signal on valid complex region."
            }
        ]
    },
    "trufor": {
        "description": "Dense Pixel-Level Anomaly Detection",
        "rules": [
            {
                "condition": "ROI_contents IS 'text_overlay' OR 'printed_text'",
                "action": "IGNORE_DETECTION",
                "reason": "False Positive: Text lacks camera sensor noise (PRNU), causing predictable drift."
            },
            {
                "condition": "ROI_contents IS 'scan_border' OR 'black_margin'",
                "action": "IGNORE_DETECTION",
                "reason": "False Positive: Scanner artifacts."
            },
            {
                "condition": "detection_area < 2% of total_image",
                "action": "IGNORE_DETECTION",
                "reason": "Noise speckles. Ignore unless high confidence cluster."
            }
        ]
    },
    "ela": {
        "description": "Error Level Analysis (Compression Gradients)",
        "rules": [
            {
                "condition": "High Error Rate ONLY on 'High Contrast Edges' (Text)",
                "action": "IGNORE_DETECTION",
                "reason": "Physics Artifact: JPEG compression always fails on sharp edges."
            },
            {
                "condition": "High Error Rate on 'Flat Surface' (Skin, Wall, Paper)",
                "action": "MARK_VALID_POSITIVE",
                "reason": "Valid anomaly: Flat surfaces should compress uniformly."
            }
        ]
    },
    "dct": {
        "description": "DCT Quantization & Histogram Analysis",
        "rules": [
            {
                "condition": "ROI_contents IS 'blocking_map_cluster' AND aligns_to_8x8_grid == True",
                "action": "MARK_VALID_POSITIVE",
                "reason": "Valid 8x8 grid disruption indicates spliced JPEG data."
            },
            {
                "condition": "ROI_contents IS 'blocking_map_cluster' AND aligns_to_8x8_grid == False",
                "action": "IGNORE_DETECTION",
                "reason": "Noise: Detection does not align with JPEG 8x8 blocks."
            },
            {
                "condition": "analysis_type IS 'histogram_periodicity' AND ROI_size_pixels < 65536",
                "action": "IGNORE_DETECTION",
                "reason": "Insufficient data points for reliable histogram analysis on small ROI."
            },
            {
                "condition": "grid_phase_shift != (0,0)",
                "action": "MARK_VALID_POSITIVE",
                "reason": "Grid misalignment indicates cropped content pasted from source with different alignment."
            }
        ]
    },
    "eof": {
        "description": "End-of-File Data Inspection",
        "rules": [
            {
                "condition": "post_eof_data_size > 10240",
                "action": "MARK_VALID_POSITIVE",
                "reason": "Large data block (>10KB) after EOF marker indicates likely Steganography or Malware."
            },
            {
                "condition": "file_system_size != internal_structure_size",
                "action": "MARK_VALID_POSITIVE",
                "reason": "File size mismatch indicates appended hidden data."
            },
            {
                "condition": " multiple_eof_markers == True",
                "action": "IGNORE_DETECTION",
                "reason": "Standard PDF incremental update structure. Not inherently malicious."
            },
            {
                "condition": "post_eof_data IS 'null_bytes' OR 'xmp_padding'",
                "action": "IGNORE_DETECTION",
                "reason": "Benign system padding or editor metadata artifacts."
            }
        ]
    },
    "metadata": {
        "description": "EXIF/XMP Inconsistency Analysis",
        "rules": [
            {
                "condition": "software_make_conflict == True",
                "action": "MARK_VALID_POSITIVE",
                "reason": "Conflict between Camera Make and Editing Software traces."
            },
            {
                "condition": "thumbnail_mismatch == True",
                "action": "MARK_VALID_POSITIVE",
                "reason": "Embedded thumbnail differs from main image (edit did not update thumb)."
            },
            {
                "condition": "modify_date < create_date",
                "action": "MARK_VALID_POSITIVE",
                "reason": "Time Travel: Modification date predates creation date."
            },
            {
                "condition": "gps_timezone_mismatch == True",
                "action": "MARK_VALID_POSITIVE",
                "reason": "GPS location contradicts timestamp time zone."
            },
            {
                "condition": "metadata_fields IS 'empty' OR 'stripped'",
                "action": "IGNORE_DETECTION",
                "reason": "Privacy stripping by social media platforms is not forgery."
            }
        ]
    },
    "orphan": {
        "description": "Orphaned Object Detection (PDF/structure)",
        "rules": [
            {
                "condition": "unreferenced_object_found == True",
                "action": "MARK_VALID_POSITIVE",
                "reason": "Hidden object exists in file body but missing from XREF table."
            },
            {
                "condition": "deleted_object_stream_found == True",
                "action": "MARK_VALID_POSITIVE",
                "reason": "Residual data from previous version found in deleted stream."
            },
            {
                "condition": "slack_space_fragment_found == True",
                "action": "MARK_VALID_POSITIVE",
                "reason": "File header found in disk slack space (deleted file fragment)."
            },
            {
                "condition": "object_type IS 'font_descriptor' OR 'zero_length'",
                "action": "IGNORE_DETECTION",
                "reason": "Common benign PDF generation artifact."
            }
        ]
    }
}

