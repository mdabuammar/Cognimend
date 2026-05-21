import os
import sys
import bcrypt
import psycopg2
import psycopg2.extras
import getpass
import json
from dotenv import load_dotenv

# Load configuration from .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
PG_DB   = os.getenv("POSTGRES_DB", "cognimend")
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "password123")

def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASS
    )

def _log_audit(conn, user_id, role, action, target_id=None, metadata=None, ip="127.0.0.1"):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO admin_action_logs (
                    workspace_id, actor_user_id, actor_role, action, 
                    target_user_id, metadata_json, ip_address
                ) VALUES (NULL, %s, %s, %s, %s, %s::jsonb, %s)
            """, (user_id, role, action, target_id, json.dumps(metadata or {}), ip))
    except Exception as e:
        # Don't fail if table doesn't exist yet
        pass

def reset_password(email):
    print(f"--- Resetting Password for: {email} ---")
    
    password = getpass.getpass("Enter new password: ")
    confirm = getpass.getpass("Confirm new password: ")
    
    if password != confirm:
        print("Error: Passwords do not match.")
        return
    
    if len(password) < 8:
        print("Error: Password must be at least 8 characters long.")
        return

    # Hash password using bcrypt
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Verify user exists and is platform admin
            cur.execute("""
                SELECT u.id, pa.role 
                FROM users u
                LEFT JOIN platform_admins pa ON pa.user_id = u.id
                WHERE u.email = %s
            """, (email,))
            user = cur.fetchone()
            
            if not user:
                print(f"Error: User with email {email} not found.")
                return
            
            user_id = user["id"]
            role = user["role"] or "user"
            
            # 2. Update password
            cur.execute("UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s", (pw_hash, user_id))
            
            # 3. Revoke all refresh tokens for this user
            cur.execute("UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = %s AND revoked_at IS NULL", (user_id,))
            
            conn.commit()
            _log_audit(conn, user_id, role, "user.password_reset_cli", target_id=str(user_id))
            conn.commit()
            
            print(f"\n✅ Password for {email} has been reset successfully.")
            print("All existing sessions have been revoked.")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reset a Cognimend user's password safely.")
    parser.add_argument("--email", required=True, help="Email address of the user")
    
    args = parser.parse_args()
    reset_password(args.email)
