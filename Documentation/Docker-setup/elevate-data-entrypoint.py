import os
import sys
import time
import base64
import zipfile
import subprocess
import logging
import xml.etree.ElementTree as ET
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
    log_file_path = conf.get("elevate.data.entrypoint.log.path")

    logger = logging.getLogger("elevate-data-entrypoint")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger, log_file_path

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

    # Console
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File (daily rotation)
    try:
        fh = TimedRotatingFileHandler(log_file_path, when="midnight", interval=1, backupCount=7, encoding="utf-8")
        fh.suffix = "%Y-%m-%d"

        def namer(default_name):
            base, date = default_name.rsplit(".", 1)
            return f"{base}-{date}.log"

        fh.namer = namer
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    except Exception as e:
        print(f"Warning: Could not setup file logging: {e}")

    return logger, log_file_path

# ---------------------------------------------------
# Global Configuration
# ---------------------------------------------------
CHECK_INTERVAL_SEC = int(conf.get("health.check.interval.sec"))
FLINK_URL = conf.get("flink.url")
JOB_JARS = dict(conf.get("health.check.flink.job.jars"))

# Akka-service config
AKKA_JAR = conf.get("akka.service.jar")
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
MENTORING_CRON_TIME = conf.get("mentoring.batch.job.cron.time")

# Shared HTTP Session
session = requests.Session()
session.headers.update({"Authorization": AKKA_TOKEN})

# ---------------------------------------------------
# Akka Service
# ---------------------------------------------------
akka_proc = None

def is_akka_running():
    """Check if akka service is healthy via its /health endpoint."""
    try:
        r = requests.get(AKKA_HEALTH, timeout=5)
        return r.status_code == 200 and r.json().get("status") == "UP"
    except Exception:
        return False


def start_akka_service():
    global akka_proc

    if is_akka_running():
        logger.info("Akka service is already running. Skipping....")
        return

    if not AKKA_JAR or not os.path.exists(AKKA_JAR):
        logger.error(f"Akka JAR not found: {AKKA_JAR}")
        return

    logger.info(f"Starting akka-service from {AKKA_JAR}...")

    akka_log_path = conf.get("akka.service.log.path")

    command = ["java", f"-Dconfig.file={UNIFIED_CONF}", "-jar", AKKA_JAR]

    try:
        akka_log_file = open(akka_log_path, "a")

        akka_proc = subprocess.Popen(command, stdout=akka_log_file, stderr=subprocess.STDOUT, preexec_fn=os.setpgrp)

        logger.info(f"Akka service started (PID={akka_proc.pid})")
        logger.info(f"Akka logs: {akka_log_path}")

    except Exception as e:
        logger.error(f"Failed to start akka service: {e}")

# ---------------------------------------------------
# Tmux Session Helpers
# ---------------------------------------------------
def run_tmux(*args):
    proc = subprocess.Popen(["tmux"] + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid)
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
    rc = run_tmux("has-session", "-t", session_name)
    if rc == 0:
        logger.info(f"tmux session '{session_name}' already running. Skipping creation.")
        return

    # Create new session only if not running
    logger.info(f"Starting {session_name} in tmux: {script_path}")
    run_tmux("new-session", "-d", "-s", session_name, f"python3 {script_path}")

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

def get_entry_class_from_pom(jar_path):
    """Derive the pom.xml path from the jar path and extract <mainClass>.

    Given a jar at: /app/stream-jobs/<module>/target/<artifact>.jar
    The pom.xml is at: /app/stream-jobs/<module>/pom.xml
    """
    try:
        # jar is inside <module>/target/; go up two levels to reach <module>/
        module_dir = os.path.dirname(os.path.dirname(jar_path))
        pom_path = os.path.join(module_dir, "pom.xml")

        if not os.path.exists(pom_path):
            logger.warning(f"pom.xml not found at {pom_path}")
            return None

        tree = ET.parse(pom_path)
        root = tree.getroot()

        ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
        ns_prefix = f"{{{ns}}}" if ns else ""

        main_class = root.find(f".//{ns_prefix}mainClass")
        if main_class is not None and main_class.text:
            logger.info(f"Found mainClass in {pom_path}: {main_class.text.strip()}")
            return main_class.text.strip()

        logger.warning(f"<mainClass> not found in {pom_path}")
    except Exception as e:
        logger.error(f"Failed reading pom.xml for {jar_path}: {e}")
    return None

def check_and_upload_jar(jar_path):
    """If jar is already uploaded on Flink, return the jar_id. Otherwise, upload the jar and return the jar_id."""
    jar_filename = os.path.basename(jar_path)

    # Check if the jar is already uploaded on Flink
    try:
        r = session.get(f"{FLINK_URL}/jars")
        if r.status_code == 200:
            for jar in r.json().get("files", []):
                # Flink stores jars as "<uuid>_<original-filename>"
                uploaded_name = jar.get("name", "")
                if uploaded_name.endswith(jar_filename):
                    jar_id = jar.get("id", "").split("/")[-1]
                    logger.info(f"Jar already uploaded: {uploaded_name} (id={jar_id}). Skipping upload.")
                    return jar_id
    except Exception as e:
        logger.warning(f"Could not check existing jars on Flink: {e}")

    # Not found — upload the jar
    try:
        with open(jar_path, "rb") as f:
            r = session.post(f"{FLINK_URL}/jars/upload", files={"jarfile": f})
        if r.status_code == 200:
            jar_id = r.json().get("filename", "").split("/")[-1]
            logger.info(f"Jar uploaded successfully: {jar_filename} (id={jar_id})")
            return jar_id
        logger.error(f"Jar upload failed: {r.status_code} - {r.text}")
    except Exception as e:
        logger.error(f"Error uploading jar {jar_path}: {e}")
    return None

def submit_job(jar_path):
    if not os.path.exists(jar_path):
        logger.error(f"Jar file not found: {jar_path}")
        return

    entry_class = get_entry_class_from_pom(jar_path)
    if not entry_class:
        logger.error(f"Could not detect entry class for {jar_path}")
        return

    jar_id = check_and_upload_jar(jar_path)

    if not jar_id: return

    try:
        with open(UNIFIED_CONF, "rb") as f:
            config_content = base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to read configs for job submission: {e}")
        return

    logger.info(f"Submitting job with Jar ID: {jar_id}, Class: {entry_class}")
    payload = {"entryClass": entry_class, "programArgs": f"--config.content {config_content}"}
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

        start_akka_service()
        setup_tmux_session("resource_cleanup", CLEANUP_SCRIPT, DATA_CLEANUP_ENABLED)
        setup_cron_job(MENTORING_SCRIPT, MENTORING_CRON_TIME, MENTORING_ENABLED)
        
        for name, jar in JOB_JARS.items():
            is_running = check_job_running(name)
            if is_running is True:
                logger.info(f"Job '{name}' is RUNNING.")
            elif is_running is False:
                logger.info(f"Job '{name}' not running. Submitting...")
                submit_job(jar)
            else:
                logger.warning(f"Status of '{name}' unknown. Skipping resubmission.")

        logger.info(f"Sleeping {CHECK_INTERVAL_SEC}s...\n")
        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    logger, log_file = setup_logging()

    logger.info(f"Starting Elevate entry point script...")

    monitor_jobs(logger, log_file)

