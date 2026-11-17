from flask import Blueprint, request, jsonify, session
from extensions import db
from models import Skill, StudentSkill, Student, User

skill_bp = Blueprint('skill', __name__)

VALID_PROFICIENCY = ['Beginner', 'Intermediate', 'Advanced']


def get_session_user(user_id):
    """Load the current account record for session validation."""
    return db.session.get(User, user_id)


def require_session_role(allowed_roles, forbidden_message):
    """Validate the session against the user's current database role."""
    user_id = session.get('user_id')

    if not user_id:
        return None, None, (jsonify({'error': 'Not logged in'}), 401)

    session_role = session.get('role')
    user = get_session_user(user_id)

    if not user or user.role != session_role:
        session.clear()
        return None, None, (jsonify({'error': 'Not logged in'}), 401)

    if session_role not in allowed_roles:
        return None, None, (
            jsonify({'error': forbidden_message}),
            403
        )

    return user_id, session_role, None


def require_coordinator():
    _, _, error = require_session_role(
        ('coordinator',),
        'Only coordinators can perform this action'
    )
    return error


def require_student():
    user_id, _, error = require_session_role(
        ('student',),
        'Only students can perform this action'
    )

    if error:
        return None, error

    student = Student.query.filter_by(user_id=user_id).first()

    if not student:
        return None, (
            jsonify({
                'error': 'Student profile not found. Create your profile first.'
            }),
            404
        )

    return student, None


@skill_bp.route('/', methods=['POST'])
def add_skill():
    auth_error = require_coordinator()
    if auth_error:
        return auth_error

    data = request.get_json()
    if 'name' not in data or not data['name']:
        return jsonify({'error': 'Skill name is required'}), 400

    existing = Skill.query.filter_by(name=data['name']).first()
    if existing:
        return jsonify({'error': 'Skill already exists', 'id': existing.id}), 409

    new_skill = Skill(name=data['name'], category=data.get('category'))
    db.session.add(new_skill)
    db.session.commit()

    return jsonify({'message': 'Skill added successfully', 'id': new_skill.id}), 201


@skill_bp.route('/', methods=['GET'])
def list_skills():
    skills = Skill.query.all()
    return jsonify([{'id': s.id, 'name': s.name, 'category': s.category} for s in skills]), 200


@skill_bp.route('/my-skills', methods=['POST'])
def add_my_skill():
    student, error = require_student()
    if error:
        return error

    data = request.get_json()
    if 'skill_id' not in data:
        return jsonify({'error': 'skill_id is required'}), 400

    skill = Skill.query.get(data['skill_id'])
    if not skill:
        return jsonify({'error': 'Skill not found'}), 404

    existing = StudentSkill.query.filter_by(student_id=student.id, skill_id=skill.id).first()
    if existing:
        return jsonify({'error': 'You already added this skill'}), 409

    proficiency = data.get('proficiency', 'Beginner')
    if proficiency not in VALID_PROFICIENCY:
        return jsonify({'error': f'proficiency must be one of {VALID_PROFICIENCY}'}), 400

    new_entry = StudentSkill(student_id=student.id, skill_id=skill.id, proficiency=proficiency)
    db.session.add(new_entry)
    db.session.commit()

    return jsonify({'message': 'Skill added to your profile', 'id': new_entry.id}), 201


@skill_bp.route('/my-skills', methods=['GET'])
def list_my_skills():
    student, error = require_student()
    if error:
        return error

    entries = StudentSkill.query.filter_by(student_id=student.id).all()
    return jsonify([{
        'skill_name': e.skill.name,
        'category': e.skill.category,
        'proficiency': e.proficiency
    } for e in entries]), 200