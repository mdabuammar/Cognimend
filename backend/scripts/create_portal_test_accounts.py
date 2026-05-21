import os
import bcrypt
import psycopg2
import psycopg2.extras
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../.env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("test_data")

# DB Config
PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
PG_DB   = os.getenv("POSTGRES_DB", "cognimend")
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASS = os.getenv("POSTGRES_PASSWORD", "")

def get_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER, password=PG_PASS
    )

def create_user(cur, email, password, full_name):
    # Use bcrypt for hashing
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    cur.execute(
        "INSERT INTO users (email, password_hash, full_name) VALUES (%s, %s, %s) "
        "ON CONFLICT (email) DO UPDATE SET password_hash = %s, full_name = %s RETURNING id",
        (email, pw_hash, full_name, pw_hash, full_name)
    )
    user_id = cur.fetchone()["id"]
    
    # Ensure auth_accounts entry
    cur.execute(
        "INSERT INTO auth_accounts (user_id, provider) VALUES (%s, 'local') ON CONFLICT DO NOTHING",
        (user_id,)
    )
    return user_id

def main():
    logger.info("Starting test account creation...")
    
    account_password = os.getenv("LOCAL_TEST_ACCOUNT_PASSWORD")
    if not account_password:
        raise RuntimeError("Set LOCAL_TEST_ACCOUNT_PASSWORD before creating local test accounts.")

    customer_email = os.getenv("LOCAL_TEST_CUSTOMER_EMAIL", "local-user@example.invalid")
    owner_email = os.getenv("LOCAL_TEST_OWNER_EMAIL", "local-owner@example.invalid")
    staff_email = os.getenv("LOCAL_TEST_REVIEWER_EMAIL", "local-reviewer@example.invalid")
    admin_email = os.getenv("LOCAL_TEST_ADMIN_EMAIL", "local-admin@example.invalid")

    PASSWORDS = {
        customer_email: account_password,
        owner_email: account_password,
        staff_email: account_password,
        admin_email: account_password,
    }

    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Create Users
            customer_id = create_user(cur, customer_email, PASSWORDS[customer_email], "Test Member")
            owner_id    = create_user(cur, owner_email,    PASSWORDS[owner_email],    "Workspace Owner")
            staff_id    = create_user(cur, staff_email,    PASSWORDS[staff_email],    "Test Reviewer")
            admin_id    = create_user(cur, admin_email,    PASSWORDS[admin_email],    "Test Admin")

            # 2. Create Workspace
            workspace_name = "Cognimend Test Organization"
            cur.execute(
                "INSERT INTO workspaces (name, slug, owner_id) VALUES (%s, %s, %s) "
                "ON CONFLICT (slug) DO UPDATE SET name = %s, owner_id = %s RETURNING id",
                (workspace_name, "test-org", owner_id, workspace_name, owner_id)
            )
            workspace_id = cur.fetchone()["id"]

            # 3. Add Members
            # Owner as owner
            cur.execute(
                "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (%s, %s, 'owner') "
                "ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = 'owner'",
                (workspace_id, owner_id)
            )
            # Customer as member
            cur.execute(
                "INSERT INTO workspace_members (workspace_id, user_id, role) VALUES (%s, %s, 'member') "
                "ON CONFLICT (workspace_id, user_id) DO UPDATE SET role = 'member'",
                (workspace_id, customer_id)
            )

            # 4. Create Departments
            departments = ["Policies", "Finance", "Operations", "Support", "General"]
            for dept_name in departments:
                cur.execute(
                    "INSERT INTO departments (workspace_id, name, slug, created_by) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (workspace_id, slug) DO NOTHING",
                    (workspace_id, dept_name, dept_name.lower().replace(" ", "-"), owner_id)
                )

            # 5. Assign Staff Role
            cur.execute(
                "INSERT INTO staff_accounts (user_id, staff_role, status) VALUES (%s, %s, 'active') "
                "ON CONFLICT (user_id) DO UPDATE SET staff_role = %s, status = 'active'",
                (staff_id, "support_agent", "support_agent")
            )

            # 6. Assign Super Admin Role
            cur.execute(
                "INSERT INTO platform_admins (user_id, role, status) VALUES (%s, %s, 'active') "
                "ON CONFLICT (user_id) DO UPDATE SET role = %s, status = 'active'",
                (admin_id, "super_admin", "super_admin")
            )

            # 7. Audit Log
            cur.execute(
                "INSERT INTO admin_action_logs (actor_user_id, action, reason, metadata_json) "
                "VALUES (%s, 'test_accounts.seed', 'portal_access_verification', %s)",
                (admin_id, '{"reason": "portal_access_verification"}')
            )

            conn.commit()
            
            # Print Final Report
            print("\n" + "="*50)
            print("LOCAL TEST ACCOUNTS STATUS")
            print("="*50)
            print(f"{'Email':<30} | {'Role':<15} | {'Status':<10}")
            print("-" * 59)
            print(f"{customer_email:<30} | {'member':<15} | {'UPDATED':<10}")
            print(f"{owner_email:<30} | {'owner':<15} | {'UPDATED':<10}")
            print(f"{staff_email:<30} | {'reviewer':<15} | {'UPDATED':<10}")
            print(f"{admin_email:<30} | {'admin':<15} | {'UPDATED':<10}")
            print("="*50 + "\n")

    except Exception as e:
        logger.error(f"Error during seeding: {e}")
        if 'conn' in locals(): conn.rollback()
    finally:
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    main()
