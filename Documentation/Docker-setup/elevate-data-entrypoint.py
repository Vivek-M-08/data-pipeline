import os
import sys
import time
import base64
import zipfile
import subprocess
import logging
import requests
from pyhocon import ConfigFactory
from logging.handlers import TimedRotatingFileHandler

# ---------------------------------------------------
# Configuration & Paths
# ---------------------------------------------------
UNIFIED_CONF = os.getenv("UNIFIED_PIPELINE_CONF", "/app/unified-common.conf")

if not os.path.exists(UNIFIED_CONF):
    print(f"ERROR: Configuration file not found at {UNIFIED_CONF}")
    sys.exit(1)

conf = ConfigFactory.parse_file(UNIFIED_CONF)

# ---------------------------------------------------
# Setup Logging
# ---------------------------------------------------
def setup_logging():
    log_file = conf.get("elevate.data.entrypoint.log.path")
    log_dir = os.path.dirname(log_file)

    try:
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    except OSError:
        log_file = "elevate-data.log"
        log_dir = ""

    logger = logging.getLogger("elevate-data-entrypoint")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger, log_file

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )

    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File (daily rotation)
    try:
        fh = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=7,
            encoding="utf-8"
        )
        fh.suffix = "%Y-%m-%d"

        def namer(default_name):
            base, date = default_name.rsplit(".", 1)
            return f"{base}-{date}.log"

        fh.namer = namer
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    except Exception as e:
        print(f"Warning: Could not setup file logging: {e}")

    return logger, log_file

# ---------------------------------------------------
# Global Configuration
# ---------------------------------------------------
CHECK_INTERVAL_SEC = int(conf.get("health.check.interval.sec"))
FLINK_URL = conf.get("flink.url")
JOB_JARS = dict(conf.get("health.check.job-jars"))

# Akka-service config
AKKA_JAR = conf.get("health.check.akka-jar")
AKKA_HOST = conf.get("akka.http.host")
AKKA_PORT = int(conf.get("akka.http.port"))
AKKA_TOKEN = conf.get("akka.security.api.token")

AKKA_HEALTH = f"http://{AKKA_HOST}:{AKKA_PORT}/health"
FLINK_HEALTH_API = f"http://{AKKA_HOST}:{AKKA_PORT}/api/health/flink"

# Data-cleanup config
DATA_CLEANUP_ENABLED = conf.get("data.cleanup.enabled")
CLEANUP_SCRIPT = conf.get("data.cleanup.script.path")

# Mentoring-push config
MENTORING_ENABLED = conf.get("mentoring.batch.job.enabled")
MENTORING_SCRIPT = conf.get("mentoring.batch.job.script.path")
MENTORING_CRON = conf.get("mentoring.batch.job.cron")

# Shared HTTP Session
session = requests.Session()
session.headers.update({"Authorization": AKKA_TOKEN})

# ---------------------------------------------------
# Akka Service
# ---------------------------------------------------
_akka_proc = None

def is_akka_running():
    """Check if akka service is already running"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", AKKA_JAR],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return result.returncode == 0
    except Exception:
        return False


def start_akka_service(logger, log_file):
    global _akka_proc

    if is_akka_running():
        logger.info("Akka service is already running. Skipping start.")
        return

    if not AKKA_JAR or not os.path.exists(AKKA_JAR):
        logger.error(f"Akka JAR not found: {AKKA_JAR}")
        return

    logger.info(f"Starting akka-service from {AKKA_JAR}...")

    log_dir = os.path.dirname(log_file)
    akka_log_path = os.path.join(log_dir, "elevate-data.log") if log_dir else "elevate-data.log"

    try:
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
    except OSError:
        akka_log_path = "akka-service.log"

    command = [
        "java",
        f"-Dconfig.file={UNIFIED_CONF}",
        "-jar",
        AKKA_JAR
    ]

    try:
        akka_log_file = open(akka_log_path, "a")

        _akka_proc = subprocess.Popen(
            command,
            env={**os.environ, "UNIFIED_PIPELINE_CONF": UNIFIED_CONF},
            stdout=akka_log_file,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setpgrp
        )

        logger.info(f"Akka service started (PID={_akka_proc.pid})")
        logger.info(f"Akka logs: {akka_log_path}")

    except Exception as e:
        logger.error(f"Failed to start akka service: {e}")

# ---------------------------------------------------
# Tmux Session Helpers
# ---------------------------------------------------
def _run_tmux(*args):
    """Run a tmux command, reaping the child immediately to avoid zombies."""
    proc = subprocess.Popen(
        ["tmux"] + list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid
    )
    stdout, stderr = proc.communicate()
    return proc.returncode


def setup_tmux_session(session_name, script_path, enabled):
    if not enabled:
        logger.info(f"{session_name} is disabled. Skipping.")
        return

    if not script_path or not os.path.exists(script_path):
        logger.error(f"Script for {session_name} not found at {script_path}")
        return

    # Check tmux availability
    try:
        proc = subprocess.Popen(["tmux", "-V"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.communicate()
        if proc.returncode != 0:
            raise FileNotFoundError
    except FileNotFoundError:
        logger.error(f"tmux not found. {session_name} requires tmux.")
        return

    # Check if session already exists
    rc = _run_tmux("has-session", "-t", session_name)
    if rc == 0:
        logger.info(f"tmux session '{session_name}' already running. Skipping creation.")
        return

    # Create new session only if not running
    logger.info(f"Starting {session_name} in tmux: {script_path}")
    _run_tmux("new-session", "-d", "-s", session_name, f"python3 {script_path}")

# ---------------------------------------------------
# Cron Setup
# ---------------------------------------------------
def setup_cron_job(script_path, cron_schedule, enabled):

    if not enabled:
        logger.info("Mentoring batch job is disabled. Skipping setup.")
        return

    if not script_path or not os.path.exists(script_path):
        logger.error(f"Cron script not found at {script_path}")
        return

    # Check if crontab already has this script
    try:
        res = subprocess.run(["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # return code 1 usually means no crontab for user, which is fine
        current_cron = res.stdout if res.returncode == 0 else ""
        
        if script_path in current_cron:
            logger.info(f"Cron job for {script_path} is already setup. Skipping.")
            return

        # Setup cron job to run every 2 hours
        cron_command = f"{cron_schedule} /bin/bash {script_path} >> /tmp/run-batch.log 2>&1\n"
        new_cron = (current_cron + "\n" + cron_command).lstrip()
        
        process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        process.communicate(new_cron)
        
        if process.returncode == 0:
            logger.info(f"Successfully setup cron job for {script_path} with schedule '{cron_schedule}'.")
        else:
            logger.error(f"Failed to setup cron job for {script_path}.")
    except Exception as e:
        logger.error(f"Error setting up cron job: {e}")

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
        logger.error(f"Failed reading manifest for {jar_path}: {e}")
    return None

def upload_jar(jar_path):
    try:
        with open(jar_path, "rb") as f:
            r = session.post(f"{FLINK_URL}/jars/upload", files={"jarfile": f})
        if r.status_code == 200:
            return r.json().get("filename", "").split("/")[-1]
        logger.error(f"Jar upload failed: {r.status_code} - {r.text}")
    except Exception as e:
        logger.error(f"Error uploading jar {jar_path}: {e}")
    return None

def submit_job(jar_path):
    if not os.path.exists(jar_path):
        logger.error(f"Jar file not found: {jar_path}")
        return

    entry_class = get_entry_class_from_jar(jar_path)
    if not entry_class:
        logger.error(f"Could not detect entry class for {jar_path}")
        return

    jar_id = upload_jar(jar_path)
    if not jar_id: return

    try:
        with open(UNIFIED_CONF, "rb") as f:
            config_content = base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to read configs for job submission: {e}")
        return

    logger.info(f"Submitting job with Jar ID: {jar_id}, Class: {entry_class}")
    payload = {
        "entryClass": entry_class,
        "programArgs": f"--config.content {config_content}"
    }
    r = session.post(f"{FLINK_URL}/jars/{jar_id}/run", json=payload)
    logger.info(f"Submit Response: {r.status_code} - {r.text}")

def check_job_running(job_name):
    try:
        r = session.get(FLINK_HEALTH_API)
        if r.status_code != 200:
            return None
        jobs = r.json().get("jobs", [])
        return any(job.get("name") == job_name and job.get("status") == "RUNNING" for job in jobs)
    except Exception as e:
        logger.error(f"Error checking status for '{job_name}': {e}")
        return None
    
# ---------------------------------------------------
# Main Loop
# ---------------------------------------------------
def monitor_jobs(logger, log_file):
    while True:
        logger.info("Checking Flink jobs status...")

        start_akka_service(logger, log_file)
        setup_tmux_session("resource_cleanup", CLEANUP_SCRIPT, DATA_CLEANUP_ENABLED)
        setup_cron_job(MENTORING_SCRIPT, MENTORING_CRON, MENTORING_ENABLED)
        
        for name, jar in JOB_JARS.items():
            is_running = check_job_running(name)
            if is_running is True:
                logger.info(f"Job '{name}' is RUNNING.")
            elif is_running is False:
                logger.info(f"Job '{name}' not running. Submitting...")
                submit_job(jar)
            else:
                logger.warning(f"Status of '{name}' unknown. Skipping resubmission.")

        logger.info(f"Sleeping {CHECK_INTERVAL_SEC}s...")
        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    logger, log_file = setup_logging()

    logger.info("Starting Elevate entry point script...")

    monitor_jobs(logger, log_file)

