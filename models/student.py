from extensions import db

class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    register_number = db.Column(db.String(30), unique=True, nullable=False)
    course = db.Column(db.String(50))
    branch = db.Column(db.String(50))
    semester = db.Column(db.Integer)
    cgpa = db.Column(db.Float)
    phone = db.Column(db.String(15))
    graduation_year = db.Column(db.Integer)

    user = db.relationship('User', backref=db.backref('student_profile', uselist=False))

    def __repr__(self):
        return f'<Student {self.register_number}>'