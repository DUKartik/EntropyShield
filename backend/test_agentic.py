import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.policy_engine import extract_rules_from_text
import logging

# Configure logger to see the agentic loop in the console
logging.basicConfig(level=logging.INFO)

policy_doc = """
### Anti-Money Laundering (AML) Rules
1. Any transaction above $10,000 made through the 'Wire' payment format must be thoroughly investigated for potential money laundering.
2. If there's a GDPR violation involving a fine greater than 500,000 EUR, it needs to be escalated to the compliance board immediately.
"""

print("Starting Agentic Extraction Test...")
results = extract_rules_from_text(policy_doc, "Global Compliance Policy")

print("\n--- Final Output ---")
import json
print(json.dumps(results, indent=2))
