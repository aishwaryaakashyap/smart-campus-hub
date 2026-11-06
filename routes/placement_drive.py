
from flask import Blueprint, request, jsonify, session
from sqlalchemy.exc import SQLAlchemyError
from extensions import db
from models import PlacementDrive, Company
from datetime import datetime
import math


drive_bp = Blueprint('drive', __name__)


def require_coordinator():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    if session.get('role') != 'coordinator':
        return jsonify({
            'error': 'Only coordinators can perform this action'
        }), 403

    return None


def validate_drive_data(data):
    """Validate placement-drive input before creating a record."""

    if not isinstance(data, dict):
        return 'A valid JSON object is required'

    # Company ID
    company_id = data.get('company_id')

    if (
        isinstance(company_id, bool)
        or not isinstance(company_id, int)
        or company_id <= 0
    ):
        return 'company_id must be a positive integer'

    # Job role
    job_role = data.get('job_role')

    if not isinstance(job_role, str) or not job_role.strip():
        return 'job_role must be a non-empty string'

    data['job_role'] = job_role.strip()

    # Status
    status = data.get('status', 'Open')

    if not isinstance(status, str) or status not in ('Open', 'Closed'):
        return 'status must be Open or Closed'

    data['status'] = status

    # Minimum CGPA
    min_cgpa = data.get('min_cgpa')

    if min_cgpa is not None:
        if (
            isinstance(min_cgpa, bool)
            or not isinstance(min_cgpa, (int, float))
            or not math.isfinite(min_cgpa)
            or min_cgpa < 0
        ):
            return 'min_cgpa must be a non-negative number'

    # Eligible semester
    semester = data.get('eligible_semester')

    if semester is not None:
        if (
            isinstance(semester, bool)
            or not isinstance(semester, int)
            or semester <= 0
        ):
            return 'eligible_semester must be a positive integer'

    # Eligible branches
    branches = data.get('eligible_branches')

    if branches is not None:
        if not isinstance(branches, str):
            return 'eligible_branches must be a string'

        branch_list = [branch.strip() for branch in branches.split(',')]

        if not branch_list or any(not branch for branch in branch_list):
            return 'eligible_branches must contain valid branch names'

        data['eligible_branches'] = ','.join(branch_list)

    return None


def parse_date(value):
    if value is None or value == '':
        return None

    if not isinstance(value, str):
        raise ValueError('Invalid date format. Use YYYY-MM-DD.')

    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        raise ValueError('Invalid date format. Use YYYY-MM-DD.')


@drive_bp.route('/', methods=['POST'])
def create_drive():
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    data = request.get_json(silent=True)

    validation_error = validate_drive_data(data)

    if validation_error:
        return jsonify({'error': validation_error}), 400

    company = Company.query.get(data['company_id'])

    if not company:
        return jsonify({'error': 'Company not found'}), 404

    try:
        drive_date = parse_date(data.get('drive_date'))
        application_deadline = parse_date(
            data.get('application_deadline')
        )

        if (
            drive_date is not None
            and application_deadline is not None
            and application_deadline > drive_date
        ):
            return jsonify({
                'error': 'application_deadline cannot be later than drive_date'
            }), 400

        new_drive = PlacementDrive(
            company_id=data['company_id'],
            job_role=data['job_role'],
            job_description=data.get('job_description'),
            drive_date=drive_date,
            application_deadline=application_deadline,
            salary_package=data.get('salary_package'),
            location=data.get('location'),
            status=data['status'],
            min_cgpa=data.get('min_cgpa'),
            eligible_branches=data.get('eligible_branches'),
            eligible_semester=data.get('eligible_semester')
        )

    except (ValueError, TypeError) as error:
        return jsonify({'error': str(error)}), 400

    try:
        db.session.add(new_drive)
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()

        return jsonify({
            'error': 'Unable to create placement drive'
        }), 500

    return jsonify({
        'message': 'Placement drive created successfully',
        'id': new_drive.id
    }), 201


@drive_bp.route('/', methods=['GET'])
def list_drives():
    drives = PlacementDrive.query.all()

    result = []

    for d in drives:
        result.append({
            'id': d.id,
            'company_name': d.company.name,
            'job_role': d.job_role,
            'location': d.location,
            'salary_package': d.salary_package,
            'application_deadline': (
                str(d.application_deadline)
                if d.application_deadline else None
            ),
            'status': d.status
        })

    return jsonify(result), 200


@drive_bp.route('/<int:drive_id>', methods=['GET'])
def get_drive(drive_id):
    d = PlacementDrive.query.get(drive_id)

    if not d:
        return jsonify({
            'error': 'Placement drive not found'
        }), 404

    return jsonify({
        'id': d.id,
        'company_name': d.company.name,
        'job_role': d.job_role,
        'job_description': d.job_description,
        'drive_date': (
            str(d.drive_date) if d.drive_date else None
        ),
        'application_deadline': (
            str(d.application_deadline)
            if d.application_deadline else None
        ),
        'salary_package': d.salary_package,
        'location': d.location,
        'status': d.status,
        'min_cgpa': d.min_cgpa,
        'eligible_branches': d.eligible_branches,
        'eligible_semester': d.eligible_semester
    }), 200


@drive_bp.route('/<int:drive_id>/close', methods=['PUT'])
def close_drive(drive_id):
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    d = PlacementDrive.query.get(drive_id)

    if not d:
        return jsonify({
            'error': 'Placement drive not found'
        }), 404

    d.status = 'Closed'

    try:
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()

        return jsonify({
            'error': 'Unable to close placement drive'
        }), 500

    return jsonify({
        'message': 'Placement drive closed successfully'
    }), 200
