import psycopg2
import os
hash = os.getenv('LOCAL_ADMIN_PASSWORD_HASH', '')
if not hash:
    raise RuntimeError('Set LOCAL_ADMIN_PASSWORD_HASH before updating the local admin password.')
try:
    conn = psycopg2.connect(host='127.0.0.1', port=5432, dbname='cognimend', user='postgres', password=os.getenv('POSTGRES_PASSWORD', ''))
    cur = conn.cursor()
    cur.execute("UPDATE users SET password_hash = %s WHERE email = %s", (hash, os.getenv('LOCAL_ADMIN_EMAIL', 'local-admin@example.invalid')))
    conn.commit()
    cur.close()
    conn.close()
    print("Admin password hash updated successfully")
except Exception as e:
    print(f"Error: {e}")
