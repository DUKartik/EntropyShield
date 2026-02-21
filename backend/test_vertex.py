import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.policy_engine import extract_rules_from_text

# Provide a simple policy text
policy = "All expenses above $50 must have a receipt."
print("Running Vertex AI extraction...")
result = extract_rules_from_text(policy, "Test Policy")
print(result)
