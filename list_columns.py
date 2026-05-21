import psycopg2
import json

try:
    conn = psycopg2.connect('host=localhost port=5432 dbname=cognimend user=postgres password=password123')
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
    columns = [r[0] for r in cur.fetchall()]
    print(json.dumps(columns))
except Exception as e:
    print(f"Error: {e}")
