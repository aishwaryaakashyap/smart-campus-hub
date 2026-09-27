from flask import Blueprint, request, jsonify, session
from extensions import db
from models import Application, Student, PlacementDrive
from services.eligibility import check_eligibility

application_bp = Blueprint('application', __name__)


def require_student():
    if 'user_id' not in session:
        return None, (jsonify({'error': 'Not logged in'}), 401)
    if session.get('role') != 'student':
        return None, (jsonify({'error': 'Only students can perform this action'}), 403)

    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        return None, (jsonify({'error': 'Student profile not found. Complete your profile first.'}), 404)

    return student, None


@application_bp.route('/check-eligibility/<int:drive_id>', methods=['GET'])
def check_eligibility_route(drive_id):
    student, error = require_student()
    if error:
        return error

    drive = PlacementDrive.query.get(drive_id)
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

    data = request.get_json()
    if 'drive_id' not in data:
        return jsonify({'error': 'drive_id is required'}), 400

    drive = PlacementDrive.query.get(data['drive_id'])
    if not drive:
        return jsonify({'error': 'Placement drive not found'}), 404

    if drive.status != 'Open':
        return jsonify({'error': 'This placement drive is closed'}), 400

    existing = Application.query.filter_by(student_id=student.id, drive_id=drive.id).first()
    if existing:
        return jsonify({'error': 'You have already applied to this drive'}), 409

    is_eligible, reasons = check_eligibility(student, drive)
    if not is_eligible:
        return jsonify({'error': 'You are not eligible for this drive', 'reasons': reasons}), 403

    new_application = Application(
        student_id=student.id,
        drive_id=drive.id,
        status='Applied'
    )
    db.session.add(new_application)
    db.session.commit()

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

    applications = Application.query.filter_by(student_id=student.id).all()
    result = []
    for a in applications:
        result.append({
            'application_id': a.id,
            'company_name': a.drive.company.name,
            'job_role': a.drive.job_role,
            'status': a.status,
            'applied_date': str(a.applied_date)
        })
    return jsonify(result), 200


@application_bp.route('/<int:application_id>/status', methods=['PUT'])
def update_status(application_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    if session.get('role') != 'coordinator':
        return jsonify({'error': 'Only coordinators can perform this action'}), 403

    application = Application.query.get(application_id)
    if not application:
        return jsonify({'error': 'Application not found'}), 404

    data = request.get_json()
    valid_statuses = ['Applied', 'Under Review', 'Shortlisted', 'Interview', 'Selected', 'Not Selected', 'Withdrawn']

    if 'status' not in data or data['status'] not in valid_statuses:
        return jsonify({'error': f'status must be one of {valid_statuses}'}), 400

    application.status = data['status']
    application.remarks = data.get('remarks', application.remarks)
    db.session.commit()

    return jsonify({'message': 'Application status updated successfully'}), 200