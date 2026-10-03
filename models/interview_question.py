from extensions import db

class InterviewQuestion(db.Model):
    __tablename__ = 'interview_questions'

    id = db.Column(db.Integer, primary_key=True)
    round_id = db.Column(db.Integer, db.ForeignKey('interview_rounds.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    topic = db.Column(db.String(100))
    difficulty = db.Column(db.String(20))

    round = db.relationship('InterviewRound', backref='questions')

    def __repr__(self):
        return f'<InterviewQuestion {self.question_text[:30]}>'