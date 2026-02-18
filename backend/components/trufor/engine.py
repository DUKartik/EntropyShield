import os
import torch
import numpy as np
import torch.nn.functional as F
from PIL import Image
import sys
import threading
from pathlib import Path

# Add backend root to sys.path 
backend_root = Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

from utils.debug_logger import get_logger
from utils.determinism import set_global_seed, get_tensor_fingerprint
logger = get_logger()

# Add trufor_core to sys.path so 'import lib' works
trufor_core_path = backend_root / 'components' / 'trufor' / 'core'
if str(trufor_core_path) not in sys.path:
    sys.path.append(str(trufor_core_path))

try:
    from lib.config import config as default_cfg
    from lib.config import update_config
    from lib.utils import get_model
    TruForFactory = get_model
except ImportError as e:
    logger.warning(f"Warning: TruFor core modules not found. Error: {e}")
    TruForFactory = None
    default_cfg = None

class TruForEngine:
    _instance = None
    _model = None
    _device = "cuda" if torch.cuda.is_available() else "cpu"
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TruForEngine, cls).__new__(cls)
                cls._instance._load_model()
        return cls._instance

    def _load_model(self):
        if TruForFactory is None:
            logger.error("TruFor dependencies missing. Skipping model load.")
            return

        logger.info(f"Loading TruFor Model on {self._device}...")
        
        try:
            # 1. Load Configuration
            # We use the default config from lib.config and merge our yaml
            conf_path = trufor_core_path / 'lib' / 'config' / 'trufor_ph3.yaml'
            
            cfg = default_cfg
            if conf_path.exists():
                logger.info(f"DEBUG: Config found. Merging from {conf_path}...")
                cfg.merge_from_file(str(conf_path))
                logger.info(f"DEBUG: Loaded TruFor config from {conf_path}")
            else:
                logger.info(f"DEBUG: TruFor config NOT FOUND at {conf_path}")
            
            # MODEL.DEVICE does not exist in TruFor config, and we handle .to(device) manually below
            # cfg.merge_from_list(["MODEL.DEVICE", self._device])
            
            # 2. Initialize Architecture via Factory
            logger.info("DEBUG: Initializing Model Architecture (Factory)...")
            self._model = TruForFactory(cfg)
            logger.info("DEBUG: Model Architecture Initialized.")
            
            # 3. Load Weights
            weights_path = trufor_core_path / 'weights' / 'trufor.pth.tar'
            logger.info(f"DEBUG: Checking weights at {weights_path}")
            if not weights_path.exists():
                logger.warning(f"Warning: Missing TruFor weights at {weights_path}")
                # DEBUG: List directory to see what IS there
                parent_dir = weights_path.parent
                if parent_dir.exists():
                    logger.info(f"DEBUG: Contents of {parent_dir}: {list(parent_dir.iterdir())}")
                else:
                    logger.info(f"DEBUG: Parent directory {parent_dir} does NOT exist.")
                return
                
            checkpoint = torch.load(weights_path, map_location=self._device, weights_only=False)
            logger.info("DEBUG: Weights file loaded into memory. Loading state dict...")
            self._model.load_state_dict(checkpoint['state_dict'])
            self._model.eval()
            
            logger.info(f"DEBUG: Moving model to device: {self._device}...")
            self._model.to(self._device)
            logger.info("DEBUG: Model moved to device.")
            logger.info("TruFor Model Loaded Successfully.")
            
        except Exception as e:
            logger.error(f"TruFor Load Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self._model = None

    def analyze(self, image_path: str):
        """
        Returns:
            - anomaly_map: 0-1 float array (The forgery heatmap)
            - confidence_map: 0-1 float array (How much to trust the heatmap)
            - score: Global integrity score (0 = Fake, 1 = Real)
        """
        if self._model is None:
            return {
                "heatmap": None,
                "confidence_map": None, 
                "trust_score": 1.0, # Fail safe
                "error": "Model not loaded"
            }

        try:
            # 1. Preprocessing
            logger.info(f"DEBUG: Opening image {image_path}...")
            img = Image.open(image_path).convert('RGB')
            original_size = img.size
            logger.info(f"DEBUG: Image opened. Original Size: {original_size}")
            logger.info(f"DEBUG: TruFor Analyzing Image {image_path} with size: {original_size}")
            
            # Limit size for T4/CPU stability
            if max(original_size) > 1024:
                logger.info(f"DEBUG: Resizing image from {original_size} to max 1024...")
                img.thumbnail((1024, 1024))
                logger.info(f"DEBUG: Resized to {img.size}")
            
            # Upscale if too small (TruFor fails if feature map < 8x8 kernel)
            # 256px should contain 5 downsamples (256->128->64->32->16->8) safely
            if min(img.size) < 256:
                img = img.resize((max(256, img.size[0]), max(256, img.size[1])), Image.BILINEAR)
            
            img_tensor = self._transform_image(img).to(self._device)
            
            # --- DETERMINISM & FINGERPRINTING ---
            set_global_seed(42)
            logger.info(get_tensor_fingerprint(img_tensor, "TruFor_Input_Tensor"))
            # ------------------------------------

            # 2. Inference
            logger.info(f"DEBUG: Starting TruFor Inference on device {self._device}...")
            with torch.no_grad():
                # TruFor outputs a tuple: (pred, conf, det, npp)
                # pred: Anomaly map logits (B, 2, H, W)
                # conf: Confidence map logits (B, 1, H, W)
                pred, conf, det, npp = self._model(img_tensor)
            logger.info("DEBUG: TruFor Inference Complete.")
            
            # Post-process Anomaly Map (Softmax -> Class 1)
            # pred shape: (1, 2, H, W)
            pred_prob = torch.softmax(pred, dim=1)[:, 1, :, :] # Take forgery class
            
            # Post-process Confidence Map (Sigmoid)
            # conf shape: (1, 1, H, W)
            if conf is not None:
                conf_prob = torch.sigmoid(conf).squeeze(1)
            else:
                conf_prob = torch.ones_like(pred_prob)

            # 3. Extract & Resize back to original
            # Pass already-processed 0-1 tensors (cpu numpy)
            anomaly = self._resize_map(pred_prob.squeeze().cpu().numpy(), original_size)
            confidence = self._resize_map(conf_prob.squeeze().cpu().numpy(), original_size)
            
            # 4. Calculate Global Score
            # We weigh the anomaly score by the confidence.
            # If anomaly is high but confidence is low, we ignore it.
            weighted_anomaly = anomaly * confidence
            
            # Use 99.5th percentile instead of max to ignore single-pixel outliers
            # This makes the score much more stable.
            anomaly_peak = np.percentile(weighted_anomaly, 99.5)
            
            # Global Score = 1.0 - Scaled Anomaly
            # We assume anomaly > 0.5 is significant enough to drop score to 0.
            # Sensitivity adjustment:
            sensitivity = float(os.getenv("TRUFOR_SENSITIVITY", "1.0"))
            
            # Map [0, 1] -> [100, 0] with simpler linear logic
            # If peak is 0.8, score should be low.
            # Score = 1.0 - min(1.0, peak * sensitivity)
            
            global_score = max(0.0, 1.0 - (anomaly_peak * sensitivity))

            # DEBUG: Print stats
            logger.info(f"DEBUG: TruFor Analysis Complete. Global Score: {global_score:.4f}, Anomaly Peak: {anomaly_peak:.4f}")

            # Save heatmap for frontend (return as array, pipeline handles saving)
            return {
                "heatmap": weighted_anomaly, 
                "raw_confidence": confidence,
                "trust_score": float(global_score),
                "verdict": "Forged" if global_score < 0.5 else "Authentic"
            }
        except Exception as e:
            logger.error(f"TruFor Analysis Failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"trust_score": 1.0, "error": str(e)}

    def _transform_image(self, img):
        # Standard RGB normalization for TruFor
        arr = np.array(img).astype(np.float32) / 255.0
        arr = np.transpose(arr, (2, 0, 1)) # HWC -> CHW
        return torch.tensor(arr).unsqueeze(0) # Add batch dim

    def _resize_map(self, prob_map, target_size):
        # Resize to original image dimensions for overlay
        # prob_map is already 0-1 float numpy array
        prob_img = Image.fromarray((prob_map * 255).astype(np.uint8))
        prob_img = prob_img.resize(target_size, Image.BILINEAR)
        return np.array(prob_img) / 255.0
