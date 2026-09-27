from flask import Blueprint, request, jsonify, session
from extensions import db
from models import PlacementDrive, Company
from datetime import datetime

drive_bp = Blueprint('drive', __name__)


def require_coordinator():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    if session.get('role') != 'coordinator':
        return jsonify({'error': 'Only coordinators can perform this action'}), 403
    return None


@drive_bp.route('/', methods=['POST'])
def create_drive():
    auth_error = require_coordinator()
    if auth_error:
        return auth_error

    data = request.get_json()

    required_fields = ['company_id', 'job_role']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'{field} is required'}), 400

    company = Company.query.get(data['company_id'])
    if not company:
        return jsonify({'error': 'Company not found'}), 404

    def parse_date(value):
        if not value:
            return None
        return datetime.strptime(value, '%Y-%m-%d').date()

    new_drive = PlacementDrive(
        company_id=data['company_id'],
        job_role=data['job_role'],
        job_description=data.get('job_description'),
        drive_date=parse_date(data.get('drive_date')),
        application_deadline=parse_date(data.get('application_deadline')),
        salary_package=data.get('salary_package'),
        location=data.get('location'),
        status=data.get('status', 'Open'),
        min_cgpa=data.get('min_cgpa'),
        eligible_branches=data.get('eligible_branches'),
        eligible_semester=data.get('eligible_semester')
    )

    db.session.add(new_drive)
    db.session.commit()

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
            'application_deadline': str(d.application_deadline) if d.application_deadline else None,
            'status': d.status
        })
    return jsonify(result), 200


@drive_bp.route('/<int:drive_id>', methods=['GET'])
def get_drive(drive_id):
    d = PlacementDrive.query.get(drive_id)
    if not d:
        return jsonify({'error': 'Placement drive not found'}), 404

    return jsonify({
        'id': d.id,
        'company_name': d.company.name,
        'job_role': d.job_role,
        'job_description': d.job_description,
        'drive_date': str(d.drive_date) if d.drive_date else None,
        'application_deadline': str(d.application_deadline) if d.application_deadline else None,
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
        return jsonify({'error': 'Placement drive not found'}), 404

    d.status = 'Closed'
    db.session.commit()

    return jsonify({'message': 'Placement drive closed successfully'}), 200