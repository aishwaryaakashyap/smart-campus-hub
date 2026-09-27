from extensions import db
from datetime import datetime

class PlacementDrive(db.Model):
    __tablename__ = 'placement_drives'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    job_role = db.Column(db.String(150), nullable=False)
    job_description = db.Column(db.Text)
    drive_date = db.Column(db.Date)
    application_deadline = db.Column(db.Date)
    salary_package = db.Column(db.String(50))
    location = db.Column(db.String(150))
    status = db.Column(db.String(20), default='Open')  # Open / Closed
    min_cgpa = db.Column(db.Float)
    eligible_branches = db.Column(db.String(255))  # comma-separated, e.g. "CSE,ISE,ECE"
    eligible_semester = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company', backref='placement_drives')

    def __repr__(self):
        return f'<PlacementDrive {self.job_role} at company_id={self.company_id}>'