import asyncio
from datetime import datetime
import json
import os
from dotenv import load_dotenv

# vertexai is NOT imported at module level — google-cloud-aiplatform has a heavy
# import chain (~29 s on first load). It is imported lazily inside
# run_semantic_reasoning() which only runs when a document is uploaded.

load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", os.getenv("PROJECT_ID", "your-project-id"))
REGION = os.getenv("REGION", "asia-south1")
from prompts.model_context import FORENSIC_DECISION_TREE

def run_semantic_reasoning_sync_wrapper(gcs_uri, mime_type, local_report):
    """
    Synchronous wrapper for legacy support if needed, but we should switch to async.
    """
    pass 

async def run_semantic_reasoning(gcs_uri, mime_type="application/pdf", local_report=None, pipeline_type="structural"):
    """
    Sends a file from GCS directly to Gemini 1.5 Pro for forensic analysis.
    Now ASYNC to prevent blocking the main event loop.
    """
    # Lazy imports: vertexai only loads the first time this function is called
    import vertexai  # noqa: PLC0415
    from vertexai.generative_models import GenerativeModel, Part  # noqa: PLC0415
    try:
        vertexai.init(project=PROJECT_ID, location=REGION)
    except Exception as e:
        pass  # Already initialised or placeholder ID — handled below

    try:
        # Reference the file in the Bucket (Zero download latency!)
        document_part = Part.from_uri(
            uri=gcs_uri,
            mime_type=mime_type
        )

        # Prepare Context String from Local Report
        local_context = "No prior local analysis available."
        if local_report:
            # SANITIZATION: Remove heavy Base64 strings to prevent Token Limit Error
            def sanitize_data(data):
                if isinstance(data, dict):
                    return {k: sanitize_data(v) for k, v in data.items() if k not in ['heatmap_image', 'ela_image', 'noise_map']}
                elif isinstance(data, list):
                    # Truncate long lists (e.g., histogram values)
                    if len(data) > 50 and all(isinstance(x, (int, float)) for x in data):
                        return data[:10] + [f"... {len(data)-10} more items ..."]
                    return [sanitize_data(item) for item in data]
                elif isinstance(data, str):
                    # Safety check: if a string looks like a base64 image (starts with data:image), drop it
                    if len(data) > 1000 and "data:image" in data[:50]:
                        return "<Base64 Image Data Omitted>"
                    if len(data) > 5000: # General truncation for massive logs
                        return data[:1000] + "... (truncated)"
                return data

            # We want to provide the FULL details to the AI so it can explain everything
            # serialized in a readable format.
            clean_report = sanitize_data(local_report) # Create deep-ish copy via recursion
            
            details = clean_report.get('details', {})
            flags = clean_report.get('flags', [])
            score = clean_report.get('score', 0)
            
            # Create a clean summary object
            context_data = {
                "local_risk_score": score,
                "technical_flags": flags,
                "detailed_metrics": details
            }
            
            local_context = f"""
            FULL LOCAL FORENSIC ANALYSIS DATA:
            {json.dumps(context_data, indent=2)}
            """

        # 3. Define the Prompt (The one above)
        prompt = """
        Analyze the attached document using the provided forensic context.
        """
        
        now = datetime.now()
        # Explicit date format to prevent LLM hallucinations (e.g., thinking 30/01 is future of 31/01)
        current_date_str = f"{now.strftime('%d %B %Y')} (Day: {now.day}, Month: {now.month}, Year: {now.year})"

        system_instruction = f"""
        YOU ARE A LOGIC ENGINE, NOT A CREATIVE WRITER.
        Your job is to EXECUTE the "FORENSIC_DECISION_TREE" on the provided "local_report".

        PIPELINE CONTEXT:
        - Pipeline Used: {pipeline_type}
        - IMPORTANT: When digital signatures are detected, the system ONLY runs cryptographic validation.
        - This means: Visual forensics (SegFormer, TruFor, ELA) and structural checks (metadata, EOF markers) are SKIPPED.
        - DO NOT flag missing visual or structural data as suspicious when pipeline_type is "cryptographic".
        - The cryptographic pipeline is the MOST TRUSTED path - if a valid signature exists, the document is authentic.

        INPUT DATA:
        - Local Report: {json.dumps(local_context)} (Contains tool outputs) 
        - FORENSIC_DECISION_TREE: {json.dumps(FORENSIC_DECISION_TREE, indent=2)}
        - GCS Image: (The visual evidence)

        ALGORITHM:
        **TOOL-BASED CHECK (SegFormer, TruFor, ELA)**:
           - LOOK at the "bounding_boxes" or "heatmap" provided by the tool.
           - LOOK at the actual image region defined by those boxes.
           - MATCH against the "rules" in the Decision Tree.
           - ORDER OF PRECEDENCE:
             - IF specific rule matches -> OUTPUT that verdict.
             - IF multiple rules match -> "IGNORE_DETECTION" (Conservative approach).
             - IF no specific exclusion applies -> "MARK_VALID_POSITIVE" (Trust the tool).

        CRITICAL OVERRIDES:
        - IF a tool reports "is_tampered: false" AND confidence < 0.5:
          -> Verdict = "VALID" (The tool worked and found nothing).
          -> REASON: "Tool successfully confirmed no tampering found."
          -> DO NOT say "Invalid because confidence low". That is wrong. A negative result is a valid result.
        - IF a tool reports "is_tampered: true" BUT the ROI is text:
          -> Verdict = "INVALID" (False Positive).

        OUTPUT FORMAT (Strict JSON):
        {{
            "authenticity_score": (Integer 0-100)
                - Start at 100.
                - DEDUCT 20 points for each VALID_POSITIVE tool detection (SegFormer, TruFor, etc).
                - DEDUCT 20 points for your own Visual findings (Digital Overlays, etc).
                - DO NOT Deduct for INVALID/IGNORED tool detections.
                - SCORE CANNOT BE LESS THAN 0.
                - NOTE: Cryptographic validation is handled separately by the backend. Do NOT include it in your score.
            "validation_map": {{
                "segformer": {{ "verdict": "VALID" | "INVALID", "reason": "Matched Rule: [Text Overlay Exclusion]..." }},
                "trufor": {{ "verdict": "VALID" | "INVALID", "reason": "..." }},
                "ela": {{ "verdict": "VALID" | "INVALID", "reason": "..." }},
                "metadata": {{ "verdict": "VALID" | "INVALID", "reason": "..." }}
            }},
            "flagged_issues": [List of strings],
            "summary": (String) - High-level executive summary.,
            "reasoning": (String) - detailed explanation.
        }}
        """
        # 4. Generate Content (ASYNC with Timeout)
        # We set temperature to 0.0 for maximum factual consistency
        
        # Initialize model with system instructions
        model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
        model = GenerativeModel(model_name, system_instruction=system_instruction)

        # 55-Second Timeout for Agentic Reasoning to prevent UI hanging
        try:
            response = await asyncio.wait_for(
                model.generate_content_async(
                    [document_part, prompt],
                    generation_config={"response_mime_type": "application/json", "temperature": 0.0}
                ),
                timeout=55.0
            )
        except asyncio.TimeoutError:
            return {
                "authenticity_score": 50, # Neutral fallback
                "flagged_issues": ["Agentic Reasoning Timed Out (High Load)"],
                "summary": "The AI reasoning layer could not complete in time. Falling back to technical analysis only.",
                "reasoning": "System processing timeout. Technical signals (metadata, visual, crypto) remain valid.",
                "validation_map": {}, 
                "model_name": model_name
            }

        # 5. Parse and Return
        result = json.loads(response.text)
        result['model_name'] = model_name
        return result

    except Exception as e:
        return {"error": f"Reasoning layer failed: {str(e)}", "authenticity_score": 50, "reasoning": "Processing Error"}
