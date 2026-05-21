import bcrypt
import os
import psycopg2

try:
    new_password = os.getenv('LOCAL_ADMIN_PASSWORD')
    if not new_password:
        raise RuntimeError('Set LOCAL_ADMIN_PASSWORD before resetting the local admin password.')
    h = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn = psycopg2.connect(host='localhost', port=5432, dbname='cognimend', user='postgres', password=os.getenv('POSTGRES_PASSWORD', ''))
    cur = conn.cursor()
    cur.execute("UPDATE users SET password_hash = %s WHERE email = %s", (h, os.getenv('LOCAL_ADMIN_EMAIL', 'local-admin@example.invalid')))
    conn.commit()
    print("Local admin password updated")
except Exception as e:
    print(f"Error: {e}")
