"""
Startup speed & import isolation check.
Run from the backend/ directory:
    .\venv\Scripts\python scripts\check_startup.py
"""
import sys
import time

t0 = time.time()
from main import app  # noqa: E402
elapsed = time.time() - t0

HEAVY = ("torch", "cv2", "PIL", "pyhanko", "pypdf")
loaded = [k for k in sys.modules if any(x in k for x in HEAVY)]

print(f"\n=== Startup Import Time: {elapsed:.2f}s ===")
if loaded:
    print(f"[WARN] Heavy modules loaded at startup (should be empty):")
    for m in sorted(set(m.split(".")[0] for m in loaded)):
        print(f"  - {m}")
else:
    print("[OK] No heavy forensic modules loaded at startup. Fast startup confirmed!")
print()
