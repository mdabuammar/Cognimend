import os
import sys
import bcrypt
import psycopg2
import psycopg2.extras
import getpass
import hashlib
import json
import uuid
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
        print(f"Warning: Could not log audit event: {e}")

def create_super_admin(email, full_name):
    print(f"--- Creating Super Admin: {email} ---")
    
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
            # 1. Check if user already exists
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            
            if user:
                user_id = user["id"]
                print(f"User with email {email} already exists. Updating and promoting...")
                cur.execute("UPDATE users SET password_hash = %s, full_name = %s, is_active = TRUE WHERE id = %s", (pw_hash, full_name, user_id))
            else:
                # 2. Insert into users
                cur.execute("""
                    INSERT INTO users (email, password_hash, full_name, email_verified, is_active)
                    VALUES (%s, %s, %s, TRUE, TRUE) RETURNING id
                """, (email, pw_hash, full_name))
                user_id = cur.fetchone()["id"]
                
                # 3. Insert into auth_accounts
                cur.execute("INSERT INTO auth_accounts (user_id, provider) VALUES (%s, 'local')", (user_id,))
            
            # 4. Insert into platform_admins as super_admin
            cur.execute("""
                INSERT INTO platform_admins (user_id, role, status)
                VALUES (%s, 'super_admin', 'active')
                ON CONFLICT (user_id) DO UPDATE SET role = 'super_admin', status = 'active'
            """, (user_id,))
            
            # 5. Bootstrap workspace if needed (optional but good for consistency)
            # Check if has workspace
            cur.execute("SELECT id FROM workspaces WHERE owner_id = %s", (user_id,))
            if not cur.fetchone():
                cur.execute("SELECT id FROM plans WHERE name = 'enterprise' LIMIT 1")
                plan = cur.fetchone()
                plan_id = plan["id"] if plan else None
                
                ws_name = f"{full_name}'s Admin Workspace"
                cur.execute(
                    "INSERT INTO workspaces (name, slug, owner_id, plan_id) VALUES (%s, %s, %s, %s) RETURNING id",
                    (ws_name, f"admin-{str(user_id)[:8]}", user_id, plan_id)
                )
                ws_id = cur.fetchone()["id"]
                cur.execute("INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (%s, %s, 'owner')", (ws_id, user_id))
                if plan_id:
                    cur.execute("INSERT INTO subscriptions (workspace_id, plan_id, status) VALUES (%s, %s, 'active')", (ws_id, plan_id))

            conn.commit()
            _log_audit(conn, user_id, "super_admin", "platform.admin_created", target_id=str(user_id))
            conn.commit()
            
            print(f"\n✅ Super Admin created successfully!")
            print(f"Email: {email}")
            print(f"Role: super_admin")
            print(f"Login at: {os.getenv('FRONTEND_URL', 'http://localhost:8080')}/login")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Create a Cognimend Super Admin user safely.")
    parser.add_argument("--email", required=True, help="Email address for the admin")
    parser.add_argument("--name", required=True, help="Full name of the admin")
    
    args = parser.parse_args()
    create_super_admin(args.email, args.name)
