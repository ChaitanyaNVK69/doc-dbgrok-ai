import sqlite3
from datetime import datetime

conn = sqlite3.connect('doctor_dashboard.db')
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM patients")
print("Total Patients:", c.fetchone()[0])

c.execute("SELECT COUNT(*) FROM appointments WHERE date >= ?", (datetime.now().strftime('%Y-%m-%d'),))
print("Upcoming Appointments:", c.fetchone()[0])

c.execute("SELECT COUNT(*) FROM appointments WHERE status = 'completed'")
print("Completed Appointments:", c.fetchone()[0])

c.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
print("Pending Tasks:", c.fetchone()[0])

c.execute("SELECT id, name, age, gender, condition, ai_risk_level, medical_history, recent_vitals, contact_info, allergies, medications, last_visit_date FROM patients")
print("Patients:", [dict(row) for row in c.fetchall()])

c.execute("SELECT id, description, status, priority FROM tasks WHERE status = 'pending' ORDER BY priority DESC")
print("Tasks:", [dict(row) for row in c.fetchall()])

conn.close()