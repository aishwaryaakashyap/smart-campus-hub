from extensions import db

class StudentSkill(db.Model):
    __tablename__ = 'student_skills'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False)
    proficiency = db.Column(db.String(20))  # Beginner / Intermediate / Advanced

    student = db.relationship('Student', backref='student_skills')
    skill = db.relationship('Skill', backref='student_skills')

    def __repr__(self):
        return f'<StudentSkill student_id={self.student_id} skill_id={self.skill_id}>'