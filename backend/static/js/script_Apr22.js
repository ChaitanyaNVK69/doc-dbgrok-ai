// static/script.js
// JavaScript for Doctor Dashboard AI calendar and AI insights

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


// Fetch all AI-driven insights
function loadAllAIInsights() {
    fetch('/all_ai_insights/1')  // Example patient_id=1
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch AI insights');
            return response.json();
        })
        .then(data => {
            console.log("AI insights fetched:", data);

            // Suggested Appointments
            const apptList = document.getElementById('suggested-appointments');
            if (data.suggested_appointments && data.suggested_appointments.suggested_slots) {
                apptList.innerHTML = data.suggested_appointments.suggested_slots.map(slot => `<li>${slot}</li>`).join('');
            } else {
                apptList.innerHTML = '<li>No suggestions available</li>';
            }

            // Health Trends
            const trendsList = document.getElementById('health-trends');
            if (data.health_trends && data.health_trends.trends) {
                trendsList.innerHTML = `<li>Risk: ${data.health_trends.trends.risk}</li>`;
            } else {
                trendsList.innerHTML = '<li>No trends available</li>';
            }

            // Patient Risk Clusters
            const clustersList = document.getElementById('risk-clusters');
            if (data.risk_clusters && data.risk_clusters.clusters) {
                clustersList.innerHTML = data.risk_clusters.clusters.map(c => `<li>${c.name}: ${c.cluster_label}</li>`).join('');
            } else {
                clustersList.innerHTML = '<li>No clusters available</li>';
            }

            // No-Show Predictions
            const noShowList = document.getElementById('no-show-predictions');
            if (data.no_show_prediction && data.no_show_prediction.no_show_probability) {
                noShowList.innerHTML = `<li>No-Show Probability: ${(data.no_show_prediction.no_show_probability * 100).toFixed(2)}%</li>`;
            } else {
                noShowList.innerHTML = '<li>No predictions available</li>';
            }

            // Follow-Up Recommendations
            const followUpList = document.getElementById('follow-up-recommendations');
            if (data.follow_up_recommendations && data.follow_up_recommendations.recommendation) {
                followUpList.innerHTML = `<li>${data.follow_up_recommendations.recommendation.follow_up}</li>`;
            } else {
                followUpList.innerHTML = '<li>No recommendations available</li>';
            }

            // Medication Interactions
            const medList = document.getElementById('med-interactions');
            if (data.med_interactions && data.med_interactions.interactions && data.med_interactions.interactions.length > 0) {
                medList.innerHTML = data.med_interactions.interactions.map(i => `<li>${i.medications.join(' + ')}: ${i.warning}</li>`).join('');
            } else {
                medList.innerHTML = '<li>No interactions detected</li>';
            }

            // Real-Time Vitals Alerts
            const vitalsList = document.getElementById('vitals-alerts');
            if (data.vitals_alerts && data.vitals_alerts.alerts && data.vitals_alerts.alerts.length > 0) {
                vitalsList.innerHTML = data.vitals_alerts.alerts.map(alert => `<li>${alert}</li>`).join('');
            } else {
                vitalsList.innerHTML = '<li>No active alerts</li>';
            }

            // Resource Allocation
            const resourceList = document.getElementById('resource-allocation');
            if (data.resource_allocation && data.resource_allocation.recommendations) {
                resourceList.innerHTML = data.resource_allocation.recommendations.map(r => `<li>${r.date}: ${r.staff_needed} staff, ${r.equipment_needed} equipment</li>`).join('');
            } else {
                resourceList.innerHTML = '<li>No recommendations available</li>';
            }

            // Fetch prioritized tasks separately
            fetch('/prioritize_tasks')
                .then(response => {
                    if (!response.ok) throw new Error('Failed to fetch prioritized tasks');
                    return response.json();
                })
                .then(data => {
                    const taskList = document.getElementById('task-list');
                    if (data.prioritized_tasks) {
                        taskList.innerHTML = data.prioritized_tasks.map(task => `<li>${task.description} (Priority: ${task.priority})</li>`).join('');
                    } else {
                        taskList.innerHTML = '<li>No tasks available</li>';
                    }
                })
                .catch(error => {
                    console.error("Error fetching prioritized tasks:", error);
                });
        })
        .catch(error => {
            console.error("Error fetching AI insights:", error);
        });
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

// Fetch AI-driven medication interactions
function loadMedInteractions() {
    fetch('/check_med_interactions/1')  // Example patient_id=1
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch medication interactions');
            return response.json();
        })
        .then(data => {
            const list = document.getElementById('med-interactions');
            if (data.interactions && data.interactions.length > 0) {
                list.innerHTML = data.interactions.map(i => `<li>${i.medications.join(' + ')}: ${i.warning}</li>`).join('');
            } else {
                list.innerHTML = '<li>No interactions detected</li>';
            }
        })
        .catch(error => {
            console.error("Error fetching medication interactions:", error);
        });
}

// Handle real-time vitals alerts
function setupVitalsAlerts() {
    if (socket) {
        socket.on('vitals_alert', (data) => {
            console.log('Vitals alert received:', data);
            const list = document.getElementById('vitals-alerts');
            list.innerHTML = data.alerts.map(alert => `<li>${alert}</li>`).join('');
            setTimeout(() => {
                list.innerHTML = '<li>No active alerts</li>';
            }, 10000); // Clear after 10 seconds
        });
    }
}

// Fetch AI-driven resource allocation
function loadResourceAllocation() {
    fetch('/resource_allocation')
        .then(response => {
            if (!response.ok) throw new Error('Failed to fetch resource allocation');
            return response.json();
        })
        .then(data => {
            const list = document.getElementById('resource-allocation');
            if (data.recommendations) {
                list.innerHTML = data.recommendations.map(r => `<li>${r.date}: ${r.staff_needed} staff, ${r.equipment_needed} equipment</li>`).join('');
            } else {
                list.innerHTML = '<li>No recommendations available</li>';
            }
        })
        .catch(error => {
            console.error("Error fetching resource allocation:", error);
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
    loadMedInteractions();
    setupVitalsAlerts();
    loadResourceAllocation();
    loadAllAIInsights();
    

    // Simulate vitals monitoring for testing
    setInterval(() => {
        fetch('/monitor_vitals/1');  // Example patient_id=1
    }, 30000); // Every 30 seconds
});