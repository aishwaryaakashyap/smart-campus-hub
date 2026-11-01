
from flask import Blueprint, request, jsonify, session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from extensions import db
from models import Application, Student, PlacementDrive
from services.eligibility import check_eligibility
from services.notifications import create_notification

application_bp = Blueprint('application', __name__)


def require_student():
    if 'user_id' not in session:
        return None, (jsonify({'error': 'Not logged in'}), 401)

    if session.get('role') != 'student':
        return None, (
            jsonify({'error': 'Only students can perform this action'}),
            403
        )

    student = Student.query.filter_by(
        user_id=session['user_id']
    ).first()

    if not student:
        return None, (
            jsonify({
                'error': 'Student profile not found. Complete your profile first.'
            }),
            404
        )

    return student, None


def get_json_object():
    """Ensure the request contains a valid JSON object."""
    if not request.is_json:
        return None, (
            jsonify({'error': 'Content-Type must be application/json'}),
            415
        )

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return None, (
            jsonify({'error': 'Request body must be a valid JSON object'}),
            400
        )

    return data, None


@application_bp.route(
    '/check-eligibility/<int:drive_id>',
    methods=['GET']
)
def check_eligibility_route(drive_id):
    student, error = require_student()
    if error:
        return error

    drive = db.session.get(PlacementDrive, drive_id)

    if not drive:
        return jsonify({'error': 'Placement drive not found'}), 404

    is_eligible, reasons = check_eligibility(student, drive)

    return jsonify({
        'drive_id': drive.id,
        'job_role': drive.job_role,
        'eligible': is_eligible,
        'reasons': reasons if not is_eligible else []
    }), 200


@application_bp.route('/', methods=['POST'])
def apply():
    student, error = require_student()
    if error:
        return error

    data, error = get_json_object()
    if error:
        return error

    drive_id = data.get('drive_id')

    if (
        isinstance(drive_id, bool)
        or not isinstance(drive_id, int)
        or drive_id <= 0
    ):
        return jsonify({
            'error': 'drive_id must be a positive integer'
        }), 400

    drive = db.session.get(PlacementDrive, drive_id)

    if not drive:
        return jsonify({'error': 'Placement drive not found'}), 404

    if drive.status != 'Open':
        return jsonify({'error': 'This placement drive is closed'}), 400

    existing = Application.query.filter_by(
        student_id=student.id,
        drive_id=drive.id
    ).first()

    if existing:
        return jsonify({
            'error': 'You have already applied to this drive'
        }), 409

    is_eligible, reasons = check_eligibility(student, drive)

    if not is_eligible:
        return jsonify({
            'error': 'You are not eligible for this drive',
            'reasons': reasons
        }), 403

    new_application = Application(
        student_id=student.id,
        drive_id=drive.id,
        status='Applied'
    )

    try:
        db.session.add(new_application)
        db.session.commit()

    except IntegrityError as exc:
        db.session.rollback()
        original_error = getattr(exc, 'orig', None)
        error_args = getattr(original_error, 'args', ())
        if error_args and error_args[0] == 1062:
            return jsonify({
                'error': 'You have already applied to this drive'
            }), 409

        return jsonify({
            'error': 'Unable to submit application at this time'
        }), 500

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to submit application at this time'
        }), 500

    return jsonify({
        'message': 'Application submitted successfully',
        'application_id': new_application.id,
        'status': new_application.status
    }), 201


@application_bp.route('/my-applications', methods=['GET'])
def my_applications():
    student, error = require_student()
    if error:
        return error

    applications = Application.query.filter_by(
        student_id=student.id
    ).all()

    result = []

    for application in applications:
        result.append({
            'application_id': application.id,
            'company_name': application.drive.company.name,
            'job_role': application.drive.job_role,
            'status': application.status,
            'applied_date': str(application.applied_date)
        })

    return jsonify(result), 200


@application_bp.route(
    '/<int:application_id>/status',
    methods=['PUT']
)
def update_status(application_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    if session.get('role') != 'coordinator':
        return jsonify({
            'error': 'Only coordinators can perform this action'
        }), 403

    application = db.session.get(Application, application_id)

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    data, error = get_json_object()
    if error:
        return error

    new_status = data.get('status')

    valid_statuses = {
        'Applied',
        'Under Review',
        'Shortlisted',
        'Interview',
        'Selected',
        'Not Selected',
        'Withdrawn'
    }

    if (
        not isinstance(new_status, str)
        or new_status not in valid_statuses
    ):
        return jsonify({
            'error': 'Invalid status',
            'valid_statuses': sorted(valid_statuses)
        }), 400

    remarks = data.get('remarks', application.remarks)

    if remarks is not None and not isinstance(remarks, str):
        return jsonify({
            'error': 'remarks must be a string or null'
        }), 400

    old_status = application.status

    try:
        application.status = new_status
        application.remarks = remarks

        if old_status != new_status:
            create_notification(
                user_id=application.student.user_id,
                title='Placement Application Update',
                message=(
                    f'Your application for {application.drive.job_role} '
                    f'has been updated from {old_status} to {new_status}.'
                ),
                notification_type='placement_status'
            )

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to update application at this time'
        }), 500

    except Exception:
        db.session.rollback()
        raise

    return jsonify({
        'message': 'Application status updated successfully'
    }), 200
