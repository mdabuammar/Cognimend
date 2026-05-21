import psycopg2
import json

try:
    conn = psycopg2.connect('host=localhost port=5432 dbname=cognimend user=postgres password=password123')
    cur = conn.cursor()
    cur.execute("SELECT email, role FROM users")
    rows = cur.fetchall()
    print(json.dumps(rows))
except Exception as e:
    print(f"Error: {e}")
