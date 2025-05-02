import sqlite3

def test_database():
    try:
        conn = sqlite3.connect('doctor_dashboard.db')
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print("Tables:", tables)
        expected_tables = ['users', 'patients', 'appointments', 'tasks']
        for table in expected_tables:
            if table in tables:
                print(f"✓ Table '{table}' exists")
            else:
                print(f"✗ Table '{table}' is missing")
        
        # Check data in each table
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"Rows in {table}: {count}")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

if __name__ == '__main__':
    test_database()