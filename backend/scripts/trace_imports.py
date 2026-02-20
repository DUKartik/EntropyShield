"""Trace which module in main's import chain is slow and loads heavy libs."""
import sys
import time

HEAVY = ("torch", "cv2", "PIL", "pyhanko", "pypdf")

modules_to_probe = [
    "utils.debug_logger",
    "services.database_connector",
    "services.policy_engine",
    "services.scoring_engine",
    "services.forensic_reasoning",
    "services.gcs_service",
    "routers.admin",
    "routers.compliance",
    "routers.forensics",
    "main",
]

for mod in modules_to_probe:
    before = set(sys.modules.keys())
    t0 = time.time()
    try:
        __import__(mod)
    except Exception as e:
        print(f"[ERR] {mod}: {e}")
        continue
    elapsed = time.time() - t0
    after = set(sys.modules.keys())
    new_heavy = [k for k in (after - before) if any(x in k for x in HEAVY)]
    flag = " <-- HEAVY" if new_heavy else ""
    print(f"{elapsed:>6.2f}s  {mod}{flag}")
    if new_heavy:
        for h in sorted(set(k.split(".")[0] for k in new_heavy)):
            print(f"          pulled in: {h}")
