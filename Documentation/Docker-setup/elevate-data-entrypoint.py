import os
import sys
import json
import time
import base64
import zipfile
import subprocess
import atexit
import logging
from logging.handlers import RotatingFileHandler
import requests
from pyhocon import ConfigFactory

# ---------------------------------------------------
# Configuration & Paths
# ---------------------------------------------------
UNIFIED_CONF = os.getenv("UNIFIED_PIPELINE_CONF", "/job-configs/unified-common.conf")

if not os.path.exists(UNIFIED_CONF):
    print(f"ERROR: Configuration file not found at {UNIFIED_CONF}")
    sys.exit(1)

conf = ConfigFactory.parse_file(UNIFIED_CONF)

def resolve_path(path):
    """Resolve /app paths to local paths if needed."""
    if not path:
        return path
    if not os.path.exists(path) and path.startswith("/app/"):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local_path = path.replace("/app", base_dir)
        if os.path.exists(local_path):
            return local_path
    return path

# ---------------------------------------------------
# Setup Logging
# ---------------------------------------------------
def setup_logging():
    log_file = os.getenv("LOG_FILE_PATH") or conf.get("elevate-data.log-path", "/logs/elevate-data.log")
    log_dir = os.path.dirname(log_file)
    
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError:
            log_file = "elevate-data.log"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Console Handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler
    try:
        fh = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        print(f"Warning: Could not setup file logging: {e}")

    return log_file

LOG_FILE = setup_logging()
logging.info("Starting Elevate entry point script...")

# ---------------------------------------------------
# Global Configuration
# ---------------------------------------------------
CHECK_INTERVAL_SEC = int(conf.get("health.check.interval.sec", 60))
API_TIMEOUT_SEC = int(conf.get("health.check.api-timeout-sec", 30))
FLINK_URL = conf.get("flink.url")
JOB_JARS = dict(conf.get("health.check.job-jars", {}))
JOB_CONF_PATHS = list(conf.get("health.check.job-conf", []))

# Akka-service config
AKKA_JAR = resolve_path(conf.get("health.check.akka-jar"))
AKKA_HOST = conf.get("akka.http.host", "localhost")
AKKA_PORT = int(conf.get("akka.http.port", 8080))
AKKA_TOKEN = conf.get("akka.security.api.token", "")

AKKA_HEALTH = f"http://{AKKA_HOST}:{AKKA_PORT}/health"
FLINK_HEALTH_API = f"http://{AKKA_HOST}:{AKKA_PORT}/api/health/flink"

# Data-cleanup config
DATA_CLEANUP_ENABLED = conf.get("data.cleanup.enabled", False)
CLEANUP_SCRIPT = resolve_path(conf.get("data.cleanup.script.path"))

# Mentoring-push config
MENTORING_ENABLED = conf.get("mentoring.batch.job.enabled", False)
MENTORING_SCRIPT = resolve_path(conf.get("mentoring.batch.job.script.path"))

# Shared HTTP Session
session = requests.Session()
session.headers.update({"Authorization": AKKA_TOKEN})

# ---------------------------------------------------
# Akka Service
# ---------------------------------------------------
_akka_proc = None

def start_akka_service():
    global _akka_proc
    if not AKKA_JAR or not os.path.exists(AKKA_JAR):
        logging.error(f"Akka JAR not found: {AKKA_JAR}")
        return

    logging.info(f"Starting akka-service from {AKKA_JAR}...")
    log_dir = os.path.dirname(LOG_FILE)
    akka_log_path = os.path.join(log_dir, "akka-service.log") if log_dir else "akka-service.log"
    
    try:
        akka_log_file = open(akka_log_path, "a")
    except OSError:
        akka_log_file = open("akka-service.log", "a")

    _akka_proc = subprocess.Popen(
        ["java", f"-Dconfig.file={UNIFIED_CONF}", "-jar", AKKA_JAR],
        env={**os.environ, "UNIFIED_PIPELINE_CONF": UNIFIED_CONF},
        stdout=akka_log_file,
        stderr=subprocess.STDOUT,
    )
    logging.info(f"Akka service started (PID={_akka_proc.pid}). Logs at {akka_log_path}")

def wait_for_service(url, name, retries=30, delay=3, expected_status=200):
    logging.info(f"Waiting for {name} to become ready at {url}...")
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, timeout=10)
            if r.status_code == expected_status:
                logging.info(f"{name} is ready.")
                return True
        except Exception:
            pass
        
        if name == "Akka" and _akka_proc and _akka_proc.poll() is not None:
            logging.error("Akka service process exited unexpectedly.")
            sys.exit(1)

        logging.info(f"{name} not ready yet, retrying ({attempt}/{retries})...")
        time.sleep(delay)
    
    logging.error(f"{name} did not become ready in time.")
    sys.exit(1)

def stop_akka_service():
    if _akka_proc and _akka_proc.poll() is None:
        logging.info("Stopping akka-service...")
        _akka_proc.terminate()
        try:
            _akka_proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            _akka_proc.kill()
        logging.info("Akka service stopped.")

atexit.register(stop_akka_service)

# ---------------------------------------------------
# Tmux Session Helpers
# ---------------------------------------------------
def setup_tmux_session(session_name, script_path, enabled):
    if not enabled:
        logging.info(f"{session_name} is disabled. Skipping.")
        return

    if not script_path or not os.path.exists(script_path):
        logging.error(f"Script for {session_name} not found at {script_path}")
        return

    try:
        subprocess.run(["tmux", "-V"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logging.error(f"tmux not found. {session_name} requires tmux.")
        return

    res = subprocess.run(["tmux", "has-session", "-t", session_name], capture_output=True)
    if res.returncode == 0:
        logging.info(f"Restarting tmux session '{session_name}'...")
        subprocess.run(["tmux", "kill-session", "-t", session_name])

    logging.info(f"Starting {session_name} in tmux: {script_path}")
    subprocess.run(["tmux", "new-session", "-d", "-s", session_name, f"python3 {script_path}"])

# ---------------------------------------------------
# Flink Job Helpers
# ---------------------------------------------------
def get_entry_class_from_jar(jar_path):
    try:
        with zipfile.ZipFile(jar_path) as jar:
            manifest = jar.read("META-INF/MANIFEST.MF").decode()
            lines = []
            for line in manifest.splitlines():
                if line.startswith(" "):
                    if lines: lines[-1] += line[1:]
                elif line.strip():
                    lines.append(line)
            for line in lines:
                if line.startswith("Main-Class:"):
                    return line.split(":", 1)[1].strip()
    except Exception as e:
        logging.error(f"Failed reading manifest for {jar_path}: {e}")
    return None

def upload_jar(jar_path):
    try:
        with open(jar_path, "rb") as f:
            r = session.post(f"{FLINK_URL}/jars/upload", files={"jarfile": f})
        if r.status_code == 200:
            return r.json().get("filename", "").split("/")[-1]
        logging.error(f"Jar upload failed: {r.status_code} - {r.text}")
    except Exception as e:
        logging.error(f"Error uploading jar {jar_path}: {e}")
    return None

def submit_job(jar_path):
    jar_path = resolve_path(jar_path)
    if not os.path.exists(jar_path):
        logging.error(f"Jar file not found: {jar_path}")
        return

    entry_class = get_entry_class_from_jar(jar_path)
    if not entry_class:
        logging.error(f"Could not detect entry class for {jar_path}")
        return

    jar_id = upload_jar(jar_path)
    if not jar_id: return

    logging.info(f"Submitting job with Jar ID: {jar_id}, Class: {entry_class}")
    payload = {
        "entryClass": entry_class,
        "programArgs": "--config.file.path /job-configs/unified-common.conf"
    }
    r = session.post(f"{FLINK_URL}/jars/{jar_id}/run", json=payload)
    logging.info(f"Submit Response: {r.status_code} - {r.text}")

def check_job_running(job_name):
    try:
        r = session.get(FLINK_HEALTH_API, timeout=API_TIMEOUT_SEC)
        if r.status_code != 200:
            return None
        jobs = r.json().get("jobs", [])
        return any(job.get("name") == job_name and job.get("status") == "RUNNING" for job in jobs)
    except Exception as e:
        logging.error(f"Error checking status for '{job_name}': {e}")
        return None

# ---------------------------------------------------
# Main Loop
# ---------------------------------------------------
def monitor_jobs():
    while True:
        logging.info("Polling Flink jobs status...")
        for name, jar in JOB_JARS.items():
            is_running = check_job_running(name)
            if is_running is True:
                logging.info(f"Job '{name}' is RUNNING.")
            elif is_running is False:
                logging.info(f"Job '{name}' not running. Submitting...")
                submit_job(jar)
            else:
                logging.warning(f"Status of '{name}' unknown. Skipping resubmission.")
        
        logging.info(f"Sleeping {CHECK_INTERVAL_SEC}s...")
        time.sleep(CHECK_INTERVAL_SEC)

if __name__ == "__main__":
    start_akka_service()
    wait_for_service(AKKA_HEALTH, "Akka")
    
    if FLINK_URL:
        wait_for_service(f"{FLINK_URL}/overview", "Flink")
    
    setup_tmux_session("resource_cleanup", CLEANUP_SCRIPT, DATA_CLEANUP_ENABLED)
    setup_tmux_session("mentoring_batch_job", MENTORING_SCRIPT, MENTORING_ENABLED)
    
    monitor_jobs()
