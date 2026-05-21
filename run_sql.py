import psycopg2

def run_sql(filename):
    conn = psycopg2.connect('host=localhost port=5432 dbname=cognimend user=postgres password=password123')
    cur = conn.cursor()
    with open(filename, 'r') as f:
        sql = f.read()
        cur.execute(sql)
    conn.commit()
    cur.close()
    conn.close()
    print(f"Successfully executed {filename}")

if __name__ == "__main__":
    try:
        run_sql('init_enterprise_rbac.sql')
    except Exception as e:
        print(f"Error: {e}")
