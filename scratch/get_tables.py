import psycopg2
conn = psycopg2.connect("postgresql://dbadmin:HaysDemo_%23123@agentic-platform-db-dev.ctgoo20ag6cj.ap-south-1.rds.amazonaws.com:5432/agenticdb")
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
for row in cur.fetchall():
    print(row[0])
