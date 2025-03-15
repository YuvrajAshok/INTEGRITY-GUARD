import os
import logging
from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime

logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
db.init_app(app)

from models import User, ActivityLog, ExamSession, RiskScore
from ai_model import compute_risk_score

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/student/exam')
def student_exam():
    return render_template('student_exam.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/api/start_exam', methods=['POST'])
def start_exam():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not authenticated'}), 401
    
    exam_session = ExamSession(user_id=user_id, start_time=datetime.utcnow())
    db.session.add(exam_session)
    db.session.commit()
    
    return jsonify({
        'session_id': exam_session.id,
        'start_time': exam_session.start_time.isoformat()
    })

@app.route('/api/log_activity', methods=['POST'])
def log_activity():
    data = request.json
    session_id = data.get('session_id')
    
    activity_log = ActivityLog(
        session_id=session_id,
        activity_type=data.get('type'),
        timestamp=datetime.utcnow(),
        data=data.get('data')
    )
    db.session.add(activity_log)
    
    # Compute new risk score
    risk_value = compute_risk_score(session_id)
    risk_score = RiskScore(
        session_id=session_id,
        score=risk_value,
        timestamp=datetime.utcnow()
    )
    db.session.add(risk_score)
    db.session.commit()
    
    return jsonify({'risk_score': risk_value})

@app.route('/api/risk_score/<int:session_id>')
def get_risk_score(session_id):
    latest_score = RiskScore.query.filter_by(session_id=session_id)\
        .order_by(RiskScore.timestamp.desc()).first()
    
    if not latest_score:
        return jsonify({'error': 'No risk score found'}), 404
        
    return jsonify({
        'score': latest_score.score,
        'timestamp': latest_score.timestamp.isoformat()
    })

@app.route('/api/submit_exam', methods=['POST'])
def submit_exam():
    data = request.json
    session_id = data.get('session_id')
    
    exam_session = ExamSession.query.get(session_id)
    if not exam_session:
        return jsonify({'error': 'Session not found'}), 404
        
    exam_session.end_time = datetime.utcnow()
    exam_session.completed = True
    db.session.commit()
    
    return jsonify({'status': 'completed'})

with app.app_context():
    db.create_all()
