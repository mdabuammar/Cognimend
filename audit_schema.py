import psycopg2
import json

def get_schema(table_name):
    conn = psycopg2.connect('host=localhost port=5432 dbname=cognimend user=postgres password=password123')
    cur = conn.cursor()
    cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}'")
    cols = cur.fetchall()
    cur.close()
    conn.close()
    return cols

tables = ['users', 'workspaces', 'workspace_members', 'platform_admins', 'staff_accounts', 'departments', 'department_members']
schema = {}
for t in tables:
    try:
        schema[t] = get_schema(t)
    except Exception as e:
        schema[t] = f"Error: {e}"

print(json.dumps(schema, indent=2))
