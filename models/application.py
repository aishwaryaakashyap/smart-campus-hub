from extensions import db
from datetime import datetime

class Application(db.Model):
    __tablename__ = 'applications'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    drive_id = db.Column(db.Integer, db.ForeignKey('placement_drives.id'), nullable=False)
    applied_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(30), default='Applied')
    remarks = db.Column(db.Text)

    student = db.relationship('Student', backref='applications')
    drive = db.relationship('PlacementDrive', backref='applications')

    def __repr__(self):
        return f'<Application student_id={self.student_id} drive_id={self.drive_id}>'