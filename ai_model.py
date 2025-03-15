import numpy as np
from sklearn.ensemble import IsolationForest
from datetime import datetime, timedelta
from models import ActivityLog
from app import db

def analyze_activity_patterns(activity_logs):
    """Analyze activity patterns for suspicious behavior"""
    patterns = {
        'rapid_typing': 0,
        'unusual_mouse': 0,
        'tab_switches': 0,
        'time_gaps': 0
    }

    for i, log in enumerate(activity_logs):
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
        if i > 0:
            time_gap = (log.timestamp - activity_logs[i-1].timestamp).total_seconds()
            if time_gap > 30:  # 30 seconds gap
                patterns['time_gaps'] += 1

    return patterns

def extract_features(activity_logs):
    """Extract features from activity logs for anomaly detection"""
    if not activity_logs:
        return np.zeros((1, 10))

    # Basic features
    keystroke_intervals = []
    mouse_speeds = []
    tab_switches = 0

    for log in activity_logs:
        if log.activity_type == 'keystroke':
            interval = log.data.get('keyInterval')
            if interval:
                keystroke_intervals.append(min(interval, 1000))  # Cap at 1 second

        elif log.activity_type == 'mouse':
            speed = log.data.get('speed')
            if speed:
                mouse_speeds.append(min(speed, 2000))  # Cap at 2000 pixels/sec

        elif log.activity_type == 'tabswitch':
            tab_switches += 1

    # Compute statistical features
    features = [
        np.mean(keystroke_intervals) if keystroke_intervals else 0,
        np.std(keystroke_intervals) if keystroke_intervals else 0,
        np.mean(mouse_speeds) if mouse_speeds else 0,
        np.std(mouse_speeds) if mouse_speeds else 0,
        tab_switches,
        len(activity_logs),  # Total activity count
        len(keystroke_intervals),  # Keystroke count
        len(mouse_speeds),  # Mouse movement count
        max(keystroke_intervals) if keystroke_intervals else 0,
        max(mouse_speeds) if mouse_speeds else 0
    ]

    return np.array(features).reshape(1, -1)

def compute_risk_score(session_id):
    """Compute comprehensive risk score using Isolation Forest"""

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
    final_score = min(1.0, base_score + pattern_penalty)

    return float(final_score)