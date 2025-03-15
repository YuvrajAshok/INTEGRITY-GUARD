class ExamMonitor {
    constructor() {
        this.sessionId = null;
        this.lastKeystrokeTime = Date.now();
        this.mousePoints = [];
        this.riskScore = 0;
        
        this.initializeMonitoring();
    }
    
    async initializeMonitoring() {
        // Start exam session
        const response = await fetch('/api/start_exam', {
            method: 'POST'
        });
        const data = await response.json();
        this.sessionId = data.session_id;
        
        // Set up event listeners
        document.addEventListener('keydown', this.handleKeyDown.bind(this));
        document.addEventListener('keyup', this.handleKeyUp.bind(this));
        document.addEventListener('mousemove', this.handleMouseMove.bind(this));
        document.addEventListener('visibilitychange', this.handleTabSwitch.bind(this));
        
        // Start periodic risk score updates
        this.updateRiskScore();
    }
    
    async logActivity(type, data) {
        try {
            const response = await fetch('/api/log_activity', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    type: type,
                    data: data
                })
            });
            
            const result = await response.json();
            this.updateRiskDisplay(result.risk_score);
            
        } catch (error) {
            console.error('Failed to log activity:', error);
        }
    }
    
    handleKeyDown(event) {
        const currentTime = Date.now();
        const keyInterval = currentTime - this.lastKeystrokeTime;
        
        this.logActivity('keystroke', {
            key: event.key,
            keyInterval: keyInterval,
            timestamp: currentTime
        });
        
        this.lastKeystrokeTime = currentTime;
    }
    
    handleKeyUp(event) {
        const holdTime = Date.now() - this.lastKeystrokeTime;
        
        this.logActivity('keystroke', {
            key: event.key,
            holdTime: holdTime,
            timestamp: Date.now()
        });
    }
    
    handleMouseMove(event) {
        this.mousePoints.push({
            x: event.clientX,
            y: event.clientY,
            timestamp: Date.now()
        });
        
        if (this.mousePoints.length >= 10) {
            const points = this.mousePoints;
            this.mousePoints = [];
            
            // Calculate mouse movement metrics
            const speed = this.calculateMouseSpeed(points);
            const distance = this.calculateMouseDistance(points);
            
            this.logActivity('mouse', {
                speed: speed,
                distance: distance,
                timestamp: Date.now()
            });
        }
    }
    
    handleTabSwitch() {
        this.logActivity('tabswitch', {
            hidden: document.hidden,
            timestamp: Date.now()
        });
    }
    
    calculateMouseSpeed(points) {
        if (points.length < 2) return 0;
        
        const timeElapsed = points[points.length - 1].timestamp - points[0].timestamp;
        const distance = this.calculateMouseDistance(points);
        
        return distance / (timeElapsed || 1);
    }
    
    calculateMouseDistance(points) {
        let distance = 0;
        
        for (let i = 1; i < points.length; i++) {
            const dx = points[i].x - points[i-1].x;
            const dy = points[i].y - points[i-1].y;
            distance += Math.sqrt(dx*dx + dy*dy);
        }
        
        return distance;
    }
    
    async updateRiskScore() {
        try {
            const response = await fetch(`/api/risk_score/${this.sessionId}`);
            const data = await response.json();
            this.updateRiskDisplay(data.score);
        } catch (error) {
            console.error('Failed to update risk score:', error);
        }
        
        setTimeout(() => this.updateRiskScore(), 5000);
    }
    
    updateRiskDisplay(score) {
        const riskDisplay = document.getElementById('risk-score');
        if (riskDisplay) {
            riskDisplay.textContent = `Risk Score: ${(score * 100).toFixed(1)}%`;
            riskDisplay.className = score > 0.7 ? 'high-risk' : score > 0.4 ? 'medium-risk' : 'low-risk';
        }
    }
    
    async submitExam() {
        try {
            await fetch('/api/submit_exam', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            });
            
            window.location.href = '/';
            
        } catch (error) {
            console.error('Failed to submit exam:', error);
        }
    }
}

// Initialize monitoring when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.examMonitor = new ExamMonitor();
});
