from flask import Flask
from config import Config
from extensions import db
from models import User, Student, Company
from routes.auth import auth_bp
from routes.company import company_bp

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(company_bp, url_prefix='/api/companies')

@app.route('/')
def home():
    return '<h1>Smart Campus Hub</h1><p>Flask + Database connected!</p>'

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")
    app.run(debug=True, host='0.0.0.0', port=5000)