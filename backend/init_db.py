import psycopg2
import os

def init_db():
    conn_string = os.environ.get('DATABASE_URL')
    if not conn_string:
        raise ValueError("DATABASE_URL environment variable not set")
    # Use sslmode='require' on Render, 'prefer' locally
    sslmode = 'require' if os.environ.get('RENDER') == 'true' else 'prefer'
    conn = psycopg2.connect(conn_string, sslmode=sslmode)
    c = conn.cursor()

    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT NOT NULL
        )
    ''')

    # Doctors table
    c.execute('''
        CREATE TABLE IF NOT EXISTS doctors (
            id SERIAL PRIMARY KEY,
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
            id SERIAL PRIMARY KEY,
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

    # Appointments table
    c.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id SERIAL PRIMARY KEY,
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

    # Medical notes table
    c.execute('''
        CREATE TABLE IF NOT EXISTS medical_notes (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER,
            subjective TEXT NOT NULL,
            objective TEXT NOT NULL,
            assessment TEXT NOT NULL,
            plan TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
    ''')

    # Billing table
    c.execute('''
        CREATE TABLE IF NOT EXISTS billing (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER,
            visit_cost REAL NOT NULL,
            amount_due REAL NOT NULL,
            status TEXT NOT NULL,
            alert TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
    ''')

    # Patient notes table
    c.execute('''
        CREATE TABLE IF NOT EXISTS patient_notes (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    ''')

    # WhatsApp messages table (legacy)
    c.execute('''
        CREATE TABLE IF NOT EXISTS whatsapp_messages (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER,
            message TEXT NOT NULL,
            sender TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            message_type TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    ''')

    # WhatsApp conversations table
    c.execute('''
        CREATE TABLE IF NOT EXISTS whatsapp_conversations (
            id SERIAL PRIMARY KEY,
            patient_id INTEGER,
            message TEXT NOT NULL,
            sender TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            message_type TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
    ''')

    # WhatsApp FAQ table
    c.execute('''
        CREATE TABLE IF NOT EXISTS whatsapp_faq (
            id SERIAL PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL
        )
    ''')

    # Populate whatsapp_faq with sample FAQs if empty
    c.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'whatsapp_faq'
        )
    """)
    table_exists = c.fetchone()[0]
    if table_exists:
        c.execute('SELECT COUNT(*) FROM whatsapp_faq')
        count = c.fetchone()[0]
        if count == 0:
            sample_faqs = [
                ('What are the clinic hours?', 'Our clinic hours are 9 AM to 5 PM, Monday to Friday.'),
                ('How do I book an appointment?', 'Please reply with "book appointment" to see available slots.'),
                ('Where is the clinic located?', 'The clinic is located at 123 Health St, Wellness City.')
            ]
            c.executemany('INSERT INTO whatsapp_faq (question, answer) VALUES (%s, %s)', sample_faqs)

    # Chatbot FAQ table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chatbot_faq (
            id SERIAL PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL
        )
    ''')

    # Populate chatbot_faq with sample FAQs if empty
    c.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'chatbot_faq'
        )
    """)
    table_exists = c.fetchone()[0]
    if table_exists:
        c.execute('SELECT COUNT(*) FROM chatbot_faq')
        count = c.fetchone()[0]
        if count == 0:
            sample_faqs = [
                ('What are the clinic hours?', 'Our clinic hours are 9 AM to 5 PM, Monday to Friday.'),
                ('How do I book an appointment?', 'I can help you book an appointment! Please provide your patient ID.'),
                ('Where is the clinic located?', 'The clinic is located at 123 Health St, Wellness City.')
            ]
            c.executemany('INSERT INTO chatbot_faq (question, answer) VALUES (%s, %s)', sample_faqs)

    # Chatbot conversations table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chatbot_conversations (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            message TEXT NOT NULL,
            sender TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            message_type TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Chatbot patient mappings table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chatbot_patient_mappings (
            user_id INTEGER PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (patient_id) REFERENCES patients (id)
        )
    ''')

    # Email logs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS email_logs (
            id SERIAL PRIMARY KEY,
            recipient_email TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            sent_at TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT
        )
    ''')

    # Tasks table
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
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