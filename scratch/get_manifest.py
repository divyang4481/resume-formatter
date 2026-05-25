import sqlite3
import json

db_path = "backend/.data/app.db"
template_id = "850c153b-c624-4bff-9b1c-24e4ed158d72"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT manifest FROM templates WHERE id = ?", (template_id,))
row = cursor.fetchone()

if row:
    manifest = json.loads(row[0])
    print(json.dumps(manifest, indent=2))
else:
    print("Template not found")

conn.close()
