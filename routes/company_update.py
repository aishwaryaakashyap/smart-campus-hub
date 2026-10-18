from flask import Blueprint, request, jsonify, session
from extensions import db
from models import CompanyUpdate, Company

update_bp = Blueprint('update', __name__)


def require_coordinator():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    if session.get('role') != 'coordinator':
        return jsonify({
            'error': 'Only coordinators can perform this action'
        }), 403

    return None


@update_bp.route('/', methods=['POST'])
def post_update():
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'A valid JSON object is required'
        }), 400

    required_fields = ['company_id', 'title', 'message']

    for field in required_fields:
        if field not in data or data[field] is None:
            return jsonify({
                'error': f'{field} is required'
            }), 400

        if isinstance(data[field], str) and not data[field].strip():
            return jsonify({
                'error': f'{field} is required'
            }), 400

    company_id = data['company_id']

    if (
        isinstance(company_id, bool)
        or not isinstance(company_id, int)
        or company_id <= 0
    ):
        return jsonify({
            'error': 'company_id must be a positive integer'
        }), 400

    if not isinstance(data['title'], str):
        return jsonify({
            'error': 'title must be a string'
        }), 400

    if not isinstance(data['message'], str):
        return jsonify({
            'error': 'message must be a string'
        }), 400

    company = db.session.get(Company, company_id)

    if not company:
        return jsonify({
            'error': 'Company not found'
        }), 404

    new_update = CompanyUpdate(
        company_id=company_id,
        title=data['title'].strip(),
        message=data['message'].strip()
    )

    try:
        db.session.add(new_update)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to post company update'
        }), 500

    return jsonify({
        'message': 'Update posted successfully',
        'id': new_update.id
    }), 201


@update_bp.route('/company/<int:company_id>', methods=['GET'])
def list_updates_for_company(company_id):
    company = db.session.get(Company, company_id)

    if not company:
        return jsonify({
            'error': 'Company not found'
        }), 404

    updates = (
        CompanyUpdate.query
        .filter_by(company_id=company_id)
        .order_by(CompanyUpdate.posted_at.desc())
        .all()
    )

    result = []

    for update in updates:
        result.append({
            'id': update.id,
            'title': update.title,
            'message': update.message,
            'posted_at': str(update.posted_at)
        })

    return jsonify(result), 200


@update_bp.route('/', methods=['GET'])
def list_all_updates():
    updates = (
        CompanyUpdate.query
        .order_by(CompanyUpdate.posted_at.desc())
        .all()
    )

    result = []

    for update in updates:
        result.append({
            'id': update.id,
            'company_name': update.company.name,
            'title': update.title,
            'message': update.message,
            'posted_at': str(update.posted_at)
        })

    return jsonify(result), 200
