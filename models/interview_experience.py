from extensions import db
from datetime import datetime

class InterviewExperience(db.Model):
    __tablename__ = 'interview_experiences'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    job_role = db.Column(db.String(150))
    year = db.Column(db.Integer)
    selection_status = db.Column(db.String(20))  # Selected / Not Selected
    overall_difficulty = db.Column(db.String(20))  # Easy / Medium / Hard
    preparation_summary = db.Column(db.Text)
    selection_factors = db.Column(db.Text)  # student-reported, not causal
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship('Student', backref='interview_experiences')
    company = db.relationship('Company', backref='interview_experiences')

    def __repr__(self):
        return f'<InterviewExperience student_id={self.student_id} company_id={self.company_id}>'