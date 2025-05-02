import sqlite3
from datetime import datetime, timedelta
import random

def populate_db():
    conn = sqlite3.connect('doctor_dashboard.db')
    c = conn.cursor()
    
    # Clear existing data
    c.execute('DELETE FROM users')
    c.execute('DELETE FROM doctors')
    c.execute('DELETE FROM patients')
    c.execute('DELETE FROM appointments')
    c.execute('DELETE FROM tasks')
    c.execute('DELETE FROM patient_notes')



    #   # Create patient_notes table with date column
    # c.execute('''
    #     CREATE TABLE IF NOT EXISTS patient_notes (
    #         id INTEGER PRIMARY KEY AUTOINCREMENT,
    #         patient_id INTEGER,
    #         note TEXT,
    #         date TEXT,
    #         FOREIGN KEY (patient_id) REFERENCES patients(id)
    #     )
    # ''')

    
    # Add a sample user with email
    c.execute('INSERT INTO users (username, password, email) VALUES (?, ?, ?)', 
              ('doctor', 'password123', 'chaitanya.nvk@example.com'))

    # c.execute('INSERT INTO patient_notes (patient_id, note) VALUES (?, ?)', (1, 'Patient is feeling happy and improving.'))
    # c.execute('INSERT INTO patient_notes (patient_id, note) VALUES (?, ?)', (2, 'Patient reports pain and worsening symptoms.'))          
    # c.execute('UPDATE patients SET last_appointment = ? WHERE id = ?', ('2023-10-01T10:00:00', 1))
    # c.execute('UPDATE patients SET last_appointment = ? WHERE id = ?', ('2023-09-15T14:00:00', 2))
    # Add sample patients
    doctors = [
        (1, 'Dr. John Smith', 'smith@example.com', 'smith123', 'Gynachologist', '2025-04-21 14:00:00'),
        (2, 'Dr. Emily Johnson', 'emily@example.com', 'emily123', 'Ortho', '2025-04-2251 12:00:00'),
        (3, 'Dr. Michael Brown', 'michel@example.com', 'michel123', 'General', '2025-04-27 13:00:00'),
        ]
    c.executemany('INSERT INTO doctors (id, name, email, password, specialty, created_at) VALUES (?, ?, ?, ?, ?, ?)', doctors)
    
    
    # Add sample patients
    patients = [
        ('John Doe', 45, 'M', 'Hypertension', 0.6, 'Previous heart surgery', 'HR:80, BP:120/80', 'john@example.com', 'None', 'Amlodipine', '2025-03-15', '+916364034559'),
        ('Jane Smith', 30, 'F', 'Diabetes', 0.4, 'Type 2 diabetes', 'HR:90, BP:110/70', 'jane@example.com', 'Peanuts', 'Metformin', '2025-04-01', '+917672098619'),
        ('Virat Kohili', 36, 'M', 'Diabetes', 0.5, 'Type 1 diabetes', 'HR:80, BP:100/70', 'kohli@example.com', 'Banana', 'Metformin', '2025-04-10', '+917989351473'),
        ('Ajay Jadeja', 35, 'M', 'Diabetes', 0.6, 'Type 2 diabetes', 'HR:90, BP:120/70', 'jadeja@example.com', 'Apple', 'Metformin', '2025-04-16', '+918885269314'),
        ('MS Dhoni', 45, 'M', 'Head ach & High BP', 0.7, 'Low diabetes', 'HR:90, BP:100/70', 'msd@example.com', 'Orange', 'MefthalSpas', '2025-04-19', '+918123049997'),
        ('Shubham Gil', 25, 'M', 'Stomach ach & Low BP', 0.8, 'Bone Facture', 'HR:80, BP:100/70', 'gil@example.com', 'Grape', 'Dolo', '2025-04-14', '+919989978547'),
    ]
    c.executemany('INSERT INTO patients (name, age, gender, condition, risk_level, medical_history, recent_vitals, contact_info, allergies, medications, last_visit, whatsapp_number) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', patients)
    
    # Update last_appointment for patients (after inserting patients)
    c.execute('UPDATE patients SET last_appointment = ? WHERE id = ?', ('2023-10-01T10:00:00', 1))
    c.execute('UPDATE patients SET last_appointment = ? WHERE id = ?', ('2023-09-15T14:00:00', 2))

    # Add sample appointments
    appointments = [
        (1, 'John Doe', 1, 'Dr.John Smith', 'Checkup', '2025-04-18', '10:00', 'Routine checkup', 'Feeling Lazy', 'Upcoming'),
        (2, 'Jane Smith', 2, 'Emily Johnson', 'Follow-up', '2025-04-19', '14:00', 'Diabetes review', 'Feeling Sick', 'Upcoming'),
        (1, 'John Doe', 3, 'Michael Brown', 'Consultation', '2025-04-10', '09:00', 'Post-surgery', 'Feeling Painful', 'Completed'),
        (2, 'Shubham Gill', 1, 'Dr.John Smith', 'Consultation', '2025-04-27', '09:00', 'Pre-surgery', 'Feeling Nervus', 'Upcoming'),
    ]
    c.executemany('INSERT INTO appointments (patient_id, patient_name, doctor_id, doctor_name, title, date, time, notes, reason, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', appointments)
    

    # Add sample tasks
    tasks = [
        ('Review John Doe’s lab results', 'High', 'Pending', '2025-04-20'),
        ('Follow up with Jane Smith', 'Medium', 'Pending', '2025-04-21'),
        ('Update patient records', 'Low', 'Completed', '2025-04-15'),
        ('Review Shubham Gil records', 'High', 'Pending', '2025-04-28'),
    ]
    c.executemany('INSERT INTO tasks (description, priority, status, due_date) VALUES (?, ?, ?, ?)', tasks)

    # Add sample Patient_Note
    # Sample data for patient_notes
    patient_notes = [
        (1, 1, "Patient reports chest pain", "2025-04-20 10:00:00"),
        (2, 2, "Follow-up for hypertension", "2025-04-21 14:00:00"),
        (3, 3, "Patient reports fatigue", "2025-04-22 09:00:00")
    ]
    # Insert patient_notes data
    c.executemany('INSERT INTO patient_notes (id, patient_id, note, created_at) VALUES (?, ?, ?, ?)', patient_notes)

    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    populate_db()