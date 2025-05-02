import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
import os

# Suppress TensorFlow GPU and optimization warnings
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

class RiskModel:
    def __init__(self, data_path='data/patient_trends.csv'):
        self.scaler = StandardScaler()
        try:
            # Load and preprocess data
            data = pd.read_csv(data_path)
            self.features = ['age', 'heart_rate', 'bp_systolic', 'condition_severity']
            self.X = data[self.features]
            self.X_scaled = self.scaler.fit_transform(self.X)
            
            # Build a simple neural network
            self.model = Sequential([
                Dense(16, activation='relu', input_shape=(4,)),
                Dense(8, activation='relu'),
                Dense(1, activation='sigmoid')
            ])
            self.model.compile(optimizer='adam', loss='binary_crossentropy')
            # Placeholder: Train model (replace with actual training data)
            # self.model.fit(self.X_scaled, data['risk_level'], epochs=10, verbose=0)
            print("TensorFlow model initialized successfully")
        except FileNotFoundError:
            print(f"Data file {data_path} not found. Using fallback model.")
            self.model = None
        except Exception as e:
            print(f"Error initializing TensorFlow model: {e}")
            self.model = None

    def predict_risk(self, age, heart_rate, blood_pressure, condition):
        if self.model is None:
            return 0.5  # Fallback prediction
        
        try:
            # Process inputs
            bp_systolic = float(blood_pressure.split('/')[0]) if '/' in blood_pressure else 120.0
            condition_severity = {'Diabetes': 0.8, 'Hypertension': 0.6, 'None': 0.1}.get(condition, 0.5)
            features = np.array([[age, heart_rate, bp_systolic, condition_severity]])
            features_scaled = self.scaler.transform(features)
            
            # Predict risk
            risk = self.model.predict(features_scaled, verbose=0)[0][0]
            return float(risk)
        except Exception as e:
            print(f"Error predicting risk: {e}")
            return 0.5

if __name__ == "__main__":
    model = RiskModel()
    risk = model.predict_risk(50, 80, '120/80', 'Diabetes')
    print(f"Predicted risk: {risk}")