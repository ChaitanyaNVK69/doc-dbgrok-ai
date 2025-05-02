import sqlite3
from datetime import datetime

conn = sqlite3.connect('/Users/chaitanya/Desktop/doctor-dashboard-ai/backend/doctor_dashboard.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Clear existing appointments
cursor.execute('DELETE FROM appointments')

# Ensure testdoctor exists
cursor.execute('INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)', ('testdoctor', 'doc123', 'Doctor'))
doctor_id = cursor.execute('SELECT user_id FROM users WHERE username = ?', ('testdoctor',)).fetchone()['user_id']

# Add Patients (120 total, if not already present)
cursor.execute('SELECT COUNT(*) as count FROM patients').fetchone()
if cursor.fetchone()['count'] == 0:
    conditions = ['Hypertension', 'Diabetes', 'Asthma', 'Osteoarthritis', 'COPD']
    genders = ['Male', 'Female']
    for i in range(1, 121):
        name = f'Patient {i}'
        age = 20 + (i % 50)
        gender = genders[i % 2]
        condition = conditions[i % 5]
        cursor.execute(
            'INSERT INTO patients (user_id, name, age, gender, current_condition) VALUES (?, ?, ?, ?, ?)',
            (doctor_id, name, age, gender, condition)
        )

# Add Appointments (8 upcoming, 25 completed, all in April 2024)
# Upcoming: April 15–22, 2024 (after April 12, 2024)
for i in range(8):
    day = 15 + i
    date = f'2024-04-{day:02d} 10:00:00'
    cursor.execute(
        'INSERT INTO appointments (patient_id, doctor_id, appointment_time) VALUES (?, ?, ?)',
        (i + 1, doctor_id, date)
    )
# Completed: April 1–8, 2024 (before April 12, 2024)
for i in range(8):
    day = 1 + i
    date = f'2024-04-{day:02d} 10:00:00'
    cursor.execute(
        'INSERT INTO appointments (patient_id, doctor_id, appointment_time) VALUES (?, ?, ?)',
        (i + 9, doctor_id, date)
    )
# Additional completed appointments to reach 25 total
for i in range(17):
    day = 9 + i
    if day <= 31:
        date = f'2024-04-{day:02d} 10:00:00'
        cursor.execute(
            'INSERT INTO appointments (patient_id, doctor_id, appointment_time) VALUES (?, ?, ?)',
            (i + 17, doctor_id, date)
        )

conn.commit()
conn.close()
print("Appointments added successfully.")