from flask import Blueprint, request, jsonify, session
from extensions import db
from models import CompanyUpdate, Company

update_bp = Blueprint('update', __name__)


def require_coordinator():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    if session.get('role') != 'coordinator':
        return jsonify({'error': 'Only coordinators can perform this action'}), 403
    return None


@update_bp.route('/', methods=['POST'])
def post_update():
    auth_error = require_coordinator()
    if auth_error:
        return auth_error

    data = request.get_json()
    required_fields = ['company_id', 'title', 'message']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'{field} is required'}), 400

    company = Company.query.get(data['company_id'])
    if not company:
        return jsonify({'error': 'Company not found'}), 404

    new_update = CompanyUpdate(
        company_id=data['company_id'],
        title=data['title'],
        message=data['message']
    )
    db.session.add(new_update)
    db.session.commit()

    return jsonify({
        'message': 'Update posted successfully',
        'id': new_update.id
    }), 201


@update_bp.route('/company/<int:company_id>', methods=['GET'])
def list_updates_for_company(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({'error': 'Company not found'}), 404

    updates = CompanyUpdate.query.filter_by(company_id=company_id).order_by(CompanyUpdate.posted_at.desc()).all()
    result = []
    for u in updates:
        result.append({
            'id': u.id,
            'title': u.title,
            'message': u.message,
            'posted_at': str(u.posted_at)
        })
    return jsonify(result), 200


@update_bp.route('/', methods=['GET'])
def list_all_updates():
    updates = CompanyUpdate.query.order_by(CompanyUpdate.posted_at.desc()).all()
    result = []
    for u in updates:
        result.append({
            'id': u.id,
            'company_name': u.company.name,
            'title': u.title,
            'message': u.message,
            'posted_at': str(u.posted_at)
        })
    return jsonify(result), 200