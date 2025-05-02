const socket = io();


socket.on('connect', () => {
    socket.emit('register_session', { user_id: '{{ current_user.id }}' });
});

socket.on('chat_message', (data) => {
    const messages = document.getElementById('chat-messages');
    messages.innerHTML += `<p><strong>${data.sender}:</strong> ${data.message}</p>`;
    messages.scrollTop = messages.scrollHeight;
});

function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (message) {
        socket.emit('chat_message', { recipient_id: 'all', message: message }); // 'all' for broadcast
        input.value = '';
    }
}

function deletePatient(id) {
    if (confirm('Are you sure you want to delete this patient?')) {
        fetch(`/api/patient/${id}`, { method: 'DELETE' })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.querySelector(`tr[data-patient-id="${id}"]`).remove();
                } else {
                    alert('Error deleting patient');
                }
            })
            .catch(error => console.error('Error deleting patient:', error));
    }
}

function updateTask(id, status) {
    fetch(`/api/update_task/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: status })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.querySelector(`tr[data-task-id="${id}"]`).remove();
            } else {
                alert('Error updating task');
            }
        })
        .catch(error => console.error('Error updating task:', error));
}




// Initialize FullCalendar
function initializeCalendar() {
    var calendarEl = document.getElementById('calendar');
    if (!calendarEl) {
        console.error("Calendar element not found. Ensure <div id='calendar'> exists in dashboard.html.");
        return;
    }
    try {
        console.log("Checking if FullCalendar is defined...");
        if (typeof FullCalendar === 'undefined') {
            console.error("FullCalendar is not defined. Ensure fullcalendar.min.js is loaded from /static/lib/fullcalendar/fullcalendar.min.js.");
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
            console.warn("Today's date element not found. Check for <div id='today-date'>.");
        }

        var calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            initialDate: today,
            height: '500px',
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
                        console.log("Add Appointment modal opened with date:", info.dateStr);
                    } else {
                        console.error("Add Appointment modal not found. Check for <div id='addAppointmentModal'>.");
                    }
                } else {
                    console.error("Add Appointment date input not found. Check for <input id='addAppointmentDate'>.");
                }
            },
            eventClick: function(info) {
                console.log("Event clicked:", info.event.id);
                window.location.href = '/edit_appointment/' + info.event.id;
            },
            eventClassNames: function(arg) {
                return arg.event.classNames; // Apply high-priority (red) or low-priority (blue)
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
                            console.warn("No events returned. Check appointments table.");
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

// Fetch AI-driven appointment suggestions
function loadSuggestedAppointments() {
    fetch('/suggest_appointment/1')  // Example patient_id=1
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch suggested appointments');
            return response.json();
        })
        .then(data => {
            const list = document.getElementById('suggested-appointments');
            if (data.suggested_slots) {
                list.innerHTML = data.suggested_slots.map(slot => `<li>${slot}</li>`).join('');
            } else {
                list.innerHTML = '<li>No suggestions available</li>';
            }
        })
        .catch(error => {
            console.error("Error fetching suggested appointments:", error);
        });
}

// Fetch AI-driven health trends
function loadHealthTrends() {
    fetch('/health_trends/1')  // Example patient_id=1
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch health trends');
            return response.json();
        })
        .then(data => {
            const list = document.getElementById('health-trends');
            if (data.trends) {
                list.innerHTML = `<li>Risk: ${data.trends.risk}</li>`;
            } else {
                list.innerHTML = '<li>No trends available</li>';
            }
        })
        .catch(error => {
            console.error("Error fetching health trends:", error);
        });
}

// Fetch AI-prioritized tasks
function loadPrioritizedTasks() {
    fetch('/prioritize_tasks')
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch prioritized tasks');
            return response.json();
        })
        .then(data => {
            const list = document.getElementById('task-list');
            if (data.prioritized_tasks) {
                list.innerHTML = data.prioritized_tasks.map(task => `<li>${task.description} (Priority: ${task.priority})</li>`).join('');
            } else {
                list.innerHTML = '<li>No tasks available</li>';
            }
        })
        .catch(error => {
            console.error("Error fetching prioritized tasks:", error);
        });
}


// Fetch AI-driven patient risk clusters
function loadRiskClusters() {
    fetch('/patient_risk_clusters')
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch risk clusters');
            return response.json();
        })
        .then(data => {
            const list = document.getElementById('risk-clusters');
            if (data.clusters) {
                list.innerHTML = data.clusters.map(c => `<li>${c.name}: ${c.cluster_label}</li>`).join('');
            } else {
                list.innerHTML = '<li>No clusters available</li>';
            }
        })
        .catch(error => {
            console.error("Error fetching risk clusters:", error);
        });
}

// Fetch AI-driven no-show predictions
function loadNoShowPredictions() {
    fetch('/no_show_prediction/1')  // Example patient_id=1
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch no-show predictions');
            return response.json();
        })
        .then(data => {
            const list = document.getElementById('no-show-predictions');
            if (data.no_show_probability) {
                list.innerHTML = `<li>No-Show Probability: ${(data.no_show_probability * 100).toFixed(2)}%</li>`;
            } else {
                list.innerHTML = '<li>No predictions available</li>';
            }
        })
        .catch(error => {
            console.error("Error fetching no-show predictions:", error);
        });
}

// Fetch AI-driven follow-up recommendations
function loadFollowUpRecommendations() {
    fetch('/follow_up_recommendations/1')  // Example patient_id=1
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch follow-up recommendations');
            return response.json();
        })
        .then(data => {
            const list = document.getElementById('follow-up-recommendations');
            if (data.recommendation) {
                list.innerHTML = `<li>${data.recommendation.follow_up}</li>`;
            } else {
                list.innerHTML = '<li>No recommendations available</li>';
            }
        })
        .catch(error => {
            console.error("Error fetching follow-up recommendations:", error);
        });
}

// SocketIO event listeners
if (socket) {
    socket.on('connect', () => {
        console.log('SocketIO connected successfully.');
    });

    socket.on('appointment_scheduled', (data) => {
        console.log('Appointment scheduled:', data);
        const calendar = initializeCalendar();
        if (calendar) {
            console.log("Refetching calendar events...");
            calendar.refetchEvents();
        }
    });

    socket.on('appointment_canceled', (data) => {
        console.log('Appointment canceled:', data);
        const calendar = initializeCalendar();
        if (calendar) {
            console.log("Refetching calendar events...");
            calendar.refetchEvents();
        }
    });
} else {
    console.warn("SocketIO not available, real-time calendar updates disabled.");
}

// Initialize page
document.addEventListener('DOMContentLoaded', () => {
    console.log("Page loaded, initializing calendar and AI features...");
    initializeCalendar();
    loadSuggestedAppointments();
    loadHealthTrends();
    loadPrioritizedTasks();
    loadRiskClusters();
    loadNoShowPredictions();
    loadFollowUpRecommendations();
});