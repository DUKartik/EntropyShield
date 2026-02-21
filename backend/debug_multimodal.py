import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.policy_engine import extract_rules_from_document
import logging

logging.basicConfig(level=logging.INFO)

test_pdf_path = "test.pdf"

try:
    results = extract_rules_from_document(test_pdf_path, "Multimodal Test Policy")
    print("\n--- Final Output ---")
    import json
    print(json.dumps(results, indent=2))
except Exception as e:
    print(f"FAILED: {e}")
