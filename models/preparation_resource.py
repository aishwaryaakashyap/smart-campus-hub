from extensions import db

class PreparationResource(db.Model):
    __tablename__ = 'preparation_resources'

    id = db.Column(db.Integer, primary_key=True)
    experience_id = db.Column(db.Integer, db.ForeignKey('interview_experiences.id'), nullable=False)
    resource_type = db.Column(db.String(50))  # YouTube, GeeksforGeeks, LeetCode, Notes, Course, Mock Interview, Other
    resource_name = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(500))
    description = db.Column(db.Text)

    experience = db.relationship('InterviewExperience', backref='resources')

    def __repr__(self):
        return f'<PreparationResource {self.resource_name}>'