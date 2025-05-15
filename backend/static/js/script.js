// static/script.js
// JavaScript for Doctor Dashboard AI frontend
// Handles authentication, dashboard, patients, appointments, tasks, voice commands, chat, and dynamic calendar

// Initialize SocketIO
let socket;
try {
    console.log("Initializing SocketIO...");
    if (typeof io === 'undefined') {
        throw new Error("Socket.IO 'io' is not defined. Ensure socket.io.min.js is loaded.");
    }
    socket = io();
    console.log("SocketIO initialized successfully.");
} catch (e) {
    console.error("SocketIO initialization failed:", e.message);
}


// Global variables
// Global variable to track Chart.js instance for patient-summary-chart
let patientSummaryChartInstance = null;
let userRole = null;
let userId = null;
let selectedDate = 15; // Default to April 15, 2025
let currentMonth = 3; // 0-based (3 = April)
let currentYear = 2025; // Show April 2025
const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
let mediaRecorder;
let audioChunks = [];

// ***************** Utility functions ****************************
// function showError(elementId, message) {
//     const errorElement = document.getElementById(elementId);
//     if (errorElement) {
//         errorElement.textContent = message;
//         errorElement.style.display = 'block';
//     } else {
//         console.warn(`Error element ${elementId} not found`);
//     }
// }

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
    // else {
    //     console.warn("Notification elements not found");
    // }
}

function daysInMonth(month, year) {
    return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(month, year) {
    return new Date(year, month, 1).getDay();
}

// **************** Filter patients based on search input *****************
function filterPatients() {
    const searchInput = document.getElementById('patientSearch')?.value.toLowerCase();
    if (!searchInput) {
        console.warn("Patient search input not found");
        return;
    }
    const rows = document.querySelectorAll('#patientTable tbody tr');
    rows.forEach(row => {
        const name = row.cells[0].textContent.toLowerCase();
        const condition = row.cells[3].textContent.toLowerCase();
        row.style.display = (name.includes(searchInput) || condition.includes(searchInput)) ? '' : 'none';
    });
}

// **********  Handle login form submission **********************
function handleLogin(event) {
    event.preventDefault();
    const username = document.getElementById('username')?.value;
    const password = document.getElementById('password')?.value;
    if (!username || !password) {
        showError('errorMessage', 'Username and password are required');
        return;
    }
    clearError('errorMessage');

    fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
        credentials: 'include'
    })
    .then(response => {
        console.log('Login response status:', response.status);
        if (!response.ok) throw new Error('Login failed');
        return response.json();
    })
    .then(data => {
        if (socket) {
            socket.emit('register_session', { username });
        }
        window.location.href = '/dashboard';
    })
    .catch(error => {
        console.error('Error during login:', error.message);
        showError('errorMessage', 'Login failed: ' + error.message);
    });
}

// ********************* Handle registration form submission *********************************
function handleRegister(event) {
    event.preventDefault();
    const username = document.getElementById('username')?.value;
    const password = document.getElementById('password')?.value;
    const role = document.getElementById('role')?.value;
    clearError('errorMessage');

    if (!username || !password || !role) {
        showError('errorMessage', 'All fields are required');
        return;
    }

    fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password, role }),
        credentials: 'include'
    })
    .then(response => {
        console.log('Register response status:', response.status);
        if (!response.ok) throw new Error('Registration failed');
        return response.json();
    })
    .then(data => {
        window.location.href = '/login';
    })
    .catch(error => {
        console.error('Error during registration:', error.message);
        showError('errorMessage', 'Registration failed: ' + error.message);
    });
}

// ********************* Load patients for the dashboard ************************
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
        if (searchInput) {
            searchInput.addEventListener('input', filterPatients);
        } else {
            console.warn("Patient search input not found");
        }
    } catch (error) {
        console.error('Error loading patients:', error.message);
        showError('errorMessage', 'Error loading patients: ' + error.message);
    }
}

// ********************  Open patient details modal  ***********************************
async function openPatientModal(patientId) {
    try {
        console.log(`Fetching patient details for ID ${patientId}...`);
        const response = await fetch(`/api/patients/${patientId}`, { credentials: 'include' });
        console.log('Patient details response status:', response.status);
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        const patient = await response.json();
        console.log('Patient details:', patient);

        document.getElementById('modal-patient-id').textContent = patient.patient_id || 'N/A';
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

        const modal = document.getElementById('patient-modal');
        if (modal) {
            modal.classList.remove('hidden');
        } else {
            console.error("Patient modal not found");
        }
    } catch (error) {
        console.error('Error fetching patient details:', error.message);
        showError('errorMessage', 'Error fetching patient details: ' + error.message);
    }
}

// ***************** Close patient details modal ***********************
function closeModal() {
    const modal = document.getElementById('patient-modal');
    if (modal) {
        modal.classList.add('hidden');
    } else {
        console.warn("Patient modal not found");
    }
}

// *********************** Analyze health trend for a patient **************************
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

// ********************** Suggest an appointment time for a patient **************************
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

// **************** Load tasks for the dashboard *******************************
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

// ********************* Update task status *********************************
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

// ******************** Create a new task ************************************
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

// ********************* Load appointments for the selected date *****************
// async function loadAppointments() {
//     try {
//         const date = `${currentYear}-${String(currentMonth + 1).padStart(2, '0')}-${String(selectedDate).padStart(2, '0')}`;
//         console.log(`Fetching appointments for ${date}...`);
//         const response = await fetch(`/api/appointments?date=${date}`, { credentials: 'include' });
//         console.log('Appointments response status:', response.status);
//         if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
//         const appointments = await response.json();
//         console.log('Appointments fetched:', appointments);

//         const appointmentList = document.getElementById('appointment-list');
//         if (!appointmentList) {
//             console.error('Appointment list not found');
//             return;
//         }

//         appointmentList.innerHTML = appointments.length === 0
//             ? '<li class="text-gray-500">No appointments scheduled.</li>'
//             : appointments.map(a => `
//                 <li class="flex justify-between items-center p-2 bg-gray-100 rounded">
//                     <span>Patient ${a.patient_id} at ${a.appointment_time.split(' ')[1]}</span>
//                     <button onclick="cancelAppointment(${a.appointment_id})" class="text-red-500 hover:underline">Cancel</button>
//                 </li>
//             `).join('');

//         // Update metrics (count all appointments for the month)
//         const monthResponse = await fetch(`/api/appointments?date=${currentYear}-${String(currentMonth + 1).padStart(2, '0')}`, { credentials: 'include' });
//         console.log('Month appointments response status:', monthResponse.status);
//         if (!monthResponse.ok) throw new Error(`HTTP error! Status: ${monthResponse.status}`);
//         const monthAppointments = await monthResponse.json();
//         console.log('Month appointments:', monthAppointments);

//         const referenceDate = new Date('2024-04-01T00:00:00');
//         console.log('Reference date:', referenceDate);
//         let upcoming = 0;
//         let completed = 0;
//         monthAppointments.forEach(a => {
//             const date = new Date(a.appointment_time);
//             console.log(`Comparing ${date} with ${referenceDate}: ${date >= referenceDate ? 'upcoming' : 'completed'}`);
//             if (date >= referenceDate) upcoming++;
//             else completed++;
//         });
//         console.log(`Upcoming: ${upcoming}, Completed: ${completed}`);
//         document.getElementById('upcomingAppointments').textContent = upcoming;
//         document.getElementById('completedAppointments').textContent = completed;
//     } catch (error) {
//         console.error('Error loading appointments:', error.message);
//         showError('errorMessage', 'Error loading appointments: ' + error.message);
//     }
// }

async function loadAppointments() {
    try {
        console.log('Fetching appointments for dashboard (three-day range)...');
        // Use date_range=three_days for dashboard appointment list
        const response = await fetch('/get_appointments?date_range=three_days', { credentials: 'include' });
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
            ? '<li class="text-gray-500">No appointments scheduled for yesterday, today, or tomorrow.</li>'
            : appointments.map(a => `
                <li class="list-group-item p-3 flex justify-between items-center">
                    <span>${a.title} - ${a.patient_name} (${a.date} ${a.time}, ${a.status})</span>
                    <a href="/edit_appointment/${a.id}" class="btn-primary text-sm" title="Edit appointment ${a.title}" aria-label="Edit appointment ${a.title}">Edit</a>
                </li>
            `).join('');

        // Update metrics (count all appointments for the month for overview)
        const monthResponse = await fetch(`/get_appointments?date=${currentYear}-${String(currentMonth + 1).padStart(2, '0')}`, { credentials: 'include' });
        console.log('Month appointments response status:', monthResponse.status);
        if (!monthResponse.ok) throw new Error(`HTTP error! Status: ${monthResponse.status}`);
        const monthAppointments = await monthResponse.json();
        console.log('Month appointments:', monthAppointments);

        const referenceDate = new Date('2024-04-01T00:00:00');
        let upcoming = 0;
        let completed = 0;
        monthAppointments.forEach(a => {
            const date = new Date(a.date);
            if (date >= referenceDate) upcoming++;
            else completed++;
        });
        document.getElementById('upcomingAppointments').textContent = upcoming;
        document.getElementById('completedAppointments').textContent = completed;
    } catch (error) {
        console.error('Error loading appointments:', error.message);
        showError('errorMessage', 'Error loading appointments: ' + error.message);
    }
}




// ***************  Select a date on the calendar ****************
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

// ******************** Cancel an appointment *******************
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

// *********** Navigate calendar months ***********
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

// ************************ Handle voice commands ******************************
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

// **************** Load chat recipients ************************
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

// *************************   Send a chat message *******************
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
        if (socket) {
            socket.emit('chat_message', {
                user_id: userId,
                recipient_id: recipientId,
                message: message
            });
            chatInput.value = '';
        } else {
            console.error("SocketIO not initialized");
            showError('errorMessage', 'Real-time messaging unavailable');
        }
    } catch (error) {
        console.error('Error sending chat message:', error.message);
        showError('errorMessage', 'Error sending chat message: ' + error.message);
    }
}





// *********************** Fetch AI patient list for dropdown **************************
// Fetch patient list for dropdown
function loadPatientList() {
    fetch('/api/patients', { credentials: 'include' })
        .then(response => {
            console.log(`Response status for /api/patients: ${response.status}`);
            if (!response.ok) {
                throw new Error(`Failed to fetch patients: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Patients fetched:", data);
            const select = document.getElementById('ai-patient-select');
            if (!select) {
                console.error("Patient select element not found. Ensure <select id='ai-patient-select'> exists in ai_insights.html.");
                return;
            }
            select.innerHTML = '<option value="">Select a patient</option>';
            if (data && Array.isArray(data) && data.length > 0) {
                data.forEach(patient => {
                    const option = document.createElement('option');
                    option.value = patient.patient_id;
                    option.textContent = patient.name;
                    select.appendChild(option);
                });
            } else {
                select.innerHTML += '<option value="">No patients available</option>';
                console.warn("No patients found in response");
            }
        })
        .catch(error => {
            console.error("Error fetching patient list:", error.message);
            const select = document.getElementById('ai-patient-select');
            if (select) {
                select.innerHTML = '<option value="">Error loading patients</option>';
            }
        });
}









// ************************ Handle theme selection
function setupThemeSelection() {
    const select = document.getElementById('theme-select');
    const aiInsights = document.getElementById('ai-insights');
    const advancedAiInsights = document.getElementById('advanced-ai-insights');

    if (!select || !aiInsights || !advancedAiInsights) {
        console.error("Theme select or insights elements not found.");
        return;
    }

    // Load current theme from server
    fetch('/api/user', { credentials: 'include' })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to fetch user: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.theme) {
                select.value = data.theme;
                aiInsights.classList.remove('royal-blue', 'emerald-green', 'classic-white');
                advancedAiInsights.classList.remove('royal-blue', 'emerald-green', 'classic-white');
                aiInsights.classList.add(data.theme);
                advancedAiInsights.classList.add(data.theme);
                console.log("Initial theme loaded:", data.theme);
            }
        })
        .catch(error => {
            console.error("Error loading user theme:", error);
            aiInsights.classList.add('royal-blue'); // Fallback
            advancedAiInsights.classList.add('royal-blue');
        });

    select.addEventListener('change', () => {
        const theme = select.value;
        aiInsights.classList.remove('royal-blue', 'emerald-green', 'classic-white');
        advancedAiInsights.classList.remove('royal-blue', 'emerald-green', 'classic-white');
        aiInsights.classList.add(theme);
        advancedAiInsights.classList.add(theme);

        // Save theme preference
        fetch('/update_theme', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ theme }),
            credentials: 'include'
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Failed to save theme: ${response.status} ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                console.log("Theme saved:", data.theme);
            })
            .catch(error => {
                console.error("Error saving theme:", error);
                alert("Failed to save theme. Please try again.");
            });
    });
}


// Fetch prioritized tasks
function loadPrioritizedTasks() {
    const tasksList = document.getElementById('prioritized-tasks');
    if (!tasksList) {
        console.warn("Prioritized tasks element not found. Ensure <ul id='prioritized-tasks'> exists in ai_insights.html.");
        return;
    }

    fetch('/prioritize_tasks', { credentials: 'include' })
        .then(response => {
            console.log(`Response status for /prioritize_tasks: ${response.status}`);
            if (!response.ok) {
                throw new Error(`Failed to fetch prioritized tasks: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Prioritized tasks fetched:", data);
            if (data.prioritized_tasks && data.prioritized_tasks.length > 0) {
                tasksList.innerHTML = data.prioritized_tasks.map(task => `<li>${task.description} (Priority: ${task.priority.toFixed(2)})</li>`).join('');
            } else {
                tasksList.innerHTML = `<li>${data.error || 'No prioritized tasks available'}</li>`;
            }
        })
        .catch(error => {
            console.error("Error fetching prioritized tasks:", error.message);
            tasksList.innerHTML = `<li>Error loading tasks: ${error.message}</li>`;
        });
}


// Fetch appointments for /dashboard/appointments
function fetchAppointments() {
    const appointmentList = document.getElementById('appointment-list');
    if (!appointmentList) {
        console.warn("Appointment list element not found. Ensure <tbody id='appointment-list'> exists in appointments.html.");
        return;
    }

    fetch('/api/appointments', { credentials: 'include' })
        .then(response => {
            console.log(`Response status for /api/appointments: ${response.status}`);
            if (!response.ok) {
                throw new Error(`Failed to fetch appointments: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Appointments fetched:", data);
            if (data && Array.isArray(data) && data.length > 0) {
                appointmentList.innerHTML = data.map(appt => `
                    <tr class="border-b">
                        <td class="py-2 px-4">${appt.patient_name || 'Unknown'}</td>
                        <td class="py-2 px-4">${appt.doctor_name || 'Unknown'}</td>
                        <td class="py-2 px-4">${appt.date}</td>
                        <td class="py-2 px-4">${appt.time}</td>
                        <td class="py-2 px-4">${appt.status}</td>
                        <td class="py-2 px-4">${appt.reason || 'N/A'}</td>
                    </tr>
                `).join('');
            } else {
                appointmentList.innerHTML = `<tr><td colspan="6" class="py-2 px-4 text-center">No appointments available</td></tr>`;
            }
        })
        .catch(error => {
            console.error("Error fetching appointments:", error.message);
            appointmentList.innerHTML = `<tr><td colspan="6" class="py-2 px-4 text-center">Error loading appointments: ${error.message}</td></tr>`;
        });
}


// Fetch doctors for dropdown
function loadDoctors() {
    const doctorSelect = document.getElementById('doctor-id');
    if (!doctorSelect) {
        console.warn("Doctor select element not found. Ensure <select id='doctor-id'> exists in appointments.html.");
        return;
    }

    fetch('/api/doctors', { credentials: 'include' })
        .then(response => {
            console.log(`Response status for /api/doctors: ${response.status}`);
            if (!response.ok) {
                throw new Error(`Failed to fetch doctors: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Doctors fetched:", data);
            doctorSelect.innerHTML = '<option value="">Select a doctor</option>';
            if (data && Array.isArray(data) && data.length > 0) {
                data.forEach(doctor => {
                    const option = document.createElement('option');
                    option.value = doctor.id;
                    option.textContent = doctor.name;
                    doctorSelect.appendChild(option);
                });
            } else {
                doctorSelect.innerHTML += '<option value="">No doctors available</option>';
                console.warn("No doctors found in response");
            }
        })
        .catch(error => {
            console.error("Error fetching doctors:", error.message);
            doctorSelect.innerHTML = '<option value="">Error loading doctors</option>';
        });
}




// ***************************** Load dashboard content  ***********************************
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
        if (socket) {
            socket.emit('register_session', { user_id: userId });
        }

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

            // Initialize dynamic calendar
            const calendar = initializeCalendar();
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



// Handle manual appointment form submission
function handleAppointmentForm() {
    const form = document.getElementById('appointment-form');
    if (!form) {
        console.warn("Appointment form not found.");
        return;
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        const appointmentData = {
            patient_id: formData.get('patient_id'),
            doctor_id: formData.get('doctor_id'),
            date: formData.get('date'),
            time: formData.get('time'),
            reason: formData.get('reason')
        };

        if (!appointmentData.patient_id || !appointmentData.doctor_id || !appointmentData.date || !appointmentData.time || !appointmentData.reason) {
            showError('errorMessage', 'All fields are required.');
            return;
        }

        try {
            const response = await fetch('/api/appointments', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(appointmentData),
                credentials: 'include'
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || `HTTP error! Status: ${response.status}`);
            }
            showNotification('Appointment booked successfully!', 'info');
            form.reset();
            fetchAppointments();
        } catch (error) {
            console.error("Error booking appointment:", error.message);
            showError('errorMessage', `Error booking appointment: ${error.message}`);
        }
    });
}


// Handle AI-driven appointment scheduling
async function scheduleAppointment() {
    const patientId = document.getElementById('whatsapp-patient-select')?.value;
    if (!patientId) {
        showError('errorMessage', 'Please select a patient.');
        return;
    }

    try {
        const response = await fetch('/schedule_appointment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: patientId }),
            credentials: 'include'
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || `HTTP error! Status: ${response.status}`);
        }
        showNotification(`AI-scheduled appointment for ${result.slot}`, 'info');
        loadWhatsAppConversation();
    } catch (error) {
        console.error('Error scheduling appointment:', error.message);
        showError('errorMessage', `Error scheduling appointment: ${error.message}`);
    }
}


// *************** Handle logout ********************
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

// ************************* SocketIO event listeners ***********************
if (socket) {
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

    if (socket) {
        socket.on('new_message', (data) => {
            console.log('New message received:', data);
            const patientId = document.getElementById('whatsapp-patient-select')?.value;
            if (data.patient_id == patientId) {
                loadWhatsAppConversation();
            }
        });
    }

    // socket.on('appointment_scheduled', (data) => {
    //     console.log('Appointment scheduled:', data);
    //     loadAppointments();
    //     const calendar = initializeCalendar();
    //     if (calendar) {
    //         console.log("Refetching calendar events due to new appointment...");
    //         calendar.refetchEvents();
    //     }
    // });
    socket.on('appointment_scheduled', (data) => {
        console.log('Appointment scheduled:', data);
        showNotification(data.message, 'info');
        // Refresh appointments based on the current page
        if (document.getElementById('appointment-list')) {
            fetchAppointments(); // For appointments.html
        } else if (document.getElementById('calendar')) {
            loadAppointments(); // For dashboard.html
            const calendar = initializeCalendar();
            if (calendar) {
                console.log("Refetching calendar events due to new appointment...");
                calendar.refetchEvents();
            }
        }
    });

    // socket.on('appointment_canceled', (data) => {
    //     console.log('Appointment canceled:', data);
    //     loadAppointments();
    //     const calendar = initializeCalendar();
    //     if (calendar) {
    //         console.log("Refetching calendar events due to canceled appointment...");
    //         calendar.refetchEvents();
    //     }
    // });

    socket.on('appointment_canceled', (data) => {
        console.log('Appointment canceled:', data);
        showNotification('Appointment canceled successfully.', 'info');
        // Refresh appointments based on the current page
        if (document.getElementById('appointment-list')) {
            fetchAppointments(); // For appointments.html
        } else if (document.getElementById('calendar')) {
            loadAppointments(); // For dashboard.html
            const calendar = initializeCalendar();
            if (calendar) {
                console.log("Refetching calendar events due to canceled appointment...");
                calendar.refetchEvents();
            }
        }
    });


    socket.on('notification', (data) => {
        console.log('Notification received:', data);
        showNotification(data.message, data.type);
    });
    //Whats up Requirement 
    socket.on('emergency_alert', (data) => {
        console.log('Emergency alert received:', data);
        showNotification(`Emergency Alert: ${data.message}`, 'warning');
    });

    
} else {
    console.warn("SocketIO not available, real-time features disabled.");
}



// Highlight today's date in calendar
document.addEventListener('DOMContentLoaded', function() {
    
    const today = new Date();
    const todayCells = document.querySelectorAll('.calendar td');
    todayCells.forEach(cell => {
        if (cell.dataset.date === today.toISOString().split('T')[0]) {
            cell.classList.add('today');
        }
    });

    // Task prioritization (move high-priority tasks to top)
    const taskList = document.querySelectorAll('.task-item');
    taskList.forEach(task => {
        if (task.dataset.priority === 'High') {
            task.parentNode.prepend(task);
        }
    });
});





// ****************************** Initialize FullCalendar*************************************
// Initialize FullCalendar (for dashboard page)
function initializeCalendar() {
    const calendarEl = document.getElementById('calendar');
    if (!calendarEl) {
        console.warn("Calendar element not found. Ensure <div id='calendar'> exists in dashboard.html.");
        return;
    }
    try {
        console.log("Checking if FullCalendar is defined...");
        if (typeof FullCalendar === 'undefined') {
            console.error("FullCalendar is not defined. Ensure fullcalendar.min.js is loaded.");
            return;
        }
        console.log("Initializing FullCalendar...");

        // Display today's date
        const today = new Date();
        const todayFormatted = `${['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'][today.getMonth()]} ${today.getDate()}, ${today.getFullYear()}`;
        const todayDateEl = document.getElementById('today-date');
        if (todayDateEl) {
            todayDateEl.textContent = `Today: ${todayFormatted}`;
            console.log("Today's date displayed:", todayFormatted);
        } else {
            console.warn("Today's date element not found.");
        }

        const calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            initialDate: today,
            height: '500px',
            events: '/get_appointments',
            selectable: true,
            dateClick: function(info) {
                console.log("Date clicked:", info.dateStr);
                const dateInput = document.getElementById('addAppointmentDate');
                if (dateInput) {
                    dateInput.value = info.dateStr;
                    const modal = document.getElementById('addAppointmentModal');
                    if (modal) {
                        modal.classList.remove('hidden');
                        console.log("Add Appointment modal opened with date:", info.dateStr);
                    } else {
                        console.error("Add Appointment modal not found.");
                    }
                } else {
                    console.error("Add Appointment date input not found.");
                }
            },
            eventClick: function(info) {
                console.log("Event clicked:", info.event.id);
                window.location.href = '/edit_appointment/' + info.event.id;
            },
            eventClassNames: function(arg) {
                return arg.event.classNames;
            },
            eventsFetch: function(fetchInfo, successCallback, failureCallback) {
                console.log("Fetching events from /get_appointments...");
                fetch('/get_appointments', { credentials: 'include' })
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! Status: ${response.status} ${response.statusText}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        console.log("Events fetched:", data);
                        if (!Array.isArray(data)) {
                            console.warn("Events data is not an array:", data);
                            successCallback([]);
                        } else if (data.length === 0) {
                            console.warn("No events returned.");
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
        return calendar;
    } catch (e) {
        console.error("FullCalendar initialization failed:", e);
        return null;
    }
}




// ***************Fetch all AI-driven insights (for AI Insights page or dashboard page if applicable)*****************************
// Fetch all AI-driven insights
// function loadAllAIInsights(patientId) {
//     if (!patientId || isNaN(patientId)) {
//         console.warn("Invalid or missing patientId:", patientId);
//         ['suggested-appointments', 'health-trends', 'risk-clusters', 'no-show-predictions', 'follow-up-recommendations', 'med-interactions', 'vitals-alerts', 'resource-allocation', 'patient-sentiment', 'appointment-priority', 'follow-up-reminder', 'health-risk-prediction', 'triage-tasks', 'image-analysis', 'unified-data', 'wearable-monitoring', 'compliance-check', 'personalized-plan'].forEach(id => {
//             const element = document.getElementById(id);
//             if (element) {
//                 element.innerHTML = '<li>Please select a valid patient</li>';
//             } else {
//                 console.warn(`Element with id '${id}' not found in DOM. Ensure <ul id="${id}"> exists in ai_insights.html.`);
//             }
//         });
//         return;
//     }

//     console.log(`Fetching AI insights for patientId: ${patientId}`);
//     fetch(`/all_ai_insights/${patientId}`, { 
//         credentials: 'include',
//         headers: {
//             'Accept': 'application/json'
//         }
//     })
//         .then(response => {
//             console.log(`Response status for /all_ai_insights/${patientId}: ${response.status}`);
//             if (!response.ok) {
//                 return response.text().then(text => {
//                     throw new Error(`Failed to fetch AI insights: ${response.status} ${response.statusText} - ${text}`);
//                 });
//             }
//             return response.json();
//         })
//         .then(data => {
//             console.log("AI insights fetched:", data);




//             // Patient Notes from Transcription
//             const notesList = document.getElementById('patient-notes');
//             if (notesList) {
//                 fetch(`/api/patient_notes/${patientId}`, { credentials: 'include' })
//                     .then(response => {
//                         if (!response.ok) {
//                             return response.json().then(err => {
//                                 throw new Error(err.error || `Failed to fetch patient notes (Status: ${response.status})`);
//                             });
//                         }
//                         return response.json();
//                     })
//                     .then(data => {
//                         if (data && data.length > 0) {
//                             // notesList.innerHTML = data.map(note => `<li>${note.date}: ${note.note}</li>`).join('');
//                             notesList.innerHTML = data.map(note => `<li>${note.created_at || 'No date available'}: ${note.note}</li>`).join('');
//                         } else {
//                             notesList.innerHTML = '<li>No notes available</li>';
//                         }
//                     })
//                     .catch(error => {
//                         console.error("Error fetching patient notes:", error.message);
//                         notesList.innerHTML = `<li>Error loading notes: ${error.message}</li>`;
//                     });
//             } else {
//                 console.warn("Patient notes element not found. Ensure <ul id='patient-notes'> exists in ai_insights.html.");
//             }



//             // Suggested Appointments
//             const apptList = document.getElementById('suggested-appointments');
//             if (apptList) {
//                 if (data.suggested_appointments && data.suggested_appointments.suggested_slots && data.suggested_appointments.suggested_slots.length > 0) {
//                     apptList.innerHTML = data.suggested_appointments.suggested_slots.map(slot => `<li>${slot}</li>`).join('');
//                 } else {
//                     apptList.innerHTML = `<li>${data.suggested_appointments && data.suggested_appointments.error ? data.suggested_appointments.error : 'No suggestions available'}</li>`;
//                 }
//             } else {
//                 console.warn("Suggested appointments element not found. Ensure <ul id='suggested-appointments'> exists in ai_insights.html.");
//             }

//             // Health Trends
//             const trendsList = document.getElementById('health-trends');
//             if (trendsList) {
//                 if (data.health_trends && data.health_trends.trends && data.health_trends.trends.risk) {
//                     trendsList.innerHTML = `<li>Risk: ${data.health_trends.trends.risk}</li>`;
//                 } else {
//                     trendsList.innerHTML = `<li>${data.health_trends && data.health_trends.error ? data.health_trends.error : 'No trends available'}</li>`;
//                 }
//             } else {
//                 console.warn("Health trends element not found. Ensure <ul id='health-trends'> exists in ai_insights.html.");
//             }

//             // Patient Risk Clusters
//             const clustersList = document.getElementById('risk-clusters');
//             if (clustersList) {
//                 if (data.risk_clusters && data.risk_clusters.clusters && data.risk_clusters.clusters.length > 0) {
//                     clustersList.innerHTML = data.risk_clusters.clusters.map(c => `<li>${c.name}: ${c.cluster_label}</li>`).join('');
//                 } else {
//                     clustersList.innerHTML = `<li>${data.risk_clusters && data.risk_clusters.error ? data.risk_clusters.error : 'No clusters available'}</li>`;
//                 }
//             } else {
//                 console.warn("Risk clusters element not found. Ensure <ul id='risk-clusters'> exists in ai_insights.html.");
//             }

//             // No-Show Predictions
//             const noShowList = document.getElementById('no-show-predictions');
//             if (noShowList) {
//                 if (data.no_show_prediction && data.no_show_prediction.no_show_probability !== undefined) {
//                     noShowList.innerHTML = `<li>No-Show Probability: ${(data.no_show_prediction.no_show_probability * 100).toFixed(2)}%</li>`;
//                 } else {
//                     noShowList.innerHTML = `<li>${data.no_show_prediction && data.no_show_prediction.error ? data.no_show_prediction.error : 'No predictions available'}</li>`;
//                 }
//             } else {
//                 console.warn("No-show predictions element not found. Ensure <ul id='no-show-predictions'> exists in ai_insights.html.");
//             }

//             // Follow-Up Recommendations
//             const followUpList = document.getElementById('follow-up-recommendations');
//             if (followUpList) {
//                 if (data.follow_up_recommendations && data.follow_up_recommendations.recommendation && data.follow_up_recommendations.recommendation.follow_up) {
//                     followUpList.innerHTML = `<li>${data.follow_up_recommendations.recommendation.follow_up}</li>`;
//                 } else {
//                     followUpList.innerHTML = `<li>${data.follow_up_recommendations && data.follow_up_recommendations.error ? data.follow_up_recommendations.error : 'No recommendations available'}</li>`;
//                 }
//             } else {
//                 console.warn("Follow-up recommendations element not found. Ensure <ul id='follow-up-recommendations'> exists in ai_insights.html.");
//             }

//             // Medication Interactions
//             const medList = document.getElementById('med-interactions');
//             if (medList) {
//                 if (data.med_interactions && data.med_interactions.interactions && data.med_interactions.interactions.length > 0) {
//                     medList.innerHTML = data.med_interactions.interactions.map(i => `<li>${i.medications.join(' + ')}: ${i.warning}</li>`).join('');
//                 } else {
//                     medList.innerHTML = `<li>${data.med_interactions && data.med_interactions.error ? data.med_interactions.error : 'No interactions detected'}</li>`;
//                 }
//             } else {
//                 console.warn("Medication interactions element not found. Ensure <ul id='med-interactions'> exists in ai_insights.html.");
//             }

//             // Real-Time Vitals Alerts
//             const vitalsList = document.getElementById('vitals-alerts');
//             if (vitalsList) {
//                 if (data.vitals_alerts && data.vitals_alerts.alerts && data.vitals_alerts.alerts.length > 0) {
//                     vitalsList.innerHTML = data.vitals_alerts.alerts.map(alert => `<li>${alert}</li>`).join('');
//                 } else {
//                     vitalsList.innerHTML = `<li>${data.vitals_alerts && data.vitals_alerts.error ? data.vitals_alerts.error : 'No active alerts'}</li>`;
//                 }
//             } else {
//                 console.warn("Vitals alerts element not found. Ensure <ul id='vitals-alerts'> exists in ai_insights.html.");
//             }

//             // Resource Allocation
//             const resourceList = document.getElementById('resource-allocation');
//             if (resourceList) {
//                 if (data.resource_allocation && data.resource_allocation.recommendations && data.resource_allocation.recommendations.length > 0) {
//                     resourceList.innerHTML = data.resource_allocation.recommendations.map(r => `<li>${r.date}: ${r.staff_needed} staff, ${r.equipment_needed} equipment</li>`).join('');
//                 } else {
//                     resourceList.innerHTML = `<li>${data.resource_allocation && data.resource_allocation.error ? data.resource_allocation.error : 'No recommendations available'}</li>`;
//                 }
//             } else {
//                 console.warn("Resource allocation element not found. Ensure <ul id='resource-allocation'> exists in ai_insights.html.");
//             }

//             // Patient Sentiment
//             const sentimentList = document.getElementById('patient-sentiment');
//             if (sentimentList) {
//                 if (data.patient_sentiment && data.patient_sentiment.sentiment) {
//                     sentimentList.innerHTML = `<li>Sentiment: ${data.patient_sentiment.sentiment} (Confidence: ${(data.patient_sentiment.confidence * 100).toFixed(2)}%)</li>`;
//                 } else {
//                     sentimentList.innerHTML = `<li>${data.patient_sentiment && data.patient_sentiment.error ? data.patient_sentiment.error : 'No sentiment available'}</li>`;
//                 }
//             } else {
//                 console.warn("Patient sentiment element not found. Ensure <ul id='patient-sentiment'> exists in ai_insights.html.");
//             }

//             // Appointment Priority
//             const priorityList = document.getElementById('appointment-priority');
//             if (priorityList) {
//                 if (data.appointment_priority && data.appointment_priority.priority_level) {
//                     priorityList.innerHTML = `<li>Priority: ${data.appointment_priority.priority_level} (Score: ${data.appointment_priority.priority_score.toFixed(2)})</li>`;
//                 } else {
//                     priorityList.innerHTML = `<li>${data.appointment_priority && data.appointment_priority.error ? data.appointment_priority.error : 'No priority available'}</li>`;
//                 }
//             } else {
//                 console.warn("Appointment priority element not found. Ensure <ul id='appointment-priority'> exists in ai_insights.html.");
//             }

//             // Follow-Up Reminder
//             const reminderList = document.getElementById('follow-up-reminder');
//             if (reminderList) {
//                 if (data.follow_up_reminder && data.follow_up_reminder.reminder) {
//                     reminderList.innerHTML = `<li>${data.follow_up_reminder.reminder}</li>`;
//                 } else {
//                     reminderList.innerHTML = `<li>${data.follow_up_reminder && data.follow_up_reminder.error ? data.follow_up_reminder.error : 'No reminder available'}</li>`;
//                 }
//             } else {
//                 console.warn("Follow-up reminder element not found. Ensure <ul id='follow-up-reminder'> exists in ai_insights.html.");
//             }

//             // Patient Summary (Chart)
//             const summaryCanvas = document.getElementById('patient-summary-chart');
//             if (summaryCanvas && data.patient_summary && data.patient_summary.vitals) {
//                 // Destroy existing chart instance if it exists
//                 if (patientSummaryChartInstance) {
//                     patientSummaryChartInstance.destroy();
//                     patientSummaryChartInstance = null;
//                 }
//                 patientSummaryChartInstance = new Chart(summaryCanvas, {
//                     type: 'line',
//                     data: {
//                         labels: data.patient_summary.labels || ['Latest'],
//                         datasets: [{
//                             label: 'Heart Rate',
//                             data: data.patient_summary.vitals.map(v => v.heart_rate || 0),
//                             borderColor: 'blue',
//                             fill: false
//                         }, {
//                             label: 'Blood Pressure',
//                             data: data.patient_summary.vitals.map(v => v.heart_rate || 0),
//                             borderColor: 'red',
//                             fill: false
//                         }]
//                     },
//                     options: { responsive: true }
//                 });
//             } else {
//                 console.warn("Patient summary chart element or data not found. Ensure <canvas id='patient-summary-chart'> exists in ai_insights.html.");
//             }

//             // Health Risk Prediction
//             const riskList = document.getElementById('health-risk-prediction');
//             if (riskList) {
//                 if (data.health_risk_prediction && data.health_risk_prediction.alert) {
//                     riskList.innerHTML = `<li>${data.health_risk_prediction.alert} (<a href="${data.health_risk_prediction.guideline}" target="_blank">Guideline</a>)</li>`;
//                 } else {
//                     riskList.innerHTML = `<li>${data.health_risk_prediction && data.health_risk_prediction.error ? data.health_risk_prediction.error : 'No risk alerts'}</li>`;
//                 }
//             } else {
//                 console.warn("Health risk prediction element not found. Ensure <ul id='health-risk-prediction'> exists in ai_insights.html.");
//             }

//             // Triaged Tasks
//             const triageList = document.getElementById('triage-tasks');
//             if (triageList) {
//                 if (data.triage_tasks && data.triage_tasks.triaged_tasks && data.triage_tasks.triaged_tasks.length > 0) {
//                     triageList.innerHTML = data.triage_tasks.triaged_tasks.map(t => `<li>${t.description} (Score: ${t.triage_score.toFixed(2)})</li>`).join('');
//                 } else {
//                     triageList.innerHTML = `<li>${data.triage_tasks && data.triage_tasks.error ? data.triage_tasks.error : 'No triaged tasks'}</li>`;
//                 }
//             } else {
//                 console.warn("Triage tasks element not found. Ensure <ul id='triage-tasks'> exists in ai_insights.html.");
//             }

//             // Image Analysis
//             const imageList = document.getElementById('image-analysis');
//             if (imageList) {
//                 if (data.image_analysis && data.image_analysis.condition) {
//                     imageList.innerHTML = `<li>${data.image_analysis.condition} (Confidence: ${(data.image_analysis.confidence * 100).toFixed(2)}%)</li>`;
//                 } else {
//                     imageList.innerHTML = `<li>${data.image_analysis && data.image_analysis.error ? data.image_analysis.error : 'No diagnosis available'}</li>`;
//                 }
//             } else {
//                 console.warn("Image analysis element not found. Ensure <ul id='image-analysis'> exists in ai_insights.html.");
//             }

//             // Unified Data
//             const unifiedList = document.getElementById('unified-data');
//             if (unifiedList) {
//                 if (data.unified_data && data.unified_data.ehr) {
//                     unifiedList.innerHTML = `<li>EHR: ${data.unified_data.ehr.history}</li>`;
//                 } else {
//                     unifiedList.innerHTML = `<li>${data.unified_data && data.unified_data.error ? data.unified_data.error : 'No unified data'}</li>`;
//                 }
//             } else {
//                 console.warn("Unified data element not found. Ensure <ul id='unified-data'> exists in ai_insights.html.");
//             }

//             // Wearable Monitoring
//             const wearableList = document.getElementById('wearable-monitoring');
//             if (wearableList) {
//                 if (data.wearable_monitoring && data.wearable_monitoring.alert) {
//                     wearableList.innerHTML = `<li>${data.wearable_monitoring.alert} (HR: ${data.wearable_monitoring.heart_rate})</li>`;
//                 } else {
//                     wearableList.innerHTML = `<li>${data.wearable_monitoring && data.wearable_monitoring.error ? data.wearable_monitoring.error : 'No wearable data'}</li>`;
//                 }
//             } else {
//                 console.warn("Wearable monitoring element not found. Ensure <ul id='wearable-monitoring'> exists in ai_insights.html.");
//             }

//             // Compliance Check
//             const complianceList = document.getElementById('compliance-check');
//             if (complianceList) {
//                 if (data.compliance_check && data.compliance_check.status) {
//                     complianceList.innerHTML = `<li>${data.compliance_check.status} (Audit: ${data.compliance_check.audit_trail})</li>`;
//                 } else {
//                     complianceList.innerHTML = `<li>${data.compliance_check && data.compliance_check.error ? data.compliance_check.error : 'No compliance data'}</li>`;
//                 }
//             } else {
//                 console.warn("Compliance check element not found. Ensure <ul id='compliance-check'> exists in ai_insights.html.");
//             }

//             // Personalized Plan
//             const planList = document.getElementById('personalized-plan');
//             if (planList) {
//                 if (data.personalized_plan && data.personalized_plan.recommendations && data.personalized_plan.recommendations.length > 0) {
//                     planList.innerHTML = data.personalized_plan.recommendations.map(r => `<li>${r}</li>`).join('');
//                 } else {
//                     planList.innerHTML = `<li>${data.personalized_plan && data.personalized_plan.error ? data.personalized_plan.error : 'No plan available'}</li>`;
//                 }
//             } else {
//                 console.warn("Personalized plan element not found. Ensure <ul id='personalized-plan'> exists in ai_insights.html.");
//             }
//         })
//         .catch(error => {
//             console.error("Error fetching AI insights:", error.message);
//             ['suggested-appointments', 'health-trends', 'risk-clusters', 'no-show-predictions', 'follow-up-recommendations', 'med-interactions', 'vitals-alerts', 'resource-allocation', 'patient-sentiment', 'appointment-priority', 'follow-up-reminder', 'health-risk-prediction', 'triage-tasks', 'image-analysis', 'unified-data', 'wearable-monitoring', 'compliance-check', 'personalized-plan'].forEach(id => {
//                 const element = document.getElementById(id);
//                 if (element) {
//                     element.innerHTML = `<li>Error loading data: ${error.message}</li>`;
//                 } else {
//                     console.warn(`Element with id '${id}' not found in DOM. Ensure <ul id="${id}"> exists in ai_insights.html.`);
//                 }
//             });
//         });
// }


function loadAllAIInsights(patientId) {
    if (!patientId || isNaN(patientId)) {
        console.warn("Invalid or missing patientId:", patientId);
        ['suggested-appointments', 'health-trends', 'risk-clusters', 'no-show-predictions', 'follow-up-recommendations', 'med-interactions', 'vitals-alerts', 'resource-allocation', 'patient-sentiment', 'appointment-priority', 'follow-up-reminder', 'health-risk-prediction', 'triage-tasks', 'image-analysis', 'unified-data', 'wearable-monitoring', 'compliance-check', 'personalized-plan'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.innerHTML = '<li>Please select a valid patient</li>';
            } else {
                console.warn(`Element with id '${id}' not found in DOM. Ensure <ul id="${id}"> exists in ai_insights.html.`);
            }
        });
        return;
    }
    console.log(`Fetching AI insights for patientId: ${patientId}`);
    fetch(`/all_ai_insights/${patientId}`, { 
        credentials: 'include',
        headers: { 'Accept': 'application/json' }
    })
        .then(response => {
            console.log(`Response status for /all_ai_insights/${patientId}: ${response.status}`);
            if (!response.ok) {
                return response.text().then(text => {
                    throw new Error(`Failed to fetch AI insights: ${response.status} ${response.statusText} - ${text}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log("AI insights fetched:", data);
            // Patient Notes from Transcription
            const notesList = document.getElementById('patient-notes');
            if (notesList) {
                fetch(`/api/patient_notes/${patientId}`, { credentials: 'include' })
                    .then(response => {
                        if (!response.ok) {
                            return response.json().then(err => {
                                throw new Error(err.error || `Failed to fetch patient notes (Status: ${response.status})`);
                            });
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (data && data.length > 0) {
                            notesList.innerHTML = data.map(note => `<li>${note.created_at || 'No date available'}: ${note.note}</li>`).join('');
                        } else {
                            notesList.innerHTML = '<li>No notes available</li>';
                        }
                    })
                    .catch(error => {
                        console.error("Error fetching patient notes:", error.message);
                        notesList.innerHTML = `<li>Error loading notes: ${error.message}</li>`;
                    });
            } else {
                console.warn("Patient notes element not found. Ensure <ul id='patient-notes'> exists in ai_insights.html.");
            }
            // Structured Medical Notes (SOAP)
            const medicalNotesList = document.getElementById('medical-notes');
            if (medicalNotesList) {
                fetch(`/medical_notes/${patientId}`, { credentials: 'include' })
                    .then(response => {
                        if (!response.ok) throw new Error('Failed to fetch medical notes');
                        return response.json();
                    })
                    .then(notes => {
                        medicalNotesList.innerHTML = notes.length === 0
                            ? '<p class="text-gray-500">No structured medical notes found.</p>'
                            : notes.map(note => `
                                <div class="p-2 bg-gray-100 rounded mb-2">
                                    <p><strong>Created At:</strong> ${note.created_at}</p>
                                    <p><strong>Subjective:</strong> ${note.subjective}</p>
                                    <p><strong>Objective:</strong> ${note.objective}</p>
                                    <p><strong>Assessment:</strong> ${note.assessment}</p>
                                    <p><strong>Plan:</strong> ${note.plan}</p>
                                </div>
                            `).join('');
                    })
                    .catch(error => {
                        console.error("Error fetching medical notes:", error.message);
                        medicalNotesList.innerHTML = `<p class="text-gray-500">Error loading structured notes: ${error.message}</p>`;
                    });
            }
            // Suggested Appointments
            const apptList = document.getElementById('suggested-appointments');
            if (apptList) {
                if (data.suggested_appointments && data.suggested_appointments.suggested_slots && data.suggested_appointments.suggested_slots.length > 0) {
                    apptList.innerHTML = data.suggested_appointments.suggested_slots.map(slot => `<li>${slot}</li>`).join('');
                } else {
                    apptList.innerHTML = `<li>${data.suggested_appointments && data.suggested_appointments.error ? data.suggested_appointments.error : 'No suggestions available'}</li>`;
                }
            } else {
                console.warn("Suggested appointments element not found. Ensure <ul id='suggested-appointments'> exists in ai_insights.html.");
            }
            // Health Trends
            const trendsList = document.getElementById('health-trends');
            if (trendsList) {
                if (data.health_trends && data.health_trends.trends && data.health_trends.trends.risk) {
                    trendsList.innerHTML = `<li>Risk: ${data.health_trends.trends.risk}</li>`;
                } else {
                    trendsList.innerHTML = `<li>${data.health_trends && data.health_trends.error ? data.health_trends.error : 'No trends available'}</li>`;
                }
            } else {
                console.warn("Health trends element not found. Ensure <ul id='health-trends'> exists in ai_insights.html.");
            }
            // Patient Risk Clusters
            const clustersList = document.getElementById('risk-clusters');
            if (clustersList) {
                if (data.risk_clusters && data.risk_clusters.clusters && data.risk_clusters.clusters.length > 0) {
                    clustersList.innerHTML = data.risk_clusters.clusters.map(c => `<li>${c.name}: ${c.cluster_label}</li>`).join('');
                } else {
                    clustersList.innerHTML = `<li>${data.risk_clusters && data.risk_clusters.error ? data.risk_clusters.error : 'No clusters available'}</li>`;
                }
            } else {
                console.warn("Risk clusters element not found. Ensure <ul id='risk-clusters'> exists in ai_insights.html.");
            }
            // No-Show Predictions
            const noShowList = document.getElementById('no-show-predictions');
            if (noShowList) {
                if (data.no_show_prediction && data.no_show_prediction.no_show_probability !== undefined) {
                    noShowList.innerHTML = `<li>No-Show Probability: ${(data.no_show_prediction.no_show_probability * 100).toFixed(2)}%</li>`;
                } else {
                    noShowList.innerHTML = `<li>${data.no_show_prediction && data.no_show_prediction.error ? data.no_show_prediction.error : 'No predictions available'}</li>`;
                }
            } else {
                console.warn("No-show predictions element not found. Ensure <ul id='no-show-predictions'> exists in ai_insights.html.");
            }
            // Follow-Up Recommendations
            const followUpList = document.getElementById('follow-up-recommendations');
            if (followUpList) {
                if (data.follow_up_recommendations && data.follow_up_recommendations.recommendation && data.follow_up_recommendations.recommendation.follow_up) {
                    followUpList.innerHTML = `<li>${data.follow_up_recommendations.recommendation.follow_up}</li>`;
                } else {
                    followUpList.innerHTML = `<li>${data.follow_up_recommendations && data.follow_up_recommendations.error ? data.follow_up_recommendations.error : 'No recommendations available'}</li>`;
                }
            } else {
                console.warn("Follow-up recommendations element not found. Ensure <ul id='follow-up-recommendations'> exists in ai_insights.html.");
            }
            // Medication Interactions
            const medList = document.getElementById('med-interactions');
            if (medList) {
                if (data.med_interactions && data.med_interactions.interactions && data.med_interactions.interactions.length > 0) {
                    medList.innerHTML = data.med_interactions.interactions.map(i => `<li>${i.medications.join(' + ')}: ${i.warning}</li>`).join('');
                } else {
                    medList.innerHTML = `<li>${data.med_interactions && data.med_interactions.error ? data.med_interactions.error : 'No interactions detected'}</li>`;
                }
            } else {
                console.warn("Medication interactions element not found. Ensure <ul id='med-interactions'> exists in ai_insights.html.");
            }
            // Real-Time Vitals Alerts
            const vitalsList = document.getElementById('vitals-alerts');
            if (vitalsList) {
                if (data.vitals_alerts && data.vitals_alerts.alerts && data.vitals_alerts.alerts.length > 0) {
                    vitalsList.innerHTML = data.vitals_alerts.alerts.map(alert => `<li>${alert}</li>`).join('');
                } else {
                    vitalsList.innerHTML = `<li>${data.vitals_alerts && data.vitals_alerts.error ? data.vitals_alerts.error : 'No active alerts'}</li>`;
                }
            } else {
                console.warn("Vitals alerts element not found. Ensure <ul id='vitals-alerts'> exists in ai_insights.html.");
            }
            // Resource Allocation
            const resourceList = document.getElementById('resource-allocation');
            if (resourceList) {
                if (data.resource_allocation && data.resource_allocation.recommendations && data.resource_allocation.recommendations.length > 0) {
                    resourceList.innerHTML = data.resource_allocation.recommendations.map(r => `<li>${r.date}: ${r.staff_needed} staff, ${r.equipment_needed} equipment</li>`).join('');
                } else {
                    resourceList.innerHTML = `<li>${data.resource_allocation && data.resource_allocation.error ? data.resource_allocation.error : 'No recommendations available'}</li>`;
                }
            } else {
                console.warn("Resource allocation element not found. Ensure <ul id='resource-allocation'> exists in ai_insights.html.");
            }
            // Patient Sentiment
            const sentimentList = document.getElementById('patient-sentiment');
            if (sentimentList) {
                if (data.patient_sentiment && data.patient_sentiment.sentiment) {
                    sentimentList.innerHTML = `<li>Sentiment: ${data.patient_sentiment.sentiment} (Confidence: ${(data.patient_sentiment.confidence * 100).toFixed(2)}%)</li>`;
                } else {
                    sentimentList.innerHTML = `<li>${data.patient_sentiment && data.patient_sentiment.error ? data.patient_sentiment.error : 'No sentiment available'}</li>`;
                }
            } else {
                console.warn("Patient sentiment element not found. Ensure <ul id='patient-sentiment'> exists in ai_insights.html.");
            }
            // Appointment Priority
            const priorityList = document.getElementById('appointment-priority');
            if (priorityList) {
                if (data.appointment_priority && data.appointment_priority.priority_level) {
                    priorityList.innerHTML = `<li>Priority: ${data.appointment_priority.priority_level} (Score: ${data.appointment_priority.priority_score.toFixed(2)})</li>`;
                } else {
                    priorityList.innerHTML = `<li>${data.appointment_priority && data.appointment_priority.error ? data.appointment_priority.error : 'No priority available'}</li>`;
                }
            } else {
                console.warn("Appointment priority element not found. Ensure <ul id='appointment-priority'> exists in ai_insights.html.");
            }
            // Follow-Up Reminder
            const reminderList = document.getElementById('follow-up-reminder');
            if (reminderList) {
                if (data.follow_up_reminder && data.follow_up_reminder.reminder) {
                    reminderList.innerHTML = `<li>${data.follow_up_reminder.reminder}</li>`;
                } else {
                    reminderList.innerHTML = `<li>${data.follow_up_reminder && data.follow_up_reminder.error ? data.follow_up_reminder.error : 'No reminder available'}</li>`;
                }
            } else {
                console.warn("Follow-up reminder element not found. Ensure <ul id='follow-up-reminder'> exists in ai_insights.html.");
            }
            // Patient Summary (Chart and Text)
            // Patient Summary (Chart and Text)
            const summaryCanvas = document.getElementById('patient-summary-chart');
            const ehrSummaryList = document.getElementById('ehr-summary-list');
            if (summaryCanvas && ehrSummaryList && data.patient_summary && data.patient_summary.vitals) {
                // Destroy existing chart instance if it exists
                if (patientSummaryChartInstance) {
                    patientSummaryChartInstance.destroy();
                    patientSummaryChartInstance = null;
                }
                patientSummaryChartInstance = new Chart(summaryCanvas, {
                    type: 'line',
                    data: {
                        labels: data.patient_summary.vitals.labels || ['Latest'],
                        datasets: [{
                            label: 'Heart Rate',
                            data: [data.patient_summary.vitals.heart_rate],
                            borderColor: 'blue',
                            fill: false
                        }, {
                            label: 'Blood Pressure (Systolic)',
                            data: [data.patient_summary.vitals.bp_systolic],
                            borderColor: 'red',
                            fill: false
                        }]
                    },
                    options: { responsive: true }
                });

                // Render textual EHR summary
                ehrSummaryList.innerHTML = `
                    <li><strong>Medical History:</strong> ${data.patient_summary.medical_history}</li>
                    <li><strong>Medications:</strong> ${data.patient_summary.medications}</li>
                    <li><strong>Recent Appointments:</strong> ${
                        data.patient_summary.recent_appointments.length > 0
                            ? data.patient_summary.recent_appointments.map(appt => `${appt.date} ${appt.time} with ${appt.doctor_name} (${appt.status})`).join(', ')
                            : 'No recent appointments'
                    }</li>
                    <li><strong>Recent Notes:</strong> ${
                        data.patient_summary.recent_notes.length > 0
                            ? data.patient_summary.recent_notes.map(note => `${note.created_at}: ${note.subjective} (Assessment: ${note.assessment})`).join('; ')
                            : 'No recent notes'
                    }</li>
                `;
            } else {
                console.warn("Patient summary chart or EHR summary list element not found.");
                if (ehrSummaryList) {
                    ehrSummaryList.innerHTML = '<li>No summary available</li>';
                }
            }




            // Health Risk Prediction
            const riskList = document.getElementById('health-risk-prediction');
            if (riskList) {
                if (data.health_risk_prediction && data.health_risk_prediction.alert) {
                    riskList.innerHTML = `<li>${data.health_risk_prediction.alert} (<a href="${data.health_risk_prediction.guideline}" target="_blank">Guideline</a>)</li>`;
                } else {
                    riskList.innerHTML = `<li>${data.health_risk_prediction && data.health_risk_prediction.error ? data.health_risk_prediction.error : 'No risk alerts'}</li>`;
                }
            } else {
                console.warn("Health risk prediction element not found. Ensure <ul id='health-risk-prediction'> exists in ai_insights.html.");
            }
            // Triaged Tasks
            const triageList = document.getElementById('triage-tasks');
            if (triageList) {
                if (data.triage_tasks && data.triage_tasks.triaged_tasks && data.triage_tasks.triaged_tasks.length > 0) {
                    triageList.innerHTML = data.triage_tasks.triaged_tasks.map(t => `<li>${t.description} (Score: ${t.triage_score.toFixed(2)})</li>`).join('');
                } else {
                    triageList.innerHTML = `<li>${data.triage_tasks && data.triage_tasks.error ? data.triage_tasks.error : 'No triaged tasks'}</li>`;
                }
            } else {
                console.warn("Triage tasks element not found. Ensure <ul id='triage-tasks'> exists in ai_insights.html.");
            }
            // Image Analysis
            const imageList = document.getElementById('image-analysis');
            if (imageList) {
                if (data.image_analysis && data.image_analysis.condition) {
                    imageList.innerHTML = `<li>${data.image_analysis.condition} (Confidence: ${(data.image_analysis.confidence * 100).toFixed(2)}%)</li>`;
                } else {
                    imageList.innerHTML = `<li>${data.image_analysis && data.image_analysis.error ? data.image_analysis.error : 'No diagnosis available'}</li>`;
                }
            } else {
                console.warn("Image analysis element not found. Ensure <ul id='image-analysis'> exists in ai_insights.html.");
            }
            // Unified Data
            const unifiedList = document.getElementById('unified-data');
            if (unifiedList) {
                if (data.unified_data && data.unified_data.ehr) {
                    unifiedList.innerHTML = `<li>EHR: ${data.unified_data.ehr.history}</li>`;
                } else {
                    unifiedList.innerHTML = `<li>${data.unified_data && data.unified_data.error ? data.unified_data.error : 'No unified data'}</li>`;
                }
            } else {
                console.warn("Unified data element not found. Ensure <ul id='unified-data'> exists in ai_insights.html.");
            }
            // Wearable Monitoring
            const wearableList = document.getElementById('wearable-monitoring');
            if (wearableList) {
                if (data.wearable_monitoring && data.wearable_monitoring.alert) {
                    wearableList.innerHTML = `<li>${data.wearable_monitoring.alert} (HR: ${data.wearable_monitoring.heart_rate})</li>`;
                } else {
                    wearableList.innerHTML = `<li>${data.wearable_monitoring && data.wearable_monitoring.error ? data.wearable_monitoring.error : 'No wearable data'}</li>`;
                }
            } else {
                console.warn("Wearable monitoring element not found. Ensure <ul id='wearable-monitoring'> exists in ai_insights.html.");
            }
            // Compliance Check
            const complianceList = document.getElementById('compliance-check');
            if (complianceList) {
                if (data.compliance_check && data.compliance_check.status) {
                    complianceList.innerHTML = `<li>${data.compliance_check.status} (Audit: ${data.compliance_check.audit_trail})</li>`;
                } else {
                    complianceList.innerHTML = `<li>${data.compliance_check && data.compliance_check.error ? data.compliance_check.error : 'No compliance data'}</li>`;
                }
            } else {
                console.warn("Compliance check element not found. Ensure <ul id='compliance-check'> exists in ai_insights.html.");
            }
            // Personalized Plan
            const planList = document.getElementById('personalized-plan');
            if (planList) {
                if (data.personalized_plan && data.personalized_plan.recommendations && data.personalized_plan.recommendations.length > 0) {
                    planList.innerHTML = data.personalized_plan.recommendations.map(r => `<li>${r}</li>`).join('');
                } else {
                    planList.innerHTML = `<li>${data.personalized_plan && data.personalized_plan.error ? data.personalized_plan.error : 'No plan available'}</li>`;
                }
            } else {
                console.warn("Personalized plan element not found. Ensure <ul id='personalized-plan'> exists in ai_insights.html.");
            }
        })
        .catch(error => {
            console.error("Error fetching AI insights:", error.message);
            ['suggested-appointments', 'health-trends', 'risk-clusters', 'no-show-predictions', 'follow-up-recommendations', 'med-interactions', 'vitals-alerts', 'resource-allocation', 'patient-sentiment', 'appointment-priority', 'follow-up-reminder', 'health-risk-prediction', 'triage-tasks', 'image-analysis', 'unified-data', 'wearable-monitoring', 'compliance-check', 'personalized-plan'].forEach(id => {
                const element = document.getElementById(id);
                if (element) {
                    element.innerHTML = `<li>Error loading data: ${error.message}</li>`;
                } else {
                    console.warn(`Element with id '${id}' not found in DOM. Ensure <ul id="${id}"> exists in ai_insights.html.`);
                }
            });
        });
}

// ********************** Handle real-time vitals alerts *********************************
// Handle real-time vitals alerts
function setupVitalsAlerts() {
    if (socket) {
        socket.on('vitals_alert', (data) => {
            console.log('Vitals alert received:', data);
            const list = document.getElementById('vitals-alerts');
            if (list) {
                if (data.alerts && data.alerts.length > 0) {
                    list.innerHTML = data.alerts.map(alert => `<li>${alert}</li>`).join('');
                } else {
                    list.innerHTML = '<li>No active alerts</li>';
                }
                setTimeout(() => {
                    list.innerHTML = '<li>No active alerts</li>';
                }, 10000); // Clear after 10 seconds
            } else {
                console.warn("Vitals alerts element not found. Ensure <ul id='vitals-alerts'> exists in ai_insights.html.");
            }
        });
    } else {
        console.warn("SocketIO not available, vitals alerts disabled.");
    }
}




// ***************** Transcription functionality ***********************
// Transcription functionality
// function setupTranscription() {
//     const transcribeButton = document.getElementById('transcribe-button');
//     if (!transcribeButton) {
//         console.warn("Transcribe button not found.");
//         return;
//     }

//     // Check if SpeechRecognition is supported
//     const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
//     if (!SpeechRecognition) {
//         console.error("SpeechRecognition not supported in this browser.");
//         showError('errorMessage', 'Speech recognition is not supported in this browser. Please use a modern browser like Chrome.');
//         transcribeButton.disabled = true;
//         return;
//     }

//     let isTranscribing = false;
//     const recognition = new SpeechRecognition();
//     recognition.lang = 'en-US';
//     recognition.interimResults = true;
//     recognition.continuous = true;

//     transcribeButton.addEventListener('click', async () => {
//         const patientSelect = document.getElementById('ai-patient-select');
//         const patientId = patientSelect?.value;

//         if (!patientId) {
//             showError('errorMessage', 'Please select a patient to transcribe.');
//             return;
//         }

//         try {
//             // Request microphone permission
//             await navigator.mediaDevices.getUserMedia({ audio: true });
//             if (!isTranscribing) {
//                 recognition.start();
//                 transcribeButton.textContent = 'Stop Transcription';
//                 isTranscribing = true;
//                 showNotification('Transcription started. Speak clearly.', 'info');
//             } else {
//                 recognition.stop();
//                 transcribeButton.textContent = 'Start Transcription';
//                 isTranscribing = false;
//             }
//         } catch (error) {
//             console.error("Error accessing microphone:", error.message);
//             showError('errorMessage', 'Microphone access denied or unavailable. Please check permissions.');
//         }
//     });

//     recognition.onresult = event => {
//         const patientSelect = document.getElementById('ai-patient-select');
//         const patientId = patientSelect?.value;

//         if (!patientId) {
//             console.error("Patient ID not selected during transcription.");
//             showError('errorMessage', 'Patient selection lost. Please select a patient and try again.');
//             recognition.stop();
//             return;
//         }

//         const transcript = Array.from(event.results)
//             .map(result => result[0].transcript)
//             .join('');
//         if (event.results[0].isFinal) {
//             console.log('Sending transcription to /transcribe:', { patientId, transcript });
//             fetch(`/transcribe/${patientId}`, {
//                 method: 'POST',
//                 headers: { 'Content-Type': 'application/json' },
//                 body: JSON.stringify({ transcription: transcript }),
//                 credentials: 'include'
//             })
//                 .then(response => {
//                     if (!response.ok) {
//                         return response.json().then(err => {
//                             throw new Error(err.error || `Failed to save transcription: ${response.status}`);
//                         });
//                     }
//                     return response.json();
//                 })
//                 .then(data => {
//                     console.log("Transcription saved:", data);
//                     showNotification('Transcription saved successfully.', 'info');
//                     const notesList = document.getElementById('patient-notes');
//                     if (notesList) {
//                         fetch(`/api/patient_notes/${patientId}`, { credentials: 'include' })
//                             .then(response => {
//                                 if (!response.ok) throw new Error('Failed to fetch patient notes');
//                                 return response.json();
//                             })
//                             .then(data => {
//                                 notesList.innerHTML = data.length > 0
//                                     ? data.map(note => `<li>${note.created_at || 'No date available'}: ${note.note}</li>`).join('')
//                                     : '<li>No notes available</li>';
//                             })
//                             .catch(error => {
//                                 console.error("Error fetching patient notes:", error.message);
//                                 notesList.innerHTML = `<li>Error loading notes: ${error.message}</li>`;
//                             });
//                     }
//                 })
//                 .catch(error => {
//                     console.error("Error saving transcription:", error.message);
//                     showError('errorMessage', `Error saving transcription: ${error.message}`);
//                 });
//         }
//     };

//     recognition.onerror = event => {
//         console.error("Transcription error:", event.error);
//         if (event.error === 'no-speech') {
//             showError('errorMessage', 'No speech detected. Please speak clearly or check your microphone.');
//         } else if (event.error === 'audio-capture') {
//             showError('errorMessage', 'Microphone not detected. Please ensure a microphone is connected.');
//         } else if (event.error === 'not-allowed') {
//             showError('errorMessage', 'Microphone access denied. Please allow microphone permissions in your browser.');
//         } else {
//             showError('errorMessage', `Transcription error: ${event.error}`);
//         }
//         transcribeButton.textContent = 'Start Transcription';
//         isTranscribing = false;
//     };

//     recognition.onend = () => {
//         transcribeButton.textContent = 'Start Transcription';
//         isTranscribing = false;
//     };
// }

function setupTranscription() {
    const transcribeButton = document.getElementById('transcribe-button');
    if (!transcribeButton) {
        console.warn("Transcribe button not found.");
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.error("SpeechRecognition not supported in this browser.");
        showError('errorMessage', 'Speech recognition is not supported in this browser. Please use a modern browser like Chrome.');
        transcribeButton.disabled = true;
        return;
    }

    let isTranscribing = false;
    const recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = true;
    recognition.continuous = true;

    transcribeButton.addEventListener('click', async () => {
        const patientSelect = document.getElementById('ai-patient-select');
        const patientId = patientSelect?.value;

        if (!patientId) {
            showError('errorMessage', 'Please select a patient to transcribe.');
            return;
        }

        try {
            await navigator.mediaDevices.getUserMedia({ audio: true });
            if (!isTranscribing) {
                recognition.start();
                transcribeButton.textContent = 'Stop Transcription';
                isTranscribing = true;
                showNotification('Transcription started. Speak clearly.', 'info');
            } else {
                recognition.stop();
                transcribeButton.textContent = 'Start Transcription';
                isTranscribing = false;
            }
        } catch (error) {
            console.error("Error accessing microphone:", error.message);
            showError('errorMessage', 'Microphone access denied or unavailable. Please check permissions.');
        }
    });

    recognition.onresult = event => {
        const patientSelect = document.getElementById('ai-patient-select');
        const patientId = patientSelect?.value;

        if (!patientId) {
            console.error("Patient ID not selected during transcription.");
            showError('errorMessage', 'Patient selection lost. Please select a patient and try again.');
            recognition.stop();
            return;
        }

        const transcript = Array.from(event.results)
            .map(result => result[0].transcript)
            .join('');
        if (event.results[0].isFinal) {
            console.log('Sending transcription to /transcribe:', { patientId, transcript });
            fetch(`/transcribe/${patientId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ transcription: transcript }),
                credentials: 'include'
            })
                .then(response => {
                    if (!response.ok) {
                        return response.json().then(err => {
                            throw new Error(err.error || `Failed to save transcription: ${response.status}`);
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    console.log("Transcription saved:", data);
                    showNotification('Transcription saved as SOAP notes.', 'info');
                    const notesList = document.getElementById('patient-notes');
                    if (notesList) {
                        fetch(`/medical_notes/${patientId}`, { credentials: 'include' })
                            .then(response => {
                                if (!response.ok) throw new Error('Failed to fetch medical notes');
                                return response.json();
                            })
                            .then(data => {
                                notesList.innerHTML = data.length > 0
                                    ? data.map(note => `
                                        <div class="p-2 bg-gray-100 rounded mb-2">
                                            <p><strong>Created At:</strong> ${note.created_at || 'No date available'}</p>
                                            <p><strong>Subjective:</strong> ${note.subjective}</p>
                                            <p><strong>Objective:</strong> ${note.objective}</p>
                                            <p><strong>Assessment:</strong> ${note.assessment}</p>
                                            <p><strong>Plan:</strong> ${note.plan}</p>
                                        </div>
                                    `).join('')
                                    : '<li>No notes available</li>';
                            })
                            .catch(error => {
                                console.error("Error fetching medical notes:", error.message);
                                notesList.innerHTML = `<li>Error loading notes: ${error.message}</li>`;
                            });
                    }
                })
                .catch(error => {
                    console.error("Error saving transcription:", error.message);
                    showError('errorMessage', `Error saving transcription: ${error.message}`);
                });
        }
    };

    recognition.onerror = event => {
        console.error("Transcription error:", event.error);
        if (event.error === 'no-speech') {
            showError('errorMessage', 'No speech detected. Please speak clearly or check your microphone.');
        } else if (event.error === 'audio-capture') {
            showError('errorMessage', 'Microphone not detected. Please ensure a microphone is connected.');
        } else if (event.error === 'not-allowed') {
            showError('errorMessage', 'Microphone access denied. Please allow microphone permissions in your browser.');
        } else {
            showError('errorMessage', `Transcription error: ${event.error}`);
        }
        transcribeButton.textContent = 'Start Transcription';
        isTranscribing = false;
    };

    recognition.onend = () => {
        transcribeButton.textContent = 'Start Transcription';
        isTranscribing = false;
    };
}


// Chatbot functionality
function setupChatbot() {
    const chatbotSubmit = document.getElementById('chatbot-submit');
    if (chatbotSubmit) {
        chatbotSubmit.addEventListener('click', () => {
            const patientSelect = document.getElementById('ai-patient-select');
            const patientId = patientSelect ? patientSelect.value : null;
            const chatbotInput = document.getElementById('chatbot-input');
            const query = chatbotInput ? chatbotInput.value : '';

            if (!patientId) {
                alert('Please select a patient to chat.');
                return;
            }
            if (!query) {
                alert('Please enter a query.');
                return;
            }

            fetch(`/chatbot/${patientId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query }),
                credentials: 'include'
            })
                .then(response => response.json())
                .then(data => {
                    const responseList = document.getElementById('chatbot-response');
                    if (responseList) {
                        if (data.response) {
                            responseList.innerHTML = `<li>${data.response}</li>`;
                        } else {
                            responseList.innerHTML = `<li>${data.error || 'No response available'}</li>`;
                        }
                        if (chatbotInput) chatbotInput.value = '';
                    } else {
                        console.warn("Chatbot response element not found. Ensure <ul id='chatbot-response'> exists in ai_insights.html.");
                    }
                })
                .catch(error => {
                    console.error("Error fetching chatbot response:", error);
                    const responseList = document.getElementById('chatbot-response');
                    if (responseList) {
                        responseList.innerHTML = '<li>Error loading response</li>';
                    }
                });
        });
    } else {
        console.warn("Chatbot submit button not found. Ensure <button id='chatbot-submit'> exists in ai_insights.html.");
    }
}


// ******************* Initialize page **************************
// Initialize page
document.addEventListener('DOMContentLoaded', () => {
    console.log("Page loaded, initializing features...");

    // Initialize calendar if on dashboard page
    if (document.getElementById('calendar')) {
        initializeCalendar();
    }

    // Initialize AI insights if on AI Insights page
    const aiInsightsSection = document.getElementById('ai-insights');
    if (aiInsightsSection) {
        loadPatientList();
        if (document.getElementById('prioritized-tasks')) {
            loadPrioritizedTasks();
        }
        setupVitalsAlerts();
        setupTranscription();
        setupChatbot();

        // Handle patient selection
        const patientSelect = document.getElementById('ai-patient-select');
        if (patientSelect) {
            patientSelect.addEventListener('change', () => {
                const patientId = patientSelect.value;
                console.log("Patient selected:", patientId);
                loadAllAIInsights(patientId);

                // Update export button
                const exportButton = document.getElementById('export-insights');
                if (exportButton) {
                    exportButton.onclick = () => {
                        if (patientId) {
                            console.log("Exporting insights for patient:", patientId);
                            window.location.href = `/export_insights/${patientId}`;
                        } else {
                            alert("Please select a patient to export insights.");
                        }
                    };
                } else {
                    console.error("Export insights button not found. Ensure <button id='export-insights'> exists in ai_insights.html.");
                }
            });
        } else {
            console.error("Patient select element not found. Ensure <select id='ai-patient-select'> exists in ai_insights.html.");
        }

        // Simulate vitals monitoring for testing
        setInterval(() => {
            const patientSelect = document.getElementById('ai-patient-select');
            const patientId = patientSelect ? patientSelect.value || 1 : 1; // Fallback to 1
            fetch(`/monitor_vitals/${patientId}`, { credentials: 'include' })
                .then(response => {
                    if (!response.ok) throw new Error('Failed to fetch vitals');
                    return response.json();
                })
                .then(data => {
                    console.log("Vitals fetched:", data);
                })
                .catch(error => {
                    console.error("Error fetching vitals:", error);
                });
        }, 30000); // Every 30 seconds
    }

    // Initialize appointments page if on /dashboard/appointments
    const appointmentList = document.getElementById('appointment-list');
    if (appointmentList) {
        fetchAppointments();
        loadDoctors();
        handleAppointmentForm();
    }

    // Setup dropdown menus
    setupDropdownMenus();
});



// Function to load WhatsApp tab content
// async function loadWhatsAppTab() {
//     try {
//         console.log('Loading WhatsApp tab...');
//         const response = await fetch('/whatsapp_tab', { credentials: 'include' });
//         if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
//         const html = await response.text();
//         document.getElementById('dashboard-content').innerHTML = html;
//     } catch (error) {
//         console.error('Error loading WhatsApp tab:', error.message);
//         showError('errorMessage', 'Error loading WhatsApp tab: ' + error.message);
//     }
// }

async function loadWhatsAppTab() {
    try {
        console.log('Loading WhatsApp tab...');
        const response = await fetch('/whatsapp_tab', { credentials: 'include' });
        console.log('Response status:', response.status);
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Error response:', errorText);
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        const html = await response.text();
        document.getElementById('dashboard-content').innerHTML = html;
    } catch (error) {
        console.error('Error loading WhatsApp tab:', error.message);
        showError('errorMessage', 'Error loading WhatsApp tab: ' + error.message);
    }
}





// Function to load WhatsApp conversation for a patient
// async function loadWhatsAppConversation() {
//     const patientId = document.getElementById('whatsapp-patient-select')?.value;
//     if (!patientId) return;

//     try {
//         console.log(`Fetching WhatsApp conversation for patient ${patientId}...`);
//         const response = await fetch(`/whatsapp/conversation/${patientId}`, { credentials: 'include' });
//         if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
//         const messages = await response.json();
//         const conversationDiv = document.getElementById('whatsapp-conversation');
//         if (conversationDiv) {
//             conversationDiv.innerHTML = messages.map(msg => `
//                 <div class="p-2 ${msg.sender === 'doctor' ? 'bg-blue-100' : msg.sender === 'bot' ? 'bg-green-100' : 'bg-gray-100'} rounded mb-2">
//                     <strong>${msg.sender.charAt(0).toUpperCase() + msg.sender.slice(1)} (${msg.timestamp}):</strong> ${msg.message}
//                 </div>
//             `).join('');
//             conversationDiv.scrollTop = conversationDiv.scrollHeight;
//         }
//     } catch (error) {
//         console.error('Error loading WhatsApp conversation:', error.message);
//         showError('errorMessage', 'Error loading conversation: ' + error.message);
//     }
// }

async function loadWhatsAppConversation() {
    const patientId = document.getElementById('whatsapp-patient-select')?.value;
    const summarizeButton = document.getElementById('summarize-symptoms-btn');
    if (!patientId) {
        document.getElementById('whatsapp-conversation').innerHTML = '';
        if (summarizeButton) summarizeButton.disabled = true;
        return;
    }

    try {
        console.log(`Fetching WhatsApp conversation for patient ${patientId}...`);
        const response = await fetch(`/whatsapp/conversation/${patientId}`, { credentials: 'include' });
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        const messages = await response.json();
        const conversationDiv = document.getElementById('whatsapp-conversation');
        if (conversationDiv) {
            conversationDiv.innerHTML = messages.map(msg => `
                <div class="p-2 ${msg.sender === 'doctor' ? 'bg-blue-100' : msg.sender === 'bot' ? 'bg-green-100' : 'bg-gray-100'} rounded mb-2">
                    <strong>${msg.sender.charAt(0).toUpperCase() + msg.sender.slice(1)} (${msg.timestamp}):</strong> ${msg.message}
                </div>
            `).join('');
            conversationDiv.scrollTop = conversationDiv.scrollHeight;
            // Enable Summarize Symptoms button only if patient messages exist
            // const hasPatientMessages = messages.some(msg => msg.sender === 'patient');
            if (summarizeButton) summarizeButton.disabled = false;
            //!hasPatientMessages;

        }
    } catch (error) {
        console.error('Error loading WhatsApp conversation:', error.message);
        showError('errorMessage', 'Error loading conversation: ' + error.message);
        if (summarizeButton) summarizeButton.disabled = true;
    }
}







// Function to send a WhatsApp message
// async function sendWhatsAppMessage() {
//     const patientId = document.getElementById('whatsapp-patient-select')?.value;
//     const message = document.getElementById('whatsapp-message-input')?.value.trim();
//     if (!patientId || !message) return;

//     try {
//         const response = await fetch('/whatsapp/send_message', {  // Line 1741
//             method: 'POST',
//             headers: { 'Content-Type': 'application/json' },
//             body: JSON.stringify({ patient_id: patientId, message }),
//             credentials: 'include'
//         });
//         if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
//         document.getElementById('whatsapp-message-input').value = '';
//         loadWhatsAppConversation();
//     } catch (error) {
//         console.error('Error sending WhatsApp message:', error.message);
//         showError('errorMessage', 'Error sending message: ' + error.message);
//     }
// }


async function sendWhatsAppMessage() {
    const patientId = document.getElementById('whatsapp-patient-select')?.value;
    const message = document.getElementById('whatsapp-message-input')?.value.trim();
    if (!patientId || !message) {
        showError('errorMessage', 'Please select a patient and enter a message.');
        return;
    }

    try {
        const response = await fetch('/whatsapp/send_message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: patientId, message }),
            credentials: 'include'
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
        }
        document.getElementById('whatsapp-message-input').value = '';
        showNotification('Message sent successfully.', 'info');
        loadWhatsAppConversation();
    } catch (error) {
        console.error('Error sending WhatsApp message:', error.message);
        if (error.message.includes('Recipient phone number is not registered')) {
            showError('errorMessage', 'Cannot send message: The recipient phone number is not registered with the WhatsApp Business API. Please contact support.');
        } else if (error.message.includes('Patient has not opted-in')) {
            showError('errorMessage', 'Cannot send message: The patient must send a message to your WhatsApp Business number to opt-in. Please ask them to do so.');
        } else {
            showError('errorMessage', 'Error sending message: ' + error.message);
        }
    }
}



// Function to summarize symptoms
// async function summarizeSymptoms() {
//     const patientId = document.getElementById('whatsapp-patient-select')?.value;
//     if (!patientId) {
//         console.error('No patient selected');
//         showError('errorMessage', 'Please select a patient.');
//         return;
//     }
//     console.log('Sending request to /whatsapp/summarize_symptoms with patientId:', patientId);
//     try {
//         const response = await fetch('/whatsapp/summarize_symptoms', {
//             method: 'POST',
//             headers: { 'Content-Type': 'application/json' },
//             body: JSON.stringify({ patient_id: patientId }),
//             credentials: 'include'
//         });
//         console.log('Response status:', response.status);
//         // if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
//         if (!response.ok) {
//             const errorData = await response.json();
//             throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
//         }
//         const result = await response.json();
//         showNotification(`Symptoms summarized: ${result.summary} (Triage: ${result.triage})`, 'info');
//         console.log('Response data:', result);
//         loadWhatsAppConversation();
//     } catch (error) {
//         console.error('Error summarizing symptoms:', error.message);
//         showError('errorMessage', error.message === 'No recent patient messages found' 
//             ? 'No recent patient messages available to summarize.' 
//             : 'Error summarizing symptoms: ' + error.message);
//     }
// }

async function summarizeSymptoms() {
    const patientId = document.getElementById('whatsapp-patient-select')?.value;
    if (!patientId) {
        showError('errorMessage', 'Please select a patient.');
        return;
    }

    try {
        const response = await fetch('/whatsapp/summarize_symptoms', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: patientId }),
            credentials: 'include'
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || `HTTP error! Status: ${response.status}`);
        }
        if (result.summary.includes('No recent patient messages')) {
            showError('errorMessage', 'No recent patient messages available to summarize.');
        } else {
            showNotification(`Symptoms summarized: ${result.summary} (Triage: ${result.triage})`, 'info');
        }
        loadWhatsAppConversation();
    } catch (error) {
        console.error('Error summarizing symptoms:', error.message);
        showError('errorMessage', 'Error summarizing symptoms: ' + error.message);
    }
}
















function showError(elementId, message) {
    const errorElement = document.getElementById(elementId);
    if (errorElement) {
        // Clear any existing timeout to prevent multiple timers
        if (errorElement.timeoutId) {
            clearTimeout(errorElement.timeoutId);
        }
        errorElement.textContent = message;
        errorElement.style.display = 'block';
        errorElement.classList.add('p-4', 'rounded-lg', 'bg-red-500', 'text-white');
        // Set a timeout to hide the error after 15 seconds
        errorElement.timeoutId = setTimeout(() => {
            errorElement.textContent = '';
            errorElement.style.display = 'none';
            errorElement.classList.remove('p-4', 'rounded-lg', 'bg-red-500', 'text-white');
            delete errorElement.timeoutId;
        }, 10000); // 10 seconds
    } else {
        console.warn(`Error element ${elementId} not found`);
    }
}





// Function to send test result
async function sendTestResult() {
    const patientId = document.getElementById('whatsapp-patient-select')?.value;
    if (!patientId) return;

    try {
        const response = await fetch('/whatsapp/send_test_result', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: patientId }),
            credentials: 'include'
        });
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        loadWhatsAppConversation();
    } catch (error) {
        console.error('Error sending test result:', error.message);
        showError('errorMessage', 'Error sending test result: ' + error.message);
    }
}

// Function to schedule a reminder
async function scheduleReminder() {
    const patientId = document.getElementById('whatsapp-patient-select')?.value;
    if (!patientId) return;

    try {
        const response = await fetch('/whatsapp/schedule_reminder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: patientId }),
            credentials: 'include'
        });
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        loadWhatsAppConversation();
    } catch (error) {
        console.error('Error scheduling reminder:', error.message);
        showError('errorMessage', 'Error scheduling reminder: ' + error.message);
    }
}



async function scheduleAppointment() {
    const patientId = document.getElementById('whatsapp-patient-select')?.value;
    if (!patientId) {
        showError('errorMessage', 'Please select a patient.');
        return;
    }

    try {
        const response = await fetch('/schedule_appointment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: patientId }),
            credentials: 'include'
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
        }
        const result = await response.json();
        showNotification(`Appointment scheduled for ${result.slot}`, 'info');
    } catch (error) {
        console.error('Error scheduling appointment:', error.message);
        showError('errorMessage', 'Error scheduling appointment: ' + error.message);
    }
}

//*****************Start Recording Medical Notes**************
async function startRecording() {
    try {
        const patientSelect = document.getElementById('medical-notes-patient-select');
        const patientId = patientSelect?.value;
        if (!patientId) {
            showError('errorMessage', 'Please select a patient.');
            return;
        }

        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = event => {
            console.log('Audio chunk received:', event.data);
            audioChunks.push(event.data);
        };
        mediaRecorder.onstop = () => sendVoiceNote(patientId);
        mediaRecorder.start();

        document.querySelector('button[onclick="startRecording()"]').disabled = true;
        document.querySelector('button[onclick="stopRecording()"]').disabled = false;
        showNotification('Recording started. Click "Stop Recording" to save.', 'info');
        // showNotification('Recording started. Ensure your microphone is enabled and speak clearly.', 'info');
    } catch (error) {
        console.error('Error starting recording:', error.message);
        showError('errorMessage', 'Error starting recording: ' + error.message + '. Please check microphone permissions.');
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        document.querySelector('button[onclick="startRecording()"]').disabled = false;
        document.querySelector('button[onclick="stopRecording()"]').disabled = true;
        // sendVoiceNote();
    }
}





// // sendVoiceNote funciton
// async function sendVoiceNote() {
//     const patientId = document.getElementById('medical-notes-patient-select')?.value;
//     if (!patientId) {
//         showError('errorMessage', 'Please select a patient.');
//         return;
//     }

//     const audioText = window.audioText;
//     if (!audioText) {
//         showError('errorMessage', 'No voice note recorded.');
//         return;
//     }

//     try {
//         const response = await fetch('/generate_medical_notes', {
//             method: 'POST',
//             headers: { 'Content-Type': 'application/json' },
//             body: JSON.stringify({ patient_id: patientId, audio_text: audioText }),
//             credentials: 'include'
//         });
//         const result = await response.json();
//         if (!response.ok) {
//             throw new Error(result.error || `HTTP error! Status: ${response.status}`);
//         }
//         showNotification('Medical notes generated successfully.', 'info');
//         loadMedicalNotes();
//     } catch (error) {
//         console.error('Error generating medical notes:', error.message);
//         showError('errorMessage', 'Error generating medical notes: ' + error.message);
//     } finally {
//         window.audioText = null; // Clear the temporary storage
//     }
// }

async function sendVoiceNote(patientId) {
    try {
        if (!patientId) {
            showError('errorMessage', 'Patient ID not selected.');
            return;
        }

        // Placeholder for transcription (replace with actual speech-to-text API in production)
        const audioText = "Patient reports headache and fatigue"; // Temporary placeholder
        if (!audioText) {
            showError('errorMessage', 'No audio recorded.');
            return;
        }

        console.log('Sending to /generate_medical_notes:', { patientId, audioText });
        const response = await fetch('/generate_medical_notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: patientId, audio_text: audioText }),
            credentials: 'include'
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.error || `HTTP error! Status: ${response.status}`);
        }
        showNotification('Medical notes generated successfully.', 'info');
        loadMedicalNotes();
    } catch (error) {
        console.error('Error generating medical notes:', error.message);
        showError('errorMessage', `Error generating medical notes: ${error.message}`);
    } finally {
        document.querySelector('button[onclick="startRecording()"]').disabled = false;
        document.querySelector('button[onclick="stopRecording()"]').disabled = true;
    }
}


function closeAddAppointmentModal() {
    const modal = document.getElementById('addAppointmentModal');
    if (modal) {
        modal.classList.add('hidden');
        // Reset form
        const form = document.getElementById('appointment-form');
        if (form) {
            form.reset();
        }
    } else {
        console.warn("Add Appointment modal not found");
    }
}







//******************** Load Medical Notes ****************************
async function loadMedicalNotes() {
    const patientId = document.getElementById('medical-notes-patient-select')?.value;
    if (!patientId) {
        document.getElementById('medical-notes').innerHTML = '';
        return;
    }

    try {
        const response = await fetch(`/medical_notes/${patientId}`, { credentials: 'include' });
        if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
        const notes = await response.json();
        const notesDiv = document.getElementById('medical-notes');
        if (notesDiv) {
            notesDiv.innerHTML = notes.length === 0
                ? '<p class="text-gray-500">No medical notes found.</p>'
                : notes.map(note => `
                    <div class="p-2 bg-gray-100 rounded mb-2">
                        <p><strong>Created At:</strong> ${note.created_at}</p>
                        <p><strong>Subjective:</strong> ${note.subjective}</p>
                        <p><strong>Objective:</strong> ${note.objective}</p>
                        <p><strong>Assessment:</strong> ${note.assessment}</p>
                        <p><strong>Plan:</strong> ${note.plan}</p>
                    </div>
                `).join('');
        }
    } catch (error) {
        console.error('Error loading medical notes:', error.message);
        showError('errorMessage', 'Error loading medical notes: ' + error.message);
    }
}



async function processBilling() {
    const patientId = document.getElementById('whatsapp-patient-select')?.value;
    if (!patientId) {
        showError('errorMessage', 'Please select a patient.');
        return;
    }

    try {
        const response = await fetch('/billing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: patientId, visit_cost: 100.0 }),  // Hardcoded cost for testing
            credentials: 'include'
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
        }
        const result = await response.json();
        let message = `Billing processed. Amount due: $${result.result.amount_due.toFixed(2)}.`;
        if (result.result.alert) message += ` Alert: ${result.result.alert}`;
        showNotification(message, 'info');
    } catch (error) {
        console.error('Error processing billing:', error.message);
        showError('errorMessage', 'Error processing billing: ' + error.message);
    }
}

async function sendFollowUp() {
    const patientId = document.getElementById('whatsapp-patient-select')?.value;
    if (!patientId) {
        showError('errorMessage', 'Please select a patient.');
        return;
    }

    try {
        const response = await fetch('/follow_up', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: patientId }),
            credentials: 'include'
        });
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
        }
        showNotification('Follow-up message sent.', 'info');
        loadWhatsAppConversation();
    } catch (error) {
        console.error('Error sending follow-up message:', error.message);
        showError('errorMessage', 'Error sending follow-up message: ' + error.message);
    }
}



async function generateDiagnosis() {
    const patientId = document.getElementById('diagnostics-patient-select')?.value;
    if (!patientId) {
        showError('errorMessage', 'Please select a patient.');
        document.getElementById('diagnostics').innerHTML = '<p class="text-gray-500">Select a patient to view diagnostic suggestions.</p>';
        return;
    }

    try {
        const response = await fetch('/diagnose', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ patient_id: patientId }),
            credentials: 'include'
        });
        const result = await response.json();
        if (!response.ok) {
            // const errorData = await response.json();
            throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
        }

        const diagnosticsDiv = document.getElementById('diagnostics');
        if (diagnosticsDiv) {
            if (result.diagnoses && result.diagnoses.length > 0) {
                diagnosticsDiv.innerHTML = result.diagnoses.map(diag => `
                    <div class="p-2 bg-gray-100 rounded mb-2">
                        <p><strong>Diagnosis:</strong> ${diag.diagnosis}</p>
                        <p><strong>Confidence:</strong> ${(diag.confidence * 100).toFixed(2)}%</p>
                    </div>
                `).join('');
            } else {
                diagnosticsDiv.innerHTML = '<p class="text-gray-500">No diagnostic suggestions available.</p>';
            }
            showNotification('Diagnosis generated successfully.', 'info');
        }
        showNotification('Diagnosis generated successfully.', 'info');
    } catch (error) {
        console.error('Error generating diagnosis:', error.message);
        showError('errorMessage', 'Error generating diagnosis: ' + error.message);
        document.getElementById('diagnostics').innerHTML = '<p class="text-gray-500">Error generating diagnostic suggestions.</p>';
    }
}

// Function to handle dropdown menu toggle
function setupDropdownMenus() {
    const dropdowns = document.querySelectorAll('.dropdown');
    dropdowns.forEach(dropdown => {
        const button = dropdown.querySelector('button');
        const menu = dropdown.querySelector('.dropdown-menu');

        // Toggle dropdown on button click
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const isOpen = menu.style.display === 'block';
            // Close all other dropdowns
            document.querySelectorAll('.dropdown-menu').forEach(m => {
                m.style.display = 'none';
            });
            // Toggle the current dropdown
            menu.style.display = isOpen ? 'none' : 'block';
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!dropdown.contains(e.target)) {
                menu.style.display = 'none';
            }
        });
    });
}



function navigateToPatients() {
    window.location.href = '/patients';
}

function navigateToAppointments(status) {
    window.location.href = `/dashboard/appointments?status=${status}`;
}

function navigateToTasks(status) {
    window.location.href = `/tasks?status=${status}`;
}

async function loadDashboardMetrics() {
    try {
        // Fetch Total Patients
        const patientsResponse = await fetch('/api/patients', { credentials: 'include' });
        if (!patientsResponse.ok) throw new Error('Failed to fetch patients');
        const patients = await patientsResponse.json();
        const totalPatients = patients.length;
        document.getElementById('totalPatients').textContent = totalPatients;

        // Fetch Appointments (already in loadAppointments)
        const appointmentsResponse = await fetch('/get_appointments', { credentials: 'include' });
        if (!appointmentsResponse.ok) throw new Error('Failed to fetch appointments');
        const appointments = await appointmentsResponse.json();

        // Calculate Upcoming and Completed Appointments
        const referenceDate = new Date('2025-05-02T00:00:00');  // Current date
        let upcoming = 0;
        let completed = 0;
        appointments.forEach(a => {
            const date = new Date(a.date);
            if (a.status === 'upcoming' || date >= referenceDate) {
                upcoming++;
            } else if (a.status === 'completed') {
                completed++;
            }
        });
        document.getElementById('upcomingAppointments').textContent = upcoming;
        document.getElementById('completedAppointments').textContent = completed;

        // Fetch Pending Tasks
        const tasksResponse = await fetch('/api/tasks?status=pending', { credentials: 'include' });
        if (!tasksResponse.ok) throw new Error('Failed to fetch tasks');
        const tasks = await tasksResponse.json();
        const pendingTasks = tasks.length;
        document.getElementById('pendingTasks').textContent = pendingTasks;
    } catch (error) {
        console.error('Error loading dashboard metrics:', error.message);
        showError('errorMessage', 'Error loading dashboard metrics: ' + error.message);
    }
}

