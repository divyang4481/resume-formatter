import sqlite3
import json
import os

db_path = '.data/app.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('SELECT payload_json FROM audit_events WHERE action="LLM_EXTRACTION_CLEAN_JSON" ORDER BY created_at DESC LIMIT 1')
res = cursor.fetchone()
if res:
    payload = json.loads(res[0])
    print(payload.get('clean_json', 'No clean_json in payload'))
else:
    print("No logs found for LLM_EXTRACTION_CLEAN_JSON")
conn.close()
