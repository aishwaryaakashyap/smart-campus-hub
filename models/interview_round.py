from extensions import db

class InterviewRound(db.Model):
    __tablename__ = 'interview_rounds'

    id = db.Column(db.Integer, primary_key=True)
    experience_id = db.Column(db.Integer, db.ForeignKey('interview_experiences.id'), nullable=False)
    round_number = db.Column(db.Integer, nullable=False)
    round_type = db.Column(db.String(30))  # Aptitude, Coding, Technical, HR, Group Discussion, Managerial, Other
    mode = db.Column(db.String(30))  # Online / Offline / Telephonic
    duration_minutes = db.Column(db.Integer)
    difficulty = db.Column(db.String(20))
    remarks = db.Column(db.Text)

    experience = db.relationship('InterviewExperience', backref='rounds')

    def __repr__(self):
        return f'<InterviewRound {self.round_type} for experience_id={self.experience_id}>'