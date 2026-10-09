
from flask import Blueprint, request, jsonify, session
from extensions import db
from models import Grievance, GrievanceCategory, Student

grievance_bp = Blueprint('grievance', __name__)


def require_student():
    user_id = session.get('user_id')

    if not user_id:
        return None, (jsonify({'error': 'Not logged in'}), 401)

    if session.get('role') != 'student':
        return None, (
            jsonify({'error': 'Only students can perform this action'}),
            403
        )

    student = Student.query.filter_by(user_id=user_id).first()

    if not student:
        return None, (
            jsonify({'error': 'Create your student profile first'}),
            404
        )

    return student, None


@grievance_bp.route('/categories', methods=['GET'])
def get_categories():
    categories = GrievanceCategory.query.filter_by(
        is_active=True
    ).order_by(GrievanceCategory.name).all()

    return jsonify([
        {
            'id': category.id,
            'name': category.name,
            'description': category.description
        }
        for category in categories
    ]), 200


@grievance_bp.route('/', methods=['POST'])
def submit_grievance():
    student, error = require_student()
    if error:
        return error

    data = request.get_json(silent=True) or {}

    title = data.get('title')
    description = data.get('description')
    category_id = data.get('category_id')

    if not isinstance(title, str) or not title.strip():
        return jsonify({'error': 'Title is required'}), 400

    if len(title.strip()) > 200:
        return jsonify({'error': 'Title must be 200 characters or fewer'}), 400

    if not isinstance(description, str) or not description.strip():
        return jsonify({'error': 'Description is required'}), 400

    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'A valid category_id is required'}), 400

    category = db.session.get(GrievanceCategory, category_id)

    if not category or not category.is_active:
        return jsonify({'error': 'Invalid or inactive grievance category'}), 400

    priority = data.get('priority', 'Medium')

    if priority not in ('Low', 'Medium', 'High'):
        return jsonify({
            'error': 'Priority must be Low, Medium, or High'
        }), 400

    grievance = Grievance(
        student_id=student.id,
        category_id=category.id,
        title=title.strip(),
        description=description.strip(),
        location=data.get('location'),
        priority=priority,
        status='Submitted'
    )

    db.session.add(grievance)
    db.session.commit()

    return jsonify({
        'message': 'Grievance submitted successfully',
        'grievance': {
            'id': grievance.id,
            'title': grievance.title,
            'category': category.name,
            'priority': grievance.priority,
            'status': grievance.status,
            'created_at': grievance.created_at.isoformat()
        }
    }), 201


@grievance_bp.route('/mine', methods=['GET'])
def get_my_grievances():
    student, error = require_student()
    if error:
        return error

    grievances = Grievance.query.filter_by(
        student_id=student.id
    ).order_by(Grievance.created_at.desc()).all()

    return jsonify([
        {
            'id': grievance.id,
            'title': grievance.title,
            'category': grievance.category.name,
            'priority': grievance.priority,
            'status': grievance.status,
            'created_at': grievance.created_at.isoformat(),
            'updated_at': grievance.updated_at.isoformat()
            if grievance.updated_at else None
        }
        for grievance in grievances
    ]), 200


@grievance_bp.route('/<int:grievance_id>', methods=['GET'])
def get_grievance(grievance_id):
    student, error = require_student()
    if error:
        return error

    grievance = db.session.get(Grievance, grievance_id)

    if not grievance or grievance.student_id != student.id:
        return jsonify({'error': 'Grievance not found'}), 404

    return jsonify({
        'id': grievance.id,
        'title': grievance.title,
        'description': grievance.description,
        'location': grievance.location,
        'category': grievance.category.name,
        'priority': grievance.priority,
        'status': grievance.status,
        'created_at': grievance.created_at.isoformat(),
        'updated_at': grievance.updated_at.isoformat()
        if grievance.updated_at else None
    }), 200