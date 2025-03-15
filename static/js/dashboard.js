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
                        position: 'top'
                    }
                }
            }
        });
    }
    
    async startMonitoring() {
        // Poll for active sessions and their risk scores
        setInterval(async () => {
            const activeSessions = await this.fetchActiveSessions();
            this.updateDashboard(activeSessions);
        }, 5000);
    }
    
    async fetchActiveSessions() {
        try {
            const response = await fetch('/api/active_sessions');
            return await response.json();
        } catch (error) {
            console.error('Failed to fetch active sessions:', error);
            return [];
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
        div.innerHTML = `
            <div class="card mb-3">
                <div class="card-body">
                    <h5 class="card-title">Student: ${session.username}</h5>
                    <p class="card-text">Session ID: ${session.id}</p>
                    <p class="card-text">Duration: ${this.formatDuration(session.duration)}</p>
                    <div class="risk-indicator ${this.getRiskClass(session.risk_score)}">
                        Risk Score: ${(session.risk_score * 100).toFixed(1)}%
                    </div>
                    <button class="btn btn-warning" onclick="dashboard.flagSession(${session.id})">
                        Flag for Review
                    </button>
                </div>
            </div>
        `;
        return div;
    }
    
    updateRiskChart(session) {
        const dataset = this.riskChart.data.datasets.find(ds => ds.label === `Student ${session.id}`);
        
        if (!dataset) {
            // Add new dataset for this session
            this.riskChart.data.datasets.push({
                label: `Student ${session.id}`,
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
    
    getRiskClass(score) {
        if (score > 0.7) return 'high-risk';
        if (score > 0.4) return 'medium-risk';
        return 'low-risk';
    }
    
    formatDuration(seconds) {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = seconds % 60;
        return `${minutes}m ${remainingSeconds}s`;
    }
    
    async flagSession(sessionId) {
        try {
            await fetch('/api/flag_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ session_id: sessionId })
            });
            
            // Visual feedback
            const button = document.querySelector(`button[onclick="dashboard.flagSession(${sessionId})"]`);
            button.classList.remove('btn-warning');
            button.classList.add('btn-danger');
            button.textContent = 'Flagged';
            button.disabled = true;
            
        } catch (error) {
            console.error('Failed to flag session:', error);
        }
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new AdminDashboard();
});
