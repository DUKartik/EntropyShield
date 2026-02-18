import sys
import os
import asyncio
import time
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import storage

# Ensure we can import from backend root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.pipeline_orchestrator import determine_pipeline, PipelineType, analyze_structural, analyze_visual
from services.forensic_reasoning import run_semantic_reasoning
# We import calculate_final_score to replicate the exact scoring logic used in main.py
from services.scoring_engine import calculate_final_score 

load_dotenv(override=True)

UPLOAD_DIR = Path("uploads") # Relative to where we run it, but better to be absolute
BACKEND_ROOT = Path(__file__).parent.parent
UPLOAD_DIR_ABS = BACKEND_ROOT / "uploads"
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "veridoc-uploads")

def get_latest_file():
    """Finds the most recently modified original file in uploads."""
    if not UPLOAD_DIR_ABS.exists():
        print(f"Error: Upload directory {UPLOAD_DIR_ABS} does not exist.")
        return None

    files = [f for f in UPLOAD_DIR_ABS.iterdir() if f.is_file()]
    # Filter out generated files (.ela.png, .noise.png, .trufor.png)
    files = [f for f in files if ".ela.png" not in f.name and ".noise.png" not in f.name and ".trufor.png" not in f.name]
    
    if not files:
        print("No files found in uploads.")
        return None

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    return latest_file

def upload_to_gcs_script(source_file_path, destination_blob_name):
    """Uploads a file to the bucket."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(destination_blob_name)

        print(f"Uploading {source_file_path.name} to GCS...")
        blob.upload_from_filename(str(source_file_path))

        return f"gs://{GCS_BUCKET_NAME}/{destination_blob_name}"
    except Exception as e:
        print(f"GCS Upload Failed: {e}")
        return None

async def dummy_callback(msg):
    # Simple redirect to stdout
    print(f"  [Analysis Log] {msg}")

async def main():
    print("=== VeriDoc AI Stress Test ===")
    
    # 1. Select File
    target_file = get_latest_file()
    if not target_file:
        return

    print(f"Target File: {target_file.name}")
    print("Regenerating Local Forensic Report (this ensures context is fresh)...")

    # 2. Local Analysis
    mime_type = "image/jpeg"
    if target_file.suffix.lower() == ".pdf":
        mime_type = "application/pdf"
    
    pipeline_type = determine_pipeline(str(target_file), mime_type)
    print(f"Pipeline: {pipeline_type.value}")

    report = {}
    start_time = time.time()
    try:
        if pipeline_type == PipelineType.STRUCTURAL:
             report = await analyze_structural(str(target_file), callback=dummy_callback)
        elif pipeline_type == PipelineType.VISUAL:
             report = await analyze_visual(str(target_file), callback=dummy_callback)
        else:
             print("Unsupported pipeline type.")
             return
    except Exception as e:
        print(f"Local Analysis Failed: {e}")
        return

    print(f"Local Analysis Complete ({time.time() - start_time:.2f}s). Score: {report.get('score', 'N/A')}")

    # 3. Upload to GCS
    # We use the filename as blob name to match main.py behavior roughly
    gcs_uri = upload_to_gcs_script(target_file, target_file.name)
    if not gcs_uri:
        print("Aborting due to GCS upload failure.")
        return

    # 4. Loop
    try:
        n_str = input("\nEnter number of AI query iterations to run (e.g. 5): ")
        n = int(n_str)
    except ValueError:
        print("Invalid number.")
        return

    print(f"\n--- Starting {n} AI Queries ---")
    print(f"Using Model: {os.getenv('GEMINI_MODEL_NAME', 'gemini-2.5-flash')}")
    
    results = []
    
    for i in range(1, n + 1):
        print(f"\n[Iteration {i}/{n}] Sending request...")
        iter_start = time.time()
        
        try:
            # Call the AI Wrapper
            ai_result = await run_semantic_reasoning(gcs_uri, mime_type=mime_type, local_report=report)
            print(f"DEBUG AI RESPONSE: {ai_result}")
            
            # Apply the Pseudo-RAG Scoring (Vital to match main.py logic)
            scoring_output = calculate_final_score(
                pipeline_type=pipeline_type.value,
                local_report=report,
                ai_result=ai_result
            )
            
            # Extract final score
            final_score = scoring_output["authenticity_score"]
            raw_ai_score = ai_result.get("authenticity_score", "N/A") 
            validation_map = ai_result.get("validation_map", {})
            flagged = ai_result.get("flagged_issues", [])
            breakdown = scoring_output.get("breakdown", {})
            
            duration = time.time() - iter_start
            
            print(f"  > Time: {duration:.2f}s")
            print(f"  > Final Score: {final_score}")
            print(f"  > Verdict: {scoring_output['verdict']}")
            print(f"  > AI Raw Score: {raw_ai_score}")
            print(f"  > Flags: {flagged}")
            print(f"  > Validation Map: {validation_map}")
            print(f"  > Breakdown: {breakdown}")
            
            results.append({
                "score": final_score,
                "ai_raw": raw_ai_score,
                "flags_count": len(flagged),
                "verdict": scoring_output['verdict']
            })
            
        except Exception as e:
            print(f"  > Error: {e}")
            results.append(None)
            
    # Summary
    print("\n=== Summary ===")
    valid_results = [r for r in results if r is not None]
    if valid_results:
        scores = [r["score"] for r in valid_results]
        print(f"Scores returned: {scores}")
        print(f"Min: {min(scores)}")
        print(f"Max: {max(scores)}")
        print(f"Avg: {sum(scores)/len(scores):.2f}")
        
        # Check stability
        if max(scores) - min(scores) > 5:
            print("WARNING: High variance detected (>5 points).")
        else:
            print("STABLE: Variance within 5 points.")
    else:
        print("No successful runs.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
