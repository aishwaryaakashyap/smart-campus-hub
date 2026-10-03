from extensions import db
from datetime import datetime

class CompanyUpdate(db.Model):
    __tablename__ = 'company_updates'

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)

    company = db.relationship('Company', backref='updates')

    def __repr__(self):
        return f'<CompanyUpdate {self.title}>'