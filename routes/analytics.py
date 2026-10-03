from flask import Blueprint, jsonify, session
from models import Company, PlacementDrive, Application, Student

analytics_bp = Blueprint('analytics', __name__)


def require_coordinator():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    if session.get('role') != 'coordinator':
        return jsonify({'error': 'Only coordinators can view placement analytics'}), 403

    return None



@analytics_bp.route('/placement', methods=['GET'])
def placement_analytics():
    auth_error = require_coordinator()
    if auth_error:
        return auth_error

    total_students = Student.query.count()
    total_companies = Company.query.count()
    total_drives = PlacementDrive.query.count()

    open_drives = PlacementDrive.query.filter_by(status='Open').count()
    closed_drives = PlacementDrive.query.filter_by(status='Closed').count()

    total_applications = Application.query.count()

    status_counts = {}
    statuses = [
        'Applied',
        'Under Review',
        'Shortlisted',
        'Interview',
        'Selected',
        'Not Selected',
        'Withdrawn'
    ]

    for status in statuses:
        status_counts[status] = Application.query.filter_by(status=status).count()

    selected_count = status_counts['Selected']

    company_analytics = []

    for company in Company.query.all():
        company_drives = PlacementDrive.query.filter_by(company_id=company.id).all()
        drive_ids = [drive.id for drive in company_drives]

        company_applications = (
            Application.query.filter(Application.drive_id.in_(drive_ids)).all()
            if drive_ids
            else []
        )

        company_selected = sum(
            1 for application in company_applications
            if application.status == 'Selected'
        )

        company_selection_rate = (
            round((company_selected / len(company_applications)) * 100, 2)
            if company_applications
            else 0
        )

        company_analytics.append({
            'company_id': company.id,
            'company_name': company.name,
            'drive_count': len(company_drives),
            'application_count': len(company_applications),
            'selected_count': company_selected,
            'selection_rate_percent': company_selection_rate
        })

    selection_rate = (
        round((selected_count / total_applications) * 100, 2)
        if total_applications > 0
        else 0
    )

    return jsonify({
        'total_students': total_students,
        'total_companies': total_companies,
        'total_drives': total_drives,
        'open_drives': open_drives,
        'closed_drives': closed_drives,
        'total_applications': total_applications,
        'application_status_counts': status_counts,
        'selected_count': selected_count,
        'selection_rate_percent': selection_rate,
        'company_analytics': company_analytics
    }), 200


