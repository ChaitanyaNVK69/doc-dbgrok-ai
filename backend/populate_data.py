import sqlite3
from datetime import datetime, timedelta

def populate_db():
    conn = sqlite3.connect('doctor_dashboard.db')
    c = conn.cursor()
    
    # Clear existing data
    c.execute('DELETE FROM users')
    c.execute('DELETE FROM patients')
    c.execute('DELETE FROM appointments')
    c.execute('DELETE FROM tasks')
    
    # Add a sample user
    c.execute('INSERT INTO users (username, password) VALUES (?, ?)', 
              ('doctor', 'password123'))
    
    # Add sample patients
    patients = [
        ('John Doe', 45, 'M', 'Hypertension', 0.6, 'Previous heart surgery', 'HR:80, BP:120/80', 'john@example.com', 'None', 'Amlodipine', '2025-03-15'),
        ('Jane Smith', 30, 'F', 'Diabetes', 0.4, 'Type 2 diabetes', 'HR:90, BP:110/70', 'jane@example.com', 'Peanuts', 'Metformin', '2025-04-01'),
    ]
    c.executemany('INSERT INTO patients (name, age, gender, condition, risk_level, medical_history, recent_vitals, contact_info, allergies, medications, last_visit) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', patients)
    
    # Add sample appointments
    appointments = [
        (1, 'John Doe', '2025-04-16', '10:00', 'Upcoming'),
        (2, 'Jane Smith', '2025-04-17', '14:00', 'Upcoming'),
        (1, 'John Doe', '2025-04-10', '09:00', 'Completed'),
    ]
    c.executemany('INSERT INTO appointments (patient_id, patient_name, date, time, status) VALUES (?, ?, ?, ?, ?)', appointments)
    
    # Add sample tasks
    tasks = [
        ('Review John Doe’s lab results', 'High', 'Pending'),
        ('Follow up with Jane Smith', 'Medium', 'Pending'),
        ('Update patient records', 'Low', 'Pending'),
    ]
    c.executemany('INSERT INTO tasks (description, priority, status) VALUES (?, ?, ?)', tasks)
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    populate_db()