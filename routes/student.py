
from flask import Blueprint, request, jsonify, session
from extensions import db
from models import Student, User

student_bp = Blueprint('student', __name__)


def get_session_user(user_id):
    """Load the current account record for session validation."""
    return db.session.get(User, user_id)


def require_login_student():
    """Verify that the current account is active and has the student role."""
    user_id = session.get('user_id')

    if not user_id:
        return None, (
            jsonify({'error': 'Not logged in'}),
            401
        )

    session_role = session.get('role')
    user = get_session_user(user_id)

    # Invalidate sessions for deleted, inactive, or changed-role accounts.
    if (
        not user
        or user.role != session_role
        or user.account_status != User.STATUS_ACTIVE
    ):
        session.clear()
        return None, (
            jsonify({'error': 'Not logged in'}),
            401
        )

    if session_role != 'student':
        return None, (
            jsonify({
                'error': 'Only students can perform this action'
            }),
            403
        )

    return user_id, None


@student_bp.route('/profile', methods=['POST'])
def create_profile():
    user_id, error = require_login_student()

    if error:
        return error

    existing = Student.query.filter_by(
        user_id=user_id
    ).first()

    if existing:
        return jsonify({
            'error': 'Profile already exists. Use PUT to update.'
        }), 409

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'A valid JSON object is required'
        }), 400

    if not data.get('register_number'):
        return jsonify({
            'error': 'register_number is required'
        }), 400

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

    try:
        db.session.add(new_student)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to create student profile'
        }), 500

    return jsonify({
        'message': 'Student profile created successfully',
        'id': new_student.id
    }), 201


@student_bp.route('/profile', methods=['GET'])
def get_profile():
    user_id, error = require_login_student()

    if error:
        return error

    student = Student.query.filter_by(
        user_id=user_id
    ).first()

    if not student:
        return jsonify({
            'error': 'Profile not found'
        }), 404

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

    student = Student.query.filter_by(
        user_id=user_id
    ).first()

    if not student:
        return jsonify({
            'error': 'Profile not found. Create one first.'
        }), 404

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'A valid JSON object is required'
        }), 400

    student.course = data.get(
        'course',
        student.course
    )
    student.branch = data.get(
        'branch',
        student.branch
    )
    student.semester = data.get(
        'semester',
        student.semester
    )
    student.cgpa = data.get(
        'cgpa',
        student.cgpa
    )
    student.phone = data.get(
        'phone',
        student.phone
    )
    student.graduation_year = data.get(
        'graduation_year',
        student.graduation_year
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to update student profile'
        }), 500

    return jsonify({
        'message': 'Profile updated successfully'
    }), 200
