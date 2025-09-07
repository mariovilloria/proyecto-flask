import logging, os
from datetime import datetime

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)
handler = logging.FileHandler(os.path.join(LOG_DIR, "audit.log"), encoding="utf-8")
fmt = logging.Formatter("%(asctime)s | %(message)s")
handler.setFormatter(fmt)
audit_logger.addHandler(handler)

def log_action(user, action, details=""):
    audit_logger.info(f"{user} | {action} | {details}")