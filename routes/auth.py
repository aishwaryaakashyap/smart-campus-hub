from flask import Blueprint, request, jsonify, session, render_template
from extensions import db
from models import User, Student

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'A valid JSON object is required'
        }), 400

    required_fields = ['name', 'email', 'password', 'role']

    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({
                'error': f'{field} is required'
            }), 400

    valid_roles = [
        'student',
        'coordinator',
        'advisor',
        'vice_chairperson',
        'chairperson'
    ]

    if not isinstance(data['role'], str) or data['role'] not in valid_roles:
        return jsonify({
            'error': f'Role must be one of {valid_roles}'
        }), 400

    if not all(
        isinstance(data[field], str)
        for field in ['name', 'email', 'password']
    ):
        return jsonify({
            'error': 'Name, email, and password must be strings'
        }), 400

    if not data['name'].strip() or not data['email'].strip():
        return jsonify({
            'error': 'Name and email cannot be blank'
        }), 400

    if len(data['password']) < 8:
        return jsonify({
            'error': 'Password must be at least 8 characters long'
        }), 400

    email = data['email'].strip().lower()

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        return jsonify({
            'error': 'Email already registered'
        }), 409

    new_user = User(
        name=data['name'].strip(),
        email=email,
        role=data['role']
    )
    new_user.set_password(data['password'])

    try:
        db.session.add(new_user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to register user'
        }), 500

    return jsonify({
        'message': 'User registered successfully',
        'user_id': new_user.id,
        'email': new_user.email,
        'role': new_user.role
    }), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'A valid JSON object is required'
        }), 400

    if (
        not isinstance(data.get('email'), str)
        or not isinstance(data.get('password'), str)
        or not data['email'].strip()
        or not data['password']
    ):
        return jsonify({
            'error': 'Email and password are required'
        }), 400

    email = data['email'].strip().lower()

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(data['password']):
        return jsonify({
            'error': 'Invalid email or password'
        }), 401

    session.clear()
    session['user_id'] = user.id
    session['role'] = user.role

    return jsonify({
        'message': 'Login successful',
        'user_id': user.id,
        'name': user.name,
        'role': user.role
    }), 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()

    return jsonify({
        'message': 'Logged out successfully'
    }), 200


@auth_bp.route('/me', methods=['GET'])
def me():
    if 'user_id' not in session:
        return jsonify({
            'error': 'Not logged in'
        }), 401

    user = db.session.get(User, session['user_id'])

    if not user:
        session.clear()
        return jsonify({
            'error': 'Not logged in'
        }), 401

    return jsonify({
        'user_id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role
    }), 200


@auth_bp.route('/login-page', methods=['GET'])
def login_page():
    return render_template('login.html')