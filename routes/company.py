
from flask import Blueprint, request, jsonify, session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models import Company

company_bp = Blueprint('company', __name__)


def require_coordinator():
    """Check if logged-in user is a coordinator."""
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    if session.get('role') != 'coordinator':
        return jsonify({
            'error': 'Only coordinators can perform this action'
        }), 403

    return None


def get_company_data():
    """Validate that the request contains a JSON object."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return None, (
            jsonify({'error': 'A valid JSON object is required'}),
            400
        )

    return data, None


@company_bp.route('/', methods=['POST'])
def add_company():
    auth_error = require_coordinator()
    if auth_error:
        return auth_error

    data, validation_error = get_company_data()
    if validation_error:
        return validation_error

    name = data.get('name')

    if not isinstance(name, str) or not name.strip():
        return jsonify({
            'error': 'Company name must be a non-empty string'
        }), 400

    new_company = Company(
        name=name.strip(),
        industry=data.get('industry'),
        description=data.get('description'),
        website=data.get('website'),
        location=data.get('location')
    )

    try:
        db.session.add(new_company)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to add company at this time'
        }), 500

    return jsonify({
        'message': 'Company added successfully',
        'id': new_company.id,
        'name': new_company.name
    }), 201


@company_bp.route('/', methods=['GET'])
def list_companies():
    companies = Company.query.all()

    result = []

    for company in companies:
        result.append({
            'id': company.id,
            'name': company.name,
            'industry': company.industry,
            'location': company.location
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

    data, validation_error = get_company_data()
    if validation_error:
        return validation_error

    company = Company.query.get(company_id)

    if not company:
        return jsonify({'error': 'Company not found'}), 404

    if not data:
        return jsonify({'error': 'No update data provided'}), 400

    if 'name' in data:
        name = data['name']

        if not isinstance(name, str) or not name.strip():
            return jsonify({
                'error': 'Company name must be a non-empty string'
            }), 400

        company.name = name.strip()

    company.industry = data.get('industry', company.industry)
    company.description = data.get('description', company.description)
    company.website = data.get('website', company.website)
    company.location = data.get('location', company.location)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to update company at this time'
        }), 500

    return jsonify({
        'message': 'Company updated successfully'
    }), 200


@company_bp.route('/<int:company_id>', methods=['DELETE'])
def delete_company(company_id):
    auth_error = require_coordinator()
    if auth_error:
        return auth_error

    company = Company.query.get(company_id)

    if not company:
        return jsonify({'error': 'Company not found'}), 404

    db.session.delete(company)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            'error': 'Cannot delete company because it is linked to existing records'
        }), 409
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            'error': 'Unable to delete company at this time'
        }), 500

    return jsonify({
        'message': 'Company deleted successfully'
    }), 200
