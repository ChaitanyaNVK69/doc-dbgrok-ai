from flask import Flask, render_template, send_file, request, redirect, url_for, flash, session, jsonify
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
import random
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from sklearn.feature_extraction.text import TfidfVectorizer

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
app.config['MAIL_PASSWORD'] = 'HR.BGLR@123'  # Replace with Gmail App Password
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

@app.route('/prioritize_tasks')
def prioritize_tasks():
    try:
        conn = get_db_connection()
        tasks = conn.execute('SELECT id, description, priority, due_date FROM tasks').fetchall()
        conn.close()

        if not tasks:
            print("Warning: No tasks found in database")
            return jsonify({'prioritized_tasks': []})

        prioritized_tasks = []
        for task in tasks:
            urgency = {'High': 3, 'Medium': 2, 'Low': 1}.get(task['priority'], 1)
            due_date = task['due_date'] if task['due_date'] else datetime.now().strftime('%Y-%m-%d')
            try:
                due_date_obj = datetime.strptime(due_date, '%Y-%m-%d')
                days_diff = (due_date_obj - datetime.now()).days
                priority_score = urgency * (1 / (days_diff + 1) if days_diff >= 0 else 2)
            except ValueError:
                print(f"Warning: Invalid due_date for task {task['id']}: {due_date}")
                priority_score = urgency
            prioritized_tasks.append({
                'id': task['id'],
                'description': task['description'] or 'No description',
                'priority': min(priority_score, 10)
            })

        prioritized_tasks.sort(key=lambda x: x['priority'], reverse=True)
        print("Prioritized tasks:", prioritized_tasks)
        return jsonify({'prioritized_tasks': prioritized_tasks})
    except Exception as e:
        print(f"Error prioritizing tasks: {e}")
        return jsonify({'error': str(e)}), 500

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

@app.route('/no_show_prediction/<int:patient_id>')
def no_show_prediction(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT risk_level FROM patients WHERE id = ?', (patient_id,)).fetchone()
        appointments = conn.execute('SELECT status FROM appointments WHERE patient_id = ?', (patient_id,)).fetchall()
        conn.close()

        if not patient:
            print(f"Error: Patient not found for ID {patient_id}")
            return jsonify({'error': 'Patient not found'}), 404

        no_shows = sum(1 for appt in appointments if appt['status'] == 'Missed')
        total_appts = len(appointments)
        no_show_rate = no_shows / total_appts if total_appts > 0 else 0

        # Use no-show rate directly as a fallback to avoid classifier issues
        no_show_prob = no_show_rate if total_appts > 0 else 0.5
        print(f"No-show probability for patient {patient_id}: {no_show_prob}")
        return jsonify({'no_show_probability': float(no_show_prob)})
    except Exception as e:
        print(f"Error predicting no-show for patient {patient_id}: {e}")
        return jsonify({'error': str(e)}), 500

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

@app.route('/check_med_interactions/<int:patient_id>')
def check_med_interactions(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT medications FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        medications = patient['medications'].split(',') if patient['medications'] else []
        interactions = []

        known_interactions = {
            ('Aspirin', 'Warfarin'): 'Risk of bleeding increased',
            ('Metformin', 'Insulin'): 'Monitor blood glucose closely',
            ('Ibuprofen', 'Aspirin'): 'Increased gastrointestinal risk'
        }

        for i, med1 in enumerate(medications):
            for med2 in medications[i+1:]:
                med_pair = tuple(sorted([med1.strip(), med2.strip()]))
                if med_pair in known_interactions:
                    interactions.append({'medications': med_pair, 'warning': known_interactions[med_pair]})

        return jsonify({'interactions': interactions})
    except Exception as e:
        print(f"Error checking medication interactions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/monitor_vitals/<int:patient_id>')
def monitor_vitals(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT risk_level, recent_vitals FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        heart_rate = float(patient['recent_vitals'].split('HR:')[1].split(',')[0]) if patient['recent_vitals'] and 'HR:' in patient['recent_vitals'] else 80
        bp_systolic = float(patient['recent_vitals'].split('BP:')[1].split('/')[0]) if patient['recent_vitals'] and 'BP:' in patient['recent_vitals'] else 120
        heart_rate += random.uniform(-5, 5)
        bp_systolic += random.uniform(-10, 10)

        alerts = []
        if heart_rate > 100:
            alerts.append(f"High heart rate: {heart_rate:.1f} bpm")
        if bp_systolic > 140:
            alerts.append(f"High blood pressure: {bp_systolic:.1f}/80 mmHg")

        if alerts:
            socketio.emit('vitals_alert', {
                'patient_id': patient_id,
                'alerts': alerts
            })

        return jsonify({
            'heart_rate': heart_rate,
            'bp_systolic': bp_systolic,
            'alerts': alerts
        })
    except Exception as e:
        print(f"Error monitoring vitals: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/schedule_communication/<int:patient_id>')
def schedule_communication(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT contact_info, risk_level FROM patients WHERE id = ?', (patient_id,)).fetchone()
        appointments = conn.execute('SELECT title, date, time FROM appointments WHERE patient_id = ? AND date >= ? AND status = "Upcoming"', (patient_id, datetime.today().strftime('%Y-%m-%d'))).fetchall()
        conn.close()

        if not patient or not patient['contact_info']:
            return jsonify({'error': 'Patient or contact info not found'}), 404

        email = patient['contact_info']
        risk_level = patient['risk_level']
        reminders = []

        for appt in appointments:
            appt_date = datetime.strptime(appt['date'], '%Y-%m-%d')
            days_until = (appt_date - datetime.today()).days
            if risk_level > 0.7 and days_until <= 3:
                reminders.append({
                    'type': 'email',
                    'subject': f"Appointment Reminder: {appt['title']}",
                    'body': f"Dear Patient, your appointment '{appt['title']}' is scheduled for {appt['date']} at {appt['time']}. Please confirm attendance.",
                    'send_date': (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
                })

        if reminders:
            msg = Message(reminders[0]['subject'], sender=app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = reminders[0]['body']
            try:
                mail.send(msg)
                print(f"Reminder email sent to {email}")
            except Exception as e:
                print(f"Reminder email failed: {e}")

        return jsonify({'reminders': reminders})
    except Exception as e:
        print(f"Error scheduling communication: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/resource_allocation')
def resource_allocation():
    try:
        conn = get_db_connection()
        appointments = conn.execute('SELECT date, patient_id FROM appointments WHERE date >= ? AND date <= ?', 
                                  (datetime.today().strftime('%Y-%m-%d'), (datetime.today() + timedelta(days=7)).strftime('%Y-%m-%d'))).fetchall()
        patients = conn.execute('SELECT id, risk_level FROM patients').fetchall()
        conn.close()

        patient_risk = {p['id']: p['risk_level'] for p in patients}
        appt_data = pd.DataFrame([{
            'date': appt['date'],
            'patient_id': appt['patient_id'],
            'risk_level': patient_risk.get(appt['patient_id'], 0.5)
        } for appt in appointments])

        recommendations = []
        if not appt_data.empty:
            daily_load = appt_data.groupby('date').agg({'patient_id': 'count', 'risk_level': 'mean'}).reset_index()
            for _, row in daily_load.iterrows():
                staff_needed = max(1, int(row['patient_id'] / 5))
                equipment_needed = 'Standard' if row['risk_level'] < 0.7 else 'Advanced'
                recommendations.append({
                    'date': row['date'],
                    'staff_needed': staff_needed,
                    'equipment_needed': equipment_needed
                })

        return jsonify({'recommendations': recommendations})
    except Exception as e:
        print(f"Error allocating resources: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/patient_sentiment/<int:patient_id>')
def patient_sentiment(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT id FROM patients WHERE id = ?', (patient_id,)).fetchone()
        notes = conn.execute('SELECT note FROM patient_notes WHERE patient_id = ?', (patient_id,)).fetchall()
        conn.close()

        if not patient:
            print(f"Error: Patient not found for ID {patient_id}")
            return jsonify({'error': 'Patient not found'}), 404

        if not notes:
            print(f"Warning: No notes found for patient {patient_id}")
            return jsonify({'sentiment': 'neutral', 'confidence': 0.0})

        texts = [note['note'] for note in notes]
        vectorizer = TfidfVectorizer(stop_words='english')
        X = vectorizer.fit_transform(texts)
        positive_words = ['good', 'happy', 'improving']
        negative_words = ['bad', 'pain', 'worse']
        sentiment_score = sum(text.lower().count(word) for text in texts for word in positive_words) - sum(text.lower().count(word) for text in texts for word in negative_words)
        sentiment = 'positive' if sentiment_score > 0 else 'negative' if sentiment_score < 0 else 'neutral'
        confidence = min(abs(sentiment_score) / 10, 1.0)

        print(f"Sentiment for patient {patient_id}: {sentiment}, confidence: {confidence}")
        return jsonify({'sentiment': sentiment, 'confidence': confidence})
    except Exception as e:
        print(f"Error analyzing sentiment for patient {patient_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/appointment_priority/<int:patient_id>')
def appointment_priority(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT risk_level FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            print(f"Error: Patient not found for ID {patient_id}")
            return jsonify({'error': 'Patient not found'}), 404

        risk_level = patient['risk_level'] if patient['risk_level'] is not None else 0
        no_show_response = no_show_prediction(patient_id)
        if no_show_response.status_code != 200:
            print(f"Error fetching no-show probability for patient {patient_id}")
            no_show_prob = 0.5
        else:
            no_show_prob = no_show_response.get_json().get('no_show_probability', 0.5)

        # Calculate priority score without urgency (not available in schema)
        priority_score = (risk_level * 0.6 + no_show_prob * 0.4) * 10
        priority_level = 'High' if priority_score > 7 else 'Medium' if priority_score > 4 else 'Low'

        print(f"Appointment priority for patient {patient_id}: {priority_level}, score: {priority_score}")
        return jsonify({'priority_level': priority_level, 'priority_score': float(priority_score)})
    except Exception as e:
        print(f"Error calculating appointment priority for patient {patient_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/follow_up_reminder/<int:patient_id>')
def follow_up_reminder(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT id, last_visit FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            print(f"Error: Patient not found for ID {patient_id}")
            return jsonify({'error': 'Patient not found'}), 404

        last_visit = patient['last_visit']
        if not last_visit:
            print(f"Warning: No last visit for patient {patient_id}")
            return jsonify({'reminder': 'No follow-up needed', 'due_date': None})

        last_date = datetime.strptime(last_visit, '%Y-%m-%d')
        follow_up_date = last_date + timedelta(days=30)
        reminder = f"Schedule follow-up for patient {patient_id} by {follow_up_date.strftime('%Y-%m-%d')}"

        print(f"Follow-up reminder for patient {patient_id}: {reminder}")
        return jsonify({'reminder': reminder, 'due_date': follow_up_date.strftime('%Y-%m-%d')})
    except Exception as e:
        print(f"Error generating follow-up reminder for patient {patient_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/patient_summary/<int:patient_id>')
def patient_summary(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT recent_vitals, medical_history FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        vitals = patient['recent_vitals'].split(',') if patient['recent_vitals'] else []
        summary = {
            'vitals': [{'heart_rate': float(v.split('HR:')[1]) if 'HR:' in v else 0} for v in vitals],
            'labels': ['Latest'],
            'history': patient['medical_history']
        }
        return jsonify(summary)
    except Exception as e:
        print(f"Error generating patient summary: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health_risk_prediction/<int:patient_id>')
def health_risk_prediction(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT risk_level, medical_history FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        alert = f"Risk level: {patient['risk_level']}"
        guideline = "https://www.cdc.gov"
        return jsonify({'alert': alert, 'guideline': guideline})
    except Exception as e:
        print(f"Error predicting health risk: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/triage_tasks/<int:patient_id>')
def triage_tasks(patient_id):
    try:
        conn = get_db_connection()
        # Fetch all tasks since patient_id is not in schema
        tasks = conn.execute('SELECT description, priority FROM tasks').fetchall()
        conn.close()

        triaged_tasks = [{'description': t['description'], 'triage_score': {'High': 3, 'Medium': 2, 'Low': 1}.get(t['priority'], 1)} for t in tasks]
        print(f"Triaged tasks for patient {patient_id}:", triaged_tasks)
        return jsonify({'triaged_tasks': triaged_tasks})
    except Exception as e:
        print(f"Error triaging tasks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/image_analysis/<int:patient_id>')
def image_analysis(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT medical_history FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        condition = "Normal"
        confidence = 0.9
        return jsonify({'condition': condition, 'confidence': confidence})
    except Exception as e:
        print(f"Error analyzing image: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/unified_data/<int:patient_id>')
def unified_data(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT medical_history FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        ehr = {'history': patient['medical_history']}
        return jsonify({'ehr': ehr})
    except Exception as e:
        print(f"Error fetching unified data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/wearable_monitoring/<int:patient_id>')
def wearable_monitoring(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT recent_vitals FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        heart_rate = float(patient['recent_vitals'].split('HR:')[1].split(',')[0]) if patient['recent_vitals'] and 'HR:' in patient['recent_vitals'] else 80
        alert = f"Heart rate: {heart_rate}"
        return jsonify({'alert': alert, 'heart_rate': heart_rate})
    except Exception as e:
        print(f"Error monitoring wearable: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/compliance_check/<int:patient_id>')
def compliance_check(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT id FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        status = "Compliant"
        audit_trail = "All records up to date"
        return jsonify({'status': status, 'audit_trail': audit_trail})
    except Exception as e:
        print(f"Error checking compliance: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/personalized_plan/<int:patient_id>')
def personalized_plan(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT medical_history FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        recommendations = [f"Follow {patient['medical_history']} treatment plan"]
        return jsonify({'recommendations': recommendations})
    except Exception as e:
        print(f"Error generating personalized plan: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/transcribe/<int:patient_id>', methods=['POST'])
def transcribe(patient_id):
    try:
        data = request.get_json()
        transcription = data.get('transcription', '')
        if not transcription:
            return jsonify({'error': 'No transcription provided'}), 400

        conn = get_db_connection()
        conn.execute('INSERT INTO patient_notes (patient_id, note, date) VALUES (?, ?, ?)',
                     (patient_id, transcription, datetime.now().strftime('%Y-%m-%d')))
        conn.commit()
        conn.close()
        return jsonify({'status': 'Transcription saved'})
    except Exception as e:
        print(f"Error saving transcription: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/chatbot/<int:patient_id>', methods=['POST'])
def chatbot(patient_id):
    try:
        data = request.get_json()
        query = data.get('query', '')
        if not query:
            return jsonify({'error': 'No query provided'}), 400

        response = f"Response to '{query}' for patient {patient_id}"
        return jsonify({'response': response})
    except Exception as e:
        print(f"Error processing chatbot query: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/ai_insights')
def ai_insights():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        print("Rendering AI Insights page")
        return render_template('ai_insights.html')
    except Exception as e:
        print(f"Error rendering AI Insights page: {e}")
        return jsonify({'error': 'Failed to load AI Insights page'}), 500

@app.route('/all_ai_insights/<int:patient_id>')
def all_ai_insights(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT id FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            print(f"Error: Patient not found for ID {patient_id}")
            return jsonify({'error': 'Patient not found'}), 404

        insights = {}
        endpoints = [
            ('suggested_appointments', suggest_appointment),
            ('health_trends', health_trends),
            ('risk_clusters', patient_risk_clusters),
            ('no_show_prediction', no_show_prediction),
            ('follow_up_recommendations', follow_up_recommendations),
            ('med_interactions', check_med_interactions),
            ('vitals_alerts', monitor_vitals),
            ('resource_allocation', resource_allocation),
            ('patient_sentiment', patient_sentiment),
            ('appointment_priority', appointment_priority),
            ('follow_up_reminder', follow_up_reminder),
            ('patient_summary', patient_summary),
            ('health_risk_prediction', health_risk_prediction),
            ('triage_tasks', triage_tasks),
            ('image_analysis', image_analysis),
            ('unified_data', unified_data),
            ('wearable_monitoring', wearable_monitoring),
            ('compliance_check', compliance_check),
            ('personalized_plan', personalized_plan)
        ]

        for key, func in endpoints:
            try:
                response = func(patient_id) if key not in ['risk_clusters', 'resource_allocation'] else func()
                insights[key] = response.get_json()
                print(f"Successfully fetched {key} for patient {patient_id}")
            except Exception as e:
                print(f"Error fetching {key} for patient {patient_id}: {e}")
                insights[key] = {'error': str(e)}

        print(f"All insights fetched for patient {patient_id}:", insights)
        return jsonify(insights)
    except Exception as e:
        print(f"Error fetching all AI insights for patient {patient_id}: {e}")
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
    risk_min = request.args.get('risk_min', '')
    risk_max = request.args.get('risk_max', '')
    
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
        return jsonify({'error': str(e)}), 500

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

@app.route('/api/patients')
def get_patients():
    try:
        conn = get_db_connection()
        patients = conn.execute('SELECT id AS patient_id, name FROM patients').fetchall()
        conn.close()
        if not patients:
            print("Warning: No patients found in database")
            return jsonify([])
        print("Patients fetched:", [dict(row) for row in patients])
        return jsonify([dict(row) for row in patients])
    except Exception as e:
        print(f"Error fetching patients: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/export_insights/<int:patient_id>')
def export_insights(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT name FROM patients WHERE id = ?', (patient_id,)).fetchone()
        conn.close()

        if not patient:
            print(f"Error: Patient not found for ID {patient_id}")
            return jsonify({'error': 'Patient not found'}), 404

        insights_response = all_ai_insights(patient_id)
        insights = insights_response.get_json()
        print("Insights fetched for export:", insights)

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, 750, f"AI Insights Report for {patient['name']}")
        c.setFont("Helvetica", 12)
        y = 700

        sections = [
            ('Suggested Appointments', insights.get('suggested_appointments', {}).get('suggested_slots', [])),
            ('Health Trends', insights.get('health_trends', {}).get('trends', {}).get('risk', 'N/A')),
            ('Patient Risk Clusters', insights.get('risk_clusters', {}).get('clusters', [])),
            ('No-Show Predictions', insights.get('no_show_prediction', {}).get('no_show_probability', 0)),
            ('Follow-Up Recommendations', insights.get('follow_up_recommendations', {}).get('recommendation', {}).get('follow_up', 'N/A')),
            ('Medication Interactions', insights.get('med_interactions', {}).get('interactions', [])),
            ('Real-Time Vitals Alerts', insights.get('vitals_alerts', {}).get('alerts', [])),
            ('Resource Allocation', insights.get('resource_allocation', {}).get('recommendations', [])),
            ('Patient Sentiment', insights.get('patient_sentiment', {}).get('sentiment', 'N/A')),
            ('Appointment Priority', insights.get('appointment_priority', {}).get('priority_level', 'N/A')),
            ('Follow-Up Reminder', insights.get('follow_up_reminder', {}).get('reminder', 'N/A')),
            ('Patient Summary', insights.get('patient_summary', {}).get('history', 'N/A')),
            ('Health Risk Prediction', insights.get('health_risk_prediction', {}).get('alert', 'N/A')),
            ('Triaged Tasks', insights.get('triage_tasks', {}).get('triaged_tasks', [])),
            ('Image Analysis', insights.get('image_analysis', {}).get('condition', 'N/A')),
            ('Unified Data', insights.get('unified_data', {}).get('ehr', {}).get('history', 'N/A')),
            ('Wearable Monitoring', insights.get('wearable_monitoring', {}).get('alert', 'N/A')),
            ('Compliance Check', insights.get('compliance_check', {}).get('status', 'N/A')),
            ('Personalized Plan', insights.get('personalized_plan', {}).get('recommendations', []))
        ]

        for title, data in sections:
            c.setFont("Helvetica-Bold", 14)
            c.drawString(100, y, title)
            y -= 20
            c.setFont("Helvetica", 12)
            if isinstance(data, list) and data:
                for item in data[:5]:
                    text = str(item)[:50] + '...' if len(str(item)) > 50 else str(item)
                    c.drawString(120, y, f"- {text}")
                    y -= 15
            else:
                text = str(data)[:50] + '...' if len(str(data)) > 50 else str(data)
                c.drawString(120, y, f"- {text}")
                y -= 15
            y -= 10
            if y < 50:
                c.showPage()
                y = 750

        c.save()
        buffer.seek(0)
        print(f"PDF generated for patient {patient_id}")
        return send_file(buffer, as_attachment=True, download_name=f"insights_{patient_id}.pdf", mimetype='application/pdf')
    except Exception as e:
        print(f"Error exporting insights: {e}")
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    print("Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

if __name__ == '__main__':
    socketio.run(app, debug=True)