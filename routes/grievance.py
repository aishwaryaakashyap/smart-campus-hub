
from flask import Blueprint, request, jsonify, session
from datetime import datetime, timezone

from extensions import db
from models import (
    Grievance,
    GrievanceCategory,
    GrievanceUpdate,
    Student,
    User,
)
from services.notifications import create_notification
from services.grievance_sla import calculate_sla_due_at


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


def notify_grievance_staff(grievance, title, message):
    """Notify coordinators and the assigned advisor without duplicates."""
    recipients = {}

    coordinators = User.query.filter_by(role='coordinator').all()

    for coordinator in coordinators:
        recipients[coordinator.id] = coordinator

    if grievance.assigned_to:
        advisor = db.session.get(User, grievance.assigned_to)

        if advisor and advisor.role == 'advisor':
            recipients[advisor.id] = advisor

    for recipient in recipients.values():
        create_notification(
            user_id=recipient.id,
            title=title,
            message=message,
            notification_type='grievance'
        )


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

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            'error': 'Request body must be a JSON object'
        }), 400

    title = data.get('title')
    description = data.get('description')
    category_id = data.get('category_id')

    if not isinstance(title, str) or not title.strip():
        return jsonify({'error': 'Title is required'}), 400

    if len(title.strip()) > 200:
        return jsonify({
            'error': 'Title must be 200 characters or fewer'
        }), 400

    if not isinstance(description, str) or not description.strip():
        return jsonify({'error': 'Description is required'}), 400

    if isinstance(category_id, bool):
        return jsonify({
            'error': 'A valid category_id is required'
        }), 400

    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        return jsonify({
            'error': 'A valid category_id is required'
        }), 400

    if category_id <= 0:
        return jsonify({
            'error': 'A valid category_id is required'
        }), 400

    category = db.session.get(GrievanceCategory, category_id)

    if not category or not category.is_active:
        return jsonify({
            'error': 'Invalid or inactive grievance category'
        }), 400

    priority = data.get('priority', 'Medium')

    if not isinstance(priority, str) or priority not in (
        'Low', 'Medium', 'High'
    ):
        return jsonify({
            'error': 'Priority must be Low, Medium, or High'
        }), 400

    try:
        sla_due_at = calculate_sla_due_at(priority)
    except ValueError:
        return jsonify({
            'error': 'Grievance SLA configuration is invalid'
        }), 500

    location = data.get('location')

    if location is not None and not isinstance(location, str):
        return jsonify({'error': 'Location must be text'}), 400

    grievance = Grievance(
        student_id=student.id,
        category_id=category.id,
        title=title.strip(),
        description=description.strip(),
        location=location.strip() if location and location.strip() else None,
        priority=priority,
        status='Submitted',
        sla_due_at=sla_due_at
    )

    try:
        db.session.add(grievance)
        db.session.flush()

        coordinators = User.query.filter_by(role='coordinator').all()

        for coordinator in coordinators:
            create_notification(
                user_id=coordinator.id,
                title='New Grievance Submitted',
                message=(
                    f'A new grievance "{grievance.title}" '
                    f'has been submitted.'
                ),
                notification_type='grievance'
            )

        db.session.commit()

    except Exception:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to submit grievance at this time'
        }), 500

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
        if grievance.updated_at else None,
        'sla_due_at': grievance.sla_due_at.isoformat()
        if grievance.sla_due_at else None,
        'resolution_confirmed_at':
            grievance.resolution_confirmed_at.isoformat()
            if grievance.resolution_confirmed_at else None,
        'reopen_count': grievance.reopen_count or 0
    }), 200


@grievance_bp.route('/<int:grievance_id>/confirm-resolution', methods=['PUT'])
def confirm_grievance_resolution(grievance_id):
    student, error = require_student()
    if error:
        return error

    grievance = db.session.get(Grievance, grievance_id)

    if not grievance or grievance.student_id != student.id:
        return jsonify({'error': 'Grievance not found'}), 404

    if grievance.status != 'Resolved':
        return jsonify({
            'error': 'Only resolved grievances can be confirmed'
        }), 409

    if grievance.resolution_confirmed_at:
        return jsonify({
            'message': 'Resolution has already been confirmed',
            'resolution_confirmed_at':
                grievance.resolution_confirmed_at.isoformat()
        }), 200

    confirmed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    history = GrievanceUpdate(
        grievance_id=grievance.id,
        updated_by=session['user_id'],
        old_status='Resolved',
        new_status='Resolved',
        comment='Student confirmed that the grievance is resolved.'
    )

    try:
        grievance.resolution_confirmed_at = confirmed_at
        db.session.add(history)

        notify_grievance_staff(
            grievance,
            'Grievance Resolution Confirmed',
            (
                f'The student confirmed that grievance '
                f'"{grievance.title}" is resolved.'
            )
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to confirm grievance resolution'
        }), 500

    return jsonify({
        'message': 'Grievance resolution confirmed successfully',
        'grievance_id': grievance.id,
        'resolution_confirmed_at': confirmed_at.isoformat()
    }), 200


@grievance_bp.route('/<int:grievance_id>/reopen', methods=['PUT'])
def reopen_grievance(grievance_id):
    student, error = require_student()
    if error:
        return error

    grievance = db.session.get(Grievance, grievance_id)

    if not grievance or grievance.student_id != student.id:
        return jsonify({'error': 'Grievance not found'}), 404

    if grievance.status != 'Resolved':
        return jsonify({
            'error': 'Only resolved grievances can be reopened'
        }), 409

    data = request.get_json(silent=True)

    if data is None:
        data = {}

    if not isinstance(data, dict):
        return jsonify({
            'error': 'Request body must be a JSON object'
        }), 400

    comment = data.get('comment')

    if comment is not None and not isinstance(comment, str):
        return jsonify({'error': 'Comment must be text'}), 400

    if isinstance(comment, str) and len(comment.strip()) > 1000:
        return jsonify({
            'error': 'Comment must be 1000 characters or fewer'
        }), 400

    try:
        new_sla_due_at = calculate_sla_due_at(grievance.priority)
    except ValueError:
        return jsonify({
            'error': 'Grievance SLA configuration is invalid'
        }), 500

    old_status = grievance.status
    history = GrievanceUpdate(
        grievance_id=grievance.id,
        updated_by=session['user_id'],
        old_status=old_status,
        new_status='In Progress',
        comment=(
            comment.strip()
            if isinstance(comment, str) and comment.strip()
            else 'Student requested that the grievance be reopened.'
        )
    )

    try:
        grievance.status = 'In Progress'
        grievance.resolution_confirmed_at = None
        grievance.reopen_count = (grievance.reopen_count or 0) + 1
        grievance.sla_due_at = new_sla_due_at

        # Return handling to the previously assigned advisor, if present.
        if grievance.assigned_to:
            grievance.current_handler_id = grievance.assigned_to
            grievance.current_handler_role = 'advisor'
        else:
            grievance.current_handler_id = None
            grievance.current_handler_role = None

        db.session.add(history)

        notify_grievance_staff(
            grievance,
            'Grievance Reopened',
            (
                f'The student reopened grievance "{grievance.title}". '
                f'Please review the issue.'
            )
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to reopen grievance at this time'
        }), 500

    return jsonify({
        'message': 'Grievance reopened successfully',
        'grievance_id': grievance.id,
        'old_status': old_status,
        'status': grievance.status,
        'reopen_count': grievance.reopen_count,
        'sla_due_at': grievance.sla_due_at.isoformat()
    }), 200


@grievance_bp.route('/manage', methods=['GET'])
def manage_grievances():
    user_id = session.get('user_id')
    role = session.get('role')

    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401

    if role not in ('coordinator', 'advisor'):
        return jsonify({
            'error': 'Only coordinators and advisors can access this endpoint'
        }), 403

    query = Grievance.query

    if role == 'advisor':
        query = query.filter_by(assigned_to=user_id)

    grievances = query.order_by(
        Grievance.created_at.desc()
    ).all()

    return jsonify([
        {
            'id': grievance.id,
            'title': grievance.title,
            'description': grievance.description,
            'student_id': grievance.student_id,
            'category': grievance.category.name,
            'priority': grievance.priority,
            'status': grievance.status,
            'assigned_to': grievance.assigned_to,
            'created_at': grievance.created_at.isoformat()
        }
        for grievance in grievances
    ]), 200


@grievance_bp.route('/<int:grievance_id>/assign', methods=['PUT'])
def assign_grievance(grievance_id):
    user_id = session.get('user_id')
    role = session.get('role')

    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401

    if role != 'coordinator':
        return jsonify({
            'error': 'Only coordinators can assign grievances'
        }), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'Request body must be a JSON object'
        }), 400

    advisor_id = data.get('advisor_id')

    # Booleans are integers in Python, so reject them explicitly.
    if isinstance(advisor_id, bool):
        return jsonify({
            'error': 'A valid advisor_id is required'
        }), 400

    try:
        advisor_id = int(advisor_id)
    except (TypeError, ValueError):
        return jsonify({
            'error': 'A valid advisor_id is required'
        }), 400

    if advisor_id <= 0:
        return jsonify({
            'error': 'A valid advisor_id is required'
        }), 400

    grievance = db.session.get(Grievance, grievance_id)

    if not grievance:
        return jsonify({'error': 'Grievance not found'}), 404

    advisor = db.session.get(User, advisor_id)

    if not advisor or advisor.role != 'advisor':
        return jsonify({
            'error': 'The selected user is not an advisor'
        }), 400

    try:
        # Preserve the existing advisor assignment while synchronizing
        # the Phase 16 current-handler fields.
        grievance.assigned_to = advisor.id
        grievance.current_handler_id = advisor.id
        grievance.current_handler_role = advisor.role

        create_notification(
            user_id=advisor.id,
            title='Grievance Assigned to You',
            message=(
                f'Grievance "{grievance.title}" '
                f'has been assigned to you.'
            ),
            notification_type='grievance'
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to assign grievance at this time'
        }), 500

    return jsonify({
        'message': 'Grievance assigned successfully',
        'grievance_id': grievance.id,
        'advisor_id': advisor.id
    }), 200


@grievance_bp.route('/<int:grievance_id>/status', methods=['PUT'])
def update_grievance_status(grievance_id):
    user_id = session.get('user_id')
    role = session.get('role')

    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401

    if role not in ('coordinator', 'advisor'):
        return jsonify({
            'error': 'Only coordinators and advisors can update status'
        }), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'Request body must be a JSON object'
        }), 400

    new_status = data.get('status')

    allowed_statuses = (
        'Submitted',
        'Under Review',
        'In Progress',
        'Resolved',
        'Rejected'
    )

    if not isinstance(new_status, str) or new_status not in allowed_statuses:
        return jsonify({
            'error': 'Invalid status',
            'allowed_statuses': list(allowed_statuses)
        }), 400

    grievance = db.session.get(Grievance, grievance_id)

    if not grievance:
        return jsonify({'error': 'Grievance not found'}), 404

    if role == 'advisor' and grievance.assigned_to != user_id:
        return jsonify({
            'error': 'You can update only grievances assigned to you'
        }), 403

    old_status = grievance.status

    if old_status == new_status:
        return jsonify({
            'message': 'Grievance already has this status',
            'grievance_id': grievance.id,
            'status': grievance.status
        }), 200

    comment = data.get('comment')

    if comment is not None and not isinstance(comment, str):
        return jsonify({'error': 'Comment must be text'}), 400

    history = GrievanceUpdate(
        grievance_id=grievance.id,
        updated_by=user_id,
        old_status=old_status,
        new_status=new_status,
        comment=comment.strip() if comment and comment.strip() else None
    )

    try:
        grievance.status = new_status
        grievance.resolution_confirmed_at = None

        if new_status in ('Resolved', 'Rejected'):
            grievance.current_handler_id = None
            grievance.current_handler_role = None
        else:
            grievance.current_handler_id = user_id
            grievance.current_handler_role = role

        db.session.add(history)

        if new_status == 'Resolved':
            notification_title = 'Grievance Resolved'
            notification_message = (
                f'Your grievance "{grievance.title}" has been resolved.'
            )
        else:
            notification_title = 'Grievance Status Updated'
            notification_message = (
                f'Your grievance "{grievance.title}" status changed '
                f'from "{old_status}" to "{new_status}".'
            )

        create_notification(
            user_id=grievance.student.user_id,
            title=notification_title,
            message=notification_message,
            notification_type='grievance'
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to update grievance status at this time'
        }), 500

    return jsonify({
        'message': 'Grievance status updated successfully',
        'grievance_id': grievance.id,
        'old_status': old_status,
        'status': grievance.status
    }), 200


@grievance_bp.route('/<int:grievance_id>/history', methods=['GET'])
def get_grievance_history(grievance_id):
    student, error = require_student()
    if error:
        return error

    grievance = db.session.get(Grievance, grievance_id)

    if not grievance or grievance.student_id != student.id:
        return jsonify({'error': 'Grievance not found'}), 404

    updates = GrievanceUpdate.query.filter_by(
        grievance_id=grievance.id
    ).order_by(GrievanceUpdate.created_at.asc()).all()

    return jsonify([
        {
            'old_status': update.old_status,
            'new_status': update.new_status,
            'comment': update.comment,
            'created_at': update.created_at.isoformat(),
            'updated_by': update.updated_by
        }
        for update in updates
    ]), 200



@grievance_bp.route('/advisors', methods=['GET'])
def get_grievance_advisors():
    """List advisors for coordinator assignment."""
    user_id = session.get('user_id')

    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401

    if session.get('role') != 'coordinator':
        return jsonify({
            'error': 'Only coordinators can view available advisors'
        }), 403

    advisors = User.query.filter_by(role='advisor').order_by(
        User.name.asc()
    ).all()

    return jsonify([
        {'id': advisor.id, 'name': advisor.name, 'email': advisor.email}
        for advisor in advisors
    ]), 200


@grievance_bp.route('/manage/<int:grievance_id>/history', methods=['GET'])
def get_managed_grievance_history(grievance_id):
    """View history as a coordinator or the assigned advisor."""
    user_id = session.get('user_id')
    role = session.get('role')

    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401

    if role not in ('coordinator', 'advisor'):
        return jsonify({
            'error': 'Only coordinators and advisors can view this history'
        }), 403

    grievance = db.session.get(Grievance, grievance_id)

    if not grievance:
        return jsonify({'error': 'Grievance not found'}), 404

    if role == 'advisor' and grievance.assigned_to != user_id:
        return jsonify({
            'error': 'You can view only grievances assigned to you'
        }), 403

    updates = GrievanceUpdate.query.filter_by(
        grievance_id=grievance.id
    ).order_by(GrievanceUpdate.created_at.asc()).all()

    return jsonify([
        {
            'old_status': update.old_status,
            'new_status': update.new_status,
            'comment': update.comment,
            'created_at': update.created_at.isoformat(),
            'updated_by': update.updated_by
        }
        for update in updates
    ]), 200
