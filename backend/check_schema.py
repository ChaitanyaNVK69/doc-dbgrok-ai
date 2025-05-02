import sqlite3

conn = sqlite3.connect('doctor_dashboard.db')
c = conn.cursor()
c.execute("PRAGMA table_info(appointments)")
print("Appointments columns:", c.fetchall())
conn.close()