import asyncio
import logging
import os
from enum import Enum

# ---------------------------------------------------------------------------
# Heavy forensic imports are intentionally NOT at module level.
# They are imported on first use (inside each function) so the server starts
# in ~2 s instead of ~25 s.  Importing this module is now essentially free.
# ---------------------------------------------------------------------------

# Suppress verbose pypdf warnings commonly triggered by malformed forensic samples
logging.getLogger("pypdf").setLevel(logging.WARNING)

from services.image_analyzers import analyze_quantization, perform_ela, perform_noise_analysis
from utils.debug_logger import get_logger

logger = get_logger()

# Threading is now controlled via OMP_NUM_THREADS=1 in Dockerfile

# Timeout constants for heavy ML tasks
TIMEOUT_SEGFORMER: float = 45.0
TIMEOUT_TRUFOR: float = 45.0

class PipelineType(Enum):
    STRUCTURAL = "structural"
    VISUAL = "visual"
    CRYPTOGRAPHIC = "cryptographic"

# --- PIPELINES ---


async def analyze_structural(file_path: str, callback=None):
    """
    Pipeline A: Structural Forensics (Native PDFs)
    Advanced checks including:
    1. Incremental Update Detection (EOF markers)
    2. XRef Table keyword analysis
    3. Metadata Consistency
    """
    # Lazy imports — only loaded when the pipeline actually runs
    from pypdf import PdfReader  # noqa: PLC0415
    from pyhanko.pdf_utils.reader import PdfFileReader  # noqa: PLC0415

    results = {
        "pipeline": "Structural Forensics (Real)",
        "score": 0.0,
        "flags": [],
        "details": {},
        "breakdown": []
    }
    
    try:
        # 1. Incremental Update Detection (Raw Bytes)
        with open(file_path, 'rb') as f:
            content = f.read()
            eof_count = content.count(b'%%EOF')
            # xref keyword often appears once per section in standard PDFs.
            # Multiple xrefs can also imply updates.
            xref_count = content.count(b'xref') 
            
        results['details']['eof_markers_found'] = eof_count
        results['details']['xref_keywords_found'] = xref_count
        
        if eof_count > 1:
            results['flags'].append(f"Detected {eof_count} Incremental Updates (File modified after creation)")
            penalty = 0.15 * (eof_count - 1)
            results['score'] += penalty
            results['breakdown'].append({"reason": "Incremental Updates (EOF)", "penalty": penalty * 100})
        elif eof_count == 0:
            results['flags'].append("Malformed PDF: No %%EOF marker found")
            results['score'] = 1.0 # High risk or broken
            results['breakdown'].append({"reason": "Malformed PDF (No EOF)", "penalty": 100})
            
        # XRef Analysis
        if xref_count > 1:
            # Not always malicious (linearized PDFs have 2), but suspicious if high
            if xref_count > 2:
                results['flags'].append(f"High XRef Count ({xref_count}): potential hidden structural updates")
                penalty = 0.1 * (xref_count - 2)
                results['score'] += penalty
                results['breakdown'].append({"reason": "Excessive XRef Tables", "penalty": penalty * 100})
                
        # Hidden Content / Malware Checks
        if b'/JavaScript' in content or b'/JS' in content:
             results['flags'].append("Active Content Detected: JavaScript found")
             results['score'] += 0.3 # High risk
             results['breakdown'].append({"reason": "Active Content (JavaScript)", "penalty": 30})
             
        if b'/OpenAction' in content or b'/AA' in content:
             results['flags'].append("Active Content Detected: Auto-Execution Actions found")
             results['score'] += 0.2
             results['breakdown'].append({"reason": "Auto-Execution Actions", "penalty": 20})
             
        # Orphaned Object Approx. (Object count mismatch vs XRef size)
        # This is a heuristic.
        obj_count = content.count(b' obj')
        endobj_count = content.count(b'endobj')
        
        if abs(obj_count - endobj_count) > 2:
             results['flags'].append(f"Structural Integrity Error: Mismatched Object Tags ({obj_count} vs {endobj_count})")
             results['score'] += 0.2
             results['breakdown'].append({"reason": "Mismatched Object Tags", "penalty": 20})
            
        # 2. PDF Parsing & Deep Analysis
        # We use a context manager to ensure the file handle is closed immediately after use, allowing cleanup.
        with open(file_path, 'rb') as f_stream:
            reader = PdfReader(f_stream)
            
            # A. Metadata Forensics
            meta = reader.metadata
            if meta:
                safe_meta = {k: str(v) for k, v in meta.items()}
                results['details']['metadata'] = safe_meta
                
                producer = safe_meta.get('/Producer', '').lower()
                if not producer:
                    results['flags'].append("Missing Producer Metadata")
                    results['score'] += 0.2
                    results['breakdown'].append({"reason": "Missing Producer Metadata", "penalty": 20})
                elif "phantom" in producer or "gpl output" in producer:
                    results['flags'].append(f"Suspicious Producer detected: {safe_meta.get('/Producer')}")
                    results['score'] += 0.3
                    results['breakdown'].append({"reason": "Suspicious Producer (Phantom/GPL)", "penalty": 30})
            else:
                results['flags'].append("No Metadata found")
                results['score'] += 0.1
                results['breakdown'].append({"reason": "No Metadata", "penalty": 10})
                
            # --- NEW: Deep Image Inspection (Extract & Analyze) ---
            # Checks for embedded images that might be faked (e.g., pasted signature, fake bank statement screenshot)
            try:
                embedded_images = []
                for page in reader.pages:
                    for img in page.images:
                        embedded_images.append(img)
                
                results['details']['embedded_image_count'] = len(embedded_images)
                results['details']['analyzed_images'] = []
                
                if len(embedded_images) > 0:
                    # Analyze up to 3 largest images to save time, or all if critical.
                    # For now, analyze the first 3.
                    for idx, img_obj in enumerate(embedded_images[:3]):
                        # Send Update
                        if callback:
                            await callback(f"Found embedded image {idx+1}/{len(embedded_images[:3])}. Running Visual Forensics (SegFormer)...")

                        # Save temp
                        # Save temp
                        # Handle potential missing name/ext
                        ext = "png"
                        if hasattr(img_obj, "name") and img_obj.name and "." in img_obj.name:
                            ext = img_obj.name.split('.')[-1]
                        
                        temp_img_name = f"{os.path.basename(file_path)}_img_{idx}.{ext}"
                        temp_img_path = os.path.join(os.path.dirname(file_path), temp_img_name)
                        
                        with open(temp_img_path, "wb") as fp:
                            fp.write(img_obj.data)
                            
                        # RUN VISUAL PIPELINE ON EXTRACTED CONTENT
                        # analyze_visual is now async, so we await it directly
                        visual_report = await analyze_visual(temp_img_path, callback=callback)
                        
                        # Store comprehensive results for this image
                        # We inject the temp filename so the frontend knows what to fetch
                        # Also include image metadata if available
                        image_summary = {
                            "index": idx,
                            "filename": temp_img_name,
                            "visual_report": visual_report
                        }
                        results['details']['analyzed_images'].append(image_summary)

                        # Check for flags (Original Logic Preserved)
                        if visual_report.get('score', 0) > 0.4:
                            results['flags'].append(f"Embedded Image {idx+1}: Potential Tampering Detected")
                            results['score'] += 0.4
                            
                            if 'semantic_segmentation' in visual_report['details']:
                                sem = visual_report['details']['semantic_segmentation']
                                if isinstance(sem, dict) and sem.get('is_tampered'):
                                    conf = sem.get('confidence_score', 0)
                                    results['flags'].append(f"-> SegFormer found tampering in embedded image {idx+1} (Conf: {conf:.2f})")
                                    results['score'] += 0.3
                                    results['breakdown'].append({"reason": f"Embedded Image {idx+1} Tampering", "penalty": 30})
                        
                        # --- PERSISTENCE LOGIC ---
                        # We KEEP the temp files if we analyzed them, so the frontend can show the Visual Lab for ANY processed image.
                        # This meets the user requirement: "make the visual lab thing for each image... show those graphs too"
                        # We do NOT delete the files here. They will be cleaned up by the explicit cleanup API.


            except Exception as e:
                results['warnings'] = f"Deep Image Inspection failed: {str(e)}"


            # B. Orphan / Hidden Content Analysis (Simplified Safe Mode)
            # Instead of deep traversal which risks recursion errors, we check for high-risk flags
            try:
                # Check for embedded files (often used for attacks)
                if reader.trailer and '/Root' in reader.trailer:
                    root_obj = reader.trailer['/Root']
                    # Depending on pypdf version, root_obj might be IndirectObject or Dict
                    # We access it safely
                    if hasattr(root_obj, 'get_object'):
                        root_obj = root_obj.get_object()
                    
                    if '/EmbeddedFiles' in root_obj:
                        results['flags'].append("Contains Embedded Files (Potential Payload)")
                        results['score'] += 0.3
                        results['breakdown'].append({"reason": "Hidden Embedded Files", "penalty": 30})
                        
                    if '/JS' in root_obj or '/JavaScript' in root_obj:
                        results['flags'].append("Contains Embeded JavaScript (High Risk)")
                        results['score'] += 0.5
                        results['breakdown'].append({"reason": "Embedded JavaScript Object", "penalty": 50})
                    
            except Exception as e:
                # Don't fail the whole pipeline for an advanced check
                results['warnings'] = f"Advanced structural check warning: {str(e)}"

        # Context manager closes f_stream here


        results['score'] = min(results['score'], 1.0)
            
    except Exception as e:
        results['error'] = f"Analysis Failed: {str(e)}"
        
    return results

async def analyze_cryptographic(file_path: str, callback=None):
    """
    Pipeline C: Cryptographic Analysis (Signed PDFs)
    Uses crypto_utils for robust Hybrid Trust and Zero-Touch validation.
    """
    # Lazy imports
    from pypdf import PdfReader  # noqa: PLC0415
    from pyhanko.pdf_utils.reader import PdfFileReader  # noqa: PLC0415

    if callback:
        await callback("Initializing Cryptographic Engine...")
        
    results = {
        "pipeline": "Cryptographic Analysis (Digital Signatures)",
        "score": 0.0,
        "flags": [],
        "details": {}
    }
    
    try:
        from utils.crypto_utils import get_validation_context, validate_signature_forensic
        
        # 1. Get Smart Context (AIA, OCSP, Soft-Fail, Hybrid Trust)
        if callback: await callback("Loading Hybrid Trust Store (Mozilla + Local)...")
        vc = get_validation_context()
        
        # 2. Open File
        with open(file_path, 'rb') as f:
            r = PdfFileReader(f)
            
            if not r.embedded_signatures:
                results['flags'].append("No Embedded Signatures found")
                results['details']['signature_count'] = 0
                return results
                
            sig_status = []
            
            for sig in r.embedded_signatures:
                if callback: await callback(f"Verifying Signature: {sig.field_name}...")
                
                # Use robust wrapper
                status = await validate_signature_forensic(sig, vc)
                sig_status.append(status)
                
                # DEBUG: Log the actual status returned
                logger.info(f"Signature validation result for {status['field']}:")
                logger.info(f"  - intact: {status.get('intact')}")
                logger.info(f"  - trusted: {status.get('trusted')}")
                logger.info(f"  - valid: {status.get('valid')}")
                logger.info(f"  - error: {status.get('error')}")
                logger.info(f"  - warnings: {status.get('warnings')}")
                
                # --- SCORING LOGIC ---
                if not status['intact']:
                     results['flags'].append(f"CRITICAL: Signature {status['field']} is BROKEN (Document altered after signing)")
                     results['score'] += 1.0 
                elif status['revoked']:
                     results['flags'].append(f"CRITICAL: Certificate for {status['field']} has been REVOKED")
                     results['score'] += 1.0
                elif not status['trusted']:
                     results['flags'].append(f"WARNING: Signature {status['field']} is Untrusted (Unknown Root)")
                     # We do not penalize heavily for unknown root if it is intact (could be private)
                     results['score'] += 0.2
                
                if status.get('weak_hash') or status.get('weak_key'):
                     results['flags'].append(f"Legacy Crypto Detected for {status['field']} (Weak Key/Hash)")
                     # No penalty, just flag
                     
            results['details']['signatures'] = sig_status
            results['details']['signature_count'] = len(sig_status)
            
            # Cap score
            results['score'] = min(results['score'], 1.0)
            
    except Exception as e:
        logger.warning(f"Primary Crypto Analysis Failed: {e}. Attempting Fallback...")
        
        # Fallback: Detect signatures using pypdf so we report SOMETHING instead of "N/A"
        try:
            from pypdf import PdfReader
            p_reader = PdfReader(file_path)
            fields = p_reader.get_fields() or {}
            fallback_sigs = []
            
            for k, v in fields.items():
                if v and v.get('/FT') == '/Sig':
                    fallback_sigs.append({
                        "field": k,
                        "valid": False,
                        "intact": True,  # We don't know if it's tampered, just can't parse it
                        "trusted": False,
                        "revoked": False,
                        "error": f"Format Error: {str(e)[:100]}"
                    })
            
            if fallback_sigs:
                logger.info(f"Fallback found {len(fallback_sigs)} unparseable signatures.")
                results['details']['signatures'] = fallback_sigs
                results['details']['signature_count'] = len(fallback_sigs)
                results['flags'].append("CRITICAL: Signatures detected but format is invalid/legacy (Unverifiable)")
                results['score'] = 1.0 # High Risk
            else:
                results['error'] = f"Cryptographic Analysis Failed: {str(e)}"
                
        except Exception as e2:
            results['error'] = f"Cryptographic Analysis Failed: {str(e)}"
        
    return results

async def analyze_visual(file_path: str, callback=None):
    """
    Pipeline B: Visual Analysis (Images)
    Uses ELA, Quantization Checks, and Semantic Segmentation (SegFormer).
    """
    logger.info(f"Starting Visual Analysis for: {file_path}")
    if callback:
        await callback("Starting Visual Forensics Pipeline...")

    results = {
        "pipeline": "Visual Analysis (ELA, Quantization & Semantic)",
        "score": 0.0,
        "flags": [],
        "details": {}
    }

    try:
        f_size = os.path.getsize(file_path)
        logger.info(f"DEBUG: Pipeline Visual Analysis Start. File: {file_path}, Size: {f_size/1024:.2f} KB")
    except Exception as e:
        logger.info(f"DEBUG: Could not get file stats: {e}")
    
    loop = asyncio.get_running_loop()
    
    # Define tasks efficiently
    # CPU-bound tasks (OpenCV) needed executors
    
    async def run_ela():
        if callback: await callback("Running Error Level Analysis (ELA)...")
        # Run in executor to avoid blocking main thread
        return await loop.run_in_executor(None, perform_ela, file_path)

    async def run_quant():
        if callback: await callback("Analyzing DCT Histograms...")
        return await loop.run_in_executor(None, analyze_quantization, file_path)
    
    async def run_segformer():
        # SegFormer inference might be heavy, ensure it's non-blocking
        if callback: await callback("Engaging Neural Network (SegFormer)...")
        def _run_seg():
            # Lazy import: torch + model weights load here, not at server start
            from components.segformer.inference import run_tamper_detection  # noqa: PLC0415
            return run_tamper_detection(file_path)
        return await loop.run_in_executor(None, _run_seg)

    async def run_noise():
        if callback: await callback("Calculating Noise Variance...")
        return await loop.run_in_executor(None, perform_noise_analysis, file_path)

    async def run_trufor():
        if callback: await callback("Initializing TruFor Analysis...")
        logger.info("DEBUG: TRACE: run_trufor async task started")
        
        def _analyze_safe():
            # Lazy import: torch + 300 MB TruFor weights load here, not at server start
            from components.trufor.engine import TruForEngine  # noqa: PLC0415
            logger.info(f"DEBUG: TRACE: _analyze_safe called for {file_path}")
            try:
                engine = TruForEngine()
                logger.info("DEBUG: TRACE: TruForEngine instance obtained")
                logger.info(f"DEBUG: TRACE: Calling engine.analyze({file_path})...")
                res = engine.analyze(file_path)
                logger.info("DEBUG: TRACE: engine.analyze returned")
                return res
            except Exception as e:
                logger.info(f"DEBUG: TRACE: Error in _analyze_safe: {e}")
                raise e

        return await loop.run_in_executor(None, _analyze_safe)

    # FIRE EVERYTHING AT ONCE (Parallel Execution)
    # --- SERIALIZED EXECUTION WITH FAIL-SAFE TIMEOUTS ---
    # 1. Parallel Light Tasks
    ela_res, quant_res, noise_res = await asyncio.gather(
        run_ela(),
        run_quant(),
        run_noise(),
        return_exceptions=True
    )

    segmentation_task = run_segformer()
    # 2. SegFormer (Heavy) - 45s Timeout
    try:
        logger.info("Starting SegFormer task...")
        seg_res = await asyncio.wait_for(segmentation_task, timeout=TIMEOUT_SEGFORMER)
        logger.info("SegFormer completed.")
    except asyncio.TimeoutError:
        logger.error(f"SegFormer timed out ({TIMEOUT_SEGFORMER}s)")
        seg_res = Exception(f"SegFormer Timeout ({TIMEOUT_SEGFORMER}s)")
    except Exception as e:
        seg_res = e

    trufor_task = run_trufor()
    
    # Heartbeat to keep WebSocket alive during long load times
    async def keep_alive():
        while True:
            await asyncio.sleep(15)
            if callback: await callback("Processing TruFor Model... (This may take 45s)")

    heartbeat = asyncio.create_task(keep_alive())

    # 3. TruFor (Heaviest) - 45s Timeout (User Request)
    try:
        logger.info("Starting TruFor task...")
        trufor_res = await asyncio.wait_for(trufor_task, timeout=TIMEOUT_TRUFOR)
        logger.info("TruFor completed.")
    except asyncio.TimeoutError:
        logger.error(f"TruFor timed out ({TIMEOUT_TRUFOR}s)")
        trufor_res = Exception(f"TruFor Timeout ({TIMEOUT_TRUFOR}s) — system overload")
    except Exception as e:
        trufor_res = e
    finally:
        heartbeat.cancel()

    # --- PROCESS RESULTS (Sequential Aggregation) ---

    # 1. ELA
    if isinstance(ela_res, Exception):
        results['flags'].append(f"ELA Failed: {str(ela_res)}")
        results['details']['ela'] = {"status": "error"}
    else:
        results['details']['ela'] = ela_res
        if ela_res.get('status') == 'success' and ela_res['mean_difference'] > 15:
             results['flags'].append("High ELA Response (Potential Manipulation)")
             results['score'] += 0.4

    # 2. Quantization
    if isinstance(quant_res, Exception):
        results['details']['quantization'] = {"status": "error"}
    else:
        results['details']['quantization'] = quant_res
        if quant_res.get('status') == 'success' and quant_res['suspicious']:
            results['flags'].append("Suspicious Histogram (Potential Double Quantization)")
            results['score'] += 0.3

    # 3. SegFormer
    if isinstance(seg_res, Exception):
        results["details"]["semantic_segmentation"] = f"Model Failed: {str(seg_res)}"
    else:
        results["details"]["semantic_segmentation"] = seg_res
        if seg_res.get("is_tampered"):
             conf = seg_res.get("confidence_score", 0)
             results["flags"].append(f"Deep Learning Detection (SegFormer): Tampering Detected (Conf: {conf:.2f})")
             results["score"] += 0.6 

    # 4. Noise
    if isinstance(noise_res, Exception):
        results["details"]["noise_analysis"] = f"Noise Map Failed: {str(noise_res)}"
    else:
        results["details"]["noise_analysis"] = noise_res

    # 5. TruFor
    if isinstance(trufor_res, Exception):
        results["details"]["trufor"] = {"error": str(trufor_res)}
    else:
        # TruFor Result Processing (Heatmap Saving)
        # Note: Previous implementation had huge inline code here. We must keep it.
        # But `analyze` probably returns the heatmap ARRAY, so we need to save it here?
        # WAIT: The previous code ran `trufor_engine.analyze` which returned a dict with 'heatmap'.
        # We need to replicate the saving logic here because `analyze` likely doesn't save to disk itself (based on previous code).
        
        results["details"]["trufor"] = trufor_res
        
        # Save Heatmap if present
        if isinstance(trufor_res, dict) and trufor_res.get("heatmap") is not None:
             try:
                 import matplotlib.pyplot as plt  # noqa: PLC0415
                 import numpy as np  # noqa: PLC0415
                 import cv2  # noqa: PLC0415
                 # Save formatted heatmap to disk for frontend
                 heatmap_arr = trufor_res["heatmap"]

                 # --- EXTRACT TRUFOR BOUNDING BOXES ---
                 try:
                     tf_mask = (heatmap_arr > 0.5).astype(np.uint8) * 255
                     tf_contours, _ = cv2.findContours(tf_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                     tf_boxes = []
                     h_tf, w_tf = heatmap_arr.shape
                     
                     for cnt in tf_contours:
                         x, y, w, h = cv2.boundingRect(cnt)
                         if w < 10 or h < 10: continue
                         
                         norm_box = [
                            int((y / h_tf) * 1000),
                            int((x / w_tf) * 1000),
                            int(((y + h) / h_tf) * 1000),
                            int(((x + w) / w_tf) * 1000)
                         ]
                         tf_boxes.append(norm_box)

                     logger.info(f"TruFor heatmap — max: {heatmap_arr.max():.3f}, mean: {heatmap_arr.mean():.3f}")
                     logger.info(f"Found {len(tf_boxes)} TruFor bounding boxes.")
                     results["details"]["trufor"]["bounding_boxes"] = tf_boxes
                 except Exception as exc:
                     logger.error(f"TruFor bounding box extraction failed: {exc}")
                 # -------------------------------------
                 
                 # Create RGBA
                 cmap = plt.get_cmap('jet')
                 rgba_img = cmap(heatmap_arr) # (H,W,4)
                 
                 # Set alpha logic
                 alpha = heatmap_arr.copy()
                 alpha[alpha < 0.1] = 0.0
                 alpha[alpha >= 0.1] = 0.7
                 rgba_img[:, :, 3] = alpha
                 
                 # Save
                 tf_filename = os.path.basename(file_path) + ".trufor.png"
                 tf_path = os.path.join(os.path.dirname(file_path), tf_filename)
                 
                 plt.imsave(tf_path, rgba_img)
                 
                 results["details"]["trufor"]["heatmap_path"] = tf_filename
                 # Remove raw array
                 if "heatmap" in results["details"]["trufor"]: del results["details"]["trufor"]["heatmap"]
                 if "raw_confidence" in results["details"]["trufor"]: del results["details"]["trufor"]["raw_confidence"]
             except Exception as e:
                 logger.error(f"TruFor heatmap save failed: {e}")

        # Integrate Score
        if isinstance(trufor_res, dict) and trufor_res.get("trust_score", 1.0) < 0.5:
             results["flags"].append(f"TruFor Detected Anomaly (Score: {trufor_res['trust_score']:.2f})")
             results["score"] += 0.8

    # Cap score
    results['score'] = min(results['score'], 1.0)
    
    return results

def determine_pipeline(filename: str, content_type: str) -> PipelineType:
    """
    Orchestration Logic
    """
    # Lazy imports — pypdf/pyhanko only needed when a file is actually processed
    from pypdf import PdfReader  # noqa: PLC0415
    from pyhanko.pdf_utils.reader import PdfFileReader  # noqa: PLC0415

    fn_lower = filename.lower()
    ext = fn_lower.split('.')[-1]
    
    if ext == 'pdf':
        try:
            # Content-Based Detection for Digital Signatures
            with open(filename, 'rb') as f:
                r = PdfFileReader(f)
                if len(r.embedded_signatures) > 0:
                    return PipelineType.CRYPTOGRAPHIC
                else:
                    pass
        except Exception as e:
            # Fallback: Try pypdf if pyhanko fails (some sigs crash pyhanko parsing)
            try:
                p_reader = PdfReader(filename)
                fields = p_reader.get_fields()
                if fields:
                    for v in fields.values():
                        if v and v.get('/FT') == '/Sig':
                            return PipelineType.CRYPTOGRAPHIC
            except Exception as e2:
                pass
            
            # Fallback or log error if file is unreadable (Structural pipeline handles malformed)
            pass

        return PipelineType.STRUCTURAL
        
    if ext in ['jpg', 'jpeg', 'png', 'tiff', 'bmp', 'webp']:
        return PipelineType.VISUAL
        
    # Default to structural
    return PipelineType.STRUCTURAL
