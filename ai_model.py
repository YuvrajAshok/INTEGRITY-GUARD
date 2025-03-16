import numpy as np
from sklearn.ensemble import IsolationForest
from datetime import datetime, timedelta
from models import ActivityLog
from app import db
import logging

def analyze_activity_patterns(activity_logs):
    """Analyze activity patterns for suspicious behavior"""
    try:
        if not activity_logs or len(activity_logs) < 2:
            return {
                'rapid_typing': 0,
                'unusual_mouse': 0,
                'tab_switches': 0,
                'time_gaps': 0,
                'right_clicks': 0,
                'suspicious_patterns': 0
            }
            
        patterns = {
            'rapid_typing': 0,
            'unusual_mouse': 0,
            'tab_switches': 0,
            'time_gaps': 0,
            'right_clicks': 0,
            'suspicious_patterns': 0
        }

        for i, log in enumerate(activity_logs):
            if not log.data:
                continue

            if log.activity_type == 'keystroke':
                if log.data.get('keyInterval', 1000) < 50:
                    patterns['rapid_typing'] += 2  # Increased weight
                if log.data.get('patterns', {}).get('consistentPattern'):
                    patterns['suspicious_patterns'] += 2

            elif log.activity_type == 'mouse':
                if log.data.get('speed', 0) > 800:  # Lowered threshold
                    patterns['unusual_mouse'] += 2

                pattern = log.data.get('pattern', {})
                if pattern.get('isLinear') or pattern.get('isCircular'):
                    patterns['suspicious_patterns'] += 2
                if pattern.get('suddenJumps', 0) > 0:
                    patterns['unusual_mouse'] += pattern['suddenJumps'] * 2

            elif log.activity_type == 'right_click':
                if log.data.get('timeSinceLastClick', 1000) < 300:
                    patterns['right_clicks'] += 2

            elif log.activity_type == 'tabswitch':
                patterns['tab_switches'] += 2

            if i > 0 and activity_logs[i-1].timestamp:
                time_gap = (log.timestamp - activity_logs[i-1].timestamp).total_seconds()
                if time_gap > 20:  # Lowered threshold
                    patterns['time_gaps'] += 2

        return patterns
    except Exception as e:
        logging.error(f"Error in analyze_activity_patterns: {str(e)}")
        return {'rapid_typing': 0, 'unusual_mouse': 0, 'tab_switches': 0, 
                'time_gaps': 0, 'right_clicks': 0, 'suspicious_patterns': 0}

def calculate_risk_level(patterns):
    """Calculate risk level based on frequency of suspicious activities"""
    thresholds = {
        'rapid_typing': {'low': 2, 'medium': 4, 'high': 6},
        'unusual_mouse': {'low': 2, 'medium': 4, 'high': 6},
        'tab_switches': {'low': 2, 'medium': 4, 'high': 6},
        'time_gaps': {'low': 2, 'medium': 4, 'high': 6},
        'right_clicks': {'low': 2, 'medium': 4, 'high': 6},
        'suspicious_patterns': {'low': 2, 'medium': 4, 'high': 6}
    }

    risk_levels = {}
    for pattern, count in patterns.items():
        if pattern in thresholds:
            if count >= thresholds[pattern]['high']:
                risk_levels[pattern] = 1.0
            elif count >= thresholds[pattern]['medium']:
                risk_levels[pattern] = 0.75  # Increased from 0.7
            elif count >= thresholds[pattern]['low']:
                risk_levels[pattern] = 0.5   # Increased from 0.4
            else:
                risk_levels[pattern] = 0.25  # Base risk level

    # Equal weights for all patterns for more balanced detection
    weights = {
        'rapid_typing': 1/6,
        'unusual_mouse': 1/6,
        'tab_switches': 1/6,
        'time_gaps': 1/6,
        'right_clicks': 1/6,
        'suspicious_patterns': 1/6
    }

    total_risk = sum(risk_levels[pattern] * weights[pattern] for pattern in risk_levels.keys())

    # Apply progressive scaling
    if total_risk > 0.6:
        scaled_risk = min(1.0, total_risk * 1.5)
    elif total_risk > 0.3:
        scaled_risk = min(1.0, total_risk * 1.3)
    else:
        scaled_risk = total_risk

    return scaled_risk

def compute_risk_score(session_id):
    """Compute comprehensive risk score using pattern analysis and Isolation Forest"""
    try:
        recent_time = datetime.utcnow() - timedelta(seconds=30)
        recent_logs = ActivityLog.query.filter_by(session_id=session_id)\
            .filter(ActivityLog.timestamp >= recent_time)\
            .order_by(ActivityLog.timestamp.desc()).all()

        if not recent_logs or len(recent_logs) < 2:
            return 0.0

        patterns = analyze_activity_patterns(recent_logs)
        if sum(patterns.values()) == 0:
            return 0.0
            
        pattern_risk = calculate_risk_level(patterns)
        X = extract_features(recent_logs)
        iso_forest = IsolationForest(
            n_estimators=100,
            contamination=0.3,  # Increased sensitivity
            random_state=42
        )
        iso_forest.fit(X)
        anomaly_score = -iso_forest.score_samples(X)[0]

        # Weighted combination favoring pattern-based detection
        final_score = 0.7 * pattern_risk + 0.3 * anomaly_score
        final_score = min(1.0, max(0.0, final_score))

        logging.debug(f"Risk score computed: {final_score:.2f} (pattern: {pattern_risk:.2f}, anomaly: {anomaly_score:.2f})")
        return float(final_score)

    except Exception as e:
        logging.error(f"Error in compute_risk_score: {str(e)}")
        return 0.0

def extract_features(activity_logs):
    """Extract features from activity logs for anomaly detection"""
    try:
        if not activity_logs:
            return np.zeros((1, 15))

        keystroke_intervals = []
        mouse_speeds = []
        right_clicks = []
        tab_switches = 0
        suspicious_patterns = 0

        for log in activity_logs:
            if not log.data:
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