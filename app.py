
from flask import Flask, render_template
from config import Config
from extensions import db

from models import (
    User,
    Student,
    Company,
    PlacementDrive,
    Application,
    CompanyUpdate,
    InterviewExperience,
    InterviewRound,
    InterviewQuestion,
    StudentAnswer,
    InterviewSkill,
    PreparationResource,
    Skill,
    StudentSkill,
)

from routes.company import company_bp
from routes.auth import auth_bp
from routes.placement_drive import drive_bp
from routes.application import application_bp
from routes.student import student_bp
from routes.company_update import update_bp
from routes.interview import interview_bp
from routes.interview_intelligence import intelligence_bp
from routes.skill import skill_bp
from routes.analytics import analytics_bp
from routes.skill_gap import skill_gap_bp
from routes.grievance import grievance_bp
from routes.notifications import notifications_bp


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)


# Authentication
app.register_blueprint(
    auth_bp,
    url_prefix='/api/auth'
)

# Company management
app.register_blueprint(
    company_bp,
    url_prefix='/api/companies'
)

# Placement drives
app.register_blueprint(
    drive_bp,
    url_prefix='/api/drives'
)

# Student applications
app.register_blueprint(
    application_bp,
    url_prefix='/api/applications'
)

# Student profiles
app.register_blueprint(
    student_bp,
    url_prefix='/api/students'
)

# Company announcements
app.register_blueprint(
    update_bp,
    url_prefix='/api/updates'
)

# Interview experiences
app.register_blueprint(
    interview_bp,
    url_prefix='/api/interviews'
)

# Interview intelligence
app.register_blueprint(
    intelligence_bp,
    url_prefix='/api/intelligence'
)

# Skills management
app.register_blueprint(
    skill_bp,
    url_prefix='/api/skills'
)

# Placement and grievance analytics dashboard
app.register_blueprint(
    analytics_bp,
    url_prefix='/api/analytics'
)

# Placement skill-gap analysis
app.register_blueprint(
    skill_gap_bp,
    url_prefix='/api/skill-gap'
)

# Campus grievance management
app.register_blueprint(
    grievance_bp,
    url_prefix='/api/grievances'
)

# In-app notifications
app.register_blueprint(
    notifications_bp,
    url_prefix='/api/notifications'
)


@app.route('/skill-gap')
def skill_gap_page():
    return render_template('skill_gap.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000
    )
