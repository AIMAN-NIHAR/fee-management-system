"""
Run this once to create fee_management.db, build the tables,
and load your existing data into it:

    python init_db.py

Safe to run again -- tables use CREATE TABLE IF NOT EXISTS, and
data.sql uses your original IDs so re-running just re-checks things.
"""
import sqlite3
from config import Config

conn = sqlite3.connect(Config.DATABASE)

with open('schema.sql', 'r') as f:
    conn.executescript(f.read())

with open('data.sql', 'r') as f:
    try:
        conn.executescript(f.read())
    except sqlite3.IntegrityError:
        print("Data already loaded -- skipping (this is fine if you've run this before).")

conn.commit()
conn.close()

print(f"Database ready at: {Config.DATABASE}")