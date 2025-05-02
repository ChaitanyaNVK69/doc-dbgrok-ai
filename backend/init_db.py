import sqlite3

def init_db():
    conn = sqlite3.connect('doctor_dashboard.db')
    c = conn.cursor()
    
    # Users table (added email)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT NOT NULL
        )
    ''')

    # c.execute('''
    #     CREATE TABLE IF NOT EXISTS doctors (
    #         id INTEGER PRIMARY KEY AUTOINCREMENT,
    #         name TEXT NOT NULL
    #     )
    # ''')
    # doctors = conn.execute('SELECT COUNT(*) FROM doctors').fetchone()[0]
    # if doctors == 0:
    #     sample_doctors = [
    #         ('Dr. John Smith',),
    #         ('Dr. Emily Johnson',),
    #         ('Dr. Michael Brown',)
    #     ]
    #     c.executemany('INSERT INTO doctors (name) VALUES (?)', sample_doctors)


    c.execute('''
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            specialty TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    
    # Patients table
    c.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            gender TEXT NOT NULL,
            condition TEXT,
            risk_level REAL,
            medical_history TEXT,
            recent_vitals TEXT,
            contact_info TEXT,
            allergies TEXT,
            medications TEXT,
            last_visit TEXT,
            last_appointment TEXT,
            whatsapp_number TEXT
        )
    ''')
    
    # # Appointments table
    # c.execute('''
    #     CREATE TABLE IF NOT EXISTS appointments (
    #         id INTEGER PRIMARY KEY AUTOINCREMENT,
    #         patient_id INTEGER,
    #         patient_name TEXT,
    #         title TEXT,
    #         date TEXT,
    #         time TEXT,
    #         notes TEXT,
    #         status TEXT,
    #         FOREIGN KEY (patient_id) REFERENCES patients(id)
    #     )
    # ''')

      # Create appointments table
    c.execute('''
           CREATE TABLE IF NOT EXISTS appointments (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               patient_id INTEGER,
               patient_name TEXT NOT NULL,
               doctor_id INTEGER,
               doctor_name TEXT NOT NULL,
               title TEXT,
               date TEXT NOT NULL,
               time TEXT NOT NULL,
               notes TEXT,
               reason TEXT,
               status TEXT NOT NULL,
               FOREIGN KEY (patient_id) REFERENCES patients (id),
               FOREIGN KEY (doctor_id) REFERENCES doctors (id)
           )
       ''')


        # Create medical_notes table
    c.execute('''
        CREATE TABLE IF NOT EXISTS medical_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            subjective TEXT NOT NULL,
            objective TEXT NOT NULL,
            assessment TEXT NOT NULL,
            plan TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
        ''')


        # Create billing table
    c.execute('''
            CREATE TABLE IF NOT EXISTS billing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                visit_cost REAL NOT NULL,
                amount_due REAL NOT NULL,
                status TEXT NOT NULL,
                alert TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients (id)
            )
        ''')



    # Add patient_notes table
    c.execute('''
    CREATE TABLE IF NOT EXISTS patient_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        note TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
        ''')

    # New WhatsApp messages table
    c.execute('''
        CREATE TABLE IF NOT EXISTS whatsapp_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            message TEXT NOT NULL,
            sender TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            type TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    ''')


    # New WhatsApp FAQ table
    c.execute('''
        CREATE TABLE IF NOT EXISTS whatsapp_faq (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL
        )
    ''')
    faqs = conn.execute('SELECT COUNT(*) FROM whatsapp_faq').fetchone()[0]
    if faqs == 0:
        sample_faqs = [
            ('What are the clinic hours?', 'Our clinic is open from 9 AM to 5 PM, Monday to Friday.'),
            ('How do I pay for my appointment?', 'You can pay online via our portal or at the clinic reception.')
        ]
        conn.executemany('INSERT INTO whatsapp_faq (question, answer) VALUES (?, ?)', sample_faqs)

    
    # Tasks table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT,
            priority TEXT,
            status TEXT,
            due_date TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()