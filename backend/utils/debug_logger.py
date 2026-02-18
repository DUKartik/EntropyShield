
import logging
import collections
from fastapi import APIRouter, Request
from datetime import datetime

# Configure Buffer
LOG_BUFFER_SIZE = 500
log_buffer = collections.deque(maxlen=LOG_BUFFER_SIZE)

# Custom Handler
class MemoryHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            log_buffer.append(msg)
        except Exception:
            self.handleError(record)

# Setup Logger
logger = logging.getLogger("veridoc_debug")
logger.setLevel(logging.INFO)

# Create Handler
memory_handler = MemoryHandler()
formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
memory_handler.setFormatter(formatter)
logger.addHandler(memory_handler)

# Also capture Uvicorn logs if possible, but mainly application logs
# We attach to root for broader capture
logging.getLogger().addHandler(memory_handler)


# API Router
debug_router = APIRouter()

@debug_router.get("/debug/logs")
async def get_debug_logs(limit: int = 100):
    """
    Returns the latest logs from the in-memory buffer.
    """
    # Defensive slicing
    all_logs = list(log_buffer)
    return {
        "count": len(all_logs),
        "limit": limit,
        "logs": all_logs[-limit:]
    }

@debug_router.post("/debug/logs")
async def store_frontend_log(request: Request):
    """
    Allows the frontend to push logs to the backend buffer.
    Expects JSON: { "level": "INFO", "message": "..." }
    """
    try:
        data = await request.json()
        level = data.get("level", "INFO").upper()
        message = data.get("message", "No message provided")
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        entry = f"{timestamp} - [FRONTEND:{level}] - {message}"
        log_buffer.append(entry)
        
        return {"status": "stored"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Export the logger for use elsewhere
def get_logger():
    return logger
