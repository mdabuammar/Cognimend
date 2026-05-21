import psycopg2
import os
try:
    conn = psycopg2.connect(host='127.0.0.1', port=5432, dbname='cognimend', user='postgres', password=os.getenv('POSTGRES_PASSWORD', ''))
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET email = %s WHERE email = %s",
        (os.getenv('LOCAL_ADMIN_EMAIL', 'local-admin@example.invalid'), os.getenv('LOCAL_OLD_ADMIN_EMAIL', 'local-old-admin@example.invalid')),
    )
    conn.commit()
    cur.close()
    conn.close()
    print("Local admin email updated successfully")
except Exception as e:
    print(f"Error: {e}")
