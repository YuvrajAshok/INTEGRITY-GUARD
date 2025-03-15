import numpy as np
from sklearn.ensemble import IsolationForest
from models import ActivityLog
from app import db

def extract_features(activity_logs):
    """Extract features from activity logs for anomaly detection"""
    features = []
    
    for log in activity_logs:
        if log.activity_type == 'keystroke':
            features.extend([
                log.data.get('keyInterval', 0),
                log.data.get('holdTime', 0)
            ])
        elif log.activity_type == 'mouse':
            features.extend([
                log.data.get('speed', 0),
                log.data.get('distance', 0)
            ])
        elif log.activity_type == 'tabswitch':
            features.append(1.0)  # Indicate tab switch occurred
            
    # Pad or truncate features to fixed length
    target_length = 10
    if len(features) < target_length:
        features.extend([0] * (target_length - len(features)))
    return np.array(features[:target_length]).reshape(1, -1)

def compute_risk_score(session_id):
    """Compute risk score using Isolation Forest"""
    
    # Get recent activity logs
    recent_logs = ActivityLog.query.filter_by(session_id=session_id)\
        .order_by(ActivityLog.timestamp.desc())\
        .limit(20).all()
    
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
    
    # Convert to 0-1 scale where 1 is high risk
    normalized_score = 1 - (raw_score + 0.5)  # Convert to 0-1 range
    
    return float(normalized_score)
