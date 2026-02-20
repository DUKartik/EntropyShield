"""
routers/forensics.py
Document upload and WebSocket-based forensic analysis endpoints.
"""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
# pypdf imported lazily inside analyze_document() — keeps startup cost zero

from services.gcs_service import upload_to_gcs
from services.pipeline_orchestrator import (
    PipelineType,
    analyze_cryptographic,
    analyze_structural,
    analyze_visual,
    determine_pipeline,
)
from services.forensic_reasoning import run_semantic_reasoning
from services.scoring_engine import calculate_final_score
from utils.debug_logger import get_logger
from utils.file_utils import cleanup_stale_files

logger = get_logger()

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    """
    Accept a document upload, persist it to disk, and return a task_id that
    the client uses to open the WebSocket analysis stream.

    A background task is also scheduled to purge files older than 10 minutes,
    keeping the uploads directory clean without blocking the response.
    """
    try:
        # Schedule stale-file purge (non-blocking)
        background_tasks.add_task(cleanup_stale_files, UPLOAD_DIR, 600)

        file_ext = file.filename.split(".")[-1].lower()
        task_id = str(uuid.uuid4())
        safe_filename = f"{task_id}.{file_ext}"

        logger.info(f"Upload received: {safe_filename} (original: {file.filename})")

        file_path = UPLOAD_DIR / safe_filename
        with file_path.open("wb") as buffer:
            import shutil
            shutil.copyfileobj(file.file, buffer)

        return {
            "task_id": task_id,
            "filename": file.filename,
            "file_path": str(file_path),
            "content_type": file.content_type,
        }
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/analyze/{task_id}")
async def analyze_document(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint that streams per-step progress while running the full
    forensic pipeline, then emits a final ``complete`` message with the report.
    """
    await websocket.accept()

    async def send(status: str, message: str, step: str = "", data: dict = None):
        payload = {"status": status, "message": message}
        if step:
            payload["step"] = step
        if data is not None:
            payload["data"] = data
        await websocket.send_json(payload)

    try:
        # Locate the uploaded file (named <task_id>.<ext>)
        found_file = next(
            (f for f in os.listdir(UPLOAD_DIR) if f.startswith(task_id)), None
        )
        if not found_file:
            await send("error", "File not found")
            await websocket.close()
            return

        file_path = str(UPLOAD_DIR / found_file)
        file_ext = found_file.split(".")[-1].lower()
        mime_type = (
            "application/pdf"
            if file_ext == "pdf"
            else f"image/{file_ext.replace('jpg', 'jpeg')}"
        )

        await send("info", "Starting analysis...", "INIT")

        # ── Text extraction (PDFs only) ───────────────────────────────────────
        text_content = ""
        if file_ext == "pdf":
            await send("info", "Extracting text content...", "TEXT_EXTRACTION")
            try:
                from pypdf import PdfReader  # noqa: PLC0415
                reader = PdfReader(file_path)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        text_content += text + "\n"
            except Exception:
                pass  # Non-fatal — continue without text

        # ── Pipeline selection ────────────────────────────────────────────────
        await send("info", "Determining forensic pipeline...", "PIPELINE_SELECTION")
        pipeline_type = determine_pipeline(file_path, mime_type)
        await send("info", f"Selected pipeline: {pipeline_type.value}", "PIPELINE_SELECTED")

        # ── Pipeline execution ────────────────────────────────────────────────
        await send("info", f"Running {pipeline_type.value} analysis...", "ANALYSIS_RUNNING")

        async def progress(msg: str):
            await send("info", msg, "ANALYSIS_SUBSTEP")

        if pipeline_type == PipelineType.STRUCTURAL:
            report = await analyze_structural(file_path, callback=progress)
        elif pipeline_type == PipelineType.VISUAL:
            report = await analyze_visual(file_path, callback=progress)
        elif pipeline_type == PipelineType.CRYPTOGRAPHIC:
            report = await analyze_cryptographic(file_path, callback=progress)
        else:
            report = {"error": "Unsupported pipeline"}

        await send("info", "Pipeline analysis complete.", "ANALYSIS_COMPLETE", data=report)

        # ── GCS upload + AI reasoning ─────────────────────────────────────────
        await send("info", "Uploading to secure cloud storage...", "GCS_UPLOAD")
        gcs_uri = upload_to_gcs(file_path, found_file)

        reasoning_result: dict = {"authenticity_score": 50, "summary": "AI skipped (GCS failed)"}

        if not gcs_uri:
            await send("warning", "GCS upload failed — running local forensics only.")
        else:
            model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")
            await send("info", f"Initialising {model_name} reasoning agent...", "REASONING_START")
            reasoning_result = await run_semantic_reasoning(
                gcs_uri,
                mime_type=mime_type,
                local_report=report,
                pipeline_type=pipeline_type.value,
            )

        # ── Deterministic scoring ─────────────────────────────────────────────
        logger.info(f"Scoring — pipeline: {pipeline_type.value}, report keys: {list(report.keys())}")
        scoring_output = calculate_final_score(
            pipeline_type=pipeline_type.value,
            local_report=report,
            ai_result=reasoning_result,
        )

        reasoning_result.update({
            "authenticity_score": scoring_output["authenticity_score"],
            "score_breakdown": scoring_output["breakdown"],
            "precise_scores": scoring_output.get("precise_scores", {}),
            "structural_breakdown_list": scoring_output.get("structural_breakdown_list", []),
            "scoring_weights": scoring_output.get("weights", {}),
            "verdict": scoring_output["verdict"],
            "threshold": scoring_output["threshold"],
            "original_ai_score": scoring_output["ai_dry_score"],
            "weighted_tech": scoring_output.get("weighted_tech", 0),
        })

        # ── Inject TruFor bounding boxes ──────────────────────────────────────
        # The frontend expects boxes under reasoning_result["bounding_boxes"] as
        # objects with a "box_2d" key.  TruFor returns raw lists.
        try:
            boxes_to_inject = []

            # Visual pipeline: direct image
            boxes_to_inject.extend(
                report.get("details", {}).get("trufor", {}).get("bounding_boxes", [])
            )

            # Structural pipeline: embedded images
            for img_entry in report.get("details", {}).get("analyzed_images", []):
                v_boxes = (
                    img_entry.get("visual_report", {})
                    .get("details", {})
                    .get("trufor", {})
                    .get("bounding_boxes", [])
                )
                if v_boxes:
                    logger.info(
                        f"Found {len(v_boxes)} TruFor boxes in embedded image {img_entry.get('index')}"
                    )
                    boxes_to_inject.extend(v_boxes)

            if boxes_to_inject:
                existing = reasoning_result.setdefault("bounding_boxes", [])
                existing.extend(
                    {"box_2d": box, "label": "potential_manipulation"}
                    for box in boxes_to_inject
                )
                logger.info(f"Injected {len(boxes_to_inject)} TruFor bounding boxes.")
        except Exception as e:
            logger.error(f"TruFor box injection failed: {e}")

        # ── Final response ────────────────────────────────────────────────────
        file_stats = os.stat(file_path)
        final_response = {
            "task_id": task_id,
            "filename": found_file,
            "file_size": file_stats.st_size,
            "mime_type": mime_type,
            "pipeline_used": pipeline_type.value,
            "report": report,
            "reasoning": reasoning_result,
        }

        await send("complete", "Analysis successfully completed.", "COMPLETE", data=final_response)
        await websocket.close()

    except WebSocketDisconnect:
        logger.info(f"Client disconnected during task {task_id}")
    except Exception as e:
        logger.error(f"Analysis failed for task {task_id}: {e}")
        await websocket.send_json({"status": "error", "message": str(e)})
