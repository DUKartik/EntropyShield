import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.policy_engine import extract_rules_from_text
import logging

logging.basicConfig(level=logging.INFO)

policy_doc = "Any transaction above $10,000 made through the 'Wire' payment format must be thoroughly investigated for potential money laundering."

try:
    results = extract_rules_from_text(policy_doc, "Global Compliance Policy")
    print("\n--- Final Output ---")
    import json
    print(json.dumps(results, indent=2))
except Exception as e:
    print(f"FAILED: {e}")
