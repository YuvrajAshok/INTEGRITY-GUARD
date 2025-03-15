import os
import logging
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

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
    try:
        data = request.json
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({'error': 'Missing session_id'}), 400

        # Create activity log
        activity_log = ActivityLog(
            session_id=session_id,
            activity_type=data.get('type'),
            timestamp=datetime.utcnow(),
            data=data.get('data', {})
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

        # Update mean risk score
        exam_session = ExamSession.query.get(session_id)
        if exam_session:
            all_scores = RiskScore.query.filter_by(session_id=session_id).all()
            if all_scores:
                mean_score = sum(score.score for score in all_scores) / len(all_scores)
                exam_session.mean_risk_score = mean_score
            else:
                exam_session.mean_risk_score = risk_value

        db.session.commit()

        return jsonify({
            'risk_score': risk_value,
            'mean_risk_score': exam_session.mean_risk_score if exam_session else risk_value
        })

    except Exception as e:
        logging.error(f"Error in log_activity: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/risk_score/<int:session_id>')
def get_risk_score(session_id):
    try:
        latest_score = RiskScore.query.filter_by(session_id=session_id)\
            .order_by(RiskScore.timestamp.desc()).first()

        exam_session = ExamSession.query.get(session_id)

        if not latest_score:
            return jsonify({'error': 'No risk score found'}), 404

        return jsonify({
            'score': latest_score.score,
            'mean_score': exam_session.mean_risk_score if exam_session else latest_score.score,
            'timestamp': latest_score.timestamp.isoformat()
        })

    except Exception as e:
        logging.error(f"Error in get_risk_score: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        is_admin = request.form.get('is_admin') == 'on'

        # Check if user already exists
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists')
            return redirect(url_for('register'))

        email_exists = User.query.filter_by(email=email).first()
        if email_exists:
            flash('Email already registered')
            return redirect(url_for('register'))

        # Create new user
        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=is_admin
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please login.')
        return redirect(url_for('index'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        is_admin = request.form.get('is_admin') == 'on'

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            if is_admin and not user.is_admin:
                flash('Unauthorized access to admin dashboard')
                return redirect(url_for('login'))

            session['user_id'] = user.id
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('student_exam'))

        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/api/active_sessions')
def get_active_sessions():
    # Get all active exam sessions
    active_sessions = ExamSession.query.filter_by(completed=False)\
        .order_by(ExamSession.start_time.desc()).all()

    session_data = []
    for session in active_sessions:
        # Get latest risk score
        latest_score = RiskScore.query.filter_by(session_id=session.id)\
            .order_by(RiskScore.timestamp.desc()).first()

        # Get recent suspicious activities
        recent_logs = ActivityLog.query.filter_by(session_id=session.id)\
            .order_by(ActivityLog.timestamp.desc())\
            .limit(5).all()

        # Get student info
        student = User.query.get(session.user_id)

        session_data.append({
            'id': session.id,
            'username': student.username,
            'start_time': session.start_time.isoformat(),
            'duration': int((datetime.utcnow() - session.start_time).total_seconds()),
            'risk_score': latest_score.score if latest_score else 0.0,
            'suspicious_activities': [
                {
                    'type': log.activity_type,
                    'timestamp': log.timestamp.isoformat(),
                    'data': log.data
                } for log in recent_logs
            ]
        })

    return jsonify(session_data)

@app.route('/api/end_session', methods=['POST'])
def end_session():
    data = request.json
    session_id = data.get('session_id')

    exam_session = ExamSession.query.get(session_id)
    if not exam_session:
        return jsonify({'error': 'Session not found'}), 404

    exam_session.end_time = datetime.utcnow()
    exam_session.completed = True

    # Calculate final mean risk score
    all_scores = RiskScore.query.filter_by(session_id=session_id).all()
    if all_scores:
        exam_session.mean_risk_score = sum(score.score for score in all_scores) / len(all_scores)

    db.session.commit()

    return jsonify({
        'status': 'completed',
        'mean_risk_score': exam_session.mean_risk_score
    })

with app.app_context():
    db.create_all()