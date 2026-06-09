import psycopg2
import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

# ── Firebase setup ──
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://rental-syst-default-rtdb.firebaseio.com'
})

# ── Postgres setup ──
conn = psycopg2.connect(
    dbname=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host="localhost",
    port="5432"
)
cursor = conn.cursor()

# ── Backup function ──
def backup_table(table_name):
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description]

    data = {}
    for i, row in enumerate(rows):
        data[str(i)] = dict(zip(col_names, [str(v) for v in row]))

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    ref = db.reference(f'backups/{timestamp}/{table_name}')
    ref.set(data)
    print(f"✅ Backed up {len(rows)} rows from '{table_name}'")

# ── Auto-detect all tables ──
cursor.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
""")
tables = [row[0] for row in cursor.fetchall()]
print(f"Found tables: {tables}")

for table in tables:
    backup_table(table)

cursor.close()
conn.close()
print("🎉 Backup complete!")