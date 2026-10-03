from flask import Blueprint, request, jsonify, session
from extensions import db
from models import Student

student_bp = Blueprint('student', __name__)


def require_login_student():
    if 'user_id' not in session:
        return None, (jsonify({'error': 'Not logged in'}), 401)
    if session.get('role') != 'student':
        return None, (jsonify({'error': 'Only students can perform this action'}), 403)
    return session['user_id'], None


@student_bp.route('/profile', methods=['POST'])
def create_profile():
    user_id, error = require_login_student()
    if error:
        return error

    existing = Student.query.filter_by(user_id=user_id).first()
    if existing:
        return jsonify({'error': 'Profile already exists. Use PUT to update.'}), 409

    data = request.get_json()
    if 'register_number' not in data or not data['register_number']:
        return jsonify({'error': 'register_number is required'}), 400

    new_student = Student(
        user_id=user_id,
        register_number=data['register_number'],
        course=data.get('course'),
        branch=data.get('branch'),
        semester=data.get('semester'),
        cgpa=data.get('cgpa'),
        phone=data.get('phone'),
        graduation_year=data.get('graduation_year')
    )
    db.session.add(new_student)
    db.session.commit()

    return jsonify({'message': 'Student profile created successfully', 'id': new_student.id}), 201


@student_bp.route('/profile', methods=['GET'])
def get_profile():
    user_id, error = require_login_student()
    if error:
        return error

    student = Student.query.filter_by(user_id=user_id).first()
    if not student:
        return jsonify({'error': 'Profile not found'}), 404

    return jsonify({
        'id': student.id,
        'register_number': student.register_number,
        'course': student.course,
        'branch': student.branch,
        'semester': student.semester,
        'cgpa': student.cgpa,
        'phone': student.phone,
        'graduation_year': student.graduation_year
    }), 200


@student_bp.route('/profile', methods=['PUT'])
def update_profile():
    user_id, error = require_login_student()
    if error:
        return error

    student = Student.query.filter_by(user_id=user_id).first()
    if not student:
        return jsonify({'error': 'Profile not found. Create one first.'}), 404

    data = request.get_json()
    student.course = data.get('course', student.course)
    student.branch = data.get('branch', student.branch)
    student.semester = data.get('semester', student.semester)
    student.cgpa = data.get('cgpa', student.cgpa)
    student.phone = data.get('phone', student.phone)
    student.graduation_year = data.get('graduation_year', student.graduation_year)

    db.session.commit()
    return jsonify({'message': 'Profile updated successfully'}), 200