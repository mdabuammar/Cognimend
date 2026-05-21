import os
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
import logging

logger = logging.getLogger(__name__)

# Connection pool
db_pool = None

def init_db_pool():
    global db_pool
    if db_pool is None:
        try:
            db_pool = SimpleConnectionPool(
                1, 10,
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=os.getenv("POSTGRES_PORT", "5432"),
                dbname=os.getenv("POSTGRES_DB", "cognimend"),
                user=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD", "password123")
            )
            logger.info("Gateway DB pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize DB pool: {e}")

def get_db_connection():
    if not db_pool:
        init_db_pool()
    if db_pool:
        return db_pool.getconn()
    return None

def release_db_connection(conn):
    if db_pool and conn:
        db_pool.putconn(conn)

def get_user_workspace_role(user_id: str, workspace_id: str):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT role FROM workspace_members WHERE user_id = %s AND workspace_id = %s",
                (user_id, workspace_id)
            )
            result = cursor.fetchone()
            return result['role'] if result else None
    finally:
        release_db_connection(conn)

def get_user_default_workspace(user_id: str):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT workspace_id, role FROM workspace_members WHERE user_id = %s LIMIT 1",
                (user_id,)
            )
            result = cursor.fetchone()
            return result
    finally:
        release_db_connection(conn)

def get_user_platform_role(user_id: str):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT role FROM platform_admins WHERE user_id = %s AND status = 'active'",
                (user_id,)
            )
            result = cursor.fetchone()
            return result['role'] if result else None
    finally:
        release_db_connection(conn)

def get_user_staff_role(user_id: str):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT staff_role FROM staff_accounts WHERE user_id = %s AND status = 'active'",
                (user_id,)
            )
            result = cursor.fetchone()
            return result['staff_role'] if result else None
    finally:
        release_db_connection(conn)

def log_audit_event(workspace_id: str, user_id: str, action: str, entity_type: str = None, entity_id: str = None, ip_address: str = None):
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO audit_logs (workspace_id, user_id, action, entity_type, entity_id, ip_address)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (workspace_id, user_id, action, entity_type, entity_id, ip_address)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")
    finally:
        release_db_connection(conn)
