from extensions import db


class GrievanceCategory(db.Model):
    __tablename__ = 'grievance_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<GrievanceCategory {self.name}>'