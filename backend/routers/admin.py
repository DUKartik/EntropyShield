"""
routers/admin.py
Diagnostic / admin endpoints (TruFor debug status, etc.).
These are internal developer tools and should not be exposed in production.
"""
from fastapi import APIRouter

from utils.debug_logger import get_logger

logger = get_logger()

router = APIRouter()


@router.get("/debug/trufor")
def debug_trufor_status():
    """
    Diagnostic: check whether TruFor model weights are present and the model
    is loaded.  Attempts a manual reload if the engine exists but the model is
    ``None``, capturing the specific failure for easier debugging.
    """
    try:
        import sys

        from components.trufor.engine import (
            TruForEngine,
            TruForFactory,
            default_cfg,
            trufor_core_path,
        )

        weights_path = trufor_core_path / "weights" / "trufor.pth.tar"
        conf_path = trufor_core_path / "lib" / "config" / "trufor_ph3.yaml"

        load_error = None

        # Attempt manual reload when the instance exists but the model failed
        if TruForEngine._instance and TruForEngine._instance._model is None:
            try:
                logger.info("TruFor debug: forcing manual model reload attempt...")
                if TruForFactory is None:
                    raise ImportError("TruForFactory is None (imports failed at startup)")

                cfg = default_cfg
                if conf_path.exists():
                    cfg.merge_from_file(str(conf_path))
                else:
                    load_error = f"Config file missing: {conf_path}"

                if not load_error:
                    import torch

                    model = TruForFactory(cfg)
                    checkpoint = torch.load(weights_path, map_location="cpu", weights_only=False)
                    model.load_state_dict(checkpoint["state_dict"])
                    model.eval()
                    TruForEngine._instance._model = model
                    logger.info("TruFor debug: manual reload succeeded.")
            except Exception as e:
                import traceback

                load_error = f"{e}\n{traceback.format_exc()}"
                logger.error(f"TruFor debug: reload failed — {e}")

        return {
            "weights_path": str(weights_path),
            "weights_exist": weights_path.exists(),
            "config_path": str(conf_path),
            "config_exists": conf_path.exists(),
            "model_loaded": (
                TruForEngine._instance._model is not None
                if TruForEngine._instance
                else False
            ),
            "load_error": load_error,
            "sys_path": sys.path,
        }
    except Exception as e:
        import traceback

        return {"error": str(e), "traceback": traceback.format_exc()}
