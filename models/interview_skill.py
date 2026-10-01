from extensions import db

class InterviewSkill(db.Model):
    __tablename__ = 'interview_skills'

    id = db.Column(db.Integer, primary_key=True)
    experience_id = db.Column(db.Integer, db.ForeignKey('interview_experiences.id'), nullable=False)
    skill_name = db.Column(db.String(100), nullable=False)
    importance_rating = db.Column(db.Integer)  # 1 (low) to 5 (high), student-reported

    experience = db.relationship('InterviewExperience', backref='skills')

    def __repr__(self):
        return f'<InterviewSkill {self.skill_name}>'