import psycopg2
import json

try:
    conn = psycopg2.connect('host=localhost port=5432 dbname=cognimend user=postgres password=password123')
    cur = conn.cursor()
    cur.execute("SELECT u.email, pa.role FROM platform_admins pa JOIN users u ON u.id = pa.user_id")
    rows = cur.fetchall()
    print(json.dumps(rows))
except Exception as e:
    print(f"Error: {e}")
