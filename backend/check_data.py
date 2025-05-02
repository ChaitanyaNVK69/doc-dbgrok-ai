import sqlite3
from datetime import datetime


conn = sqlite3.connect('doctor_dashboard.db')
cursor = conn.cursor()

# cursor.execute("ALTER TABLE Patients ADD COLUMN date TEXT")
# conn.commit()

cursor.execute("SELECT COUNT(*) FROM appointments WHERE date >= ?", (datetime.now().strftime('%Y-%m-%d'),))
print(cursor.fetchone()[0])

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("Tables:", [row[0] for row in cursor.fetchall()])

cursor.execute("SELECT * FROM users")
print("Users:", cursor.fetchall())

cursor.execute("SELECT * FROM patients")
print("Patients:", cursor.fetchall())


cursor.execute("SELECT * FROM appointments")
print("Appointments:", cursor.fetchall())

cursor.execute("SELECT * FROM tasks")
print("Tasks:", cursor.fetchall())

conn.close()