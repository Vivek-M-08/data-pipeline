import requests
import json
import time
import os
from pyhocon import ConfigFactory
import logging
from logging.handlers import RotatingFileHandler
logger = logging.getLogger("resource_delete_logger")

def load_metabase_config():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    UNIFIED_CONF = os.environ.get("UNIFIED_PIPELINE_CONF", os.path.abspath(os.path.join(base_dir, "../../..", 'unified-common.conf')))
    config = ConfigFactory.parse_file(UNIFIED_CONF)

    url = config.get_string("metabase.url")
    username = config.get_string("metabase.username")
    password = config.get_string("metabase.password")

    return url, username, password


class MetabaseUtil:

    def __init__(self, metabase_url, username, password):
        self.metabase_url = metabase_url.rstrip("/")
        self.username = username
        self.password = password
        self.session_token = None
        self.collection_cache = None
        self.last_cache_time = 0
        self.cache_ttl = 1800
        
    def get_session_token(self):
        if self.session_token:
            return self.session_token

        url = f"{self.metabase_url}/session"
        payload = {"username": self.username, "password": self.password}

        resp = requests.post(url, json=payload)
        if resp.status_code == 200:
            token = resp.json().get("id")
            self.session_token = token
            return token

        raise Exception(f"Authentication failed: {resp.status_code} {resp.text}")

    def list_collections(self, force_refresh=False):
        now = time.time()

        # Use cache if available
        if (not force_refresh and 
            self.collection_cache is not None and 
            now - self.last_cache_time < self.cache_ttl):
            return self.collection_cache

        url = f"{self.metabase_url}/collection"
        headers = {
            "Content-Type": "application/json",
            "X-Metabase-Session": self.get_session_token(),
        }

        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            self.collection_cache = resp.json()
            self.last_cache_time = now
            return self.collection_cache
        else:
            logger.error(f"[ERROR] Failed to list collection ({resp.status_code}): {resp.text}")
            return []

    def get_collection_id(self, target_id):
        collections = self.list_collections()

        coll_id = [
            col.get("id")
            for col in collections
            if target_id in (col.get("description") or "")
        ]

        if coll_id:
            logger.info(f"collection IDs to delete: {coll_id}")
        return coll_id

    def delete_collection(self, collection_id):
        logger.info(f">>> Deleting Metabase collection ID: {collection_id}")
        
        if len(collection_id) == 0:
            logger.info(">>> Collection ID is None, skipping deletion.")
            return False
        else:
            for cid in collection_id:
                url = f"{self.metabase_url}/collection/{cid}"
                logger.info(f">>> PUT URL: {url}")

                headers = {
                    "Content-Type": "application/json",
                    "X-Metabase-Session": self.get_session_token(),
                }

                payload = {
                    "archived": True
                }
                resp = requests.put(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    logger.info(f">>> Successfully archived collection ID: {cid}")
                else:
                    logger.info(f"[ERROR] Failed to archive collection ({resp.status_code}): {resp.text}")

    def get_permission_groups(self):
        url = f"{self.metabase_url}/permissions/group"
        headers = {
            "Content-Type": "application/json",
            "X-Metabase-Session": self.get_session_token(),
        }

        resp = requests.get(url, headers=headers)

        if resp.status_code == 200:
            return resp.json()

        raise Exception(
            f"Failed to fetch permission groups ({resp.status_code}): {resp.text}"
        )

    def delete_permission_group(self, group_id: int):
        if group_id is None:
            logger.info("No matching permission group found; skipping deletion.")
            return False
        
        url = f"{self.metabase_url}/permissions/group/{group_id}"
        
        headers = {
            "Content-Type": "application/json",
            "X-Metabase-Session": self.get_session_token(),
        }

        resp = requests.delete(url, headers=headers)

        if resp.status_code == 204:
            logger.info(f"Group {group_id} deleted successfully.")
            return True

        logger.error(
            f"[ERROR] Failed to delete group {group_id}: "
            f"{resp.status_code}, {resp.text}"
        )
        return False
    @staticmethod
    def get_permission_group_id(groups, program_id):
        for group in groups:
            if program_id in group.get("name", ""):
                return group["id"]
        return None
