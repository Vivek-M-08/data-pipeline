import json
import os
from pyhocon import ConfigFactory
from kafka import KafkaConsumer
import psycopg2
from psycopg2 import sql
import psycopg2.extras
from dashboard_resource_helper import MetabaseUtil, load_metabase_config
import logging
from logging.handlers import RotatingFileHandler

# ---------------------------------------------------
# Load config
# ---------------------------------------------------
base_dir = os.path.dirname(os.path.abspath(__file__))

# The script expects the conf file path in an env variable, or falls back to the repository root
UNIFIED_CONF = os.environ.get("UNIFIED_PIPELINE_CONF", os.path.abspath(os.path.join(base_dir, "../../..", 'unified-common.conf')))
config = ConfigFactory.parse_file(UNIFIED_CONF)

DB_HOST = config.get_string('postgres.host', 'host')
DB_USER = config.get_string('postgres.username', 'user')
DB_PASS = config.get_string('postgres.password', 'password')
DB_NAME = config.get_string('postgres.database', 'dbname')
ENV = config.get_string('job.env', 'env')      # example: "local"
TOPIC = config.get_string('kafka.resource.delete.topic', 'topic')
GROUP_ID = config.get_string('kafka.resource.delete.groupId', 'group_id')
BROKER = config.get_string('kafka.broker.servers', 'broker')

url, user, pwd = load_metabase_config()
mb = MetabaseUtil(url, user, pwd)

LOG_FILE_PATH = config.get_string('data.cleanup.log.path', '/tmp')
os.makedirs(LOG_FILE_PATH, exist_ok=True)
LOG_FILE = os.path.join(LOG_FILE_PATH, "resource-delete.log")

logger = logging.getLogger("resource_delete_logger")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)

console = logging.StreamHandler()
console.setFormatter(formatter)

logger.addHandler(handler)
logger.addHandler(console)

conn = psycopg2.connect(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASS,
    dbname=DB_NAME
)
conn.autocommit = True


def db_query(query, params=None):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query, params or ())
        return cur.fetchall()


def db_execute(query, params=None):
    with conn.cursor() as cur:
        cur.execute(query, params or ())
        
consumer = KafkaConsumer(
    TOPIC,
    bootstrap_servers=[BROKER],
    auto_offset_reset='latest',
    enable_auto_commit=True,
    group_id=GROUP_ID,
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

logger.info(f"Listening for delete events on topic: {TOPIC}")

def table_exists(table_name):
    query = sql.SQL("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = %s
        );
    """)
    rows = db_query(query, (table_name,))
    return rows[0]["exists"]

def drop_if_exists(table_name, sol_id):
    logger.info(f"Checking table: {table_name}")

    if table_exists(table_name):
        logger.info(f"Dropping table: {table_name}")

        drop_q = sql.SQL("DROP TABLE IF EXISTS {}.{} CASCADE").format(
            sql.Identifier("public"),
            sql.Identifier(table_name)
        )
        db_execute(drop_q)

        # Delete from solution table
        db_execute(
            sql.SQL("DELETE FROM {} WHERE solution_id = %s").format(
                sql.Identifier(f"{ENV}_solutions")
            ),
            (sol_id,)
        )

        # Delete dashboard metadata
        db_execute(
            sql.SQL("DELETE FROM {} WHERE entity_id = %s").format(
                sql.Identifier(f"{ENV}_dashboard_metadata")
            ),
            (sol_id,)
        )
    else:
        logger.info(f"{table_name} does not exist.")

def process_improvement_project(solution_id):

    q = sql.SQL("SELECT project_id FROM {} WHERE solution_id = %s").format(
        sql.Identifier(f"{ENV}_projects")
    )
    project_rows = db_query(q, (solution_id,))

    project_ids = [r["project_id"] for r in project_rows]

    if not project_ids:
        return False, []

    logger.info(f"Found Improvement Project IDs: {project_ids}")

    for pid in project_ids:
        del_tasks = sql.SQL("DELETE FROM {} WHERE project_id = %s").format(
            sql.Identifier(f"{ENV}_tasks")
        )
        db_execute(del_tasks, (pid,))

    db_execute(
        sql.SQL("DELETE FROM {} WHERE solution_id = %s").format(
            sql.Identifier(f"{ENV}_projects")
        ),
        (solution_id,)
    )
    db_execute(
        sql.SQL("DELETE FROM {} WHERE solution_id = %s").format(
            sql.Identifier(f"{ENV}_solutions")
        ),
        (solution_id,)
    )
    db_execute(
        sql.SQL("DELETE FROM {} WHERE entity_id = %s").format(
            sql.Identifier(f"{ENV}_dashboard_metadata")
        ),
        (solution_id,)
    )

    return True, project_ids

def process_observation(solution_id):
    tables = [
        f"{solution_id}_domain",
        f"{solution_id}_status",
        f"{solution_id}_questions",
    ]
    for tbl in tables:
        drop_if_exists(tbl, solution_id)

def process_survey(solution_id):
    tables = [
        f"{solution_id}_survey_status",
        f"{solution_id}"
    ]
    for tbl in tables:
        drop_if_exists(tbl, solution_id)


for message in consumer:
    try:
        data = message.value

        if "type" not in data or "entityId" not in data:
            logger.error("Invalid message")
            continue

        entity_type = data["type"]
        entity_id = data["entityId"]

        # ---------------- PROGRAM DELETE ----------------
        if entity_type == "program":
            program_id = entity_id
            logger.info(f"Deleting program: {program_id}")

            sol_q = sql.SQL("""
                SELECT DISTINCT solution_id
                FROM {}
                WHERE program_id = %s
            """).format(
                sql.Identifier(f"{ENV}_solutions")
            )

            rows = db_query(sol_q, (program_id,))
            solution_ids = [r["solution_id"] for r in rows]

            for sol in solution_ids:
                ok, proj_ids = process_improvement_project(sol)
                if not ok:
                    process_survey(sol)
                    process_observation(sol)

            db_execute(
                sql.SQL("DELETE FROM {} WHERE entity_id = %s").format(
                    sql.Identifier(f"{ENV}_dashboard_metadata")
                ),
                (program_id,)
            )

            collection_id = mb.get_collection_id(program_id)
            mb.delete_collection(collection_id)

            groups = mb.get_permission_groups()
            gid = mb.get_permission_group_id(groups, program_id)
            mb.delete_permission_group(gid)

        # ---------------- SOLUTION DELETE ----------------
        elif entity_type == "solution":
            solution_id = entity_id
            logger.info(f"Deleting solution: {solution_id}")

            ok, proj_ids = process_improvement_project(solution_id)

            if not ok:
                process_survey(solution_id)
                process_observation(solution_id)

            collection_id = mb.get_collection_id(solution_id)
            mb.delete_collection(collection_id)

            groups = mb.get_permission_groups()
            gid = mb.get_permission_group_id(groups, solution_id)
            mb.delete_permission_group(gid)

        else:
            logger.info("Unknown event type; skipping.")

    except Exception as e:
        logger.error(f"Error: {str(e)}")
