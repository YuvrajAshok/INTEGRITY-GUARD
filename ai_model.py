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
            'time_gaps': 0
        }

        for i, log in enumerate(activity_logs):
            if not log.data:  # Skip if data is None
                continue

            if log.activity_type == 'keystroke':
                # Check for unusually fast typing
                if log.data.get('keyInterval', 1000) < 50:  # milliseconds
                    patterns['rapid_typing'] += 1

            elif log.activity_type == 'mouse':
                # Check for unusual mouse movements
                if log.data.get('speed', 0) > 1000:  # pixels/sec
                    patterns['unusual_mouse'] += 1

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
        return {'rapid_typing': 0, 'unusual_mouse': 0, 'tab_switches': 0, 'time_gaps': 0}

def extract_features(activity_logs):
    """Extract features from activity logs for anomaly detection"""
    try:
        if not activity_logs:
            return np.zeros((1, 10))

        # Basic features
        keystroke_intervals = []
        mouse_speeds = []
        tab_switches = 0

        for log in activity_logs:
            if not log.data:  # Skip if data is None
                continue

            if log.activity_type == 'keystroke':
                interval = log.data.get('keyInterval')
                if interval is not None:
                    keystroke_intervals.append(min(float(interval), 1000))

            elif log.activity_type == 'mouse':
                speed = log.data.get('speed')
                if speed is not None:
                    mouse_speeds.append(min(float(speed), 2000))

            elif log.activity_type == 'tabswitch':
                tab_switches += 1

        # Compute statistical features with error handling
        features = [
            np.mean(keystroke_intervals) if keystroke_intervals else 0,
            np.std(keystroke_intervals) if len(keystroke_intervals) > 1 else 0,
            np.mean(mouse_speeds) if mouse_speeds else 0,
            np.std(mouse_speeds) if len(mouse_speeds) > 1 else 0,
            tab_switches,
            len(activity_logs),
            len(keystroke_intervals),
            len(mouse_speeds),
            max(keystroke_intervals) if keystroke_intervals else 0,
            max(mouse_speeds) if mouse_speeds else 0
        ]

        return np.array(features).reshape(1, -1)
    except Exception as e:
        logging.error(f"Error in extract_features: {str(e)}")
        return np.zeros((1, 10))

def compute_risk_score(session_id):
    """Compute comprehensive risk score using Isolation Forest"""
    try:
        # Get recent activity logs
        recent_logs = ActivityLog.query.filter_by(session_id=session_id)\
            .order_by(ActivityLog.timestamp.desc())\
            .limit(50).all()

        if not recent_logs:
            return 0.5  # Default score when not enough data

        # Extract features
        X = extract_features(recent_logs)

        # Train isolation forest
        iso_forest = IsolationForest(
            n_estimators=100,
            contamination=0.1,
            random_state=42
        )

        # Fit and predict
        iso_forest.fit(X)
        raw_score = iso_forest.score_samples(X)[0]

        # Analyze patterns
        patterns = analyze_activity_patterns(recent_logs)

        # Adjust score based on suspicious patterns
        pattern_penalty = (
            patterns['rapid_typing'] * 0.02 +
            patterns['unusual_mouse'] * 0.02 +
            patterns['tab_switches'] * 0.03 +
            patterns['time_gaps'] * 0.05
        )

        # Convert to 0-1 scale where 1 is high risk
        base_score = 1 - (raw_score + 0.5)  # Convert to 0-1 range
        final_score = min(1.0, max(0.0, base_score + pattern_penalty))  # Ensure score is between 0 and 1

        logging.debug(f"Risk score computed: {final_score} (base: {base_score}, penalty: {pattern_penalty})")
        return float(final_score)

    except Exception as e:
        logging.error(f"Error in compute_risk_score: {str(e)}")
        return 0.5  # Return default score on error