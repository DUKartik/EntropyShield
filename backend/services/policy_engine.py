import os
import google.generativeai as genai
from google.cloud import aiplatform
import vertexai
from vertexai.generative_models import GenerativeModel, Part
import json
import re

# Configure Vertex AI
# Configure Vertex AI
# Priority: GCP_PROJECT_ID -> GOOGLE_CLOUD_PROJECT -> Default
project_id = os.getenv("GCP_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT", "veridoc-frontend-808108840598"))
location = os.getenv("GCP_LOCATION", "us-central1")

try:
    vertexai.init(project=project_id, location=location)
except Exception as e:
    print(f"Warning: Failed to init Vertex AI: {e}")

def load_gemini_pro():
    return GenerativeModel("gemini-1.5-pro-001")

def extract_rules_from_text(policy_text: str, policy_name: str):
    """
    Uses Gemini 1.5 Pro to extract executable compliance rules from policy text.
    Returns a list of rule objects.
    """
    try:
        model = load_gemini_pro()
        
        prompt = f"""
        You are a Compliance Data Data Engineer. Your goal is to convert a human-readable policy document into executable SQL rules for a SQLite database.
        
        The database has the following tables:
        1. expenses (id, employee_id, category, amount, currency, date, description, status, merchant)
        2. employees (id, name, department, role, manager_id, location)
        3. contracts (id, vendor_name, amount, start_date, end_date, signed_by, status)
        
        POLICY DOCUMENT TITLE: {policy_name}
        POLICY CONTENT:
        {policy_text}
        
        --------------------------------------------------
        
        INSTRUCTIONS:
        1. Identify all distinct compliance rules in the text.
        2. For each rule, generate a SQL query that selects the VIOLATING records.
           - A result means a VIOLATION.
           - If the policy says "Expenses over 500 must be approved", the query should find expenses over 500 that are NOT approved.
           - Use generic SQL compatible with SQLite.
        3. Return a JSON array of objects with these fields:
           - "rule_id": Short string ID (e.g., "EXP-001")
           - "description": Human readable description of the rule.
           - "quote": The exact text from the policy extracted.
           - "sql_query": The SQL query to find violations.
           - "severity": "HIGH", "MEDIUM", or "LOW".
           
        OUTPUT FORMAT:
        Return ONLY valid JSON. Do not include markdown formatting or explanations.
        """
        
        response = model.generate_content(prompt)
        
        # Clean response (remove markdown backticks if present)
        text_resp = response.text.strip()
        if text_resp.startswith("```json"):
            text_resp = text_resp[7:-3]
        elif text_resp.startswith("```"):
            text_resp = text_resp[3:-3]
            
        return json.loads(text_resp)
        
    except Exception as e:
        print(f"Vertex AI Error: {e}")
        print("Falling back to MOCK rules for demonstration.")
        
        # FALLBACK MOCK RULES
        # so the user can test the UI even if they lack GCP permissions
        return [
            {
                "rule_id": "MOCK-EXP-001",
                "description": "High value expenses must be approved (Mock Rule)",
                "quote": "Fallback: Expenses over 1000 require approval",
                "sql_query": "SELECT * FROM expenses WHERE amount > 1000 AND status != 'APPROVED'",
                "severity": "HIGH"
            },
             {
                "rule_id": "MOCK-EXP-002",
                "description": "No expenses on weekends (Mock Rule)",
                "quote": "Fallback: Expenses incurred on Sat/Sun are not reimbursable",
                "sql_query": "SELECT * FROM expenses WHERE strftime('%w', date) IN ('0', '6')", 
                "severity": "MEDIUM"
            }
        ]
        
# Simple in-memory storage for demo purposes
# In prod, this would be in the DB
_active_policies = {} 

def save_policy(policy_id, name, rules):
    _active_policies[policy_id] = {
        "name": name,
        "rules": rules,
        "active": True
    }
    return _active_policies[policy_id]

def get_all_policies():
    return _active_policies

def seed_demo_policies():
    """
    Seeds built-in demo compliance policies so the system scan works
    out-of-the-box without requiring a manual policy upload.
    Only seeds if no policies are currently loaded.
    """
    if _active_policies:
        return  # Already have policies, don't overwrite

    demo_rules = [
        {
            "rule_id": "GDPR-001",
            "description": "High-value GDPR violations (fines over €1M)",
            "quote": "Data controllers must pay fines proportionate to the violation.",
            "sql_query": "SELECT * FROM gdpr_violations WHERE \"Price (EUR)\" > 1000000",
            "severity": "HIGH"
        },
        {
            "rule_id": "GDPR-002",
            "description": "Violations by large companies (fine > €500K)",
            "quote": "Large enterprises face higher penalties under GDPR.",
            "sql_query": "SELECT * FROM gdpr_violations WHERE \"Price (EUR)\" > 500000",
            "severity": "HIGH"
        },
        {
            "rule_id": "FIN-001",
            "description": "Suspicious financial transactions (potential laundering)",
            "quote": "Transactions flagged as suspicious must be reviewed.",
            "sql_query": "SELECT * FROM financial_transactions WHERE is_laundering = 1",
            "severity": "HIGH"
        },
        {
            "rule_id": "EXP-001",
            "description": "High-value expenses require approval",
            "quote": "All expenses over $1000 must be approved before reimbursement.",
            "sql_query": "SELECT * FROM expenses WHERE amount > 1000 AND status != 'APPROVED'",
            "severity": "HIGH"
        },
        {
            "rule_id": "EXP-002",
            "description": "Weekend expenses are not reimbursable",
            "quote": "Expenses incurred on Saturday or Sunday are not eligible for reimbursement.",
            "sql_query": "SELECT * FROM expenses WHERE strftime('%w', date) IN ('0', '6')",
            "severity": "MEDIUM"
        },
        {
            "rule_id": "EXP-003",
            "description": "Entertainment expenses over $500 need pre-approval",
            "quote": "Entertainment spending above $500 requires manager sign-off.",
            "sql_query": "SELECT * FROM expenses WHERE category = 'Entertainment' AND amount > 500 AND status != 'APPROVED'",
            "severity": "MEDIUM"
        },
    ]

    save_policy(
        policy_id="DEMO-POLICY-001",
        name="Built-in Compliance Ruleset (Demo)",
        rules=demo_rules
    )
    print("Seeded demo compliance policies.")
