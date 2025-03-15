class AdminDashboard {
    constructor() {
        this.sessions = new Map();
        this.charts = new Map();
        this.initializeDashboard();
    }

    async initializeDashboard() {
        this.setupCharts();
        this.startMonitoring();
    }

    setupCharts() {
        const ctx = document.getElementById('risk-trends').getContext('2d');
        this.riskChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: []
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 1
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const score = context.raw;
                                let riskLevel = score > 0.7 ? 'High Risk' :
                                             score > 0.4 ? 'Medium Risk' : 'Low Risk';
                                return `Risk Score: ${(score * 100).toFixed(1)}% (${riskLevel})`;
                            }
                        }
                    }
                }
            }
        });
    }

    async startMonitoring() {
        await this.updateActiveSessions();
        // Update every 3 seconds to match student monitoring frequency
        setInterval(() => this.updateActiveSessions(), 3000);
    }

    async updateActiveSessions() {
        try {
            const response = await fetch('/api/active_sessions');
            if (!response.ok) throw new Error('Failed to fetch sessions');
            const sessions = await response.json();
            this.updateDashboard(sessions);
        } catch (error) {
            console.error('Failed to fetch active sessions:', error);
        }
    }

    updateDashboard(sessions) {
        const container = document.getElementById('active-sessions');
        container.innerHTML = '';

        sessions.forEach(session => {
            const sessionElement = this.createSessionElement(session);
            container.appendChild(sessionElement);
            this.updateRiskChart(session);
        });
    }

    createSessionElement(session) {
        const div = document.createElement('div');
        div.className = 'session-card';

        const suspiciousActivities = session.suspicious_activities
            .map(activity => {
                const time = new Date(activity.timestamp).toLocaleTimeString();
                let description = '';

                if (activity.type === 'keystroke' && activity.data.keyInterval < 50) {
                    description = 'Unusually rapid typing detected';
                } else if (activity.type === 'mouse' && activity.data.speed > 1000) {
                    description = 'Suspicious mouse movement pattern';
                } else if (activity.type === 'tabswitch') {
                    description = 'Tab switching detected';
                } else if (activity.type === 'right_click') {
                    description = 'Rapid right-clicking detected';
                }

                return `<li class="list-group-item">
                    ${time} - ${description}
                </li>`;
            })
            .join('');

        div.innerHTML = `
            <div class="card mb-3">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <h5 class="card-title">Student: ${session.username}</h5>
                        <div>
                            <span class="badge ${this.getRiskBadgeClass(session.risk_score)}">
                                Current Risk: ${(session.risk_score * 100).toFixed(1)}%
                            </span>
                            <span class="badge bg-info ms-2">
                                Mean Risk: ${(session.mean_risk_score * 100).toFixed(1)}%
                            </span>
                        </div>
                    </div>
                    <p class="card-text">
                        <small class="text-muted">
                            Session Duration: ${this.formatDuration(session.duration)}
                        </small>
                    </p>
                    <div class="suspicious-activities mt-3">
                        <h6>Recent Suspicious Activities:</h6>
                        <ul class="list-group list-group-flush">
                            ${suspiciousActivities || '<li class="list-group-item">No suspicious activities detected</li>'}
                        </ul>
                    </div>
                    <button class="btn btn-danger mt-3" onclick="dashboard.endSession(${session.id})">
                        End Session
                    </button>
                </div>
            </div>
        `;
        return div;
    }

    getRiskBadgeClass(score) {
        if (score > 0.7) return 'bg-danger';
        if (score > 0.4) return 'bg-warning text-dark';
        return 'bg-success';
    }

    updateRiskChart(session) {
        const dataset = this.riskChart.data.datasets.find(ds => ds.label === `Student ${session.username}`);

        if (!dataset) {
            // Add new dataset for this session
            this.riskChart.data.datasets.push({
                label: `Student ${session.username}`,
                data: [session.risk_score],
                borderColor: this.getRandomColor(),
                fill: false
            });
        } else {
            dataset.data.push(session.risk_score);
            if (dataset.data.length > 20) {
                dataset.data.shift();
            }
        }

        // Update labels
        if (this.riskChart.data.labels.length === 0) {
            this.riskChart.data.labels = [...Array(20)].map((_, i) => i.toString());
        }

        this.riskChart.update();
    }

    getRandomColor() {
        const letters = '0123456789ABCDEF';
        let color = '#';
        for (let i = 0; i < 6; i++) {
            color += letters[Math.floor(Math.random() * 16)];
        }
        return color;
    }

    formatDuration(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}m ${remainingSeconds}s`;
    }

    async endSession(sessionId) {
        try {
            const response = await fetch('/api/end_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ session_id: sessionId })
            });

            if (response.ok) {
                // Remove the session from the dashboard
                await this.updateActiveSessions();
            }

        } catch (error) {
            console.error('Failed to end session:', error);
        }
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new AdminDashboard();
});