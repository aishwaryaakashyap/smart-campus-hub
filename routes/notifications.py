
from flask import Blueprint, jsonify, session
from extensions import db
from models import Notification

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/', methods=['GET'])
def list_notifications():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    notifications = (
        Notification.query
        .filter_by(user_id=session['user_id'])
        .order_by(Notification.created_at.desc())
        .all()
    )

    return jsonify([
        {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'notification_type': notification.notification_type,
            'is_read': notification.is_read,
            'created_at': notification.created_at.isoformat()
        }
        for notification in notifications
    ]), 200


@notifications_bp.route('/<int:notification_id>/read', methods=['PUT'])
def mark_notification_read(notification_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=session['user_id']
    ).first()

    if not notification:
        return jsonify({'error': 'Notification not found'}), 404

    notification.is_read = True
    db.session.commit()

    return jsonify({
        'message': 'Notification marked as read',
        'notification_id': notification.id
    }), 200
