class ExamMonitor {
    constructor() {
        this.sessionId = null;
        this.lastKeystrokeTime = Date.now();
        this.mousePoints = [];
        this.riskScore = 0;
        this.keyPressHistory = [];
        this.rightClickCount = 0;
        this.lastRightClickTime = Date.now();

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
        document.addEventListener('contextmenu', this.handleRightClick.bind(this));
        document.addEventListener('visibilitychange', this.handleTabSwitch.bind(this));

        // Prevent right-click context menu
        document.addEventListener('contextmenu', (e) => e.preventDefault());

        // Start periodic risk score updates (every 3 seconds)
        setInterval(() => this.updateRiskScore(), 3000);
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

        // Store keystroke data for pattern analysis
        this.keyPressHistory.push({
            key: event.key,
            time: currentTime,
            interval: keyInterval
        });

        // Keep only last 20 keystrokes for pattern analysis
        if (this.keyPressHistory.length > 20) {
            this.keyPressHistory.shift();
        }

        // Calculate typing patterns
        const patterns = this.analyzeTypingPatterns();

        this.logActivity('keystroke', {
            key: event.key,
            keyInterval: keyInterval,
            timestamp: currentTime,
            patterns: patterns
        });

        this.lastKeystrokeTime = currentTime;
    }

    analyzeTypingPatterns() {
        if (this.keyPressHistory.length < 2) return {};

        const intervals = this.keyPressHistory.slice(1).map((entry, i) => 
            entry.time - this.keyPressHistory[i].time);

        return {
            avgInterval: intervals.reduce((a, b) => a + b, 0) / intervals.length,
            rapidKeystrokes: intervals.filter(i => i < 50).length,
            consistentPattern: this.detectConsistentPattern()
        };
    }

    detectConsistentPattern() {
        // Check for repeated sequences that might indicate automated input
        const keys = this.keyPressHistory.map(k => k.key).join('');
        const patterns = {};
        for (let i = 0; i < keys.length - 2; i++) {
            const pattern = keys.substr(i, 3);
            patterns[pattern] = (patterns[pattern] || 0) + 1;
        }
        return Object.values(patterns).some(count => count > 3);
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
            const pattern = this.analyzeMousePattern(points);

            this.logActivity('mouse', {
                speed: speed,
                distance: distance,
                pattern: pattern,
                timestamp: Date.now()
            });
        }
    }

    handleRightClick(event) {
        event.preventDefault();
        const currentTime = Date.now();
        const timeSinceLastClick = currentTime - this.lastRightClickTime;
        this.rightClickCount++;

        this.logActivity('right_click', {
            count: this.rightClickCount,
            timeSinceLastClick: timeSinceLastClick,
            timestamp: currentTime
        });

        this.lastRightClickTime = currentTime;
    }

    analyzeMousePattern(points) {
        // Detect suspicious patterns like perfect circles or straight lines
        const pattern = {
            isLinear: this.checkLinearMovement(points),
            isCircular: this.checkCircularMovement(points),
            suddenJumps: this.checkSuddenJumps(points)
        };
        return pattern;
    }

    checkLinearMovement(points) {
        if (points.length < 3) return false;

        // Check if points form a roughly straight line
        let sumDeviation = 0;
        for (let i = 1; i < points.length - 1; i++) {
            const expected = {
                x: points[i-1].x + (points[i+1].x - points[i-1].x) / 2,
                y: points[i-1].y + (points[i+1].y - points[i-1].y) / 2
            };
            const deviation = Math.sqrt(
                Math.pow(points[i].x - expected.x, 2) +
                Math.pow(points[i].y - expected.y, 2)
            );
            sumDeviation += deviation;
        }
        return (sumDeviation / (points.length - 2)) < 5; // Threshold for linearity
    }

    checkCircularMovement(points) {
        if (points.length < 5) return false;

        // Calculate center point
        const center = {
            x: points.reduce((sum, p) => sum + p.x, 0) / points.length,
            y: points.reduce((sum, p) => sum + p.y, 0) / points.length
        };

        // Check if all points are roughly the same distance from center
        const distances = points.map(p => 
            Math.sqrt(Math.pow(p.x - center.x, 2) + Math.pow(p.y - center.y, 2))
        );
        const avgDistance = distances.reduce((a, b) => a + b, 0) / distances.length;
        const isCircular = distances.every(d => Math.abs(d - avgDistance) < 10);

        return isCircular;
    }

    checkSuddenJumps(points) {
        if (points.length < 2) return 0;

        let jumps = 0;
        for (let i = 1; i < points.length; i++) {
            const distance = Math.sqrt(
                Math.pow(points[i].x - points[i-1].x, 2) +
                Math.pow(points[i].y - points[i-1].y, 2)
            );
            if (distance > 200) { // Threshold for sudden jump
                jumps++;
            }
        }
        return jumps;
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
    }

    updateRiskDisplay(score) {
        const riskDisplay = document.getElementById('risk-score');
        if (riskDisplay) {
            riskDisplay.textContent = `Risk Score: ${(score * 100).toFixed(1)}%`;
            riskDisplay.className = `risk-score ${score > 0.7 ? 'high-risk' : score > 0.4 ? 'medium-risk' : 'low-risk'}`;
        }
    }

    async endSession() {
        try {
            await fetch('/api/end_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            });

            // Clear all event listeners
            document.removeEventListener('keydown', this.handleKeyDown);
            document.removeEventListener('keyup', this.handleKeyUp);
            document.removeEventListener('mousemove', this.handleMouseMove);
            document.removeEventListener('contextmenu', this.handleRightClick);
            document.removeEventListener('visibilitychange', this.handleTabSwitch);

            // Redirect to login page
            window.location.href = '/logout';

        } catch (error) {
            console.error('Failed to end session:', error);
        }
    }
}

// Initialize monitoring when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.examMonitor = new ExamMonitor();
});