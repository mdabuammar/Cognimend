import psycopg2
import os
try:
    conn = psycopg2.connect(host='127.0.0.1', port=5432, dbname='cognimend', user='postgres', password=os.getenv('POSTGRES_PASSWORD', ''))
    cur = conn.cursor()
    cur.execute("SELECT email, password_hash FROM users WHERE email = %s", (os.getenv('LOCAL_ADMIN_EMAIL', 'local-admin@example.invalid'),))
    row = cur.fetchone()
    print(f"Row: {row}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
