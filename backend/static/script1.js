// static/script.js
// JavaScript for Doctor Dashboard AI frontend
// Handles authentication, dashboard, patients, appointments, tasks, voice commands, chat, and real-time updates

// Initialize SocketIO
const socket = io();

// Global variables
let userRole = null;
let userId = null;
let selectedDate = 15; // Default to April 15, 2025
let currentMonth = 3; // 0-based (3 = April)
let currentYear = 2025; // Show April 2025
const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

// Utility functions
function showError(elementId, message) {
    const errorElement = document.getElementById(elementId);
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
}

function clearError(elementId) {
    const errorElement = document.getElementById(elementId);
    if (errorElement) {
        errorElement.textContent = '';
        errorElement.style.display = 'none';
    }
}

function showNotification(message, type) {
    const notificationArea = document.getElementById('notification-area');
    const notificationMessage = document.getElementById('notification-message');
    if (notificationArea && notificationMessage) {
        notificationMessage.textContent = message;
        notificationMessage.className = `p-4 rounded-lg text-white ${type === 'warning' ? 'bg-red-500' : 'bg-green-500'}`;
        notificationArea.classList.remove('hidden');
        setTimeout(() => {
            notificationArea.classList.add('hidden');
        }, 5000);
    }
}

function daysInMonth(month, year) {
    return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(month, year) {
    return new Date(year, month, 1).getDay();
}

// Filter patients based on search input
function filterPatients() {
    const searchInput = document.getElementById('patientSearch')?.value.toLowerCase();
    const rows = document.querySelectorAll('#patientTable tbody tr');
    rows.forEach(row => {
        const name = row.cells[0].textContent.toLowerCase();
        const condition = row.cells[3].textContent.toLowerCase();
        row.style.display = (name.includes(searchInput) || condition.includes(searchInput)) ? '' : 'none';
    });
}

// Handle login form submission
function handleLogin(event) {
    event.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    clearError('errorMessage');

    fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
        credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
        if (response.ok) {
            socket.emit('register_session', { username });
            window.location.href = '/dashboard';
        } else {
            showError('errorMessage', data.error || 'Login failed');
        }
    })
    .catch(error => {
        showError('errorMessage', 'An error occurred. Please try again.');
    });
}

// Handle registration form submission
function handleRegister(event) {
    event.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const role = document.getElementById('role').value;
    clearError('errorMessage');

    if (!role) {
        showError('errorMessage', 'Please select a role');
        return;
    }

    fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, role }),
        credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
        if (response.ok) {
            window.location.href = '/login';
        } else {
            showError('errorMessage', data.error || 'Registration failed');
        }
    })
    .catch(error => {
        showError('errorMessage', 'An error occurred. Please try again.');
    });
}

// Load patients for the dashboard
async function loadPatients() {
    try {
        console.log('Fetching patients from /api/patients...');
        const response = await fetch('/api/patients', { credentials: 'include' });
        console.log('Patients response status:', response.status);
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        const patients = await response.json();
        console.log('Patients fetched:', patients);

        const tableBody = document.getElementById('patientTable')?.querySelector('tbody');
        if (!tableBody) {
            console.error('Patient table body not found');
            return;
        }

        tableBody.innerHTML = patients.length === 0
            ? '<tr><td colspan="4" class="p-3 text-gray-500">No patients found.</td></tr>'
            : patients.map(p => `
                <tr onclick="openPatientModal('${p.patient_id}')" style="cursor: pointer;">
                    <td class="p-3">${p.name || 'N/A'}</td>
                    <td class="p-3">${p.age || 'N/A'}</td>
                    <td class="p-3">${p.gender || 'N/A'}</td>
                    <td class="p-3">${p.current_condition || 'N/A'}</td>
                </tr>
            `).join('');

        document.getElementById('totalPatients').textContent = patients.length || 0;

        const searchInput = document.getElementById('patientSearch');
        if (searchInput) searchInput.addEventListener('input', filterPatients);
    } catch (error) {
        console.error('Error loading patients:', error.message);
        showError('errorMessage', 'Error loading patients: ' + error.message);
    }
}

// Open patient details modal
async function openPatientModal(patientId) {
    try {
        console.log(`Fetching patient details for ID ${patientId}...`);
        const response = await fetch(`/api/patients/${patientId}`, { credentials: 'include' });
        console.log('Patient details response status:', response.status);
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        const patient = await response.json();
        console.log('Patient details:', patient);

        document.getElementById('modal-patient-id').textContent = patient.patient_id;
        document.getElementById('modal-patient-name').textContent = patient.name || 'N/A';
        document.getElementById('modal-patient-age').textContent = patient.age || 'N/A';
        document.getElementById('modal-patient-gender').textContent = patient.gender || 'N/A';
        document.getElementById('modal-patient-condition').textContent = patient.current_condition || 'N/A';
        document.getElementById('modal-patient-history').textContent = patient.medical_history || 'No history available';
        document.getElementById('modal-patient-vitals').textContent = patient.recent_vitals || 'No recent vitals available';
        document.getElementById('modal-patient-contact').textContent = patient.contact_info || 'Not provided';
        document.getElementById('modal-patient-allergies').textContent = patient.allergies || 'None';
        document.getElementById('modal-patient-medications').textContent = patient.medications || 'None';
        document.getElementById('modal-patient-last-visit').textContent = patient.last_visit_date || 'Not recorded';

        document.getElementById('patient-modal').classList.remove('hidden');
    } catch (error) {
        console.error('Error fetching patient details:', error.message);
        showError('errorMessage', 'Error fetching patient details: ' + error.message);
    }
}

// Close patient details modal
function closeModal() {
    document.getElementById('patient-modal').classList.add('hidden');
}

// Analyze health trend for a patient
async function analyzeHealthTrend(patientId, measurementType) {
    try {
        console.log(`Analyzing health trend for patient ID ${patientId}...`);
        const response = await fetch(`/api/patients/${patientId}/health-trends`, {
            method: 'GET',
            credentials: 'include'
        });
        console.log('Health trend response status:', response.status);
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        const result = await response.json();
        console.log('Health trend result:', result);
        alert(`Health trend for patient: Trend is ${result.trends?.condition || 'N/A'}.`);
    } catch (error) {
        console.error('Error analyzing health trend:', error.message);
        showError('errorMessage', 'Error analyzing health trend: ' + error.message);
    }
}

// Suggest an appointment time for a patient
async function suggestAppointment(patientId, riskLevel) {
    try {
        console.log(`Suggesting appointment for patient ID ${patientId}...`);
        const response = await fetch('/api/appointments/suggest', {
            method: 'GET',
            credentials: 'include'
        });
        console.log('Suggest appointment response status:', response.status);
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        const result = await response.json();
        console.log('Suggested times:', result);
        const suggestedTime = result.suggested_times?.[0] || '2025-04-23 10:00:00'; // Fallback

        const scheduleResponse = await fetch('/api/appointments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                patient_id: patientId,
                doctor_id: userId,
                appointment_time: suggestedTime
            }),
            credentials: 'include'
        });
        console.log('Schedule appointment response status:', scheduleResponse.status);
        if (!scheduleResponse.ok) throw new Error(`HTTP error! Status: ${scheduleResponse.status}`);
        const scheduleResult = await scheduleResponse.json();
        console.log('Schedule result:', scheduleResult);
        if (scheduleResult.message) {
            showNotification('Appointment scheduled successfully.', 'info');
            loadAppointments();
        }
    } catch (error) {
        console.error('Error suggesting appointment:', error.message);
        showError('errorMessage', 'Error suggesting appointment: ' + error.message);
    }
}

// Load tasks for the dashboard
async function loadTasks() {
    try {
        console.log('Fetching tasks from /api/tasks/prioritized...');
        const response = await fetch('/api/tasks/prioritized', { credentials: 'include' });
        console.log('Tasks response status:', response.status);
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        let tasks = await response.json();
        console.log('Tasks fetched:', tasks);
        tasks.sort((a, b) => a.task_id - b.task_id);

        document.getElementById('pendingTasks').textContent = tasks.length || 0;

        const taskList1 = document.getElementById('taskList1');
        const taskList2 = document.getElementById('taskList2');
        if (!taskList1 || !taskList2) {
            console.error('Task lists not found');
            return;
        }

        if (tasks.length === 0) {
            taskList1.innerHTML = '<li>No tasks available.</li>';
            taskList2.innerHTML = '';
        } else {
            taskList1.innerHTML = tasks.slice(0, 2).map(t => `
                <li>
                    <label>
                        <input type="checkbox" ${t.completed ? 'checked' : ''} onchange="updateTask(${t.task_id}, this.checked)">
                        ${t.description}
                    </label>
                </li>
            `).join('');
            taskList2.innerHTML = tasks.slice(2).map(t => `
                <li>
                    <label>
                        <input type="checkbox" ${t.completed ? 'checked' : ''} onchange="updateTask(${t.task_id}, this.checked)">
                        ${t.description}
                    </label>
                </li>
            `).join('');
        }
    } catch (error) {
        console.error('Error loading tasks:', error.message);
        showError('errorMessage', 'Error loading tasks: ' + error.message);
    }
}

// Update task status
async function updateTask(taskId, completed) {
    try {
        console.log(`Updating task ID ${taskId} to completed=${completed}...`);
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ completed }),
            credentials: 'include'
        });
        console.log('Update task response status:', response.status);
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        loadTasks();
    } catch (error) {
        console.error('Error updating task:', error.message);
        showError('errorMessage', 'Error updating task: ' + error.message);
    }
}

// Create a new task
async function handleTaskCreation(event) {
    event.preventDefault();
    const description = document.getElementById('taskDescription')?.value;
    const patientId = document.getElementById('taskPatientId')?.value || 1;
    if (!description) {
        showError('errorMessage', 'Task description is required.');
        return;
    }
    try {
        console.log(`Creating new task: ${description} for patient ID ${patientId}...`);
        await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: patientId, description }),
            credentials: 'include'
        });
        document.getElementById('taskDescription').value = '';
        loadTasks();
    } catch (error) {
        console.error('Error creating task:', error.message);
        showError('errorMessage', 'Error creating task: ' + error.message);
    }
}

// Load appointments for the selected date
async function loadAppointments() {
    try {
        const date = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(selectedDate).padStart(2, '0')}`;
        console.log(`Fetching appointments for ${date}...`);
        const response = await fetch(`/api/appointments?date=${date}`, { credentials: 'include' });
        console.log('Appointments response status:', response.status);
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        const appointments = await response.json();
        console.log('Appointments fetched:', appointments);

        const appointmentList = document.getElementById('appointment-list');
        if (!appointmentList) {
            console.error('Appointment list not found');
            return;
        }

        appointmentList.innerHTML = appointments.length === 0
            ? '<li class="text-gray-500">No appointments scheduled.</li>'
            : appointments.map(a => `
                <li class="flex justify-between items-center p-2 bg-gray-100 rounded">
                    <span>Patient ${a.patient_id} at ${a.appointment_time.split(' ')[1]}</span>
                    <button onclick="cancelAppointment(${a.appointment_id})" class="text-red-500 hover:underline">Cancel</button>
                </li>
            `).join('');

        // Update metrics (count all appointments for the month)
        const monthResponse = await fetch(`/api/appointments?date=${currentYear}-${String(currentMonth + 1).padStart(2, '0')}`, { credentials: 'include' });
        console.log('Month appointments response status:', monthResponse.status);
        if (!monthResponse.ok) throw new Error(`HTTP error! Status: ${monthResponse.status}`);
        const monthAppointments = await monthResponse.json();
        console.log('Month appointments:', monthAppointments);

        const referenceDate = new Date('2024-04-01T00:00:00');
        console.log('Reference date:', referenceDate);
        let upcoming = 0;
        let completed = 0;
        monthAppointments.forEach(a => {
            const date = new Date(a.appointment_time);
            console.log(`Comparing ${date} with ${referenceDate}: ${date >= referenceDate ? 'upcoming' : 'completed'}`);
            if (date >= referenceDate) upcoming++;
            else completed++;
        });
        console.log(`Upcoming: ${upcoming}, Completed: ${completed}`);
        document.getElementById('upcomingAppointments').textContent = upcoming;
        document.getElementById('completedAppointments').textContent = completed;
    } catch (error) {
        console.error('Error loading appointments:', error.message);
        showError('errorMessage', 'Error loading appointments: ' + error.message);
    }
}

// Select a date on the calendar
function selectDate(day) {
    selectedDate = day;
    document.querySelectorAll('.calendar-grid .day').forEach(span => {
        span.className = 'day p-2 hover:bg-indigo-100 cursor-pointer';
        if (parseInt(span.textContent) === day) {
            span.className = 'day p-2 bg-indigo-900 text-white rounded';
        }
    });
    loadAppointments();
}

// Cancel an appointment
async function cancelAppointment(appointmentId) {
    try {
        console.log(`Canceling appointment ID ${appointmentId}...`);
        await fetch(`/api/appointments/${appointmentId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        loadAppointments();
    } catch (error) {
        console.error('Error canceling appointment:', error.message);
        showError('errorMessage', 'Error canceling appointment: ' + error.message);
    }
}

// Navigate calendar months
function prevMonth() {
    currentMonth--;
    if (currentMonth < 0) {
        currentMonth = 11;
        currentYear--;
    }
    loadDashboard();
}

function nextMonth() {
    currentMonth++;
    if (currentMonth > 11) {
        currentMonth = 0;
        currentYear++;
    }
    loadDashboard();
}

// Handle voice commands
function startVoiceCommand() {
    if (!('webkitSpeechRecognition' in window)) {
        showError('errorMessage', 'Speech recognition not supported in this browser.');
        return;
    }
    const recognition = new webkitSpeechRecognition();
    recognition.lang = 'en-US';
    recognition.onresult = async (event) => {
        const command = event.results[0][0].transcript;
        try {
            console.log(`Processing voice command: ${command}...`);
            const response = await fetch('/api/voice-command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command }),
                credentials: 'include'
            });
            console.log('Voice command response status:', response.status);
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
            const data = await response.json();
            showNotification(data.response, 'info');
        } catch (error) {
            console.error('Error processing voice command:', error.message);
            showError('errorMessage', 'Error processing voice command: ' + error.message);
        }
    };
    recognition.onerror = () => {
        showError('errorMessage', 'Error with voice recognition.');
    };
    recognition.start();
}

// Load chat recipients
async function loadChatRecipients() {
    try {
        console.log('Fetching users for chat recipients...');
        const response = await fetch('/api/users', { credentials: 'include' });
        console.log('Users response status:', response.status);
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        const users = await response.json();
        console.log('Users fetched:', users);

        const recipientSelect = document.getElementById('chat-recipient');
        if (!recipientSelect) {
            console.error('Chat recipient dropdown not found');
            return;
        }
        recipientSelect.innerHTML = '<option value="all">All Users (Public)</option>';

        users.forEach(user => {
            if (user.user_id !== parseInt(userId)) {
                const option = document.createElement('option');
                option.value = user.user_id;
                option.textContent = user.username;
                recipientSelect.appendChild(option);
            }
        });
    } catch (error) {
        console.error('Error loading chat recipients:', error.message);
        showError('errorMessage', 'Error loading chat recipients: ' + error.message);
    }
}

// Send a chat message
async function sendMessage() {
    const chatInput = document.getElementById('chat-input');
    const recipientSelect = document.getElementById('chat-recipient');
    const chatbox = document.getElementById('chatbox');

    if (!chatInput || !recipientSelect || !chatbox) {
        console.error('Chat elements not found');
        return;
    }

    const message = chatInput.value.trim();
    const recipientId = recipientSelect.value;

    if (!message) return;

    try {
        console.log(`Sending chat message to recipient ${recipientId}: ${message}`);
        socket.emit('chat_message', {
            user_id: userId,
            recipient_id: recipientId,
            message: message
        });
        chatInput.value = '';
    } catch (error) {
        console.error('Error sending chat message:', error.message);
        showError('errorMessage', 'Error sending chat message: ' + error.message);
    }
}

// Load dashboard content
async function loadDashboard() {
    clearError('errorMessage');
    try {
        console.log('Checking authentication...');
        const authResponse = await fetch('/api/check-auth', { credentials: 'include' });
        console.log('Auth response status:', authResponse.status);
        if (!authResponse.ok) throw new Error(`HTTP error! Status: ${authResponse.status}`);
        const authData = await authResponse.json();
        console.log('Auth data:', authData);
        if (!authData.authenticated) {
            console.log('User not authenticated, redirecting to login');
            window.location.href = '/login';
            return;
        }

        userRole = authData.role;
        userId = authData.user_id;
        socket.emit('register_session', { user_id: userId });

        console.log(`User role: ${userRole}, User ID: ${userId}`);

        // Show "Manage Users" link for Admins
        if (userRole === 'Admin') {
            const manageUsersLink = document.getElementById('manage-users-link');
            if (manageUsersLink) {
                manageUsersLink.style.display = 'inline';
            } else {
                console.error('Manage users link not found');
            }
        }

        if (userRole === 'Doctor' || userRole === 'Admin') {
            console.log('Loading dashboard data for Doctor/Admin...');
            await loadPatients();
            await loadTasks();
            await loadAppointments();
            await loadChatRecipients();

            // Render Calendar
            console.log('Rendering calendar...');
            const calendarGrid = document.getElementById('calendarGrid');
            if (!calendarGrid) {
                console.error('Calendar grid not found');
                return;
            }
            const appointmentsResponse = await fetch(`/api/appointments?date=${currentYear}-${String(currentMonth + 1).padStart(2, '0')}`, { credentials: 'include' });
            console.log('Calendar appointments response status:', appointmentsResponse.status);
            if (!appointmentsResponse.ok) throw new Error(`HTTP error! Status: ${appointmentsResponse.status}`);
            const appointments = await appointmentsResponse.json();
            console.log('Calendar appointments:', appointments);
            const appointmentDays = appointments.map(a => {
                const date = new Date(a.appointment_time);
                return date.getDate();
            });

            calendarGrid.innerHTML = `
                <div class="day-header">S</div>
                <div class="day-header">M</div>
                <div class="day-header">T</div>
                <div class="day-header">W</div>
                <div class="day-header">T</div>
                <div class="day-header">F</div>
                <div class="day-header">S</div>
            `;
            const firstDay = getFirstDayOfMonth(currentMonth, currentYear);
            const totalDays = daysInMonth(currentMonth, currentYear);
            for (let i = 0; i < firstDay; i++) {
                calendarGrid.innerHTML += `<div></div>`;
            }
            for (let day = 1; day <= totalDays; day++) {
                const isSelected = day === selectedDate ? 'selected' : appointmentDays.includes(day) ? 'highlighted' : '';
                calendarGrid.innerHTML += `<div class="day ${isSelected}" onclick="selectDate(${day})">${day}</div>`;
            }
        } else if (userRole === 'Patient') {
            document.querySelector('.container').innerHTML = `
                <h2>Patient Dashboard</h2>
                <p>View your appointments and health trends.</p>
            `;
        } else {
            document.querySelector('.container').innerHTML = `
                <h2>User Dashboard</h2>
                <p>General user dashboard.</p>
            `;
        }
    } catch (error) {
        console.error('Error loading dashboard:', error.message);
        showError('errorMessage', 'Error loading dashboard: ' + error.message);
    }
}

// Handle logout
async function logout() {
    try {
        console.log('Logging out...');
        await fetch('/api/logout', { method: 'POST', credentials: 'include' });
        window.location.href = '/login';
    } catch (error) {
        console.error('Error logging out:', error.message);
        window.location.href = '/login';
    }
}

// SocketIO event listeners
socket.on('connect', () => {
    console.log('SocketIO connected successfully.');
});

socket.on('chat_message', (data) => {
    const chatbox = document.getElementById('chatbox');
    if (!chatbox) {
        console.error('Chatbox not found');
        return;
    }

    console.log('Chat message received:', data);
    const message = document.createElement('p');
    message.className = 'p-2 bg-gray-100 rounded mb-2';
    message.innerHTML = data.is_private
        ? `<span class="text-purple-600">[Private from ${data.from}]</span> ${data.message}`
        : `${data.username}: ${data.message}`;
    chatbox.appendChild(message);
    chatbox.scrollTop = chatbox.scrollHeight;
});

socket.on('patient_updated', () => {
    console.log('Patient updated, reloading patients...');
    loadPatients();
});

socket.on('task_updated', () => {
    console.log('Task updated, reloading tasks...');
    loadTasks();
});

socket.on('appointment_scheduled', (data) => {
    console.log('Appointment scheduled:', data);
    if (data.date === `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(selectedDate).padStart(2, '0')}`) {
        loadAppointments();
    }
});

socket.on('appointment_canceled', (data) => {
    console.log('Appointment canceled:', data);
    if (data.date === `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(selectedDate).padStart(2, '0')}`) {
        loadAppointments();
    }
});

socket.on('notification', (data) => {
    console.log('Notification received:', data);
    showNotification(data.message, data.type);
});

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const dashboardPage = document.getElementById('calendarGrid');
    const voiceButton = document.getElementById('voiceCommandButton');
    const chatForm = document.getElementById('chat-form');
    const taskForm = document.getElementById('taskForm');

    if (loginForm) loginForm.addEventListener('submit', handleLogin);
    if (registerForm) registerForm.addEventListener('submit', handleRegister);
    if (dashboardPage) loadDashboard();
    if (voiceButton) voiceButton.addEventListener('click', startVoiceCommand);
    if (chatForm) chatForm.addEventListener('submit', (e) => { e.preventDefault(); sendMessage(); });
    if (taskForm) taskForm.addEventListener('submit', handleTaskCreation);
});



// Apr 18th After Patinet Graph added this new functionality

document.addEventListener('DOMContentLoaded', function() {
    // Initialize FullCalendar
    var calendarEl = document.getElementById('calendar');
    if (!calendarEl) {
        console.error("Calendar element not found. Ensure <div id='calendar'> exists in dashboard.html.");
        return;
    }
    try {
        console.log("Checking if FullCalendar is defined...");
        if (typeof FullCalendar === 'undefined') {
            console.error("FullCalendar is not defined. Ensure fullcalendar.min.js is loaded correctly.");
            return;
        }
        console.log("Initializing FullCalendar...");
        var calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            height: 'auto', // Ensure calendar has visible height
            events: '/get_appointments',
            selectable: true,
            dateClick: function(info) {
                console.log("Date clicked:", info.dateStr);
                var dateInput = document.getElementById('addAppointmentDate');
                if (dateInput) {
                    dateInput.value = info.dateStr;
                    var modal = document.getElementById('addAppointmentModal');
                    if (modal) {
                        modal.classList.remove('hidden');
                    } else {
                        console.error("Add Appointment modal not found.");
                    }
                } else {
                    console.error("Add Appointment modal date input not found.");
                }
            },
            eventClick: function(info) {
                console.log("Event clicked:", info.event.id);
                window.location.href = '/edit_appointment/' + info.event.id;
            },
            eventClassNames: function(arg) {
                return arg.event.classNames; // Apply high-priority or low-priority styles
            },
            eventsFetch: function(fetchInfo, successCallback, failureCallback) {
                console.log("Fetching events from /get_appointments...");
                fetch('/get_appointments')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! Status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        console.log("Events fetched:", data);
                        if (!Array.isArray(data)) {
                            console.warn("Events data is not an array:", data);
                            successCallback([]);
                        } else if (data.length === 0) {
                            console.warn("No events returned from /get_appointments.");
                            successCallback([]);
                        } else {
                            successCallback(data);
                        }
                    })
                    .catch(error => {
                        console.error("Error fetching events:", error);
                        failureCallback(error);
                    });
            }
        });
        calendar.render();
        console.log("FullCalendar rendered successfully.");
    } catch (e) {
        console.error("FullCalendar initialization failed:", e);
    }

    // Task prioritization
    console.log("Prioritizing tasks...");
    const taskList = document.querySelectorAll('.task-item');
    taskList.forEach(task => {
        if (task.dataset.priority === 'High') {
            task.parentNode.prepend(task);
        }
    });

    // Bulk delete patients
    console.log("Setting up bulk delete...");
    const bulkDeleteBtn = document.getElementById('bulkDeleteBtn');
    if (bulkDeleteBtn) {
        bulkDeleteBtn.addEventListener('click', function() {
            const selected = document.querySelectorAll('.patient-checkbox:checked');
            const ids = Array.from(selected).map(cb => cb.value);
            if (ids.length > 0 && confirm('Delete selected patients?')) {
                fetch('/bulk_delete_patients', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ids: ids })
                })
                    .then(response => {
                        if (!response.ok) throw new Error('Bulk delete failed');
                        location.reload();
                    })
                    .catch(error => console.error("Bulk delete failed:", error));
            }
        });
    } else {
        console.warn("Bulk delete button not found.");
    }

    // Client-side advanced search
    console.log("Setting up advanced search...");
    const searchForm = document.querySelector('#advancedSearchModal form');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const name = document.getElementById('search-name').value.toLowerCase();
            const condition = document.getElementById('search-condition').value.toLowerCase();
            const ageMin = parseInt(document.getElementById('search-age-min').value) || 0;
            const ageMax = parseInt(document.getElementById('search-age-max').value) || Infinity;
            const riskMin = parseFloat(document.getElementById('search-risk-min').value) || 0;
            const riskMax = parseFloat(document.getElementById('search-risk-max').value) || 1;
            
            document.querySelectorAll('.table tbody tr').forEach(row => {
                const rowName = row.cells[1].textContent.toLowerCase();
                const rowCondition = row.cells[4].textContent.toLowerCase();
                const rowAge = parseInt(row.cells[2].textContent);
                const rowRisk = parseFloat(row.cells[5].textContent);
                
                const matches = (!name || rowName.includes(name)) &&
                               (!condition || rowCondition.includes(condition)) &&
                               (rowAge >= ageMin && rowAge <= ageMax) &&
                               (rowRisk >= riskMin && rowRisk <= riskMax);
                
                row.style.display = matches ? '' : 'none';
            });
        });
    } else {
        console.warn("Advanced search form not found.");
    }

    // Real-time notifications with SocketIO
    console.log("Setting up SocketIO...");
    const socket = io();
    socket.on('connect', function() {
        console.log("SocketIO connected");
    });
    socket.on('new_appointment', function(data) {
        console.log("New appointment notification:", data.message);
        const notificationDiv = document.getElementById('realTimeNotifications');
        const notificationMessage = document.getElementById('notificationMessage');
        if (notificationDiv && notificationMessage) {
            notificationMessage.textContent = data.message;
            notificationDiv.classList.remove('hidden');
            setTimeout(() => notificationDiv.classList.add('hidden'), 5000);
            // Refresh calendar events
            if (calendar) {
                console.log("Refetching calendar events...");
                calendar.refetchEvents();
            }
        } else {
            console.warn("Notification elements not found.");
        }
    });
    socket.on('new_task', function(data) {
        console.log("New task notification:", data.message);
        const notificationDiv = document.getElementById('realTimeNotifications');
        const notificationMessage = document.getElementById('notificationMessage');
        if (notificationDiv && notificationMessage) {
            notificationMessage.textContent = data.message;
            notificationDiv.classList.remove('hidden');
            setTimeout(() => notificationDiv.classList.add('hidden'), 5000);
        } else {
            console.warn("Notification elements not found.");
        }
    });
    socket.on('disconnect', function() {
        console.log("SocketIO disconnected");
    });
});