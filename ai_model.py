import numpy as np
from sklearn.ensemble import IsolationForest
from datetime import datetime, timedelta
from models import ActivityLog
from app import db
import logging

def analyze_activity_patterns(activity_logs):
    """Analyze activity patterns for suspicious behavior"""
    try:
        patterns = {
            'rapid_typing': 0,
            'unusual_mouse': 0,
            'tab_switches': 0,
            'time_gaps': 0,
            'right_clicks': 0,
            'suspicious_patterns': 0
        }

        for i, log in enumerate(activity_logs):
            if not log.data:  # Skip if data is None
                continue

            if log.activity_type == 'keystroke':
                # Check for unusually fast typing
                if log.data.get('keyInterval', 1000) < 50:  # milliseconds
                    patterns['rapid_typing'] += 1

                # Check for suspicious typing patterns
                log_patterns = log.data.get('patterns', {})
                if log_patterns.get('consistentPattern'):
                    patterns['suspicious_patterns'] += 1

            elif log.activity_type == 'mouse':
                # Check for unusual mouse movements
                if log.data.get('speed', 0) > 1000:  # pixels/sec
                    patterns['unusual_mouse'] += 1

                # Check for suspicious mouse patterns
                mouse_pattern = log.data.get('pattern', {})
                if mouse_pattern.get('isLinear') or mouse_pattern.get('isCircular'):
                    patterns['suspicious_patterns'] += 1
                if mouse_pattern.get('suddenJumps', 0) > 0:
                    patterns['unusual_mouse'] += mouse_pattern['suddenJumps']

            elif log.activity_type == 'right_click':
                if log.data.get('timeSinceLastClick', 1000) < 200:  # milliseconds
                    patterns['right_clicks'] += 1

            elif log.activity_type == 'tabswitch':
                patterns['tab_switches'] += 1

            # Check for suspicious time gaps
            if i > 0 and activity_logs[i-1].timestamp:
                time_gap = (log.timestamp - activity_logs[i-1].timestamp).total_seconds()
                if time_gap > 30:  # 30 seconds gap
                    patterns['time_gaps'] += 1

        return patterns
    except Exception as e:
        logging.error(f"Error in analyze_activity_patterns: {str(e)}")
        return {'rapid_typing': 0, 'unusual_mouse': 0, 'tab_switches': 0, 
                'time_gaps': 0, 'right_clicks': 0, 'suspicious_patterns': 0}

def calculate_risk_level(patterns):
    """Calculate risk level based on frequency of suspicious activities"""
    # Define thresholds for each pattern type - lowered thresholds for more sensitivity
    thresholds = {
        'rapid_typing': {'low': 2, 'medium': 4, 'high': 6},
        'unusual_mouse': {'low': 1, 'medium': 3, 'high': 5},
        'tab_switches': {'low': 1, 'medium': 2, 'high': 4},
        'time_gaps': {'low': 1, 'medium': 2, 'high': 3},
        'right_clicks': {'low': 1, 'medium': 3, 'high': 5},
        'suspicious_patterns': {'low': 1, 'medium': 2, 'high': 3}
    }

    # Calculate risk level for each pattern with higher risk values
    risk_levels = {}
    for pattern, count in patterns.items():
        if pattern in thresholds:
            if count >= thresholds[pattern]['high']:
                risk_levels[pattern] = 1.0  # High risk
            elif count >= thresholds[pattern]['medium']:
                risk_levels[pattern] = 0.7  # Medium risk (increased from 0.6)
            elif count >= thresholds[pattern]['low']:
                risk_levels[pattern] = 0.4  # Low risk (increased from 0.3)
            else:
                risk_levels[pattern] = 0.0  # No risk

    # Calculate weighted average risk score with adjusted weights
    weights = {
        'rapid_typing': 0.25,
        'unusual_mouse': 0.25,
        'tab_switches': 0.15,
        'time_gaps': 0.15,
        'right_clicks': 0.10,
        'suspicious_patterns': 0.10
    }

    total_risk = sum(risk_levels[pattern] * weights[pattern] 
                    for pattern in risk_levels.keys())

    # Apply exponential scaling to increase sensitivity
    scaled_risk = min(1.0, total_risk * 1.5)  # Scale up risk score
    return scaled_risk

def compute_risk_score(session_id):
    """Compute comprehensive risk score using pattern analysis and Isolation Forest"""
    try:
        # Get recent activity logs (last 30 seconds)
        recent_time = datetime.utcnow() - timedelta(seconds=30)
        recent_logs = ActivityLog.query.filter_by(session_id=session_id)\
            .filter(ActivityLog.timestamp >= recent_time)\
            .order_by(ActivityLog.timestamp.desc()).all()

        if not recent_logs:
            return 0.0  # Default score when not enough data

        # Analyze patterns
        patterns = analyze_activity_patterns(recent_logs)
        pattern_risk = calculate_risk_level(patterns)

        # Train isolation forest for anomaly detection
        X = extract_features(recent_logs)
        iso_forest = IsolationForest(
            n_estimators=100,
            contamination=0.2,  # Increased from 0.1 for more sensitivity
            random_state=42
        )
        iso_forest.fit(X)
        anomaly_score = -iso_forest.score_samples(X)[0]  # Convert to 0-1 scale

        # Combine pattern risk and anomaly detection with higher weight on patterns
        final_score = 0.8 * pattern_risk + 0.2 * anomaly_score
        final_score = min(1.0, max(0.0, final_score))  # Ensure score is between 0 and 1

        logging.debug(f"Risk score computed: {final_score:.2f} (pattern: {pattern_risk:.2f}, anomaly: {anomaly_score:.2f})")
        return float(final_score)

    except Exception as e:
        logging.error(f"Error in compute_risk_score: {str(e)}")
        return 0.0  # Return default score on error

def extract_features(activity_logs):
    """Extract features from activity logs for anomaly detection"""
    try:
        if not activity_logs:
            return np.zeros((1, 15))

        # Basic features
        keystroke_intervals = []
        mouse_speeds = []
        right_clicks = []
        tab_switches = 0
        suspicious_patterns = 0

        for log in activity_logs:
            if not log.data:  # Skip if data is None
                continue

            if log.activity_type == 'keystroke':
                interval = log.data.get('keyInterval')
                if interval is not None:
                    keystroke_intervals.append(min(float(interval), 1000))

                patterns = log.data.get('patterns', {})
                if patterns.get('consistentPattern'):
                    suspicious_patterns += 1

            elif log.activity_type == 'mouse':
                speed = log.data.get('speed')
                if speed is not None:
                    mouse_speeds.append(min(float(speed), 2000))

                pattern = log.data.get('pattern', {})
                if pattern.get('isLinear') or pattern.get('isCircular'):
                    suspicious_patterns += 1

            elif log.activity_type == 'right_click':
                time_since_last = log.data.get('timeSinceLastClick')
                if time_since_last is not None:
                    right_clicks.append(min(float(time_since_last), 2000))

            elif log.activity_type == 'tabswitch':
                tab_switches += 1

        # Compute statistical features
        features = [
            np.mean(keystroke_intervals) if keystroke_intervals else 0,
            np.std(keystroke_intervals) if len(keystroke_intervals) > 1 else 0,
            np.mean(mouse_speeds) if mouse_speeds else 0,
            np.std(mouse_speeds) if len(mouse_speeds) > 1 else 0,
            np.mean(right_clicks) if right_clicks else 0,
            np.std(right_clicks) if len(right_clicks) > 1 else 0,
            tab_switches,
            len(activity_logs),
            len(keystroke_intervals),
            len(mouse_speeds),
            len(right_clicks),
            max(keystroke_intervals) if keystroke_intervals else 0,
            max(mouse_speeds) if mouse_speeds else 0,
            max(right_clicks) if right_clicks else 0,
            suspicious_patterns
        ]

        return np.array(features).reshape(1, -1)
    except Exception as e:
        logging.error(f"Error in extract_features: {str(e)}")
        return np.zeros((1, 15))