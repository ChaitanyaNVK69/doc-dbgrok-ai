// Initialize Socket.IO
const socket = io();

// Global variable to store the user's role
let userRole = null;

// Fetch patient data with AI-predicted risk levels
async function loadPatients() {
    try {
        const response = await fetch('/api/patients');
        const patients = await response.json();
        
        const tableBody = document.getElementById('patient-table-body');
        tableBody.innerHTML = '';

        patients.forEach(patient => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="p-3"><a href="#" onclick="openPatientModal('${patient.name}'); return false;" class="text-indigo-600 hover:underline">${patient.name}</a></td>
                <td class="p-3">${patient.age}</td>
                <td class="p-3">${patient.gender}</td>
                <td class="p-3">${patient.condition}</td>
                <td class="p-3">${patient.risk_level}</td>
                <td class="p-3">
                    <button onclick="analyzeHealthTrend('${patient.name}', 'Blood Pressure')" class="bg-indigo-900 text-white px-3 py-1 rounded hover:bg-indigo-700 mr-2">Health Trend</button>
                    <button onclick="suggestAppointment('${patient.name}', '${patient.risk_level}')" class="bg-indigo-900 text-white px-3 py-1 rounded hover:bg-indigo-700 mr-2">Suggest Appointment</button>
                    ${userRole === 'admin' ? `<a href="/edit-patient/${patient.name}" class="bg-green-600 text-white px-3 py-1 rounded hover:bg-green-500">Edit</a>` : ''}
                </td>
            `;
            tableBody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading patients:', error);
    }
}

// Open patient details modal
async function openPatientModal(patientName) {
    try {
        const response = await fetch(`/api/patient-details?name=${patientName}`);
        const patient = await response.json();

        document.getElementById('modal-patient-name').textContent = patient.name;
        document.getElementById('modal-patient-age').textContent = patient.age;
        document.getElementById('modal-patient-gender').textContent = patient.gender;
        document.getElementById('modal-patient-condition').textContent = patient.condition;
        document.getElementById('modal-patient-risk').textContent = patient.risk_level;
        document.getElementById('modal-patient-history').textContent = patient.medical_history || 'No history available';
        document.getElementById('modal-patient-vitals').textContent = patient.recent_vitals || 'No recent vitals available';
        document.getElementById('modal-patient-contact').textContent = patient.contact_info || 'Not provided';
        document.getElementById('modal-patient-allergies').textContent = patient.allergies || 'None';
        document.getElementById('modal-patient-medications').textContent = patient.medications || 'None';
        document.getElementById('modal-patient-last-visit').textContent = patient.last_visit_date || 'Not recorded';

        document.getElementById('patient-modal').classList.remove('hidden');
    } catch (error) {
        console.error('Error fetching patient details:', error);
    }
}

// Close patient details modal
function closeModal() {
    document.getElementById('patient-modal').classList.add('hidden');
}

// Fetch AI-prioritized tasks
async function loadTasks() {
    try {
        const response = await fetch('/api/tasks');
        const tasks = await response.json();
        
        const taskList = document.getElementById('task-list');
        taskList.innerHTML = '';

        tasks.forEach((task, index) => {
            const li = document.createElement('li');
            li.className = 'flex items-center space-x-2';
            li.innerHTML = `
                <input type="checkbox" ${task.completed ? 'checked' : ''} onchange="updateTaskStatus(${index}, this.checked)">
                <span class="${task.completed ? 'line-through text-gray-500' : ''}">${task.task} (Patient Risk: ${task.patient_risk}, Deadline: ${task.days_until_deadline} days)</span>
                <span class="priority-${task.priority.toLowerCase()} px-2 py-1 rounded text-white">[${task.priority}]</span>
            `;
            taskList.appendChild(li);
        });
    } catch (error) {
        console.error('Error loading tasks:', error);
    }
}

// Update task completion status
async function updateTaskStatus(taskIndex, completed) {
    try {
        const response = await fetch('/api/update-task', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ task_index: taskIndex, completed })
        });
        const result = await response.json();
        if (result.success) {
            // loadTasks() will be called via SocketIO event
        }
    } catch (error) {
        console.error('Error updating task status:', error);
    }
}

let selectedDate = 10; // Default to April 10, 2024

// Select a date on the calendar
function selectDate(day) {
    selectedDate = day;
    document.querySelectorAll('.calendar-body span').forEach(span => {
        span.className = 'p-2 hover:bg-indigo-100 cursor-pointer';
        if (parseInt(span.textContent) === day) {
            span.className = 'p-2 bg-indigo-900 text-white rounded';
        }
    });
    loadAppointments();
}

// Fetch appointments for the selected date
async function loadAppointments() {
    try {
        const response = await fetch(`/api/appointments?date=2024-04-${selectedDate.toString().padStart(2, '0')}`);
        const appointments = await response.json();
        
        const appointmentList = document.getElementById('appointment-list');
        appointmentList.innerHTML = '';

        if (appointments.length === 0) {
            appointmentList.innerHTML = '<li class="text-gray-500">No appointments scheduled.</li>';
        } else {
            appointments.forEach(appointment => {
                const li = document.createElement('li');
                li.className = 'flex justify-between items-center p-2 bg-gray-100 rounded';
                li.innerHTML = `
                    <span>${appointment.patient_name} at ${appointment.time}</span>
                    <button onclick="cancelAppointment('${appointment.patient_name}', '${appointment.time}')" class="text-red-500 hover:underline">Cancel</button>
                `;
                appointmentList.appendChild(li);
            });
        }
    } catch (error) {
        console.error('Error loading appointments:', error);
    }
}

// Analyze health trend for a patient
async function analyzeHealthTrend(patientName, measurementType) {
    const chatbox = document.getElementById('chatbox');
    const spinner = showLoadingSpinner();

    try {
        const response = await fetch('/api/health-trend', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ patient_name: patientName, measurement_type: measurementType })
        });
        const result = await response.json();
        
        removeLoadingSpinner(spinner);

        const message = document.createElement('p');
        message.className = 'p-2 bg-gray-100 rounded mb-2';
        message.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>AI: Health trend for ${patientName}: Trend is ${result.trend}, predicted next value: ${result.predicted_next_value}. ${result.alert}`;
        chatbox.appendChild(message);
        chatbox.scrollTop = chatbox.scrollHeight;
    } catch (error) {
        removeLoadingSpinner(spinner);
        console.error('Error analyzing health trend:', error);
    }
}

// Suggest appointment time for a patient
async function suggestAppointment(patientName, riskLevel) {
    const chatbox = document.getElementById('chatbox');
    const spinner = showLoadingSpinner();

    try {
        const response = await fetch('/api/suggest-appointment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ patient_name: patientName, risk_level: riskLevel, date: `2024-04-${selectedDate.toString().padStart(2, '0')}` })
        });
        const result = await response.json();
        
        removeLoadingSpinner(spinner);

        const message = document.createElement('p');
        message.className = 'p-2 bg-gray-100 rounded mb-2';
        message.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>AI: Suggested appointment time for ${patientName}: ${result.suggested_time} <button onclick="scheduleAppointment('${patientName}', '${result.suggested_time}')" class="text-indigo-600 hover:underline">Schedule</button>`;
        chatbox.appendChild(message);
        chatbox.scrollTop = chatbox.scrollHeight;
    } catch (error) {
        removeLoadingSpinner(spinner);
        console.error('Error suggesting appointment:', error);
    }
}

// Schedule an appointment
async function scheduleAppointment(patientName, time) {
    const chatbox = document.getElementById('chatbox');
    const spinner = showLoadingSpinner();

    try {
        const response = await fetch('/api/schedule-appointment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ patient_name: patientName, date: `2024-04-${selectedDate.toString().padStart(2, '0')}`, time })
        });
        const result = await response.json();
        
        removeLoadingSpinner(spinner);

        if (result.success) {
            // loadAppointments() will be called via SocketIO event
            const message = document.createElement('p');
            message.className = 'p-2 bg-green-100 rounded mb-2';
            message.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>AI: Appointment scheduled for ${patientName} on 2024-04-${selectedDate.toString().padStart(2, '0')} at ${time}`;
            chatbox.appendChild(message);
            chatbox.scrollTop = chatbox.scrollHeight;
        } else {
            const message = document.createElement('p');
            message.className = 'p-2 bg-red-100 rounded mb-2';
            message.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>AI: Failed to schedule appointment: ${result.error}`;
            chatbox.appendChild(message);
            chatbox.scrollTop = chatbox.scrollHeight;
        }
    } catch (error) {
        removeLoadingSpinner(spinner);
        console.error('Error scheduling appointment:', error);
    }
}

// Cancel an appointment
async function cancelAppointment(patientName, time) {
    const chatbox = document.getElementById('chatbox');
    const spinner = showLoadingSpinner();

    try {
        const response = await fetch('/api/cancel-appointment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ patient_name: patientName, date: `2024-04-${selectedDate.toString().padStart(2, '0')}`, time })
        });
        const result = await response.json();
        
        removeLoadingSpinner(spinner);

        if (result.success) {
            // loadAppointments() will be called via SocketIO event
            const message = document.createElement('p');
            message.className = 'p-2 bg-red-100 rounded mb-2';
            message.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>AI: Appointment for ${patientName} on 2024-04-${selectedDate.toString().padStart(2, '0')} at ${time} has been canceled.`;
            chatbox.appendChild(message);
            chatbox.scrollTop = chatbox.scrollHeight;
        }
    } catch (error) {
        removeLoadingSpinner(spinner);
        console.error('Error canceling appointment:', error);
    }
}

// Show loading spinner in the chatbox
function showLoadingSpinner() {
    const chatbox = document.getElementById('chatbox');
    const spinner = document.createElement('p');
    spinner.className = 'p-2 text-gray-500';
    spinner.textContent = 'Loading...';
    chatbox.appendChild(spinner);
    chatbox.scrollTop = chatbox.scrollHeight;
    return spinner;
}

// Remove loading spinner
function removeLoadingSpinner(spinner) {
    spinner.remove();
}

// Get current timestamp
function getTimestamp() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Chatbot functionality
async function sendMessage() {
    const chatInput = document.getElementById('chat-input');
    const chatbox = document.getElementById('chatbox');
    const message = chatInput.value.trim();

    if (!message) return;

    const userMessage = document.createElement('p');
    userMessage.className = 'p-2 bg-indigo-100 rounded mb-2 text-right';
    userMessage.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>You: ${message}`;
    chatbox.appendChild(userMessage);

    const spinner = showLoadingSpinner();

    try {
        const response = await fetch('/api/chatbot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        });
        const data = await response.json();

        removeLoadingSpinner(spinner);

        const botMessage = document.createElement('p');
        botMessage.className = 'p-2 bg-gray-100 rounded mb-2';
        botMessage.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>AI: ${data.response}`;
        chatbox.appendChild(botMessage);
        chatbox.scrollTop = chatbox.scrollHeight;
    } catch (error) {
        removeLoadingSpinner(spinner);
        console.error('Error with chatbot:', error);
    }

    chatInput.value = '';
}

// Voice command functionality using Web Speech API
function startVoiceCommand() {
    const chatbox = document.getElementById('chatbox');
    
    // Check if the browser supports the Web Speech API
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        const errorMessage = document.createElement('p');
        errorMessage.className = 'p-2 bg-red-100 rounded mb-2';
        errorMessage.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>AI: Speech recognition is not supported in this browser. Please use a modern browser like Chrome.`;
        chatbox.appendChild(errorMessage);
        chatbox.scrollTop = chatbox.scrollHeight;
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US'; // Set language to English
    recognition.interimResults = false; // Only get final results
    recognition.maxAlternatives = 1; // Get the best result

    const listeningMessage = document.createElement('p');
    listeningMessage.className = 'p-2 bg-yellow-100 rounded mb-2';
    listeningMessage.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>AI: Listening for your voice command...`;
    chatbox.appendChild(listeningMessage);
    chatbox.scrollTop = chatbox.scrollHeight;

    recognition.start();

    recognition.onresult = async (event) => {
        const transcript = event.results[0][0].transcript;
        const userMessage = document.createElement('p');
        userMessage.className = 'p-2 bg-indigo-100 rounded mb-2 text-right';
        userMessage.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>You (Voice): ${transcript}`;
        chatbox.appendChild(userMessage);

        const spinner = showLoadingSpinner();

        try {
            const response = await fetch('/api/voice-command', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: transcript })
            });
            const data = await response.json();

            removeLoadingSpinner(spinner);

            const botMessage = document.createElement('p');
            botMessage.className = 'p-2 bg-gray-100 rounded mb-2';
            botMessage.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>AI: ${data.response}`;
            chatbox.appendChild(botMessage);
            chatbox.scrollTop = chatbox.scrollHeight;
        } catch (error) {
            removeLoadingSpinner(spinner);
            const errorMessage = document.createElement('p');
            errorMessage.className = 'p-2 bg-red-100 rounded mb-2';
            errorMessage.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>AI: Error processing voice command: ${error.message}`;
            chatbox.appendChild(errorMessage);
            chatbox.scrollTop = chatbox.scrollHeight;
        }
    };

    recognition.onerror = (event) => {
        const errorMessage = document.createElement('p');
        errorMessage.className = 'p-2 bg-red-100 rounded mb-2';
        errorMessage.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>AI: Speech recognition error: ${event.error}. Note: Speech recognition requires HTTPS in production.`;
        chatbox.appendChild(errorMessage);
        chatbox.scrollTop = chatbox.scrollHeight;
    };

    recognition.onend = () => {
        const endMessage = document.createElement('p');
        endMessage.className = 'p-2 bg-yellow-100 rounded mb-2';
        endMessage.innerHTML = `<span class="block text-sm text-gray-500">${getTimestamp()}</span>AI: Stopped listening.`;
        chatbox.appendChild(endMessage);
        chatbox.scrollTop = chatbox.scrollHeight;
    };
}

// Show a notification
function showNotification(message, type) {
    const notificationArea = document.getElementById('notification-area');
    const notificationMessage = document.getElementById('notification-message');
    
    notificationMessage.textContent = message;
    notificationMessage.className = `p-4 rounded-lg text-white ${type === 'warning' ? 'bg-red-500' : 'bg-green-500'}`;
    notificationArea.classList.remove('hidden');

    setTimeout(() => {
        notificationArea.classList.add('hidden');
    }, 5000);
}

// Load data when the page loads
document.addEventListener('DOMContentLoaded', () => {
    // Check if the user is logged in
    fetch('/api/check-auth', {
        method: 'GET',
        credentials: 'include' // Include cookies in the request
    })
    .then(response => response.json())
    .then(data => {
        if (!data.authenticated) {
            window.location.href = '/login';
        } else {
            userRole = data.role; // Store the user's role
            loadPatients();
            loadTasks();
            loadAppointments();
        }
    })
    .catch(error => {
        console.error('Error checking authentication:', error);
        window.location.href = '/login';
    });

    // Update logout button functionality
    document.querySelector('.logout').addEventListener('click', (e) => {
        e.preventDefault();
        fetch('/api/logout', {
            method: 'POST',
            credentials: 'include'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = '/login';
            }
        })
        .catch(error => console.error('Error logging out:', error));
    });

    // SocketIO event listeners for real-time updates
    socket.on('task_updated', (data) => {
        loadTasks();
        showNotification(`Task ${data.task_index + 1} marked as ${data.completed ? 'completed' : 'incomplete'}`, 'success');
    });

    socket.on('appointment_scheduled', (data) => {
        if (data.date === `2024-04-${selectedDate.toString().padStart(2, '0')}`) {
            loadAppointments();
        }
        showNotification(`Appointment scheduled for ${data.patient_name} on ${data.date} at ${data.time}`, 'success');
    });

    socket.on('appointment_canceled', (data) => {
        if (data.date === `2024-04-${selectedDate.toString().padStart(2, '0')}`) {
            loadAppointments();
        }
        showNotification(`Appointment for ${data.patient_name} on ${data.date} at ${data.time} canceled`, 'success');
    });

    socket.on('patient_updated', (data) => {
        loadPatients();
        showNotification(`Patient ${data.patient_name}'s details updated`, 'success');
    });

    socket.on('notification', (data) => {
        showNotification(data.message, data.type);
    });
});