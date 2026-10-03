from extensions import db

class StudentAnswer(db.Model):
    __tablename__ = 'student_answers'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('interview_questions.id'), nullable=False)
    student_answer = db.Column(db.Text)
    answer_status = db.Column(db.String(20))  # Correct / Partially Correct / Incorrect / Not Evaluated
    reference_answer = db.Column(db.Text)

    question = db.relationship('InterviewQuestion', backref='answers')

    def __repr__(self):
        return f'<StudentAnswer for question_id={self.question_id}>'