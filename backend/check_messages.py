import sqlite3
conn = sqlite3.connect('doctor_dashboard.db')

from datetime import datetime




# conn = sqlite3.connect('/Users/chaitanya/Desktop/doc-dbgrok-ai/backend/doctor_dashboard.db')
# cursor = conn.execute('SELECT id, name, whatsapp_number FROM patients WHERE name = ?', ('MS Dhoni',))
# patient = cursor.fetchone()
# print(patient)
# conn.close()


# conn = sqlite3.connect('/Users/chaitanya/Desktop/doc-dbgrok-ai/backend/doctor_dashboard.db')
# conn.execute('CREATE TABLE IF NOT EXISTS registered_numbers (phone_number TEXT PRIMARY KEY)')
# conn.commit()
# conn.close()


# conn = sqlite3.connect('/Users/chaitanya/Desktop/doc-dbgrok-ai/backend/doctor_dashboard.db')
# conn.execute('INSERT OR REPLACE INTO registered_numbers (phone_number) VALUES (?)', ('+916364034559',))
# conn.execute('INSERT OR REPLACE INTO registered_numbers (phone_number) VALUES (?)', ('+917672098619',))
# conn.commit()
# conn.close()

# cursor = conn.execute('SELECT * FROM appointments')
# print(cursor.fetchall())
# conn.close()



# conn = sqlite3.connect('/Users/chaitanya/Desktop/doc-dbgrok-ai/backend/doctor_dashboard.db')
# cursor = conn.execute('SELECT * FROM sqlite_master WHERE type="table";')
# print(cursor.fetchall())
# conn.close()

# conn = sqlite3.connect('/Users/chaitanya/Desktop/doc-dbgrok-ai/backend/doctor_dashboard.db')
# cursor = conn.execute('SELECT * FROM billing')
# print(cursor.fetchall())
# conn.close()



# conn = sqlite3.connect('/Users/chaitanya/Desktop/doc-dbgrok-ai/backend/doctor_dashboard.db')
# c = conn.cursor()
# c.execute('INSERT OR IGNORE INTO users (username, password, email) VALUES (?, ?, ?)', ('admin', 'password', 'admin@example.com'))
# conn.commit()
# c.execute('SELECT * FROM users')
# print(c.fetchall())
# conn.close()


# conn = sqlite3.connect('/Users/chaitanya/Desktop/doc-dbgrok-ai/backend/doctor_dashboard.db')
# cursor = conn.execute('SELECT * FROM sqlite_master WHERE type="table";')
# print(cursor.fetchall())
# conn.close()

# conn = sqlite3.connect('/Users/chaitanya/Desktop/doc-dbgrok-ai/backend/doctor_dashboard.db')
# cursor = conn.execute('SELECT * FROM users')
# print(cursor.fetchall())
# conn.close()


# conn = sqlite3.connect('/Users/chaitanya/Desktop/doc-dbgrok-ai/backend/doctor_dashboard.db')
# cursor = conn.execute('SELECT * FROM doctors')
# print(cursor.fetchall())
# conn.close()



# conn = sqlite3.connect('/Users/chaitanya/Desktop/doc-dbgrok-ai/backend/doctor_dashboard.db')
# c = conn.cursor()
# c.execute('SELECT * FROM patients')
# print(c.fetchall())
# c.execute('SELECT * FROM doctors')
# print(c.fetchall())
# conn.close()



# conn = sqlite3.connect('/Users/chaitanya/Desktop/doc-dbgrok-ai/backend/doctor_dashboard.db')
# c = conn.cursor()
# c.execute('SELECT * FROM appointments')
# print(c.fetchall())
# conn.close()



# conn = sqlite3.connect('/Users/chaitanya/Desktop/doc-dbgrok-ai/backend/doctor_dashboard.db')
# c = conn.cursor()
# c.execute('SELECT * FROM medical_notes')
# print("Medical Notes:", c.fetchall())
# # c.execute('SELECT * FROM appointments')
# # print("Appointments:", c.fetchall())
# conn.close()