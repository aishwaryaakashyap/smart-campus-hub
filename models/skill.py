from extensions import db

class Skill(db.Model):
    __tablename__ = 'skills'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(50))  # e.g. Programming, Database, Soft Skill

    def __repr__(self):
        return f'<Skill {self.name}>'