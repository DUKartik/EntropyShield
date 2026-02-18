from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import shutil
import uuid
import time
from contextlib import asynccontextmanager

from services.pipeline_orchestrator import determine_pipeline, PipelineType, analyze_structural, analyze_visual, analyze_cryptographic
from services.forensic_reasoning import run_semantic_reasoning
from pypdf import PdfReader
from google.cloud import storage
from dotenv import load_dotenv
from pathlib import Path
from services.scoring_engine import calculate_final_score
from utils.debug_logger import debug_router, get_logger

# New Services for Compliance
from services.database_connector import init_mock_db, execute_compliance_query, get_db_connection
from services.policy_engine import extract_rules_from_text, save_policy, get_all_policies
from services.compliance_monitor import run_compliance_check

# Initialize Logger
logger = get_logger()

load_dotenv(override=True)

UPLOAD_DIR = "uploads"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Preload heavy models to avoid cold-start hangs
    logger.info("Lifespan: Starting Application...")
    
    # 0. Initialize Mock Database for Compliance Demo
    try:
        logger.info("Lifespan: Initializing Mock Company Database...")
        init_mock_db()
        logger.info("Lifespan: Mock Database Ready.")
    except Exception as e:
        logger.error(f"Lifespan: Failed to init mock DB: {e}")

    # 1. Warmup TruFor Engine
    # This loads the weights into memory so the first request doesn't timeout
    try:
        logger.info("Lifespan: Warming up TruFor Engine (this may take a moment)...")
        from components.trufor.engine import TruForEngine
        # Instantiating the singleton forces the model to load
        TruForEngine()
        logger.info("Lifespan: TruFor Engine Warmed Up Successfully.")
    except Exception as e:
        logger.error(f"Lifespan: Failed to warm up TruFor: {e}")
        # We don't raise here to allow the app to start even if TruFor fails (it will fail gracefully on request)

    yield
    # Shutdown


app = FastAPI(title="VeriDoc API", description="Document Forgery Detection System", lifespan=lifespan)


# GCS Configuration
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "veridoc-uploads")

def cleanup_stale_files(directory: Path, max_age_seconds: int = 300):
    """
    Background task to remove files older than max_age_seconds.
    Running in background prevents blocking the upload response.
    """
    try:
        current_time = time.time()
        if not directory.exists():
            return
            
        for item in directory.iterdir():
            try:
                # Delete files/dirs older than threshold
                if item.stat().st_mtime < current_time - max_age_seconds:
                    if item.is_file() or item.is_symlink():
                        item.unlink()
                        print(f"Background Cleaned: {item.name}")
                    elif item.is_dir():
                        shutil.rmtree(item)
                        print(f"Background Cleaned Dir: {item.name}")
            except Exception as e:
                # Non-blocking tolerance - logging only
                print(f"Background cleanup warning for {item.name}: {e}")
    except Exception as e:
        print(f"Background cleanup process error: {e}")

def upload_to_gcs(source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(destination_blob_name)

        blob.upload_from_filename(source_file_name)

        return f"gs://{GCS_BUCKET_NAME}/{destination_blob_name}"
    except Exception as e:
        print(f"GCS Upload Failed: {e}")
        return None

os.makedirs(UPLOAD_DIR, exist_ok=True)


# CORS Setup
# Explicitly list allowed origins to support allow_credentials=True
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "https://veridoc-frontend-808108840598.asia-south1.run.app",
    "http://localhost:8081",
    "http://localhost:8081",
]

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://veridoc-frontend-.*\.run\.app|http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
app.mount("/static/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Include Debug Router
app.include_router(debug_router, prefix="/api")

@app.get("/")
def read_root():
    return {"status": "online", "system": "VeriDoc Agentic Core"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/api/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    """
    Uploads a document and returns a task ID for WebSocket analysis.
    """
    try:
        # 1. Schedule Cleanup (Non-blocking)
        # Using pathlib for modern Python 3.12+ style handling
        upload_path = Path(UPLOAD_DIR)
        
        # We trigger cleanup of OLD files (stale from previous sessions)
        # We assume 10 minutes (600s) is enough for a session. 
        # For immediate responsiveness, we don't wipe everything synchronously.
        background_tasks.add_task(cleanup_stale_files, upload_path, 600)
        
        # 2. Save New File
        print(f"Receiving file: {file.filename}")
        file_ext = file.filename.split('.')[-1].lower()
        task_id = str(uuid.uuid4())
        safe_filename = f"{task_id}.{file_ext}"
        
        logger.info(f"Processing Upload: {safe_filename} (Org: {file.filename})")
        
        # Ensure directory exists
        upload_path.mkdir(parents=True, exist_ok=True)
        
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {
            "task_id": task_id,
            "filename": file.filename,
            "file_path": file_path,
            "content_type": file.content_type
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws/analyze/{task_id}")
async def analyze_document(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        # Locate file (reconstruct path based on task_id - simplistic approach)
        # In a real app, look up from DB. Here we search dirtily or assume standard naming if passed, 
        # but better to pass filename in initial handshake or just find the file.
        # Let's look for the file with this UUID in the uploads dir.
        found_file = None
        for f in os.listdir(UPLOAD_DIR):
            if f.startswith(task_id):
                found_file = f
                break
        
        if not found_file:
            await websocket.send_json({"status": "error", "message": "File not found"})
            await websocket.close()
            return

        file_path = os.path.join(UPLOAD_DIR, found_file)
        filename = found_file # approximate original name not preserved in FS but okay for logic
        file_ext = found_file.split('.')[-1]
        
        # Improved MIME Type detection
        mime_type = "application/pdf" if file_ext.lower() == "pdf" else f"image/{file_ext.lower().replace('jpg', 'jpeg')}"
        
        # -------------------
        
        await websocket.send_json({"status": "info", "message": "Starting analysis...", "step": "INIT"})

        # Text Extraction
        text_content = ""
        if file_ext == 'pdf':
            await websocket.send_json({"status": "info", "message": "Extracting text content...", "step": "TEXT_EXTRACTION"})
            try:
                reader = PdfReader(file_path)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        text_content += text + "\n"
            except Exception:
                pass 

        # Pipeline Determination
        await websocket.send_json({"status": "info", "message": "Determining appropriate forensic pipeline...", "step": "PIPELINE_SELECTION"})
        # BUG FIX: Pass full file_path so the orchestrator can open the file
        pipeline_type = determine_pipeline(file_path, mime_type)
        await websocket.send_json({"status": "info", "message": f"Selected Pipeline: {pipeline_type.value}", "step": "PIPELINE_SELECTED"})

        # Execution
        await websocket.send_json({"status": "info", "message": f"Running {pipeline_type.value} analysis...", "step": "ANALYSIS_RUNNING"})
        
        async def send_progress(msg):
            await websocket.send_json({"status": "info", "message": msg, "step": "ANALYSIS_SUBSTEP"})

        report = {}
        if pipeline_type == PipelineType.STRUCTURAL:
             report = await analyze_structural(file_path, callback=send_progress)
        elif pipeline_type == PipelineType.VISUAL:
             report = await analyze_visual(file_path, callback=send_progress)
        elif pipeline_type == PipelineType.CRYPTOGRAPHIC:
             report = await analyze_cryptographic(file_path, callback=send_progress)
        else:
             report = {"error": "Unsupported pipeline requested"}
        
        await websocket.send_json({"status": "info", "message": "Pipeline analysis complete.", "step": "ANALYSIS_COMPLETE", "data": report})

        # GCS Upload
        await websocket.send_json({"status": "info", "message": "Uploading to secure cloud storage...", "step": "GCS_UPLOAD"})
        gcs_uri = upload_to_gcs(file_path, found_file)
        
        reasoning_result = {"authenticity_score": 50, "summary": "AI Skipped (GCS Fail)"} # Fallback default

        if not gcs_uri:
             await websocket.send_json({"status": "warning", "message": "GCS Upload Failed - Skipping AI, running Local Forensics only."})
        else:
            # Semantic Reasoning
            model_name_log = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
            await websocket.send_json({"status": "info", "message": f"Initializing {model_name_log} Reasoning Agent...", "step": "REASONING_START"})
            
            # Pass local report to reasoning
            reasoning_result = await run_semantic_reasoning(gcs_uri, mime_type=mime_type, local_report=report, pipeline_type=pipeline_type.value)
        
        # --- NEW DETERMINISTIC SCORING (Pseudo-RAG) ---
        logger.info(f"DEBUG: Pipeline Type -> {pipeline_type.value}")
        logger.info(f"DEBUG: Report Keys -> {list(report.keys())}")
        if "details" in report:
            logger.info(f"DEBUG: Report Details Keys -> {list(report['details'].keys())}")
            if "signatures" in report["details"]:
                logger.info(f"DEBUG: Found {len(report['details']['signatures'])} signatures in report.")
            else:
                logger.info("DEBUG: 'signatures' key MISSING in report details.")
        
        scoring_output = calculate_final_score(
            pipeline_type=pipeline_type.value,
            local_report=report,
            ai_result=reasoning_result
        )
        
        # Inject results
        reasoning_result["authenticity_score"] = scoring_output["authenticity_score"]
        reasoning_result["score_breakdown"] = scoring_output["breakdown"]
        reasoning_result["precise_scores"] = scoring_output.get("precise_scores", {})
        reasoning_result["structural_breakdown_list"] = scoring_output.get("structural_breakdown_list", [])
        reasoning_result["scoring_weights"] = scoring_output.get("weights", {})
        reasoning_result["verdict"] = scoring_output["verdict"]
        reasoning_result["threshold"] = scoring_output["threshold"]
        reasoning_result["original_ai_score"] = scoring_output["ai_dry_score"]
        reasoning_result["weighted_tech"] = scoring_output.get("weighted_tech", 0)
        
        # --- FIX: INJECT TRUFOR BOXES ---
        # The frontend expects boxes in reasoning_result["bounding_boxes"] as objects with "box_2d"
        # TruFor generates them in report["details"]["trufor"]["bounding_boxes"] as raw lists
        try:
            boxes_to_inject = []
            
            # Case A: Visual Pipeline (Direct Image)
            # 1. TruFor
            direct_tf_boxes = report.get("details", {}).get("trufor", {}).get("bounding_boxes", [])
            if direct_tf_boxes:
                boxes_to_inject.extend(direct_tf_boxes)
                
            # Case B: Structural Pipeline (PDF Embedded Images)
            analyzed_imgs = report.get("details", {}).get("analyzed_images", [])
            for img_entry in analyzed_imgs:
                # Access deeply nested visual report
                v_rep = img_entry.get("visual_report", {}).get("details", {})
                
                # 1. TruFor
                v_tf_boxes = v_rep.get("trufor", {}).get("bounding_boxes", [])
                if v_tf_boxes:
                    logger.info(f"Found {len(v_tf_boxes)} TruFor boxes in embedded image {img_entry.get('index')}")
                    boxes_to_inject.extend(v_tf_boxes)

            if boxes_to_inject:
                if "bounding_boxes" not in reasoning_result:
                    reasoning_result["bounding_boxes"] = []
                
                # Append boxes to any existing AI boxes
                for box in boxes_to_inject:
                    reasoning_result["bounding_boxes"].append({
                        "box_2d": box, 
                        "label": "potential_manipulation"
                    })
                logger.info(f"Injected total {len(boxes_to_inject)} TruFor bounding boxes into response.")
        except Exception as e:
            logger.error(f"Error injecting TruFor boxes: {e}")
        # --------------------------------
        
        # Final Result
        file_stats = os.stat(file_path)
        final_response = {
            "task_id": task_id,
            "filename": filename,
            "file_size": file_stats.st_size,
            "mime_type": mime_type,
            "pipeline_used": pipeline_type.value,
            "report": report,
            "reasoning": reasoning_result
        }
        
        # ------------------
        
        await websocket.send_json({"status": "complete", "message": "Analysis successfully completed.", "step": "COMPLETE", "data": final_response})
        await websocket.close()

    except WebSocketDisconnect:
        print(f"Client disconnected task {task_id}")
    except Exception as e:
        await websocket.send_json({"status": "error", "message": str(e)})
        logger.error(f"Analysis Failed {task_id}: {str(e)}")
        convert_e = str(e) # avoid f-string inside await if fearful







@app.get("/api/debug/trufor")
def debug_trufor_status():
    """
    Diagnostic endpoint to check if TruFor weights exist and model is loaded.
    Attempts to RELOAD if not loaded to capture the specific error.
    """
    try:
        import sys
        from components.trufor.engine import TruForEngine, trufor_core_path, TruForFactory, default_cfg
        
        # Check Paths
        weights_path_primary = trufor_core_path / 'weights' / 'trufor.pth.tar'
        conf_path = trufor_core_path / 'lib' / 'config' / 'trufor_ph3.yaml'
        
        load_error = None
        # Attempt manual reload if model is missing to catch the error
        if TruForEngine._instance and TruForEngine._instance._model is None:
            try:
                print("DEBUG: Forcing manual reload...")
                # Replicate _load_model logic to catch the specific line failing
                if TruForFactory is None:
                    raise ImportError("TruForFactory is None (imports failed)")
                
                cfg = default_cfg
                if conf_path.exists():
                    cfg.merge_from_file(str(conf_path))
                else:
                    load_error = f"Config file missing at {conf_path}"

                if not load_error:
                    # Try creating model structure
                    model = TruForFactory(cfg)
                    
                    # Try loading weights
                    checkpoint = torch.load(weights_path_primary, map_location="cpu", weights_only=False)
                    model.load_state_dict(checkpoint['state_dict'])
                    model.eval()
                    
                    # If we got here, it actually works?!
                    TruForEngine._instance._model = model
            except Exception as e:
                import traceback
                load_error = f"{str(e)}\n{traceback.format_exc()}"

        status = {
            "primary_weights_path": str(weights_path_primary),
            "primary_exists": weights_path_primary.exists(),
            "conf_path": str(conf_path),
            "conf_exists": conf_path.exists(),
            "model_loaded": TruForEngine._instance._model is not None if TruForEngine._instance else False,
            "load_last_error": load_error,
            "sys_path": sys.path,
        }
        return status
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


# --- COMPLIANCE AUTOMATION ENDPOINTS ---

@app.post("/api/policy/upload")
async def upload_policy(
    file: UploadFile = File(...),
    check_tampering: str =  "false"
):
    """
    Ingests a Policy PDF, uses AI to extract rules, and saves them.
    Optional: Runs a tamper check if check_tampering="true".
    """
    try:
        # Save file info (in memory or storage)
        print(f"Processing Policy: {file.filename} (Tamper Check: {check_tampering})")
        
        # Read PDF content
        content = await file.read()
        # Create temp file to read with pypdf
        temp_path = f"uploads/temp_policy_{uuid.uuid4()}.pdf"
        with open(temp_path, "wb") as f:
            f.write(content)

        # --- OPTIONAL TAMPER CHECK ---
        if check_tampering.lower() == "true":
            print("Running Policy Tamper Check...")
            # Run fast structural analysis
            forensic_report = await analyze_structural(temp_path)
            
            # Simple decision logic: If high risk, reject
            score = forensic_report.get("score", 0.0)
            flags = forensic_report.get("flags", [])
            
            if score > 0.5:
                print(f"Tamper Check Failed! Score: {score}")
                # Clean up and reject
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                # Format error details
                flag_msg = "; ".join(flags[:3])
                raise HTTPException(
                    status_code=400, 
                    detail=f"Security Alert: Document integrity check failed (Score: {score:.2f}). Reasons: {flag_msg}"
                )
            print("Tamper Check Passed.")

        # Extract text

            
        # Extract text
        text = ""
        try:
            reader = PdfReader(temp_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        # AI Extraction
        rules = extract_rules_from_text(text, file.filename)
        
        # Save Policy
        policy_id = str(uuid.uuid4())
        saved_policy = save_policy(policy_id, file.filename, rules)
        
        return {"status": "success", "policy_id": policy_id, "data": saved_policy}
    except Exception as e:
        logger.error(f"Policy Upload Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/compliance/run")
def trigger_compliance_check(policy_id: str = None):
    """
    Triggers the compliance monitor to check for violations.
    """
    try:
        results = run_compliance_check(policy_id)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/database/preview")
def preview_database():
    """
    Returns a preview of the mock database content.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        data = {}
        tables = ["expenses", "employees", "contracts"]
        for table in tables:
            cursor.execute(f"SELECT * FROM {table} LIMIT 10")
            rows = cursor.fetchall()
            data[table] = [dict(row) for row in rows]
            
        conn.close()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
