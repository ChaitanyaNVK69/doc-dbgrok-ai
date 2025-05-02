from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mail import Mail, Message
from flask_socketio import SocketIO, emit
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
import numpy as np
import schedule
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['DEBUG'] = True
app.config['TESTING'] = False
socketio = SocketIO(app)

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'hr.bglr@gmail.com'
app.config['MAIL_PASSWORD'] = 'your-app-password'  # Replace with Gmail App Password
mail = Mail(app)

def get_db_connection():
    conn = sqlite3.connect('doctor_dashboard.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_notifications():
    conn = get_db_connection()
    tomorrow = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.today().strftime('%Y-%m-%d')
    upcoming_appts = conn.execute('SELECT title, patient_name, date, time FROM appointments WHERE date IN (?, ?) AND status = "Upcoming"', (today, tomorrow)).fetchall()
    high_priority_tasks = conn.execute('SELECT description, due_date FROM tasks WHERE priority = "High" AND status = "Pending"').fetchall()
    conn.close()
    notifications = []
    for appt in upcoming_appts:
        notifications.append(f"Upcoming: {appt['title']} with {appt['patient_name']} on {appt['date']} at {appt['time']}")
    for task in high_priority_tasks:
        notifications.append(f"High Priority Task: {task['description']} due {task['due_date']}")
    print("Notifications:", notifications)
    return notifications

def send_email_notifications():
    conn = get_db_connection()
    user = conn.execute('SELECT email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    tomorrow = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.today().strftime('%Y-%m-%d')
    upcoming_appts = conn.execute('SELECT title, patient_name, date, time FROM appointments WHERE date IN (?, ?) AND status = "Upcoming"', (today, tomorrow)).fetchall()
    high_priority_tasks = conn.execute('SELECT description, due_date FROM tasks WHERE priority = "High" AND status = "Pending"').fetchall()
    conn.close()
    
    print(f"User: {user}, Upcoming: {upcoming_appts}, Tasks: {high_priority_tasks}")
    
    if not user or not user['email']:
        print("No user or email found")
        return
    
    email = user['email']
    subject = "Doctor Dashboard Notifications"
    body = "Your notifications:\n\n"
    for appt in upcoming_appts:
        body += f"- Upcoming: {appt['title']} with {appt['patient_name']} on {appt['date']} at {appt['time']}\n"
    for task in high_priority_tasks:
        body += f"- High Priority Task: {task['description']} due {task['due_date']}\n"
    
    if upcoming_appts or high_priority_tasks:
        msg = Message(subject, sender=app.config['MAIL_USERNAME'], recipients=[email])
        msg.body = body
        try:
            mail.send(msg)
            print(f"Email sent to {email}")
        except Exception as e:
            print(f"Email send failed: {e}")

def get_analytics():
    conn = get_db_connection()
    
    age_groups = conn.execute('''
        SELECT 
            CASE 
                WHEN age < 18 THEN '0-17'
                WHEN age < 30 THEN '18-29'
                WHEN age < 50 THEN '30-49'
                ELSE '50+' 
            END as age_group,
            COUNT(*) as count
        FROM patients
        GROUP BY age_group
    ''').fetchall() or [{'age_group': 'No Data', 'count': 0}]
    
    conditions = conn.execute('SELECT condition, COUNT(*) as count FROM patients GROUP BY condition').fetchall() or [{'condition': 'No Data', 'count': 0}]
    
    appointment_stats = conn.execute('''
        SELECT 
            status,
            COUNT(*) as count
        FROM appointments
        GROUP BY status
    ''').fetchall() or [{'status': 'No Data', 'count': 0}]
    
    task_stats = conn.execute('''
        SELECT 
            status,
            COUNT(*) as count
        FROM tasks
        GROUP BY status
    ''').fetchall() or [{'status': 'No Data', 'count': 0}]
    
    conn.close()
    
    analytics = {
        'age_groups': [{'label': row['age_group'], 'count': row['count']} for row in age_groups],
        'conditions': [{'label': row['condition'] or 'None', 'count': row['count']} for row in conditions],
        'appointment_stats': [{'label': row['status'], 'count': row['count']} for row in appointment_stats],
        'task_stats': [{'label': row['status'], 'count': row['count']} for row in task_stats]
    }
    
    print("Analytics data:", analytics)
    return analytics

# AI-driven appointment scheduling
@app.route('/suggest_appointment/<int:patient_id>')
def suggest_appointment(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT risk_level FROM patients WHERE id = ?', (patient_id,)).fetchone()
        appointments = conn.execute('SELECT date, time FROM appointments WHERE date >= ?', (datetime.today().strftime('%Y-%m-%d'),)).fetchall()
        conn.close()

        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        available_slots = []
        for day in range(1, 8):
            date = (datetime.today() + timedelta(days=day)).strftime('%Y-%m-%d')
            for hour in range(9, 17):
                slot = f"{date} {hour:02d}:00:00"
                if slot not in [f"{appt['date']} {appt['time']}" for appt in appointments]:
                    available_slots.append(slot)

        risk_level = patient['risk_level']
        if risk_level > 0.7:
            suggested_slots = available_slots[:3]
        else:
            suggested_slots = available_slots[-3:]

        return jsonify({'suggested_slots': suggested_slots})
    except Exception as e:
        print(f"Error suggesting appointment: {e}")
        return jsonify({'error': str(e)}), 500

# AI-driven health trend analysis
@app.route('/health_trends/<int:patient_id>')
def health_trends(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT recent_vitals, medical_history FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        vitals = patient['recent_vitals'].split(',') if patient['recent_vitals'] else []
        heart_rate = None
        bp_systolic = None
        for vital in vitals:
            if 'HR:' in vital:
                heart_rate = float(vital.split('HR:')[1])
            if 'BP:' in vital:
                bp_systolic = float(vital.split('BP:')[1].split('/')[0])

        trends = {'risk': 'Stable'}
        if heart_rate and heart_rate > 100:
            trends['risk'] = 'Elevated (High Heart Rate)'
        if bp_systolic and bp_systolic > 140:
            trends['risk'] = 'Elevated (High Blood Pressure)'
        if 'Diabetes' in patient['medical_history']:
            trends['risk'] = 'High (Chronic Condition)'

        return jsonify({'trends': trends})
    except Exception as e:
        print(f"Error analyzing health trends: {e}")
        return jsonify({'error': str(e)}), 500

# AI-driven task prioritization
@app.route('/prioritize_tasks')
def prioritize_tasks():
    try:
        conn = get_db_connection()
        tasks = conn.execute('SELECT id, description, patient_id FROM tasks WHERE status = "Pending"').fetchall()
        patients = conn.execute('SELECT id, risk_level FROM patients').fetchall()
        conn.close()

        patient_risk = {p['id']: p['risk_level'] for p in patients}
        task_data = pd.DataFrame([{
            'id': t['id'],
            'description': t['description'],
            'patient_id': t['patient_id'],
            'risk_level': patient_risk.get(t['patient_id'], 0.5)
        } for t in tasks])

        if not task_data.empty:
            scaler = StandardScaler()
            task_data['risk_scaled'] = scaler.fit_transform(task_data[['risk_level']])
            kmeans = KMeans(n_clusters=2, random_state=0)
            task_data['priority'] = kmeans.fit_predict(task_data[['risk_scaled']])
            task_data['priority'] = task_data['priority'].map({0: 'Low', 1: 'High'})
            task_data = task_data.sort_values(by=['priority', 'risk_level'], ascending=[False, False])

        prioritized_tasks = task_data[['id', 'description', 'priority']].to_dict('records')
        return jsonify({'prioritized_tasks': prioritized_tasks})
    except Exception as e:
        print(f"Error prioritizing tasks: {e}")
        return jsonify({'error': str(e)}), 500

# New AI-driven patient risk clustering
@app.route('/patient_risk_clusters')
def patient_risk_clusters():
    try:
        conn = get_db_connection()
        patients = conn.execute('SELECT id, name, age, risk_level, recent_vitals, medical_history FROM patients').fetchall()
        conn.close()

        patient_data = pd.DataFrame([{
            'id': p['id'],
            'name': p['name'],
            'age': p['age'],
            'risk_level': p['risk_level'],
            'heart_rate': float(p['recent_vitals'].split('HR:')[1].split(',')[0]) if p['recent_vitals'] and 'HR:' in p['recent_vitals'] else 80,
            'bp_systolic': float(p['recent_vitals'].split('BP:')[1].split('/')[0]) if p['recent_vitals'] and 'BP:' in p['recent_vitals'] else 120,
            'has_diabetes': 1 if 'Diabetes' in p['medical_history'] else 0
        } for p in patients])

        if not patient_data.empty:
            features = ['age', 'risk_level', 'heart_rate', 'bp_systolic', 'has_diabetes']
            scaler = StandardScaler()
            patient_data_scaled = scaler.fit_transform(patient_data[features])
            kmeans = KMeans(n_clusters=3, random_state=0)
            patient_data['cluster'] = kmeans.fit_predict(patient_data_scaled)
            patient_data['cluster_label'] = patient_data['cluster'].map({0: 'Low Risk', 1: 'Medium Risk', 2: 'High Risk'})
            clusters = patient_data[['id', 'name', 'cluster_label']].to_dict('records')
        else:
            clusters = []

        return jsonify({'clusters': clusters})
    except Exception as e:
        print(f"Error clustering patients: {e}")
        return jsonify({'error': str(e)}), 500

# New AI-driven no-show prediction
@app.route('/no_show_prediction/<int:patient_id>')
def no_show_prediction(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT risk_level FROM patients WHERE id = ?', (patient_id,)).fetchone()
        appointments = conn.execute('SELECT status FROM appointments WHERE patient_id = ?', (patient_id,)).fetchall()
        conn.close()

        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        # Simulate historical no-show data
        no_shows = sum(1 for appt in appointments if appt['status'] == 'Missed')
        total_appts = len(appointments)
        no_show_rate = no_shows / total_appts if total_appts > 0 else 0

        # Simple Random Forest model
        X = np.array([[patient['risk_level'], no_show_rate]])
        y = [0]  # Placeholder (0 = attend, 1 = no-show)
        clf = RandomForestClassifier(random_state=0)
        clf.fit(X, y)
        no_show_prob = clf.predict_proba(X)[0][1]

        return jsonify({'no_show_probability': float(no_show_prob)})
    except Exception as e:
        print(f"Error predicting no-show: {e}")
        return jsonify({'error': str(e)}), 500

# New AI-driven follow-up recommendations
@app.route('/follow_up_recommendations/<int:patient_id>')
def follow_up_recommendations(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT risk_level, last_visit FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        last_visit = datetime.strptime(patient['last_visit'], '%Y-%m-%d') if patient['last_visit'] else datetime.today()
        days_since_visit = (datetime.today() - last_visit).days
        risk_level = patient['risk_level']

        recommendation = {'follow_up': 'None'}
        if risk_level > 0.7 and days_since_visit > 30:
            recommendation['follow_up'] = 'Schedule follow-up within 7 days'
        elif risk_level > 0.5 and days_since_visit > 60:
            recommendation['follow_up'] = 'Schedule follow-up within 14 days'

        return jsonify({'recommendation': recommendation})
    except Exception as e:
        print(f"Error recommending follow-up: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        print("Login attempt: username=%s, password=%s" % (username, password))
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?',
                           (username, password)).fetchone()
        print("User query result: %s" % user)
        conn.close()
        if user:
            session['user_id'] = user['id']
            print("Session set with user_id: %s" % user['id'])
            return redirect(url_for('dashboard'))
        print("Login failed: No matching user found")
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    total_patients = conn.execute('SELECT COUNT(*) FROM patients').fetchone()[0]
    upcoming_appointments = conn.execute('SELECT COUNT(*) FROM appointments WHERE status = "Upcoming"').fetchone()[0]
    completed_appointments = conn.execute('SELECT COUNT(*) FROM appointments WHERE status = "Completed"').fetchone()[0]
    pending_tasks = conn.execute('SELECT COUNT(*) FROM tasks WHERE status = "Pending"').fetchone()[0]
    overview = {
        'total_patients': total_patients,
        'upcoming_appointments': upcoming_appointments,
        'completed_appointments': completed_appointments,
        'pending_tasks': pending_tasks
    }
    
    name_query = request.args.get('name', '')
    condition_query = request.args.get('condition', '')
    age_min = request.args.get('age_min', '')
    age_max = request.args.get('age_max', '')
    risk_min = request.args.get('age_min', '')
    risk_max = request.args.get('age_max', '')
    
    query = 'SELECT * FROM patients WHERE 1=1'
    params = []
    if name_query:
        query += ' AND name LIKE ?'
        params.append(f'%{name_query}%')
    if condition_query:
        query += ' AND condition LIKE ?'
        params.append(f'%{condition_query}%')
    if age_min:
        query += ' AND age >= ?'
        params.append(int(age_min))
    if age_max:
        query += ' AND age <= ?'
        params.append(int(age_max))
    if risk_min:
        query += ' AND risk_level >= ?'
        params.append(float(risk_min))
    if risk_max:
        query += ' AND risk_level <= ?'
        params.append(float(risk_max))
    
    patients = conn.execute(query, params).fetchall()
    
    appointments = conn.execute('SELECT * FROM appointments').fetchall()
    
    tasks = conn.execute('SELECT * FROM tasks').fetchall()
    
    notifications = get_notifications()
    
    analytics = get_analytics()
    
    send_email_notifications()
    
    conn.close()
    
    try:
        return render_template('dashboard.html',
                             overview=overview,
                             patients=patients,
                             appointments=appointments,
                             tasks=tasks,
                             notifications=notifications,
                             analytics=analytics,
                             search_params={
                                 'name': name_query,
                                 'condition': condition_query,
                                 'age_min': age_min,
                                 'age_max': age_max,
                                 'risk_min': risk_min,
                                 'risk_max': risk_max
                             })
    except Exception as e:
        print(f"Template rendering error: {e}")
        raise

@app.route('/get_appointments')
def get_appointments():
    conn = get_db_connection()
    appointments = conn.execute('SELECT id, title, date, time, patient_id, status FROM appointments').fetchall()
    conn.close()
    
    appt_data = pd.DataFrame([{
        'id': appt['id'],
        'title': appt['title'],
        'date': appt['date'],
        'time': appt['time'],
        'patient_id': appt['patient_id'],
        'status': appt['status']
    } for appt in appointments])
    
    if not appt_data.empty:
        conn = get_db_connection()
        patients = conn.execute('SELECT id, risk_level FROM patients').fetchall()
        conn.close()
        patient_risk = {p['id']: p['risk_level'] for p in patients}
        appt_data['risk_level'] = appt_data['patient_id'].map(patient_risk).fillna(0.5)
        
        kmeans = KMeans(n_clusters=2, random_state=0)
        appt_data['priority'] = kmeans.fit_predict(appt_data[['risk_level']])
        appt_data['priority'] = appt_data['priority'].map({0: 'Low', 1: 'High'})
        
        appt_data = appt_data.sort_values(by=['priority', 'date'], ascending=[False, True])
    
    events = []
    for _, appt in appt_data.iterrows():
        start_time = f"{appt['date']}T{appt['time']}"
        conflict = False
        for existing in events:
            if existing['start'] == start_time:
                conflict = True
                break
        events.append({
            'id': appt['id'],
            'title': f"{appt['title']} ({appt['priority']})" + (" [Conflict]" if conflict else ""),
            'start': start_time,
            'className': 'high-priority' if appt['priority'] == 'High' else 'low-priority'
        })
    
    print("Appointments fetched:", events)
    return jsonify(events)

@app.route('/add_patient', methods=['GET', 'POST'])
def add_patient():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        age = int(request.form['age'])
        gender = request.form['gender']
        condition = request.form['condition']
        medical_history = request.form['medical_history']
        recent_vitals = request.form['recent_vitals']
        contact_info = request.form['contact_info']
        allergies = request.form['allergies']
        medications = request.form['medications']
        last_visit = request.form['last_visit']
        
        heart_rate = 80
        if recent_vitals and 'HR:' in recent_vitals:
            try:
                heart_rate = int(recent_vitals.split('HR:')[1].split(',')[0])
            except:
                pass
        blood_pressure = recent_vitals.split('BP:')[1] if 'BP:' in recent_vitals else '120/80'
        risk_level = 0.5
        if condition in ['Diabetes', 'Hypertension']:
            risk_level += 0.2
        if heart_rate > 100:
            risk_level += 0.1
        if int(blood_pressure.split('/')[0]) > 140:
            risk_level += 0.1
        risk_level = min(risk_level, 1.0)
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO patients (name, age, gender, condition, risk_level, medical_history, recent_vitals, contact_info, allergies, medications, last_visit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, age, gender, condition, risk_level, medical_history, recent_vitals, contact_info, allergies, medications, last_visit))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))
    
    return render_template('add_patient.html')

@app.route('/edit_patient/<int:id>', methods=['GET', 'POST'])
def edit_patient(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    patient = conn.execute('SELECT * FROM patients WHERE id = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        age = int(request.form['age'])
        gender = request.form['gender']
        condition = request.form['condition']
        medical_history = request.form['medical_history']
        recent_vitals = request.form['recent_vitals']
        contact_info = request.form['contact_info']
        allergies = request.form['allergies']
        medications = request.form['medications']
        last_visit = request.form['last_visit']
        
        heart_rate = 80
        if recent_vitals and 'HR:' in recent_vitals:
            try:
                heart_rate = int(recent_vitals.split('HR:')[1].split(',')[0])
            except:
                pass
        blood_pressure = recent_vitals.split('BP:')[1] if 'BP:' in recent_vitals else '120/80'
        risk_level = 0.5
        if condition in ['Diabetes', 'Hypertension']:
            risk_level += 0.2
        if heart_rate > 100:
            risk_level += 0.1
        if int(blood_pressure.split('/')[0]) > 140:
            risk_level += 0.1
        risk_level = min(risk_level, 1.0)
        
        conn.execute('''
            UPDATE patients SET name = ?, age = ?, gender = ?, condition = ?, risk_level = ?,
            medical_history = ?, recent_vitals = ?, contact_info = ?, allergies = ?, medications = ?, last_visit = ?
            WHERE id = ?
        ''', (name, age, gender, condition, risk_level, medical_history, recent_vitals, contact_info, allergies, medications, last_visit, id))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))
    
    conn.close()
    return render_template('edit_patient.html', patient=patient)

@app.route('/delete_patient/<int:id>')
def delete_patient(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM patients WHERE id = ?', (id,))
    conn.execute('DELETE FROM appointments WHERE patient_id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/bulk_delete_patients', methods=['POST'])
def bulk_delete_patients():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    ids = request.json.get('ids', [])
    if ids:
        conn = get_db_connection()
        conn.execute('DELETE FROM patients WHERE id IN ({})'.format(','.join('?' * len(ids))), ids)
        conn.execute('DELETE FROM appointments WHERE patient_id IN ({})'.format(','.join('?' * len(ids))), ids)
        conn.commit()
        conn.close()
    return jsonify({'status': 'success'})

@app.route('/add_appointment', methods=['GET', 'POST'])
def add_appointment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    patients = conn.execute('SELECT id, name FROM patients').fetchall()
    
    if request.method == 'POST':
        patient_id = int(request.form['patient_id'])
        title = request.form['title']
        date = request.form['date']
        time = request.form['time']
        notes = request.form['notes']
        status = request.form['status']
        
        patient = conn.execute('SELECT name FROM patients WHERE id = ?', (patient_id,)).fetchone()
        patient_name = patient['name'] if patient else 'Unknown'
        
        conn.execute('''
            INSERT INTO appointments (patient_id, patient_name, title, date, time, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (patient_id, patient_name, title, date, time, notes, status))
        conn.commit()
        
        socketio.emit('new_appointment', {
            'message': f"New appointment: {title} with {patient_name} on {date} at {time}"
        })
        
        conn.close()
        return redirect(url_for('dashboard'))
    
    conn.close()
    return render_template('add_appointment.html', patients=patients)

@app.route('/edit_appointment/<int:id>', methods=['GET', 'POST'])
def edit_appointment(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    appointment = conn.execute('SELECT * FROM appointments WHERE id = ?', (id,)).fetchone()
    patients = conn.execute('SELECT id, name FROM patients').fetchall()
    
    if request.method == 'POST':
        patient_id = int(request.form['patient_id'])
        title = request.form['title']
        date = request.form['date']
        time = request.form['time']
        notes = request.form['notes']
        status = request.form['status']
        
        patient = conn.execute('SELECT name FROM patients WHERE id = ?', (patient_id,)).fetchone()
        patient_name = patient['name'] if patient else 'Unknown'
        
        conn.execute('''
            UPDATE appointments SET patient_id = ?, patient_name = ?, title = ?, date = ?, time = ?, notes = ?, status = ?
            WHERE id = ?
        ''', (patient_id, patient_name, title, date, time, notes, status, id))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))
    
    conn.close()
    return render_template('edit_appointment.html', appointment=appointment, patients=patients)

@app.route('/delete_appointment/<int:id>')
def delete_appointment(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM appointments WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/add_task', methods=['GET', 'POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        description = request.form['description']
        priority = request.form['priority']
        due_date = request.form['due_date']
        status = request.form['status']
        
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO tasks (description, priority, due_date, status)
            VALUES (?, ?, ?, ?)
        ''', (description, priority, due_date, status))
        conn.commit()
        
        if priority == 'High' and status == 'Pending':
            socketio.emit('new_task', {
                'message': f"High Priority Task added: {description} due {due_date}"
            })
        
        conn.close()
        return redirect(url_for('dashboard'))
    
    return render_template('add_task.html')

@app.route('/edit_task/<int:id>', methods=['GET', 'POST'])
def edit_task(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (id,)).fetchone()
    
    if request.method == 'POST':
        description = request.form['description']
        priority = request.form['priority']
        due_date = request.form['due_date']
        status = request.form['status']
        
        conn.execute('''
            UPDATE tasks SET description = ?, priority = ?, due_date = ?, status = ?
            WHERE id = ?
        ''', (description, priority, due_date, status, id))
        conn.commit()
        
        if priority == 'High' and status == 'Pending':
            socketio.emit('new_task', {
                'message': f"High Priority Task updated: {description} due {due_date}"
            })
        
        conn.close()
        return redirect(url_for('dashboard'))
    
    conn.close()
    return render_template('edit_task.html', task=task)

@app.route('/delete_task/<int:id>')
def delete_task(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM tasks WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@socketio.on('connect')
def handle_connect():
    print("Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

if __name__ == '__main__':
    socketio.run(app, debug=True)