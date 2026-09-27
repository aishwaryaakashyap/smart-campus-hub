from flask import Blueprint, request, jsonify, session
from extensions import db
from models import Company

company_bp = Blueprint('company', __name__)


def require_coordinator():
    """Check if logged-in user is a coordinator. Returns None if OK, or an error response."""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    if session.get('role') != 'coordinator':
        return jsonify({'error': 'Only coordinators can perform this action'}), 403
    return None


@company_bp.route('/', methods=['POST'])
def add_company():
    auth_error = require_coordinator()
    if auth_error:
        return auth_error

    data = request.get_json()

    if 'name' not in data or not data['name']:
        return jsonify({'error': 'Company name is required'}), 400

    new_company = Company(
        name=data['name'],
        industry=data.get('industry'),
        description=data.get('description'),
        website=data.get('website'),
        location=data.get('location')
    )

    db.session.add(new_company)
    db.session.commit()

    return jsonify({
        'message': 'Company added successfully',
        'id': new_company.id,
        'name': new_company.name
    }), 201


@company_bp.route('/', methods=['GET'])
def list_companies():
    companies = Company.query.all()
    result = []
    for c in companies:
        result.append({
            'id': c.id,
            'name': c.name,
            'industry': c.industry,
            'location': c.location
        })
    return jsonify(result), 200


@company_bp.route('/<int:company_id>', methods=['GET'])
def get_company(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({'error': 'Company not found'}), 404

    return jsonify({
        'id': company.id,
        'name': company.name,
        'industry': company.industry,
        'description': company.description,
        'website': company.website,
        'location': company.location
    }), 200


@company_bp.route('/<int:company_id>', methods=['PUT'])
def update_company(company_id):
    auth_error = require_coordinator()
    if auth_error:
        return auth_error

    company = Company.query.get(company_id)
    if not company:
        return jsonify({'error': 'Company not found'}), 404

    data = request.get_json()
    company.name = data.get('name', company.name)
    company.industry = data.get('industry', company.industry)
    company.description = data.get('description', company.description)
    company.website = data.get('website', company.website)
    company.location = data.get('location', company.location)

    db.session.commit()

    return jsonify({'message': 'Company updated successfully'}), 200


@company_bp.route('/<int:company_id>', methods=['DELETE'])
def delete_company(company_id):
    auth_error = require_coordinator()
    if auth_error:
        return auth_error

    company = Company.query.get(company_id)
    if not company:
        return jsonify({'error': 'Company not found'}), 404

    db.session.delete(company)
    db.session.commit()

    return jsonify({'message': 'Company deleted successfully'}), 200