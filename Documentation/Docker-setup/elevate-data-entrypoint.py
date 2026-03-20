# TODO: up akka service + data cleanup + mentoring batch job + autosubmission of flink job (need based as per requirement (pass as a parameter (yes/no)))
import os
import sys
import json
import time
import base64
import zipfile
import subprocess
import atexit
import requests
import logging
from logging.handlers import RotatingFileHandler
from pyhocon import ConfigFactory

# ---------------------------------------------------
# Load configuration first to get log paths
# ---------------------------------------------------
UNIFIED_CONF = os.getenv("UNIFIED_PIPELINE_CONF", "/job-configs/unified-common.conf")

if not os.path.exists(UNIFIED_CONF):
    print(f"ERROR: unified-common.conf not found at {UNIFIED_CONF}")
    sys.exit(1)

conf = ConfigFactory.parse_file(UNIFIED_CONF)

def get_config_strict(config, path, description):
    """Retrieve a value from config or exit with error if missing."""
    try:
        val = config.get(path)
        if val is None:
            raise KeyError(path)
        return val
    except KeyError:
        logging.error(f"Missing required configuration key: {path} ({description})")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error retrieving configuration key {path}: {e}")
        sys.exit(1)

# ---------------------------------------------------
# Setup Logging
# ---------------------------------------------------
def setup_logging():
    log_file = os.getenv("LOG_FILE_PATH")  # to do remove this env variable
    if not log_file:
        # Try to get from config
        log_file = conf.get("elevate-data.log-path", "/logs/elevate-data.log")

    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError:
            # Fallback to current directory if /var/log is not writable
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
# configuration
# ---------------------------------------------------
CHECK_INTERVAL_SEC = int(get_config_strict(conf, "health.check.interval.sec", "Monitor interval"))
API_TIMEOUT_SEC = int(conf.get("health.check.api-timeout-sec", 30))
FLINK_URL = get_config_strict(conf, "flink.url", "Flink JobManager URL")

JOB_JARS = dict(get_config_strict(conf, "health.check.job-jars", "Flink job jar mapping"))
JOB_CONF_ARRAY = list(get_config_strict(conf, "health.check.job-conf", "Flink job config paths"))

# Akka-service config
# _as = get_config_strict(conf, "akka-service", "Akka service settings")
AKKA_JAR     = get_config_strict(conf, "health.check.akka-jar", "Akka service JAR path")
AKKA_HOST    = get_config_strict(conf, "akka.http.host", "Akka host")
AKKA_PORT    = int(get_config_strict(conf, "akka.http.port", "Akka port"))
AKKA_HEALTH  = f"http://{AKKA_HOST}:{AKKA_PORT}/api/health"
AKKA_TOKEN   = get_config_strict(conf, "akka.security.api.token", "Akka security token")

# Data-cleanup config
DATA_CLEANUP_ENABLED = str(conf.get("data.cleanup.enabled", "no")).lower() == "yes"
CLEANUP_SCRIPT =  conf.get("data.cleanup.enabled", "/app/Documentation/data-cleanup/python-script/resource_delete.py")

# Migration-push config
MENTORING_BATCH_JOB_ENABLED = str(conf.get("mentoring.batch.job.enabled", "no")).lower() == "yes"
MENTORING_BATCH_SCRIPT = conf.get("mentoring.batch.job.enabled", "/app/Documentation/batch-scripts/mentoring.py")

# ---------------------------------------------------
# Akka Service : use the url + /health api to check the health of the service
# ---------------------------------------------------

_akka_proc = None

def start_akka_service():
    """Start the akka-service JAR as a background subprocess."""
    global _akka_proc

    logging.info(f"Starting akka-service from {AKKA_JAR} ...")

    akka_log_path = os.path.join(os.path.dirname(LOG_FILE), "akka-service.log")
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


def wait_for_akka(retries=30, delay=3):
    """Poll the health endpoint until it returns 200."""
    logging.info(f"Waiting for akka-service to become ready ({AKKA_HEALTH})...")
    headers = {"Authorization": AKKA_TOKEN}

    for attempt in range(1, retries + 1):
        try:
            r = requests.get(AKKA_HEALTH, headers=headers, timeout=30)
            if r.status_code == 200:
                logging.info(f"Akka service is ready (attempt {attempt}).")
                return
        except Exception:
            pass

        # Check if process has died unexpectedly
        if _akka_proc and _akka_proc.poll() is not None:
            logging.error("Akka service process has exited unexpectedly.")
            sys.exit(1)

        logging.info(f"Akka not ready yet, retrying ({attempt}/{retries})...")
        time.sleep(delay)

    logging.error("Akka service did not become ready in time.")
    sys.exit(1)


def stop_akka_service():
    """Gracefully terminate the akka-service subprocess on exit."""
    if _akka_proc and _akka_proc.poll() is None:
        logging.info("Stopping akka-service...")
        _akka_proc.terminate()
        try:
            _akka_proc.wait(timeout=10)
            logging.info("Akka service stopped.")
        except subprocess.TimeoutExpired:
            logging.warning("Akka service did not stop cleanly, killing it.")
            _akka_proc.kill()

atexit.register(stop_akka_service)

# ---------------------------------------------------
# Data Cleanup
# ---------------------------------------------------

def setup_data_cleanup():
    """Setup and start the data cleanup script in a tmux session if enabled."""
    if not DATA_CLEANUP_ENABLED:
        logging.info("Data cleanup is disabled in config. Skipping setup.")
        return

    logging.info("Setting up data cleanup...")

    # 1. Check if tmux is installed
    try:
        subprocess.run(["tmux", "-V"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logging.error("tmux not found. Data cleanup requires tmux to run in the background.")
        logging.error("Please install tmux manually (e.g., sudo apt install tmux -y). Skipping cleanup setup.")
        return

    # 2. Identify the script path
    actual_script = CLEANUP_SCRIPT
    if not os.path.exists(actual_script) and actual_script.startswith("/app/"):
        # Resolve relative to the local checkout (same logic as submit_job)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local_path = actual_script.replace("/app", base_dir)
        if os.path.exists(local_path):
            actual_script = local_path

    if not os.path.exists(actual_script):
        logging.error(f"Resource cleanup script not found at {actual_script}")
        return

    # 3. Check if session already exists
    res = subprocess.run(["tmux", "has-session", "-t", "resource_cleanup"], capture_output=True)
    if res.returncode == 0:
        logging.info("tmux session 'resource_cleanup' already exists. Killing it to restart.")
        subprocess.run(["tmux", "kill-session", "-t", "resource_cleanup"])

    # 4. Create a new detached tmux session and run the script
    logging.info(f"Starting data cleanup script in tmux session 'resource_cleanup': {actual_script}")
    # Use full path for python3 as recommended
    cmd = f"python3 {actual_script}"
    subprocess.run(["tmux", "new-session", "-d", "-s", "resource_cleanup", cmd])
    logging.info("Data cleanup setup complete and session started in background.")


def setup_migration_push():
    """Setup and start the migration push script in a tmux session if enabled."""
    if not MENTORING_BATCH_JOB_ENABLED:
        logging.info("Mentoring batch job is not enabled Skipping setup.")
        return

    logging.info("Setting up migration push...")

    # 1. Check if tmux is installed
    try:
        subprocess.run(["tmux", "-V"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logging.error("tmux not found. Migration push requires tmux to run in the background.")
        logging.error("Please install tmux manually (e.g., sudo apt install tmux -y). Skipping migration setup.")
        return

    # 2. Identify the script path
    actual_script = MENTORING_BATCH_SCRIPT
    if not os.path.exists(actual_script) and actual_script.startswith("/app/"):
        # Resolve relative to the local checkout
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local_path = actual_script.replace("/app", base_dir)
        if os.path.exists(local_path):
            actual_script = local_path

    if not os.path.exists(actual_script):
        logging.error(f"Mentoring Batch script not found at {actual_script}")
        return

    # 3. Check if session already exists
    res = subprocess.run(["tmux", "has-session", "-t", "mentoring_batch_job"], capture_output=True)
    if res.returncode == 0:
        logging.info("tmux session 'mentoring_batch_job' already exists. Killing it to restart.")
        subprocess.run(["tmux", "kill-session", "-t", "mentoring_batch_job"])

    # 4. Create a new detached tmux session and run the script
    logging.info(f"Starting migration push script in tmux session 'mentoring_batch_job': {actual_script}")
    cmd = f"python3 {actual_script}"
    subprocess.run(["tmux", "new-session", "-d", "-s", "mentoring_batch_job", cmd])
    logging.info("Mentoring batch job setup completed and session started in background.")


# ---------------------------------------------------
# Helpers
# ---------------------------------------------------

def get_entry_class_from_jar(jar_path):
    """Extract Main-Class from JAR manifest, handling multiline wrapping"""
    try:
        with zipfile.ZipFile(jar_path) as jar:
            manifest = jar.read("META-INF/MANIFEST.MF").decode()

            # Manifest lines can wrap at 72 chars; continuation lines start with a space.
            lines = []
            for line in manifest.splitlines():
                if line.startswith(" "):
                    if lines:
                        lines[-1] += line[1:]
                elif line.strip():
                    lines.append(line)

            for line in lines:
                if line.startswith("Main-Class:"):
                    return line.split(":", 1)[1].strip()
    except Exception as e:
        logging.error(f"Failed reading manifest: {e}")

    return None


def get_config_b64(conf_file):
    """Read config file and return base64 encoded content. Resolves /app paths locally."""
    actual_path = conf_file
    if not os.path.exists(actual_path) and actual_path.startswith("/app/"):
        # Try to resolve relative to the local checkout
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local_path = actual_path.replace("/app", base_dir)
        if os.path.exists(local_path):
            actual_path = local_path

    with open(actual_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def wait_for_flink():
    logging.info("Waiting for Flink JobManager...")

    for _ in range(30):
        try:
            r = requests.get(f"{FLINK_URL}/overview", timeout=5)
            if r.status_code == 200:
                logging.info("Flink JobManager is ready.")
                return
        except:
            pass

        logging.info("Waiting...")
        time.sleep(2)

    logging.error("Flink JobManager did not start.")
    sys.exit(1)


def upload_jar(jar_path):

    with open(jar_path, "rb") as f:

        files = {"jarfile": f}

        r = requests.post(
            f"{FLINK_URL}/jars/upload",
            files=files
        )

    if r.status_code != 200:
        logging.error(f"Jar upload failed with status {r.status_code}: {r.text}")
        return None

    try:
        data = r.json()
    except Exception as e:
        logging.error(f"Failed to parse jar upload response as JSON: {e}. Response: {r.text}")
        return None

    filename = data.get("filename", "")
    return filename.split("/")[-1]


def submit_job(jar, conf):
    """Submit a Flink job. Resolves /app paths locally."""
    actual_jar = jar
    if not os.path.exists(actual_jar) and actual_jar.startswith("/app/"):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local_jar = actual_jar.replace("/app", base_dir)
        if os.path.exists(local_jar):
            actual_jar = local_jar

    config_b64 = get_config_b64(conf)

    logging.info("----------------------------------------")
    logging.info("Submitting Job")
    logging.info(f"Jar  : {actual_jar}")
    logging.info(f"Conf : {conf}")
    logging.info("----------------------------------------")

    entry_class = get_entry_class_from_jar(actual_jar)

    logging.info(f"Detected Entry Class: {entry_class}")

    if not entry_class:
        logging.error("Could not detect entry class.")
        return

    jar_id = upload_jar(actual_jar)

    if not jar_id:
        logging.error("Jar upload failed")
        return

    logging.info(f"Uploaded jar id: {jar_id}")

    payload = {
        "entryClass": entry_class,
        "programArgs": f"--config.content {config_b64}"
    }

    requests.post(
        f"{FLINK_URL}/jars/{jar_id}/run",
        json=payload
    )

    logging.info("Job submitted.")


def check_api_job_status(job_name):

    headers = {"Authorization": AKKA_TOKEN}

    try:
        r = requests.get(
            AKKA_HEALTH,
            headers=headers,
            timeout=API_TIMEOUT_SEC
        )
        if r.status_code != 200:
            logging.warning(f"Health check API returned status {r.status_code} for {AKKA_HEALTH}")
            return None

        data = r.json()
        # FlinkHealth response is { "cluster": ..., "jobs": [...] }
        jobs = data.get("jobs", []) if isinstance(data, dict) else []

        for job in jobs:
            if isinstance(job, dict) and job.get("name") == job_name:
                if job.get("status") == "RUNNING":
                    return True
                else:
                    return False
        
        # Job not found in the list
        return False
    except Exception as e:
        logging.error(f"Error checking job status for '{job_name}': {e}")
        return None


# ---------------------------------------------------
# Job monitor loop
# ---------------------------------------------------

def monitor_jobs():

    conf = JOB_CONF_ARRAY[0]

    while True:

        logging.info("Checking Flink jobs...")

        for name, jar in JOB_JARS.items():
            status = check_api_job_status(name)

            if status is True:
                logging.info(f"Job '{name}' is already running.")
            elif status is False:
                logging.info(f"Submitting job '{name}'...")
                submit_job(jar, conf)
            else:
                logging.warning(f"Status of job '{name}' is unknown (likely timeout). Skipping resubmission to avoid duplicates.")

        logging.info(f"Sleeping {CHECK_INTERVAL_SEC} seconds...")

        time.sleep(CHECK_INTERVAL_SEC)


# ---------------------------------------------------
# Start
# ---------------------------------------------------

if __name__ == "__main__":

    # 1. Start akka-service
    start_akka_service()
    wait_for_akka()

    # 2. Wait for Flink JobManager
    wait_for_flink()

    # 3. Setup data cleanup (if enabled)
    setup_data_cleanup()

    # 4. Setup migration push (if enabled)
    setup_migration_push()

    # 5. Start Flink job monitor loop
    monitor_jobs()