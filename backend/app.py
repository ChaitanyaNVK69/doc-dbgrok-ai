import os
from dotenv import load_dotenv
# Store database connection in Flask's application context
# from flask import g
# Disable numpy's macOS check to avoid MemoryError
import numpy as np
def _dummy_check():
    pass
np._mac_os_check = _dummy_check

from flask import Flask, render_template, send_file, request, redirect, url_for, flash, session, jsonify
from flask_mail import Mail, Message
from flask_socketio import SocketIO, emit
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
import schedule
import random
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from sklearn.feature_extraction.text import TfidfVectorizer
import requests  # For WhatsApp API
import re
import requests
import threading
import psycopg2
import time
# Import the init_db function to create the database schema
from init_db import init_db

# Example using OpenAI API (requires `openai` package)
from openai import OpenAI

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', 'your-openai-api-key-here')  # Replace with your actual key
client = OpenAI(api_key=OPENAI_API_KEY)


# Add at the top of app.py, after imports
db_lock = threading.Lock()


app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['DEBUG'] = True
app.config['TESTING'] = True
socketio = SocketIO(app)


# Global cache for registered numbers
REGISTERED_NUMBERS_CACHE = None
CACHE_DURATION = 3600  # Cache for 1 hour (in seconds)

# Load environment variables
load_dotenv()


# WhatsApp API Configuration (replace with your Twilio credentials)
# WHATSAPP_API_URL = "https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
# TWILIO_ACCOUNT_SID = "your_twilio_account_sid"
# TWILIO_AUTH_TOKEN = "your_twilio_auth_token"
# WHATSAPP_FROM = "whatsapp:+14155238886"  # Twilio sandbox number

def safe_url(endpoint):
    try:
        return url_for(endpoint)
    except Exception as e:
        print(f"Error generating URL for endpoint '{endpoint}': {e}")
        return None

# Register the filter with Jinja2
app.jinja_env.filters['safe_url'] = safe_url

# Log all routes at startup
with app.app_context():
    print("Registered routes at startup:")
    for rule in app.url_map.iter_rules():
        print(f"Endpoint: {rule.endpoint}, Rule: {rule}, Methods: {list(rule.methods)}")

# WhatsApp API Configuration (Replace with your actual credentials)
WHATSAPP_API_URL = "https://graph.facebook.com/v17.0/"
WHATSAPP_PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID')
WHATSAPP_ACCESS_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN')



# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
# Update Flask-Mail configuration
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
# app.config['MAIL_USERNAME'] = 'hr.bglr@gmail.com'
# app.config['MAIL_PASSWORD'] = 'HR.BGLR@123'  # Replace with Gmail App Password
mail = Mail(app)



# def get_db_connection():
#     conn = sqlite3.connect('doctor_dashboard.db')
#     conn.row_factory = sqlite3.Row
#      # Set a busy timeout of 10 seconds to wait for locks to be released
#     conn.execute('PRAGMA busy_timeout = 10000')
#     return conn

def get_db_connection():
    # Debug: Print environment variables
    print("Environment variables:", {k: v for k, v in os.environ.items() if k.startswith('DB_') or k == 'RENDER'})
    render_env = os.environ.get('RENDER', 'false').lower()
    print(f"RENDER environment variable: {render_env}")
    is_render = render_env == 'true'
    print(f"Is running on Render? {is_render}")

    if is_render:
        print("Connecting to PostgreSQL on Render")
        try:
            # Only use PostgreSQL if explicitly on Render
            conn = psycopg2.connect(
                dbname=os.environ.get('DB_NAME'),
                user=os.environ.get('DB_USER'),
                password=os.environ.get('DB_PASSWORD'),
                host=os.environ.get('DB_HOST'),
                port=os.environ.get('DB_PORT'),
                sslmode='require'
            )
        except psycopg2.Error as e:
            print(f"Failed to connect to PostgreSQL: {e}")
            raise
    else:
        print("Forcing local SQLite database connection")
        conn = sqlite3.connect('doctor_dashboard.db')
        conn.row_factory = sqlite3.Row
    return conn

# Initialize database tables
with app.app_context():
    init_db()  # Use the init_db function from init_db.py



# def send_whatsapp_message(to, message):
#     try:
#         response = requests.post(
#             WHATSAPP_API_URL.format(TWILIO_ACCOUNT_SID),
#             auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
#             data={
#                 "From": WHATSAPP_FROM,
#                 "To": to,
#                 "Body": message
#             }
#         )
#         response.raise_for_status()
#         return response.json()
#     except Exception as e:
#         print(f"Error sending WhatsApp message: {e}")
#         return None

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

        # Send WhatsApp reminder if due soon
        days_until = (follow_up_date - datetime.today()).days
        if days_until <= 3:
            patient_contact = conn.execute('SELECT contact_info FROM patients WHERE id = ?', (patient_id,)).fetchone()['contact_info']
            send_whatsapp_message(patient_contact, reminder)
            conn.execute('INSERT INTO whatsapp_messages (patient_id, message, sender, timestamp, type) VALUES (?, ?, ?, ?, ?)',
                         (patient_id, reminder, 'bot', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text'))
            conn.commit()

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
        # Send health tip via WhatsApp
        send_whatsapp_message(patient['contact_info'], recommendations[0])
        conn.execute('INSERT INTO whatsapp_messages (patient_id, message, sender, timestamp, type) VALUES (?, ?, ?, ?, ?)',
                     (patient_id, recommendations[0], 'bot', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text'))
        conn.commit()

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

        with db_lock:
            conn = get_db_connection()
            conn.execute('INSERT INTO patient_notes (patient_id, note, created_at) VALUES (?, ?, ?)',
                         (patient_id, transcription, datetime.now().strftime('%Y-%m-%d')))
            conn.commit()
            conn.close()

        print(f"Transcription saved for patient {patient_id}: {transcription}")
        return jsonify({'status': 'Transcription saved'})
    except sqlite3.OperationalError as e:
        print(f"Database error in /transcribe for patient {patient_id}: {e}")
        return jsonify({'error': f"Database error: {str(e)}"}), 500
    except Exception as e:
        print(f"Unexpected error in /transcribe for patient {patient_id}: {e}")
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
# ************************************************ Old WhatsApp Routes***********************************************

# ********WhatsApp Routes
# @app.route('/whatsapp/webhook', methods=['POST'])
# def whatsapp_webhook():
    try:
        data = request.get_json()
        message = data.get('Body', '').lower()
        from_number = data.get('From')

        conn = get_db_connection()
        patient = conn.execute('SELECT id FROM patients WHERE contact_info = ?', (from_number,)).fetchone()
        if not patient:
            send_whatsapp_message(from_number, "Please register with the clinic to use this service.")
            return jsonify({'status': 'Patient not found'}), 404

        patient_id = patient['id']
        conn.execute('INSERT INTO whatsapp_messages (patient_id, message, sender, timestamp, type) VALUES (?, ?, ?, ?, ?)',
                     (patient_id, message, 'patient', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text'))
        conn.commit()

        # Handle FAQs
        faq = conn.execute('SELECT answer FROM whatsapp_faq WHERE LOWER(question) LIKE ?', (f'%{message}%',)).fetchone()
        if faq:
            send_whatsapp_message(from_number, faq['answer'])
            conn.execute('INSERT INTO whatsapp_messages (patient_id, message, sender, timestamp, type) VALUES (?, ?, ?, ?, ?)',
                         (patient_id, faq['answer'], 'bot', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text'))
            conn.commit()
            conn.close()
            return jsonify({'status': 'FAQ answered'})

        # Appointment Scheduling
        if 'book appointment' in message:
            slots_response = requests.get(f'http://localhost:5000/suggest_appointment/{patient_id}')
            slots = slots_response.json().get('suggested_slots', [])
            if slots:
                reply = "Available slots:\n" + "\n".join(slots[:3]) + "\nReply with the slot to book (e.g., '2025-04-23 10:00:00')."
                send_whatsapp_message(from_number, reply)
                conn.execute('INSERT INTO whatsapp_messages (patient_id, message, sender, timestamp, type) VALUES (?, ?, ?, ?, ?)',
                             (patient_id, reply, 'bot', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text'))
                conn.commit()
            conn.close()
            return jsonify({'status': 'Appointment slots sent'})

        # Symptom Triage and Emergency Alerts
        if 'pain' in message or 'symptom' in message or 'emergency' in message:
            trends_response = requests.get(f'http://localhost:5000/health_trends/{patient_id}')
            trends = trends_response.json().get('trends', {}).get('risk', 'Unknown')
            reply = f"Symptom summary: {trends}. Please wait for the doctor to review."
            send_whatsapp_message(from_number, reply)
            conn.execute('INSERT INTO whatsapp_messages (patient_id, message, sender, timestamp, type) VALUES (?, ?, ?, ?, ?)',
                         (patient_id, reply, 'bot', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text'))
            conn.commit()

            if 'Elevated' in trends or 'High' in trends or 'emergency' in message.lower():
                socketio.emit('vitals_alert', {
                    'patient_id': patient_id,
                    'alerts': [f"Urgent: Patient {patient_id} reported symptoms - {trends}"]
                })

        # Default: Escalate to Doctor
        else:
            reply = "Your message has been forwarded to the doctor. You'll hear back soon."
            send_whatsapp_message(from_number, reply)
            conn.execute('INSERT INTO whatsapp_messages (patient_id, message, sender, timestamp, type) VALUES (?, ?, ?, ?, ?)',
                         (patient_id, reply, 'bot', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text'))
            conn.commit()

        conn.close()
        return jsonify({'status': 'Message processed'})
    except Exception as e:
        print(f"Error in WhatsApp webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/whatsapp/messages/<int:patient_id>')
def get_whatsapp_messages(patient_id):
    try:
        conn = get_db_connection()
        messages = conn.execute('SELECT * FROM whatsapp_messages WHERE patient_id = ? ORDER BY timestamp ASC', (patient_id,)).fetchall()
        conn.close()
        return jsonify([dict(msg) for msg in messages])
    except Exception as e:
        print(f"Error fetching WhatsApp messages: {e}")
        return jsonify({'error': str(e)}), 500

# @app.route('/whatsapp/send/<int:patient_id>', methods=['POST'])
# def send_whatsapp_message_route(patient_id):
#     try:
#         data = request.get_json()
#         message = data.get('message')
#         if not message:
#             return jsonify({'error': 'Message is required'}), 400

#         conn = get_db_connection()
#         patient = conn.execute('SELECT contact_info FROM patients WHERE id = ?', (patient_id,)).fetchone()
#         if not patient:
#             return jsonify({'error': 'Patient not found'}), 404

#         to_number = patient['contact_info']
#         send_whatsapp_message(to_number, message)
#         conn.execute('INSERT INTO whatsapp_messages (patient_id, message, sender, timestamp, type) VALUES (?, ?, ?, ?, ?)',
#                      (patient_id, message, 'doctor', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text'))
#         conn.commit()
#         conn.close()
#         return jsonify({'status': 'Message sent'})
#     except Exception as e:
#         print(f"Error sending WhatsApp message: {e}")
#         return jsonify({'error': str(e)}), 500

@app.route('/whatsapp/summarize/<int:patient_id>', methods=['POST'])
def summarize_symptoms(patient_id):
    try:
        conn = get_db_connection()
        messages = conn.execute('SELECT message FROM whatsapp_messages WHERE patient_id = ? AND sender = "patient"', (patient_id,)).fetchall()
        conn.close()

        symptoms = " ".join([msg['message'] for msg in messages])
        trends_response = requests.get(f'http://localhost:5000/health_trends/{patient_id}')
        trends = trends_response.json().get('trends', {}).get('risk', 'Unknown')

        summary = f"Symptom summary for patient {patient_id}: {trends}"
        return jsonify({'summary': summary})
    except Exception as e:
        print(f"Error summarizing symptoms: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/whatsapp/health_tips/<int:patient_id>')
def send_health_tips(patient_id):
    try:
        conn = get_db_connection()
        patient = conn.execute('SELECT contact_info, medical_history FROM patients WHERE id = ?', (patient_id,)).fetchone()
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404

        tip = f"Health Tip: Based on your history ({patient['medical_history']}), ensure regular check-ups."
        send_whatsapp_message(patient['contact_info'], tip)
        conn.execute('INSERT INTO whatsapp_messages (patient_id, message, sender, timestamp, type) VALUES (?, ?, ?, ?, ?)',
                     (patient_id, tip, 'bot', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text'))
        conn.commit()
        conn.close()
        return jsonify({'status': 'Health tip sent'})
    except Exception as e:
        print(f"Error sending health tip: {e}")
        return jsonify({'error': str(e)}), 500

# ************************************************ Old WhatsApp Routes***********************************************

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
        print("User not logged in, redirecting to login")
        return redirect(url_for('login'))
    try:
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

    # Precompute URLs for navigation links
        nav_links = {}
        try:
            nav_links['medical_notes'] = url_for('medical_notes_endpoint')
        except Exception as e:
            print(f"Error generating URL for 'medical_notes_endpoint': {e}")
            nav_links['medical_notes'] = None
        try:
            nav_links['diagnostics'] = url_for('diagnostics_endpoint')
        except Exception as e:
            print(f"Error generating URL for 'diagnostics_endpoint': {e}")
            nav_links['diagnostics'] = None


        
        print("Rendering dashboard.html with data: overview=%s, patients=%s, appointments=%s, tasks=%s, notifications=%s, analytics=%s, nav_links=%s" % (
            overview, len(patients), len(appointments), len(tasks), notifications, analytics, nav_links
        ))
        return render_template('dashboard.html',
                            overview=overview,
                            patients=patients,
                            appointments=appointments,
                            tasks=tasks,
                            notifications=notifications,
                            analytics=analytics,
                            nav_links=nav_links,
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

@app.route('/dashboard/appointments')
def appointments():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        appointments = conn.execute('SELECT id, patient_name, doctor_name, date, time, status, reason FROM appointments').fetchall()
        patients = conn.execute('SELECT id, name FROM patients').fetchall()
        doctors = conn.execute('SELECT id, name FROM doctors').fetchall()
        conn.close()

        return render_template('appointments.html',
                             appointments=appointments,
                             patients=patients,
                             doctors=doctors)
    except Exception as e:
        print(f"Error rendering appointments page: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/appointments', methods=['GET'])
def get_appointments_api():
    try:
        conn = get_db_connection()
        appointments = conn.execute('SELECT id, patient_name, doctor_name, date, time, status, reason FROM appointments').fetchall()
        conn.close()

        appointments_list = [dict(row) for row in appointments]
        print("Appointments fetched for API:", appointments_list)
        return jsonify(appointments_list)
    except Exception as e:
        print(f"Error fetching appointments: {e}")
        return jsonify({'error': str(e)}), 500



@app.route('/api/appointments', methods=['POST'])
def book_appointment():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        doctor_id = data.get('doctor_id')
        date = data.get('date')
        time = data.get('time')
        reason = data.get('reason')
        status = 'Pending'  # Default status for new appointments

        if not all([patient_id, doctor_id, date, time, reason]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Use the lock for all database operations
        with db_lock:
            conn = get_db_connection()
            patient = conn.execute('SELECT name, contact_info FROM patients WHERE id = ?', (patient_id,)).fetchone()
            doctor = conn.execute('SELECT name FROM doctors WHERE id = ?', (doctor_id,)).fetchone()

        if not patient or not doctor:
            conn.close()
            return jsonify({'error': 'Patient or doctor not found'}), 404


         # Check for existing appointment with the same details
        existing = conn.execute('SELECT id FROM appointments WHERE patient_id = ? AND doctor_id = ? AND date = ? AND time = ?',
                               (patient_id, doctor_id, date, time)).fetchone()
        if existing:
            conn.close()
            return jsonify({'error': 'An appointment with the same details already exists'}), 409

        conn.execute('''
            INSERT INTO appointments (patient_id, patient_name, doctor_id, doctor_name, date, time, reason, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (patient_id, patient['name'], doctor_id, doctor['name'], date, time, reason, status))
        conn.commit()

        # Emit SocketIO event for real-time updates
        socketio.emit('new_appointment', {
            'message': f"New appointment booked for {patient['name']} with {doctor['name']} on {date} at {time}"
        })

        # Notify patient via WhatsApp
       # Attempt to send WhatsApp notification, but don't fail if it errors
        whatsapp_message = f"Your appointment with {doctor['name']} on {date} at {time} has been booked."
        try:
            send_whatsapp_message(patient['contact_info'], whatsapp_message)
        except Exception as e:
            print(f"Failed to send WhatsApp message to {patient['contact_info']}: {e}")
            # Log the message in the database even if the API call fails
            conn.execute('INSERT INTO whatsapp_messages (patient_id, message, sender, timestamp, type) VALUES (?, ?, ?, ?, ?)',
                        (patient_id, whatsapp_message + " (Failed to send: Recipient not in allowed list)", 'bot', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text'))
            conn.commit()

        conn.close()
        return jsonify({'status': 'Appointment booked successfully'})
    except Exception as e:
        print(f"Error booking appointment: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    try:
        conn = get_db_connection()
        doctors = conn.execute('SELECT id, name FROM doctors').fetchall()
        conn.close()

        doctors_list = [{'id': row['id'], 'name': row['name']} for row in doctors]
        print("Doctors fetched for API:", doctors_list)
        return jsonify(doctors_list)
    except Exception as e:
        print(f"Error fetching doctors: {e}")
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

    with db_lock:
        conn = get_db_connection()
        patients = conn.execute('SELECT id, name FROM patients').fetchall()
        doctors = conn.execute('SELECT id, name FROM doctors').fetchall()

        if request.method == 'POST':
            patient_id = int(request.form['patient_id'])
            doctor_id = int(request.form['doctor_id'])
            title = request.form['title']
            date = request.form['date']
            time = request.form['time']
            notes = request.form['notes']
            status = request.form['status']

            patient = conn.execute('SELECT name, contact_info FROM patients WHERE id = ?', (patient_id,)).fetchone()
            doctor = conn.execute('SELECT name FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
            patient_name = patient['name'] if patient else 'Unknown'
            doctor_name = doctor['name'] if doctor else 'Unknown'

            # Check for existing appointment
            existing = conn.execute('SELECT id FROM appointments WHERE patient_id = ? AND doctor_id = ? AND date = ? AND time = ?',
                                   (patient_id, doctor_id, date, time)).fetchone()
            if existing:
                conn.close()
                flash('An appointment with the same details already exists')
                return render_template('add_appointment.html', patients=patients, doctors=doctors)

            try:
                conn.execute('''
                    INSERT INTO appointments (patient_id, patient_name, doctor_id, doctor_name, title, date, time, notes, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (patient_id, patient_name, doctor_id, doctor_name, title, date, time, notes, status))
                conn.commit()

                socketio.emit('appointment_scheduled', {
                    'message': f"New appointment: {title} with {patient_name} on {date} at {time}"
                })

                # Notify patient via WhatsApp
                try:
                    send_whatsapp_message(patient['contact_info'], f"Your appointment '{title}' on {date} at {time} has been booked.")
                    conn.execute('INSERT INTO whatsapp_messages (patient_id, message, sender, timestamp, type) VALUES (?, ?, ?, ?, ?)',
                                 (patient_id, f"Appointment booked: {title} on {date} at {time}", 'bot', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text'))
                    conn.commit()
                except Exception as e:
                    print(f"Failed to send WhatsApp message: {e}")

                conn.close()
                return redirect(url_for('dashboard'))
            except sqlite3.OperationalError as e:
                conn.close()
                print(f"Database error in /add_appointment: {e}")
                flash(f"Database error: {str(e)}")
                return render_template('add_appointment.html', patients=patients, doctors=doctors)

        conn.close()
    return render_template('add_appointment.html', patients=patients, doctors=doctors)

# ********** Edit Appoitment ****************
# Ensure this route is outside any try block
@app.route('/edit_appointment/<int:id>', methods=['GET', 'POST'])
def edit_appointment(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    with db_lock:
        conn = get_db_connection()
        appointment = conn.execute('SELECT * FROM appointments WHERE id = ?', (id,)).fetchone()
        patients = conn.execute('SELECT id, name FROM patients').fetchall()
        doctors = conn.execute('SELECT id, name FROM doctors').fetchall()

        if request.method == 'POST':
            patient_id = int(request.form['patient_id'])
            doctor_id = int(request.form['doctor_id'])
            title = request.form['title']
            date = request.form['date']
            time = request.form['time']
            notes = request.form['notes']
            status = request.form['status']

            patient = conn.execute('SELECT name, contact_info FROM patients WHERE id = ?', (patient_id,)).fetchone()
            doctor = conn.execute('SELECT name FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
            patient_name = patient['name'] if patient else 'Unknown'
            doctor_name = doctor['name'] if doctor else 'Unknown'

            try:
                conn.execute('''
                    UPDATE appointments SET patient_id = ?, patient_name = ?, doctor_id = ?, doctor_name = ?, title = ?, date = ?, time = ?, notes = ?, status = ?
                    WHERE id = ?
                ''', (patient_id, patient_name, doctor_id, doctor_name, title, date, time, notes, status, id))
                conn.commit()

                # Notify patient via WhatsApp
                try:
                    send_whatsapp_message(patient['contact_info'], f"Your appointment '{title}' has been updated to {date} at {time}.")
                    conn.execute('INSERT INTO whatsapp_messages (patient_id, message, sender, timestamp, type) VALUES (?, ?, ?, ?, ?)',
                                 (patient_id, f"Appointment updated: {title} on {date} at {time}", 'bot', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text'))
                    conn.commit()
                except Exception as e:
                    print(f"Failed to send WhatsApp message: {e}")

                conn.close()
                return redirect(url_for('dashboard'))
            except sqlite3.OperationalError as e:
                conn.close()
                print(f"Database error in /edit_appointment: {e}")
                flash(f"Database error: {str(e)}")
                return render_template('edit_appointment.html', appointment=appointment, patients=patients, doctors=doctors)

        conn.close()
    return render_template('edit_appointment.html', appointment=appointment, patients=patients, doctors=doctors)

@app.route('/delete_appointment/<int:id>')
def delete_appointment(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    appointment = conn.execute('SELECT patient_id, title, date, time FROM appointments WHERE id = ?', (id,)).fetchone()
    if appointment:
        patient_id = appointment['patient_id']
        patient = conn.execute('SELECT contact_info FROM patients WHERE id = ?', (patient_id,)).fetchone()
        if patient:
            send_whatsapp_message(patient['contact_info'], f"Your appointment '{appointment['title']}' on {appointment['date']} at {appointment['time']} has been canceled.")
            conn.execute('INSERT INTO whatsapp_messages (patient_id, message, sender, timestamp, type) VALUES (?, ?, ?, ?, ?)',
                         (patient_id, f"Appointment canceled: {appointment['title']} on {appointment['date']} at {appointment['time']}", 'bot', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'text'))
            conn.commit()

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


# @app.route('/api/tasks')
# def get_tasks():
#     try:
#         status = request.args.get('status', None)
#         conn = get_db_connection()
#         query = 'SELECT id, patient_id, description, status, due_date FROM tasks'
#         params = []
#         if status:
#             query += ' WHERE status = %s'
#             params.append(status)
#         tasks = conn.execute(query, params).fetchall()
#         conn.close()
#         return jsonify([dict(row) for row in tasks])
#     except Exception as e:
#         print(f"Error fetching tasks: {e}")
#         return jsonify({'error': str(e)}), 500
@app.route('/api/tasks')
def get_tasks():
    try:
        status = request.args.get('status', None)  # e.g., 'pending'
        conn = get_db_connection()
        cursor = conn.cursor()

        if 'RENDER' in os.environ and os.environ.get('RENDER') == 'true':
            if status:
                query = 'SELECT id, patient_id, description, status, due_date FROM tasks WHERE status = %s ORDER BY due_date ASC'
                cursor.execute(query, (status,))
            else:
                query = 'SELECT id, patient_id, description, status, due_date FROM tasks ORDER BY due_date ASC'
                cursor.execute(query)
        else:
            if status:
                query = 'SELECT id, patient_id, description, status, due_date FROM tasks WHERE status = ? ORDER BY due_date ASC'
                cursor.execute(query, (status,))
            else:
                query = 'SELECT id, patient_id, description, status, due_date FROM tasks ORDER BY due_date ASC'
                cursor.execute(query)

        tasks = cursor.fetchall()

        task_list = [
            {
                'id': task['id'],
                'patient_id': task['patient_id'],
                'description': task['description'],
                'status': task['status'],
                'due_date': task['due_date']
            } for task in tasks
        ]

        cursor.close()
        conn.close()
        return jsonify(task_list)
    except (psycopg2.Error, sqlite3.Error) as e:
        print(f"Database error in /api/tasks: {e}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        print(f"Unexpected error in /api/tasks: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/patient_notes/<int:patient_id>')
def get_patient_notes(patient_id):
    try:
        conn = get_db_connection()
        notes = conn.execute('SELECT note, created_at FROM patient_notes WHERE patient_id = ?', (patient_id,)).fetchall()
        conn.close()
        print(f"Fetched {len(notes)} notes for patient {patient_id}")
        return jsonify([{'note': row['note'], 'date': row['created_at']} for row in notes])
    except sqlite3.OperationalError as e:
        print(f"Database error in /api/patient_notes for patient {patient_id}: {e}")
        return jsonify({'error': f"Database error: {str(e)}"}), 500
    except Exception as e:
        print(f"Unexpected error in /api/patient_notes for patient {patient_id}: {e}")
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




# Simple AI for symptom summarization (placeholder; replace with actual LLM integration)
def summarize_symptoms_ai(text):
    # Placeholder logic for symptom summarization
    keywords = {
        "fever": "Possible infection or inflammation",
        "cough": "Respiratory issue, possibly a cold or flu",
        "pain": "May require further investigation",
        "chest pain": "Critical: Possible cardiac issue",
        "headache": "Possible migraine or stress-related issue"
    }
    summary = "Symptoms: "
    triage = "Low"
    for keyword, description in keywords.items():
        if keyword.lower() in text.lower():
            summary += f"{description}, "
            if "Critical" in description:
                triage = "High"
            elif triage != "High":
                triage = "Medium"
    if summary == "Symptoms: ":
        summary = "No significant symptoms detected."
    return {"summary": summary.strip(", "), "triage": triage}

# Route to render WhatsApp tab
# @app.route('/whatsapp_tab')
# def whatsapp_tab():
#     if 'user_id' not in session:
#         return redirect(url_for('login'))
#     conn = get_db_connection()
#     patients = conn.execute('SELECT id, name, whatsapp_number FROM patients').fetchall()
#     conn.close()
#     return render_template('whatsapp_tab.html', patients=patients)
# @app.route('/whatsapp_tab')
# def whatsapp_tab():
#     if 'user_id' not in session:
#         print("User not logged in, redirecting to login")
#         return redirect(url_for('login'))
#     try:
#         conn = get_db_connection()
#         patients = conn.execute('SELECT id, name, whatsapp_number FROM patients').fetchall()
#         print(f"Fetched {len(patients)} patients")
#         patients_with_messages = []
#         for patient in patients:
#             message_count = conn.execute(
#                 'SELECT COUNT(*) FROM whatsapp_conversations WHERE patient_id = ? AND sender = "patient"',
#                 (patient['id'],)
#             ).fetchone()[0]
#             print(f"Patient {patient['id']} ({patient['name']}): {message_count} messages")
#             patients_with_messages.append({
#                 'id': patient['id'],
#                 'name': patient['name'],
#                 'whatsapp_number': patient['whatsapp_number'],
#                 'message_count': message_count
#             })
#         conn.close()
#         print("Rendering whatsapp_tab.html")
#         return render_template('whatsapp_tab.html', patients=patients_with_messages)
#     except Exception as e:
#         print(f"Error rendering WhatsApp tab: {e}")
#         return jsonify({'error': str(e)}), 500


# def get_registered_numbers():
#     headers = {
#         'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
#         'Content-Type': 'application/json'
#     }
#     response = requests.get(f'https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/phone_numbers', headers=headers)
#     if response.status_code == 200:
#         data = response.json()
#         return [phone['verified_name'] for phone in data.get('data', []) if 'verified_name' in phone]
#     print(f"Error fetching registered numbers: {response.text}")
#     return ['+919989978547']  # Fallback









@app.route('/whatsapp_tab')
def whatsapp_tab():
    if 'user_id' not in session:
        print("User not logged in, redirecting to login")
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        patients = conn.execute('SELECT id, name, whatsapp_number FROM patients').fetchall()
        print(f"Fetched {len(patients)} patients")
        patients_with_messages = []
        # Placeholder: Replace with actual API call to fetch registered numbers
        registered_numbers = get_registered_numbers()
        # ['+919989978547']  # Fetch from WhatsApp API or configuration
        for patient in patients:
            message_count = conn.execute(
                'SELECT COUNT(*) FROM whatsapp_conversations WHERE patient_id = ? AND sender = "patient"',
                (patient['id'],)
            ).fetchone()[0]
            print(f"Patient {patient['id']} ({patient['name']}): {message_count} messages")
            patients_with_messages.append({
                'id': patient['id'],
                'name': patient['name'],
                'whatsapp_number': patient['whatsapp_number'],
                'message_count': message_count,
                'is_registered': patient['whatsapp_number'] in registered_numbers if patient['whatsapp_number'] else False
            })
        conn.close()
        print("Rendering whatsapp_tab.html")
        return render_template('whatsapp_tab.html', patients=patients_with_messages)
    except Exception as e:
        print(f"Error rendering WhatsApp tab: {e}")
        return jsonify({'error': str(e)}), 500


# Webhook to receive WhatsApp messages
@app.route('/whatsapp/webhook', methods=['GET', 'POST'])
def whatsapp_webhook():
    if request.method == 'GET':
        verify_token = "mySecretToken"
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        if mode == 'subscribe' and token == verify_token:
            return challenge, 200
        return jsonify({'error': 'Verification failed'}), 403
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data received'}), 400

        # Extract message details
        message = data['entry'][0]['changes'][0]['value']['messages'][0]
        sender = message['from']  # Patient's WhatsApp number
        text = message['text']['body'] if message['type'] == 'text' else ''
        message_type = message['type']

        # Find patient by WhatsApp number
        conn = get_db_connection()
        cursor = conn.cursor()
        patient = cursor.execute('SELECT id FROM patients WHERE whatsapp_number = ?', (sender,)).fetchone()
        if not patient:
            conn.close()
            send_whatsapp_message(sender, "Please register with the clinic to use this service.")
            return jsonify({'status': 'Patient not found'}), 404

        patient_id = patient['id']
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Save message to database
        cursor.execute('INSERT INTO whatsapp_conversations (patient_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
                      (patient_id, text, 'patient', timestamp, 'text'))
        conn.commit()

        # Emit new message event for real-time update
        socketio.emit('new_message', {'patient_id': patient_id, 'message': text, 'sender': 'patient', 'timestamp': timestamp})

        # Analyze reply for urgent symptoms
        urgent_keywords = ['chest pain', 'severe', 'emergency', 'urgent']
        is_urgent = any(keyword in text.lower() for keyword in urgent_keywords)

        # Process message based on content
        response_message = None
        response_type = 'text'

        if is_urgent:
            socketio.emit('emergency_alert', {
                'patient_id': patient_id,
                'message': f"Urgent: Patient {patient_id} reported - {text}"
            })
            response_message = "This is an urgent message. The doctor has been notified and will contact you shortly."


        # Handle FAQs
        cursor.execute('SELECT answer FROM whatsapp_faq WHERE LOWER(question) LIKE ?', (f'%{text.lower()}%',))
        faq = cursor.fetchone()
        if faq:
            response_message = faq['answer']
            response_type = 'faq'

        # Handle appointment booking
        elif 'book appointment' in text.lower():
            slots_response = requests.get(f'http://localhost:5000/suggest_appointment/{patient_id}')
            slots = slots_response.json().get('suggested_slots', [])
            if slots:
                response_message = "Available slots:\n" + "\n".join(slots[:3]) + "\nReply with the slot number (1-3) to book (e.g., '1')."
                response_type = 'booking'
            else:
                response_message = "No available slots. Please try again later."

        # Confirm booking based on slot selection
        elif text.lower() in ['1', '2', '3'] and 'booking' in [msg['message_type'] for msg in cursor.execute('SELECT message_type FROM whatsapp_conversations WHERE patient_id = ? ORDER BY timestamp DESC LIMIT 1', (patient_id,)).fetchall()]:
            slots_response = requests.get(f'http://localhost:5000/suggest_appointment/{patient_id}')
            slots = slots_response.json().get('suggested_slots', [])
            slot_index = int(text) - 1
            if 0 <= slot_index < len(slots):
                selected_slot = slots[slot_index]
                date, time = selected_slot.split(' ')
                patient = cursor.execute('SELECT name, whatsapp_number FROM patients WHERE id = ?', (patient_id,)).fetchone()
                doctor_id = session.get('user_id', 1)  # Default to doctor ID 1 if session unavailable
                doctor = cursor.execute('SELECT name FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
                if doctor:
                    cursor.execute('INSERT INTO appointments (patient_id, patient_name, doctor_id, doctor_name, date, time, reason, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                  (patient_id, patient['name'], doctor_id, doctor['name'], date, time, 'WhatsApp Booking', 'Upcoming'))
                    conn.commit()
                    response_message = f"Appointment booked for {date} at {time} with {doctor['name']}."
                    response_type = 'confirmation'
                else:
                    response_message = "Error: Doctor not found."
            else:
                response_message = "Invalid slot number. Please reply with a number between 1 and 3."

        # Handle reminders
        elif 'reminder' in text.lower():
            cursor.execute('SELECT medications FROM patients WHERE id = ?', (patient_id,))
            patient = cursor.fetchone()
            if patient and patient['medications']:
                reminder_message = f"Reminder: Take your {patient['medications']} today."
                response_message = reminder_message
                response_type = 'reminder'
            else:
                response_message = "No medications found to set a reminder for."

        # Handle symptoms or emergencies
        elif is_urgent or any(keyword in text.lower() for keyword in ['fever', 'cough', 'pain', 'headache']):
            analysis = summarize_symptoms_ai(text)
            response_message = f"AI Analysis: {analysis['summary']}\nTriage: {analysis['triage']}"
            response_type = 'summary'
            if analysis['triage'] == 'High' or is_urgent:
                socketio.emit('emergency_alert', {
                    'patient_id': patient_id,
                    'message': f"Emergency: {text} (Triage: {analysis['triage']})"
                })
                response_message += "\nThis is an urgent message. The doctor has been notified."

        # Default response
        else:
            response_message = "Your message has been forwarded to the doctor. You'll hear back soon."

        # Save bot response
        cursor.execute('INSERT INTO whatsapp_conversations (patient_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
                      (patient_id, response_message, 'bot', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), response_type))
        conn.commit()
        cursor.close()
        conn.close()

        # Send response via WhatsApp API
        send_whatsapp_message(sender, response_message)
        return jsonify({'status': 'Message processed'}), 200

    except Exception as e:
        print(f"Error in webhook: {e}")
        return jsonify({'error': str(e)}), 500
# Function to send a message via WhatsApp API
# Function to send a message via WhatsApp API
# def send_whatsapp_message(phone_number, message):
#     headers = {
#         'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
#         'Content-Type': 'application/json'
#     }
#     payload = {
#         'messaging_product': 'whatsapp',
#         'to': phone_number,
#         'type': 'text',
#         'text': {'body': message}
#     }
#     response = requests.post(f'{WHATSAPP_API_URL}{WHATSAPP_PHONE_NUMBER_ID}/messages', json=payload, headers=headers)
#     if response.status_code != 200:
#         print(f"Error sending WhatsApp message: {response.text}")
def send_whatsapp_message(phone_number, message):
    headers = {
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    payload = {
        'messaging_product': 'whatsapp',
        'to': phone_number,
        'type': 'text',
        'text': {'body': message}
    }
    response = requests.post(f'{WHATSAPP_API_URL}{WHATSAPP_PHONE_NUMBER_ID}/messages', json=payload, headers=headers)
    print(f"WhatsApp API response: Status={response.status_code}, Body={response.text}")
    if response.status_code != 200:
        error_message = f"Error sending WhatsApp message: {response.text}"
        print(error_message)
        raise Exception(error_message)
    print(f"WhatsApp message sent to {phone_number}: {message}")
    return response.json()



def send_whatsapp_message(phone_number, message, use_template=False, template_name=None, template_params=None):
    headers = {
        'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
        'Content-Type': 'application/json'
    }
    if use_template:
        payload = {
            'messaging_product': 'whatsapp',
            'to': phone_number,
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {'code': 'en_US'},
                'components': [
                    {
                        'type': 'body',
                        'parameters': [{'type': 'text', 'text': param} for param in template_params]
                    }
                ]
            }
        }
    else:
        payload = {
            'messaging_product': 'whatsapp',
            'to': phone_number,
            'type': 'text',
            'text': {'body': message}
        }
    response = requests.post(f'{WHATSAPP_API_URL}{WHATSAPP_PHONE_NUMBER_ID}/messages', json=payload, headers=headers)
    print(f"WhatsApp API response: Status={response.status_code}, Body={response.text}")
    if response.status_code != 200:
        error_message = f"Error sending WhatsApp message: {response.text}"
        print(error_message)
        raise Exception(error_message)
    print(f"WhatsApp message sent to {phone_number}: {message}")
    return response.json()


# Route to get WhatsApp conversation for a patient
@app.route('/whatsapp/conversation/<int:patient_id>')
def get_whatsapp_conversation(patient_id):
    try:
        conn = get_db_connection()
        messages = conn.execute('SELECT message, sender, timestamp, message_type FROM whatsapp_conversations WHERE patient_id = ? ORDER BY timestamp ASC', (patient_id,)).fetchall()
        conn.close()
        return jsonify([dict(msg) for msg in messages])
    except Exception as e:
        print(f"Error fetching WhatsApp conversation: {e}")
        return jsonify({'error': str(e)}), 500





# Route to send a message from the dashboard
# Route to send a message from the dashboard
# @app.route('/whatsapp/send_message', methods=['POST'])
# def send_whatsapp_message_route():
#     try:
#         data = request.get_json()
#         patient_id = data.get('patient_id')
#         message = data.get('message')

#         conn = get_db_connection()
#         patient = conn.execute('SELECT whatsapp_number FROM patients WHERE id = ?', (patient_id,)).fetchone()
#         if not patient or not patient['whatsapp_number']:
#             conn.close()
#             return jsonify({'error': 'Patient or WhatsApp number not found'}), 404

#         timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#         conn.execute('INSERT INTO whatsapp_conversations (patient_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
#                     (patient_id, message, 'doctor', timestamp, 'text'))
#         conn.commit()
#         conn.close()

#         send_whatsapp_message(patient['whatsapp_number'], message)
#         return jsonify({'status': 'Message sent'})
#     except Exception as e:
#         print(f"Error sending WhatsApp message: {e}")
#         return jsonify({'error': str(e)}), 500

@app.route('/whatsapp/send_message', methods=['POST'])
def send_whatsapp_message_route():
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        message = data.get('message')
        if not patient_id or not message:
            return jsonify({'error': 'Patient ID and message are required'}), 400
        
        conn = get_db_connection()
        patient = conn.execute('SELECT whatsapp_number FROM patients WHERE id = ?', (patient_id,)).fetchone()
        if not patient or not patient['whatsapp_number']:
            conn.close()
            return jsonify({'error': 'Patient or WhatsApp number not found'}), 404
        
        # Skip opt-in check in test environment
        if not app.config['TESTING']:
            message_count = conn.execute(
                'SELECT COUNT(*) FROM whatsapp_conversations WHERE patient_id = ? AND sender = "patient"',
                (patient_id,)
            ).fetchone()[0]
            if message_count == 0:
                conn.close()
                return jsonify({'error': 'Patient has not opted-in to receive messages'}), 403
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('INSERT INTO whatsapp_conversations (patient_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
                    (patient_id, message, 'doctor', timestamp, 'text'))
        conn.commit()
        conn.close()

        try:
            response = send_whatsapp_message(patient['whatsapp_number'], message)
            print(f"WhatsApp send response: {response}")
            return jsonify({'status': 'Message sent'})
        except Exception as e:
            if "Recipient phone number not in allowed list" in str(e):
                return jsonify({'error': 'Recipient phone number is not registered with the WhatsApp Business API'}), 403
            raise e  # Re-raise other exceptions for debugging
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")
        return jsonify({'error': 'Internal server error: ' + str(e)}), 500

# Route to summarize symptoms
# @app.route('/whatsapp/summarize_symptoms', methods=['POST'])
# def summarize_symptoms_route():
#     if 'user_id' not in session:
#         return jsonify({'error': 'Unauthorized'}), 401
#     try:
#         data = request.get_json()
#         patient_id = data.get('patient_id')

#         conn = get_db_connection()
#         messages = conn.execute('SELECT message FROM whatsapp_conversations WHERE patient_id = ? AND sender = "patient" ORDER BY timestamp DESC LIMIT 5', (patient_id,)).fetchall()
#         if not messages:
#             conn.close()
#             return jsonify({'error': 'No recent patient messages found'}), 404

#         combined_text = " ".join([msg['message'] for msg in messages])
#         analysis = summarize_symptoms_ai(combined_text)

#         timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#         conn.execute('INSERT INTO whatsapp_conversations (patient_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
#                     (patient_id, analysis['summary'], 'bot', timestamp, 'summary'))
#         conn.commit()
#         conn.close()

#         return jsonify({'summary': analysis['summary'], 'triage': analysis['triage']})
#     except Exception as e:
#         print(f"Error summarizing symptoms: {e}")
#         return jsonify({'error': str(e)}), 500


@app.route('/whatsapp/summarize_symptoms', methods=['POST'])
def summarize_symptoms_route():
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        print(f"Received summarize_symptoms request for patient_id: {patient_id}")

        conn = get_db_connection()
        messages = conn.execute('SELECT message FROM whatsapp_conversations WHERE patient_id = ? AND sender = "patient" ORDER BY timestamp DESC LIMIT 5', (patient_id,)).fetchall()
        print(f"Found {len(messages)} messages for patient_id: {patient_id}")
        if not messages:
            conn.close()
            print(f"No messages found for patient_id: {patient_id}")
            return jsonify({'summary': 'No recent patient messages available to summarize.', 'triage': 'None'}), 200

        combined_text = " ".join([msg['message'] for msg in messages])
        print(f"Combined messages: {combined_text}")
        analysis = summarize_symptoms_ai(combined_text)

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('INSERT INTO whatsapp_conversations (patient_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
                    (patient_id, analysis['summary'], 'bot', timestamp, 'summary'))
        conn.commit()
        conn.close()

        print(f"Summary for patient_id {patient_id}: {analysis}")
        return jsonify({'summary': analysis['summary'], 'triage': analysis['triage']}), 200
    except Exception as e:
        print(f"Error summarizing symptoms for patient_id {patient_id}: {e}")
        return jsonify({'error': str(e)}), 500



# Route to send test results
@app.route('/whatsapp/send_test_result', methods=['POST'])
def send_test_result():
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')

        with db_lock:
            conn = get_db_connection()
            patient = conn.execute('SELECT whatsapp_number FROM patients WHERE id = ?', (patient_id,)).fetchone()
        if not patient or not patient['whatsapp_number']:
            conn.close()
            return jsonify({'error': 'Patient or WhatsApp number not found'}), 404

        # Placeholder for test result (replace with actual logic)
        result_link = "https://example.com/test_result.pdf"  # Replace with actual secure link
        message = f"Your test result is ready. View it here: {result_link}"

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('INSERT INTO whatsapp_conversations (patient_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
                    (patient_id, message, 'bot', timestamp, 'result'))
        conn.commit()
        conn.close()

        send_whatsapp_message(patient['whatsapp_number'], message)
        return jsonify({'status': 'Test result sent'})
    except Exception as e:
        print(f"Error sending test result: {e}")
        return jsonify({'error': str(e)}), 500

# Route to schedule reminders
@app.route('/whatsapp/schedule_reminder', methods=['POST'])
def schedule_reminder():
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')

        with db_lock:
            conn = get_db_connection()
            patient = conn.execute('SELECT whatsapp_number, medications FROM patients WHERE id = ?', (patient_id,)).fetchone()
        if not patient or not patient['whatsapp_number']:
            conn.close()
            return jsonify({'error': 'Patient or WhatsApp number not found'}), 404

        # Example reminder (replace with actual scheduling logic)
        reminder_message = f"Reminder: Take your {patient['medications'] or 'medication'} at 10 AM tomorrow."

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('INSERT INTO whatsapp_conversations (patient_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
                    (patient_id, reminder_message, 'bot', timestamp, 'reminder'))
        conn.commit()
        conn.close()

        send_whatsapp_message(patient['whatsapp_number'], reminder_message)
        return jsonify({'status': 'Reminder scheduled'})
    except Exception as e:
        print(f"Error scheduling reminder: {e}")
        return jsonify({'error': str(e)}), 500


def get_registered_numbers():
    global REGISTERED_NUMBERS_CACHE
    # Check if cache exists and is still valid
    if REGISTERED_NUMBERS_CACHE is not None:
        print("Using cached registered numbers")
        return REGISTERED_NUMBERS_CACHE

    try:
        headers = {
            'Authorization': f'Bearer {WHATSAPP_ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        response = requests.get(f'https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/phone_numbers', headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Extract phone numbers from the response
            registered_numbers = [phone['wa_id'] for phone in data.get('data', []) if 'wa_id' in phone]
            print(f"Fetched registered numbers: {registered_numbers}")
            REGISTERED_NUMBERS_CACHE = registered_numbers
            return registered_numbers
        else:
            print(f"Error fetching registered numbers: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"Exception while fetching registered numbers: {e}")
        return []




# Initialize doctors table if it doesn't exist
# def init_doctors_table():
#     conn = get_db_connection()
#     conn.execute('''
#         CREATE TABLE IF NOT EXISTS doctors (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             name TEXT NOT NULL
#         )
#     ''')
#     # Insert sample doctors if table is empty
#     doctors = conn.execute('SELECT COUNT(*) FROM doctors').fetchone()[0]
#     if doctors == 0:
#         sample_doctors = [
#             ('Dr. John Smith',),
#             ('Dr. Emily Johnson',),
#             ('Dr. Michael Brown',)
#         ]
#         conn.executemany('INSERT INTO doctors (name) VALUES (?)', sample_doctors)
#         conn.commit()
#     conn.close()


# Add WhatsApp-related tables and columns
def init_whatsapp_tables():
    conn = get_db_connection()

    # Check if whatsapp_number column already exists in patients table
    cursor = conn.execute("PRAGMA table_info(patients)")
    columns = [row[1] for row in cursor.fetchall()]  # Get list of column names
    if 'whatsapp_number' not in columns:
        try:
            conn.execute('''
                ALTER TABLE patients ADD COLUMN whatsapp_number TEXT
            ''')
        except sqlite3.OperationalError as e:
            print(f"Error adding whatsapp_number column: {e}")

    # Add message_type column to chatbot_conversations if missing (for SQLite)
    if 'RENDER' not in os.environ:
        cursor = conn.execute("PRAGMA table_info(chatbot_conversations)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'message_type' not in columns:
            try:
                conn.execute('ALTER TABLE chatbot_conversations ADD COLUMN message_type TEXT')
                conn.execute("UPDATE chatbot_conversations SET message_type = 'text' WHERE message_type IS NULL")
            except sqlite3.OperationalError as e:
                print(f"Error adding message_type column to chatbot_conversations: {e}")

    conn.commit()
    conn.close()


# Call initialization functions on startup
# init_doctors_table()
init_whatsapp_tables()





def get_doctor_availability(doctor_id, start_date, days=7):
    conn = get_db_connection()
    # Fetch existing appointments for the doctor
    appointments = conn.execute('SELECT date, time FROM appointments WHERE doctor_id = ? AND date >= ?', 
                              (doctor_id, start_date)).fetchall()
    conn.close()
    
    # Convert existing appointments to a set for quick lookup
    booked_slots = {f"{appt['date']} {appt['time']}" for appt in appointments}
    
    # Generate available slots (9 AM to 5 PM, hourly)
    available_slots = []
    for day in range(days):
        date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=day)).strftime('%Y-%m-%d')
        for hour in range(9, 17):
            slot = f"{date} {hour:02d}:00:00"
            if slot not in booked_slots:
                available_slots.append(slot)
    return available_slots



@app.route('/schedule_appointment', methods=['POST'])
def schedule_appointment():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        doctor_id = session.get('user_id')  # Assuming the logged-in user is the doctor
        
        with db_lock:
            conn = get_db_connection()
            patient = conn.execute('SELECT name, whatsapp_number, risk_level FROM patients WHERE id = ?', (patient_id,)).fetchone()
            doctor = conn.execute('SELECT name FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
        if not patient:
            conn.close()
            return jsonify({'error': 'Patient not found'}), 404
        if not doctor:
            conn.close()
            return jsonify({'error': 'Doctor not found'}), 404
        
        # Get available slots starting from tomorrow
        start_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        available_slots = get_doctor_availability(doctor_id, start_date)
        
        if not available_slots:
            conn.close()
            return jsonify({'error': 'No available slots'}), 400

        # # Prioritize based on risk level (higher risk gets earlier slots)
        # risk_level = patient['risk_level'] or 0.5
        # if risk_level > 0.7:
        #     selected_slot = available_slots[0]  # Earliest slot for high risk
        # elif risk_level > 0.5:
        #     selected_slot = available_slots[len(available_slots)//2]  # Middle slot for medium risk
        # else:
        #     selected_slot = available_slots[-1]  # Latest slot for low risk

        # Prioritize based on risk level
        risk_level = patient['risk_level'] or 0.5
        selected_slot = available_slots[0] if risk_level > 0.7 else available_slots[len(available_slots)//2] if risk_level > 0.5 else available_slots[-1]
        date, time = selected_slot.split(' ')

        # Check for existing appointment
        existing = conn.execute('SELECT id FROM appointments WHERE patient_id = ? AND doctor_id = ? AND date = ? AND time = ?',
                                (patient_id, doctor_id, date, time)).fetchone()
        if existing:
                conn.close()
                return jsonify({'error': 'Slot already booked'}), 409

        
        # date, time = selected_slot.split(' ')
        # conn.execute('INSERT INTO appointments (patient_id, patient_name, doctor_id, doctor_name, date, time, reason, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        #             (patient_id, patient['name'], doctor_id, doctor['name'], date, time, 'AI Scheduled Appointment', 'Upcoming'))
        # conn.commit()
        # conn.close()

        conn.execute('''
                INSERT INTO appointments (patient_id, patient_name, doctor_id, doctor_name, date, time, reason, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (patient_id, patient['name'], doctor_id, doctor['name'], date, time, 'AI Scheduled Appointment', 'Upcoming'))
        conn.commit()


        # Send WhatsApp confirmation
        # message = f"Your appointment with {doctor['name']} is scheduled for {date} at {time}."
        # send_whatsapp_message(patient['whatsapp_number'], message)


    #     send_whatsapp_message(patient['whatsapp_number'], f"Your appointment with {doctor['name']} is scheduled for {date} at {time}.")

    #     return jsonify({'status': 'Appointment scheduled', 'slot': selected_slot})
    # except Exception as e:
    #     print(f"Error scheduling appointment: {e}")
    #     return jsonify({'error': str(e)}), 500
    # Notify patient via WhatsApp
        try:
            send_whatsapp_message(patient['whatsapp_number'], f"Your appointment with {doctor['name']} is scheduled for {date} at {time}.")
        except Exception as e:
            print(f"Failed to send WhatsApp message: {e}")

        conn.close()

        socketio.emit('appointment_scheduled', {
            'message': f"AI-scheduled appointment for {patient['name']} with {doctor['name']} on {date} at {time}"
        })

        return jsonify({'status': 'Appointment scheduled', 'slot': selected_slot})
    except sqlite3.OperationalError as e:
        print(f"Database error in /schedule_appointment: {e}")
        return jsonify({'error': f"Database error: {str(e)}"}), 500
    except Exception as e:
        print(f"Error scheduling appointment: {e}")
        return jsonify({'error': str(e)}), 500

    
def send_daily_reminders():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        patients = cursor.execute('SELECT id, name, medications, whatsapp_number FROM patients WHERE medications IS NOT NULL').fetchall()
        for patient in patients:
            if patient['whatsapp_number']:
                reminder_message = f"Reminder: Take your {patient['medications']} today."
                try:
                    send_whatsapp_message(patient['whatsapp_number'], reminder_message)
                    cursor.execute('INSERT INTO whatsapp_conversations (patient_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
                                  (patient['id'], reminder_message, 'bot', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'reminder'))
                except Exception as e:
                    print(f"Failed to send reminder to patient {patient['id']}: {e}")
        conn.commit()
        cursor.close()
        conn.close()
        print("Daily reminders sent successfully")
    except Exception as e:
        print(f"Error sending daily reminders: {e}")

def generate_soap_notes(text):
    # Simple NLP to extract SOAP components (Subjective, Objective, Assessment, Plan)
    subjective = "Patient reports: " + text
    objective = "Vitals: HR:80, BP:120/80 (placeholder)"  # Replace with actual data in production
    assessment = "Assessment: Possible condition based on symptoms (placeholder)"
    plan = "Plan: Follow-up in 1 week, prescribe medication (placeholder)"
    
    # In production, use NLP (e.g., spaCy, BERT) to extract entities and structure notes
    keywords = {"headache": "Possible migraine", "fever": "Possible infection", "chest pain": "Cardiac evaluation needed"}
    for keyword, diag in keywords.items():
        if keyword.lower() in text.lower():
            assessment = f"Assessment: {diag}"
            plan = "Plan: Schedule diagnostic tests"
            break
    
    return {
        'subjective': subjective,
        'objective': objective,
        'assessment': assessment,
        'plan': plan
    }



@app.route('/generate_medical_notes', methods=['POST'])
def generate_medical_notes():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        audio_text = data.get('audio_text')  # In production, this would come from a speech-to-text API
        
        if not patient_id or not audio_text:
            return jsonify({'error': 'Patient ID and audio text are required'}), 400

         # Use the lock for all database operations
        with db_lock:
            conn = get_db_connection()
            patient = conn.execute('SELECT name FROM patients WHERE id = ?', (patient_id,)).fetchone()
            if not patient:
                conn.close()
                return jsonify({'error': 'Patient not found'}), 404
        
            # Generate SOAP notes
            notes = generate_soap_notes(audio_text)

            # Simplified SOAP notes generation
            notes = {
                'subjective': f"Patient reports: {audio_text}",
                'objective': "Vitals: HR:80, BP:120/80 (placeholder)",
                'assessment': "Pending further evaluation",
                'plan': "Follow-up in 1 week"
            }

            # Store notes in database
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute('INSERT INTO medical_notes (patient_id, subjective, objective, assessment, plan, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                        (patient_id, notes['subjective'], notes['objective'], notes['assessment'], notes['plan'], timestamp))
            conn.commit()
            conn.close()

        return jsonify({'status': 'Notes generated successfully', 'notes': notes})
    except sqlite3.OperationalError as e:
        print(f"Database error in /generate_medical_notes: {e}")
        return jsonify({'error': f"Database error: {str(e)}"}), 500
    except Exception as e:
        print(f"Error generating medical notes: {e}")
        return jsonify({'error': str(e)}), 500




@app.route('/medical_notes/<int:patient_id>')
def get_medical_notes(patient_id):
    try:
        conn = get_db_connection()
        notes = conn.execute('SELECT * FROM medical_notes WHERE patient_id = ? ORDER BY created_at DESC', (patient_id,)).fetchall()
        conn.close()
        return jsonify([dict(note) for note in notes])
    except Exception as e:
        print(f"Error fetching medical notes: {e}")
        return jsonify({'error': str(e)}), 500    



def process_billing_data(patient_id, visit_cost):
    # Simulate insurance claim and embezzlement detection
    insurance_coverage = 0.8 * visit_cost  # 80% coverage (placeholder)
    amount_due = visit_cost - insurance_coverage
    
    # Simple embezzlement detection: flag if amount_due is negative
    if amount_due < 0:
        return {'status': 'Suspicious', 'amount_due': amount_due, 'alert': 'Possible embezzlement detected: Negative balance'}
    
    return {'status': 'Processed', 'amount_due': amount_due, 'alert': None}

@app.route('/billing', methods=['POST'])
def billing():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        visit_cost = data.get('visit_cost', 100.0)  # Default cost for testing
        
        if not patient_id:
            return jsonify({'error': 'Patient ID is required'}), 400

        conn = get_db_connection()
        patient = conn.execute('SELECT name, whatsapp_number FROM patients WHERE id = ?', (patient_id,)).fetchone()
        if not patient:
            conn.close()
            return jsonify({'error': 'Patient not found'}), 404

        # Process billing
        billing_result = process_billing_data(patient_id, visit_cost)
        
        # Store billing data
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('INSERT INTO billing (patient_id, visit_cost, amount_due, status, alert, created_at) VALUES (?, ?, ?, ?, ?, ?)',
                    (patient_id, visit_cost, billing_result['amount_due'], billing_result['status'], billing_result['alert'], timestamp))
        conn.commit()
        conn.close()

        # Send WhatsApp notification
        message = f"Billing processed for your visit. Amount due: ${billing_result['amount_due']:.2f}."
        if billing_result['alert']:
            message += f" Alert: {billing_result['alert']}"
        send_whatsapp_message(patient['whatsapp_number'], message)

        return jsonify({'status': 'Billing processed', 'result': billing_result})
    except Exception as e:
        print(f"Error processing billing: {e}")
        return jsonify({'error': str(e)}), 500





@app.route('/follow_up', methods=['POST'])
def follow_up():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        
        if not patient_id:
            return jsonify({'error': 'Patient ID is required'}), 400

        conn = get_db_connection()
        patient = conn.execute('SELECT name, whatsapp_number, risk_level, medications FROM patients WHERE id = ?', (patient_id,)).fetchone()
        if not patient:
            conn.close()
            return jsonify({'error': 'Patient not found'}), 404

        # Determine follow-up message based on risk level and medications
        message = f"Hi {patient['name']}, how are you feeling today?"
        if patient['medications']:
            message += f" Have you taken your {patient['medications']}?"
        if patient['risk_level'] > 0.7:
            message += " Please report any new symptoms immediately."

        # Send WhatsApp message
        send_whatsapp_message(patient['whatsapp_number'], message)

        # Log the follow-up message
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('INSERT INTO whatsapp_conversations (patient_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
                    (patient_id, message, 'bot', timestamp, 'follow-up'))
        conn.commit()
        conn.close()

        return jsonify({'status': 'Follow-up message sent'})
    except Exception as e:
        print(f"Error sending follow-up message: {e}")
        return jsonify({'error': str(e)}), 500

# **********Diagnosis based on patient data***********************
def diagnose_patient(patient_data):
    # Simple diagnosis based on patient data (in production, use ML models like BERT)
    symptoms = patient_data.get('symptoms', '').lower()
    medical_history = patient_data.get('medical_history', '').lower()
    
    diagnoses = []
    if 'headache' in symptoms:
        diagnoses.append({'diagnosis': 'Possible Migraine', 'confidence': 0.8})
    if 'fever' in symptoms:
        diagnoses.append({'diagnosis': 'Possible Infection', 'confidence': 0.7})
    if 'chest pain' in symptoms:
        diagnoses.append({'diagnosis': 'Cardiac Issue', 'confidence': 0.9})
    if 'diabetes' in medical_history:
        diagnoses.append({'diagnosis': 'Monitor Blood Sugar Levels', 'confidence': 0.85})
    
    return diagnoses if diagnoses else [{'diagnosis': 'No diagnosis available', 'confidence': 0.0}]

@app.route('/diagnose', methods=['POST'])
def diagnose():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        patient_id = data.get('patient_id')
        
        if not patient_id:
            return jsonify({'error': 'Patient ID is required'}), 400

        conn = get_db_connection()
        patient = conn.execute('SELECT medical_history FROM patients WHERE id = ?', (patient_id,)).fetchone()
        messages = conn.execute('SELECT message FROM whatsapp_conversations WHERE patient_id = ? AND sender = "patient" ORDER BY timestamp DESC LIMIT 5', (patient_id,)).fetchall()
        

        if not patient:
            conn.close()
            return jsonify({'error': 'Patient not found'}), 404

        # Combine patient data
        patient_data = {
            'symptoms': " ".join([msg['message'] for msg in messages]) if messages else "No recent symptoms reported",
            'medical_history': patient['medical_history'] or 'No medical history available'
        }

        # Generate diagnoses
        diagnoses = diagnose_patient(patient_data)
        conn.close()
        return jsonify({'status': 'Diagnosis generated', 'diagnoses': diagnoses})
    except Exception as e:
        print(f"Error generating diagnosis: {e}")
        return jsonify({'error': str(e)}), 500



@app.route('/medical_notes', endpoint='medical_notes_endpoint')
def medical_notes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    patients = conn.execute('SELECT id, name FROM patients').fetchall()
    conn.close()
    return render_template('medical_notes.html', patients=patients)

@app.route('/diagnostics', endpoint='diagnostics_endpoint')
def diagnostics():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    patients = conn.execute('SELECT id, name FROM patients').fetchall()
    conn.close()
    return render_template('diagnostics.html', patients=patients)


@app.route('/debug/routes')
def debug_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': list(rule.methods),
            'rule': str(rule)
        })
    print("Registered routes:", routes)
    return jsonify(routes)



@app.route('/tasks')
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        status = request.args.get('status', None)  # e.g., 'pending'
        conn = get_db_connection()
        cursor = conn.cursor()

        # Use a single query with conditional parameter passing
        # SQLite uses ? placeholders, PostgreSQL uses %s
        if 'RENDER' in os.environ and os.environ.get('RENDER') == 'true':
            if status:
                query = 'SELECT id, patient_id, description, status, due_date FROM tasks WHERE status = %s ORDER BY due_date ASC'
                cursor.execute(query, (status,))
            else:
                query = 'SELECT id, patient_id, description, status, due_date FROM tasks ORDER BY due_date ASC'
                cursor.execute(query)
        else:
            if status:
                query = 'SELECT id, patient_id, description, status, due_date FROM tasks WHERE status = ? ORDER BY due_date ASC'
                cursor.execute(query, (status,))
            else:
                query = 'SELECT id, patient_id, description, status, due_date FROM tasks ORDER BY due_date ASC'
                cursor.execute(query)

        tasks = cursor.fetchall()

        # Convert to list of dictionaries for template rendering
        task_list = [
            {
                'id': task['id'],
                'patient_id': task['patient_id'],
                'description': task['description'],
                'status': task['status'],
                'due_date': task['due_date']
            } for task in tasks
        ]

        cursor.close()
        conn.close()
        return render_template('tasks.html', tasks=task_list)
    except (psycopg2.Error, sqlite3.Error) as e:
        print(f"Database error in /tasks: {e}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        print(f"Unexpected error in /tasks: {e}")
        return jsonify({'error': str(e)}), 500



@app.route('/patients')
def patients():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        patients = conn.execute('SELECT id, name, whatsapp_number FROM patients ORDER BY name').fetchall()
        conn.close()
        return render_template('patients.html', patients=patients)
    except Exception as e:
        print(f"Error rendering patients page: {e}")
        return jsonify({'error': str(e)}), 500



# Route to render the Dynamic Chatbot page
@app.route('/dynamic_chatbot')
def dynamic_chatbot():
    if 'user_id' not in session:
        print("User not logged in, redirecting to login")
        return redirect(url_for('login'))
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        chat_history = cursor.execute('SELECT message, sender FROM chatbot_conversations WHERE user_id = ? ORDER BY timestamp ASC',
                                    (session['user_id'],)).fetchall()
        cursor.close()
        conn.close()
        print("Rendering dynamic_chatbot.html")
        return render_template('dynamic_chatbot.html', chat_history=chat_history)
    except Exception as e:
        print(f"Error rendering Dynamic Chatbot page: {e}")
        return jsonify({'error': 'Failed to load Dynamic Chatbot page'}), 500



# SocketIO handler for dynamic chatbot messages
#     try:
#         message = data.get('message', '')
#         if not message:
#             emit('chat_response', {'error': 'No message provided'}, broadcast=False)
#             return

#         user_id = session.get('user_id')
#         if not user_id:
#             emit('chat_response', {'error': 'User not authenticated'}, broadcast=False)
#             return

#         conn = get_db_connection()
#         cursor = conn.cursor()

#         # Check for patient ID in the message (e.g., "My patient ID is 1")
#         patient_id = session.get('chatbot_patient_id')
#         if not patient_id:
#             match = re.match(r'.*patient ID is (\d+)', message, re.IGNORECASE)
#             if match:
#                 patient_id = int(match.group(1))
#                 session['chatbot_patient_id'] = patient_id
#                 response = f"Patient ID {patient_id} set. How can I assist you?"
#                 response_type = 'patient_id_set'
#             else:
#                 # Look for a patient associated with the user (e.g., if user_id matches a patient_id)
#                 patient = cursor.execute('SELECT id, name FROM patients WHERE id = ?', (user_id,)).fetchone()
#                 if patient:
#                     patient_id = patient['id']
#                     session['chatbot_patient_id'] = patient_id
#                     response = f"Using your patient ID {patient_id}. How can I assist you?"
#                     response_type = 'patient_id_set'
#                 else:
#                     response = "Please provide your patient ID to proceed (e.g., 'My patient ID is 1')."
#                     response_type = 'patient_id_request'
        

#         # Handle FAQs
#         elif 'book appointment' not in message.lower() and 'reminder' not in message.lower():
#             cursor.execute('SELECT answer FROM chatbot_faq WHERE LOWER(question) LIKE ?', (f'%{message.lower()}%',))
#             faq = cursor.fetchone()
#         if faq:
#             response = faq['answer']
#             response_type = 'faq'

#         # Handle appointment booking
#         elif 'book appointment' in message.lower():
#             # Check if patient ID is provided in session or message
#             patient = cursor.execute('SELECT id, name FROM patients WHERE id = (SELECT id FROM patients WHERE id = ? LIMIT 1)', (user_id,)).fetchone()
#             if not patient:
#                 response = "Please provide your patient ID to book an appointment (e.g., 'My patient ID is 1')."
#                 response_type = 'booking_request'
#             else:
#                 patient_id = patient['id']
#                 slots_response = requests.get(f'http://localhost:5000/suggest_appointment/{patient_id}')
#                 slots = slots_response.json().get('suggested_slots', [])
#                 if slots:
#                     response = "Available slots:\n" + "\n".join(slots[:3]) + "\nPlease select a slot number (1-3) to book (e.g., '1')."
#                     response_type = 'booking'
#                 else:
#                     response = "No available slots. Please try again later."
#                     response_type = 'booking'

#         # Confirm booking based on slot selection
#         elif message.lower() in ['1', '2', '3'] and 'booking' in [msg['message_type'] for msg in cursor.execute('SELECT message_type FROM chatbot_conversations WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1', (user_id,)).fetchall()]:
#             patient = cursor.execute('SELECT id, name FROM patients WHERE id = (SELECT id FROM patients WHERE id = ? LIMIT 1)', (user_id,)).fetchone()
#             if patient:
#                 patient_id = patient['id']
#                 slots_response = requests.get(f'http://localhost:5000/suggest_appointment/{patient_id}')
#                 slots = slots_response.json().get('suggested_slots', [])
#                 slot_index = int(message) - 1
#                 if 0 <= slot_index < len(slots):
#                     selected_slot = slots[slot_index]
#                     date, time = selected_slot.split(' ')
#                     doctor_id = 1  # Default doctor; adjust based on logic
#                     doctor = cursor.execute('SELECT name FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
#                     if doctor:
#                         cursor.execute('INSERT INTO appointments (patient_id, patient_name, doctor_id, doctor_name, date, time, reason, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
#                                       (patient_id, patient['name'], doctor_id, doctor['name'], date, time, 'Chatbot Booking', 'Upcoming'))
#                         conn.commit()
#                         response = f"Appointment booked for {date} at {time} with {doctor['name']}."
#                         response_type = 'confirmation'
#                     else:
#                         response = "Error: Doctor not found."
#                         response_type = 'error'
#                 else:
#                     response = "Invalid slot number. Please select a number between 1 and 3."
#                     response_type = 'booking'
#             else:
#                 response = "Please provide your patient ID to book an appointment (e.g., 'My patient ID is 1')."
#                 response_type = 'booking_request'

#         # Handle reminders
#         elif 'reminder' in message.lower():
#             patient = cursor.execute('SELECT id, name, medications FROM patients WHERE id = (SELECT id FROM patients WHERE id = ? LIMIT 1)', (user_id,)).fetchone()
#             if patient and patient['medications']:
#                 reminder_message = f"Reminder: Take your {patient['medications']} today."
#                 response = reminder_message
#                 response_type = 'reminder'
#             else:
#                 response = "No medications found to set a reminder for."
#                 response_type = 'reminder'

#         # Default to OpenAI API or placeholder response
#         else:
#             if OPENAI_API_KEY != 'your-openai-api-key':
#                 try:
#                     response = client.chat.completions.create(
#                         model="gpt-3.5-turbo",
#                         messages=[
#                             {"role": "system", "content": "You are a medical assistant chatbot for a doctor dashboard. Provide helpful responses related to patient care, scheduling, and medical advice."},
#                             {"role": "user", "content": message}
#                         ],
#                         max_tokens=150
#                     ).choices[0].message.content
#                     response_type = 'ai_response'
#                 except Exception as api_error:
#                     print(f"OpenAI API error: {api_error}")
#                     response = "Bot: Sorry, I couldn't process your request due to an API error. Please try again later."
#                     response_type = 'error'
#             else:
#                 response = f"Bot: I received your message: '{message}'. How can I assist you today?"
#                 response_type = 'placeholder'

#         # Save chat history
#         timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#         cursor.execute('INSERT INTO chatbot_conversations (user_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
#                       (user_id, message, 'user', timestamp, 'text'))
#         cursor.execute('INSERT INTO chatbot_conversations (user_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
#                       (user_id, response, 'bot', timestamp, response_type))
#         conn.commit()
#         cursor.close()
#         conn.close()

#         emit('chat_response', {'message': response}, broadcast=False)
#         print(f"Chatbot responded: {response}")
#     except Exception as e:
#         print(f"Error handling chatbot message: {e}")
#         emit('chat_response', {'error': str(e)}, broadcast=False)
# @socketio.on('send_message')
# def handle_send_message(data):
#     try:
#         message = data.get('message', '')
#         if not message:
#             emit('chat_response', {'error': 'No message provided'}, broadcast=False)
#             return

#         user_id = session.get('user_id')
#         if not user_id:
#             emit('chat_response', {'error': 'User not authenticated'}, broadcast=False)
#             return

#         conn = get_db_connection()
#         cursor = conn.cursor()

#         # Check for patient ID in the message (e.g., "My patient ID is 1")
#         patient_id = session.get('chatbot_patient_id')
#         if not patient_id:
#             match = re.match(r'.*patient ID is (\d+)', message, re.IGNORECASE)
#             if match:
#                 patient_id = int(match.group(1))
#                 session['chatbot_patient_id'] = patient_id
#                 response = f"Patient ID {patient_id} set. How can I assist you?"
#                 response_type = 'patient_id_set'
#             else:
#                 # Look for a patient associated with the user (e.g., if user_id matches a patient_id)
#                 patient = cursor.execute('SELECT id, name FROM patients WHERE id = ?', (user_id,)).fetchone()
#                 if patient:
#                     patient_id = patient['id']
#                     session['chatbot_patient_id'] = patient_id
#                     response = f"Using your patient ID {patient_id}. How can I assist you?"
#                     response_type = 'patient_id_set'
#                 else:
#                     response = "Please provide your patient ID to proceed (e.g., 'My patient ID is 1')."
#                     response_type = 'patient_id_request'

#         # Handle FAQs
#         elif 'book appointment' not in message.lower() and 'reminder' not in message.lower():
#             cursor.execute('SELECT answer FROM chatbot_faq WHERE LOWER(question) LIKE ?', (f'%{message.lower()}%',))
#             faq = cursor.fetchone()
#             if faq:
#                 response = faq['answer']
#                 response_type = 'faq'
#             else:
#                 # Default to OpenAI API or placeholder response
#                 if OPENAI_API_KEY != 'your-openai-api-key':
#                     try:
#                         response = client.chat.completions.create(
#                             model="gpt-3.5-turbo",
#                             messages=[
#                                 {"role": "system", "content": "You are a medical assistant chatbot for a doctor dashboard. Provide helpful responses related to patient care, scheduling, and medical advice."},
#                                 {"role": "user", "content": message}
#                             ],
#                             max_tokens=150
#                         ).choices[0].message.content
#                         response_type = 'ai_response'
#                     except Exception as api_error:
#                         print(f"OpenAI API error: {api_error}")
#                         response = "Bot: Sorry, I couldn't process your request due to an API error. Please try again later."
#                         response_type = 'error'
#                 else:
#                     response = f"Bot: I received your message: '{message}'. How can I assist you today?"
#                     response_type = 'placeholder'

#         # Handle appointment booking
#         elif 'book appointment' in message.lower():
#             patient = cursor.execute('SELECT id, name FROM patients WHERE id = ?', (patient_id,)).fetchone()
#             if not patient:
#                 response = "Invalid patient ID. Please provide a valid patient ID (e.g., 'My patient ID is 1')."
#                 response_type = 'error'
#                 session.pop('chatbot_patient_id', None)  # Clear invalid patient ID
#             else:
#                 slots_response = requests.get(f'http://localhost:5000/suggest_appointment/{patient_id}')
#                 slots = slots_response.json().get('suggested_slots', [])
#                 if slots:
#                     response = "Available slots:\n" + "\n".join(slots[:3]) + "\nPlease select a slot number (1-3) to book (e.g., '1')."
#                     response_type = 'booking'
#                     session['chatbot_booking_slots'] = slots  # Store slots in session for confirmation
#                 else:
#                     response = "No available slots. Please try again later."
#                     response_type = 'booking'

#         # Confirm booking based on slot selection
#         elif message.lower() in ['1', '2', '3'] and 'booking' in [msg['message_type'] for msg in cursor.execute('SELECT message_type FROM chatbot_conversations WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1', (user_id,)).fetchall()]:
#             slots = session.get('chatbot_booking_slots', [])
#             if not slots:
#                 response = "Booking session expired. Please start again by saying 'book appointment'."
#                 response_type = 'error'
#             else:
#                 slot_index = int(message) - 1
#                 if 0 <= slot_index < len(slots):
#                     selected_slot = slots[slot_index]
#                     date, time = selected_slot.split(' ')
#                     patient = cursor.execute('SELECT id, name FROM patients WHERE id = ?', (patient_id,)).fetchone()
#                     doctor_id = 1  # Default doctor; adjust based on logic
#                     doctor = cursor.execute('SELECT name FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
#                     if doctor:
#                         cursor.execute('INSERT INTO appointments (patient_id, patient_name, doctor_id, doctor_name, date, time, reason, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
#                                       (patient_id, patient['name'], doctor_id, doctor['name'], date, time, 'Chatbot Booking', 'Upcoming'))
#                         conn.commit()
#                         response = f"Appointment booked for {date} at {time} with {doctor['name']}."
#                         response_type = 'confirmation'
#                         session.pop('chatbot_booking_slots', None)  # Clear slots after booking
#                     else:
#                         response = "Error: Doctor not found."
#                         response_type = 'error'
#                 else:
#                     response = "Invalid slot number. Please select a number between 1 and 3."
#                     response_type = 'booking'

#         # Handle reminders
#         elif 'reminder' in message.lower():
#             patient = cursor.execute('SELECT id, name, medications FROM patients WHERE id = ?', (patient_id,)).fetchone()
#             if patient:
#                 if patient['medications']:
#                     reminder_message = f"Reminder: Take your {patient['medications']} today."
#                     response = reminder_message
#                     response_type = 'reminder'
#                 else:
#                     response = "No medications found to set a reminder for."
#                     response_type = 'reminder'
#             else:
#                 response = "Invalid patient ID. Please provide a valid patient ID (e.g., 'My patient ID is 1')."
#                 response_type = 'error'
#                 session.pop('chatbot_patient_id', None)  # Clear invalid patient ID

#         # Save chat history
#         timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#         cursor.execute('INSERT INTO chatbot_conversations (user_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
#                       (user_id, message, 'user', timestamp, 'text'))
#         cursor.execute('INSERT INTO chatbot_conversations (user_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
#                       (user_id, response, 'bot', timestamp, response_type))
#         conn.commit()
#         cursor.close()
#         conn.close()

#         emit('chat_response', {'message': response}, broadcast=False)
#         print(f"Chatbot responded: {response}")
#     except Exception as e:
#         print(f"Error handling chatbot message: {e}")
#         emit('chat_response', {'error': str(e)}, broadcast=False)

@socketio.on('send_message')
def handle_send_message(data):
    try:
        message = data.get('message', '')
        if not message:
            emit('chat_response', {'error': 'No message provided'}, broadcast=False)
            return

        user_id = session.get('user_id')
        if not user_id:
            emit('chat_response', {'error': 'User not authenticated'}, broadcast=False)
            return

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get patient ID from chatbot_patient_mappings
        cursor.execute('SELECT patient_id FROM chatbot_patient_mappings WHERE user_id = ?', (user_id,))
        mapping = cursor.fetchone()
        patient_id = mapping['patient_id'] if mapping else None

        # Handle patient ID change or reset
        if 'change patient id' in message.lower():
            cursor.execute('DELETE FROM chatbot_patient_mappings WHERE user_id = ?', (user_id,))
            conn.commit()
            response = "Patient ID cleared. Please provide a new patient ID (e.g., 'My patient ID is 1')."
            response_type = 'patient_id_reset'
        elif 'reset patient id' in message.lower():
            cursor.execute('DELETE FROM chatbot_patient_mappings WHERE user_id = ?', (user_id,))
            conn.commit()
            session.pop('chatbot_booking_slots', None)  # Clear any booking context
            session.pop('chatbot_doctors', None)  # Clear doctor selection context
            response = "Patient ID and booking context reset. Please provide a new patient ID (e.g., 'My patient ID is 1')."
            response_type = 'patient_id_reset'
        # Check for patient ID in the message (e.g., "My patient ID is 1")
        elif not patient_id:
            match = re.match(r'.*patient ID is (\d+)', message, re.IGNORECASE)
            if match:
                patient_id = int(match.group(1))
                cursor.execute('INSERT OR REPLACE INTO chatbot_patient_mappings (user_id, patient_id, timestamp) VALUES (?, ?, ?)',
                              (user_id, patient_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
                response = f"Patient ID {patient_id} set. How can I assist you?"
                response_type = 'patient_id_set'
            else:
                # Look for a patient associated with the user (e.g., if user_id matches a patient_id)
                patient = cursor.execute('SELECT id, name FROM patients WHERE id = ?', (user_id,)).fetchone()
                if patient:
                    patient_id = patient['id']
                    cursor.execute('INSERT OR REPLACE INTO chatbot_patient_mappings (user_id, patient_id, timestamp) VALUES (?, ?, ?)',
                                  (user_id, patient_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    conn.commit()
                    response = f"Using your patient ID {patient_id}. How can I assist you?"
                    response_type = 'patient_id_set'
                else:
                    response = "Please provide your patient ID to proceed (e.g., 'My patient ID is 1')."
                    response_type = 'patient_id_request'

        # Handle FAQs
        elif 'book appointment' not in message.lower() and 'reminder' not in message.lower():
            cursor.execute('SELECT answer FROM chatbot_faq WHERE LOWER(question) LIKE ?', (f'%{message.lower()}%',))
            faq = cursor.fetchone()
            if faq:
                response = faq['answer']
                response_type = 'faq'
            else:
                # Default to OpenAI API or placeholder response
                if OPENAI_API_KEY != 'your-openai-api-key':
                    try:
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "You are a medical assistant chatbot for a doctor dashboard. Provide helpful responses related to patient care, scheduling, and medical advice."},
                                {"role": "user", "content": message}
                            ],
                            max_tokens=150
                        ).choices[0].message.content
                        response_type = 'ai_response'
                    except Exception as api_error:
                        print(f"OpenAI API error: {api_error}")
                        response = "Bot: Sorry, I couldn't process your request due to an API error. Please try again later."
                        response_type = 'error'
                else:
                    response = f"Bot: I received your message: '{message}'. How can I assist you today?"
                    response_type = 'placeholder'

        # Handle appointment booking
        elif 'book appointment' in message.lower():
            patient = cursor.execute('SELECT id, name FROM patients WHERE id = ?', (patient_id,)).fetchone()
            if not patient:
                response = "Invalid patient ID. Please provide a valid patient ID (e.g., 'My patient ID is 1')."
                response_type = 'error'
                cursor.execute('DELETE FROM chatbot_patient_mappings WHERE user_id = ?', (user_id,))
                conn.commit()
            else:
                # Get list of doctors for selection
                doctors = cursor.execute('SELECT id, name FROM doctors').fetchall()
                if doctors:
                    response = "Please select a doctor:\n" + "\n".join([f"{i+1}. {doctor['name']}" for i, doctor in enumerate(doctors)]) + "\nReply with the doctor number (e.g., '1')."
                    response_type = 'doctor_selection'
                    session['chatbot_doctors'] = [doctor['id'] for doctor in doctors]
                else:
                    response = "No doctors available. Please try again later."
                    response_type = 'error'

        # Handle doctor selection
        elif message.lower() in [str(i) for i in range(1, 10)] and 'doctor_selection' in [msg['message_type'] for msg in cursor.execute('SELECT message_type FROM chatbot_conversations WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1', (user_id,)).fetchall()]:
            doctors = session.get('chatbot_doctors', [])
            doctor_index = int(message) - 1
            if 0 <= doctor_index < len(doctors):
                doctor_id = doctors[doctor_index]
                session['chatbot_selected_doctor'] = doctor_id
                start_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
                slots = get_doctor_availability(doctor_id, start_date)
                if slots:
                    response = "Available slots:\n" + "\n".join(slots[:3]) + "\nPlease select a slot number (1-3) to book (e.g., '1')."
                    response_type = 'booking'
                    session['chatbot_booking_slots'] = slots
                else:
                    response = "No available slots for this doctor. Please try again later."
                    response_type = 'booking'
            else:
                response = "Invalid doctor number. Please select a number from the list."
                response_type = 'doctor_selection'

        # Confirm booking based on slot selection
        elif message.lower() in ['1', '2', '3'] and 'booking' in [msg['message_type'] for msg in cursor.execute('SELECT message_type FROM chatbot_conversations WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1', (user_id,)).fetchall()]:
            slots = session.get('chatbot_booking_slots', [])
            doctor_id = session.get('chatbot_selected_doctor')
            if not slots or not doctor_id:
                response = "Booking session expired. Please start again by saying 'book appointment'."
                response_type = 'error'
            else:
                slot_index = int(message) - 1
                if 0 <= slot_index < len(slots):
                    selected_slot = slots[slot_index]
                    date, time = selected_slot.split(' ')
                    patient = cursor.execute('SELECT id, name FROM patients WHERE id = ?', (patient_id,)).fetchone()
                    doctor = cursor.execute('SELECT name FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
                    if doctor:
                        cursor.execute('INSERT INTO appointments (patient_id, patient_name, doctor_id, doctor_name, date, time, reason, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                                      (patient_id, patient['name'], doctor_id, doctor['name'], date, time, 'Chatbot Booking', 'Upcoming'))
                        conn.commit()
                        response = f"Appointment booked for {date} at {time} with {doctor['name']}."
                        response_type = 'confirmation'
                        session.pop('chatbot_booking_slots', None)
                        session.pop('chatbot_selected_doctor', None)
                        session.pop('chatbot_doctors', None)
                    else:
                        response = "Error: Doctor not found."
                        response_type = 'error'
                else:
                    response = "Invalid slot number. Please select a number between 1 and 3."
                    response_type = 'booking'

        # Handle reminders
        elif 'reminder' in message.lower():
            patient = cursor.execute('SELECT id, name, medications FROM patients WHERE id = ?', (patient_id,)).fetchone()
            if patient:
                if patient['medications']:
                    reminder_message = f"Reminder: Take your {patient['medications']} today. Daily reminders are scheduled at 9:00 AM via WhatsApp."
                    response = reminder_message
                    response_type = 'reminder'
                else:
                    response = "No medications found to set a reminder for."
                    response_type = 'reminder'
            else:
                response = "Invalid patient ID. Please provide a valid patient ID (e.g., 'My patient ID is 1')."
                response_type = 'error'
                cursor.execute('DELETE FROM chatbot_patient_mappings WHERE user_id = ?', (user_id,))
                conn.commit()

        # Save chat history
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('INSERT INTO chatbot_conversations (user_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
                      (user_id, message, 'user', timestamp, 'text'))
        cursor.execute('INSERT INTO chatbot_conversations (user_id, message, sender, timestamp, message_type) VALUES (?, ?, ?, ?, ?)',
                      (user_id, response, 'bot', timestamp, response_type))
        conn.commit()
        cursor.close()
        conn.close()

        emit('chat_response', {'message': response}, broadcast=False)
        print(f"Chatbot responded: {response}")
    except Exception as e:
        print(f"Error handling chatbot message: {e}")
        emit('chat_response', {'error': str(e)}, broadcast=False)


@socketio.on('connect')
def handle_connect():
    print("Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    print("Client disconnected")

if __name__ == '__main__':
    # socketio.run(app, debug=True)
    # Schedule daily reminders at 9:00 AM
    schedule.every().day.at("09:00").do(send_daily_reminders)

    # Start the scheduler in a separate thread
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    socketio.run(app, debug=True)
