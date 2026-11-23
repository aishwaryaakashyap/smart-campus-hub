from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from services.record_deletion_guard import find_referencing_records
from services.activity_log import record_activity
from models import ActivityLog, AcademicClass, Student, User


academic_admin_bp = Blueprint(
    "academic_admin",
    __name__
)


def get_session_user(user_id):
    """Load the current user from the database."""
    return db.session.get(User, user_id)


def require_coordinator():
    """
    Require an authenticated, active Coordinator account.

    Verify the database role and account status on every request so
    stale sessions cannot retain administrative access.
    """
    user_id = session.get("user_id")

    if not user_id:
        return jsonify({"error": "Not logged in"}), 401

    session_role = session.get("role")
    user = get_session_user(user_id)

    if not user or user.role != session_role:
        session.clear()
        return jsonify({"error": "Not logged in"}), 401

    if user.account_status != User.STATUS_ACTIVE:
        session.clear()
        return jsonify({"error": "Account is not active"}), 401

    if user.role != User.ROLE_COORDINATOR:
        return jsonify({
            "error": "Only active coordinators can perform this action"
        }), 403

    return None


def serialize_advisor(advisor):
    """Return safe Advisor account details without password information."""
    return {
        "id": advisor.id,
        "name": advisor.name,
        "email": advisor.email,
        "account_status": advisor.account_status
    }


def serialize_academic_class(academic_class):
    """Convert an academic class and its assigned Advisor to JSON."""
    advisor = academic_class.advisor

    advisor_data = None

    if advisor:
        advisor_data = serialize_advisor(advisor)

    return {
        "id": academic_class.id,
        "course": academic_class.course,
        "branch": academic_class.branch,
        "section": academic_class.section,
        "admission_year": academic_class.admission_year,
        "advisor_user_id": academic_class.advisor_user_id,
        "advisor": advisor_data,
        "is_active": bool(academic_class.is_active),
        "created_at": (
            academic_class.created_at.isoformat()
            if academic_class.created_at else None
        ),
        "updated_at": (
            academic_class.updated_at.isoformat()
            if academic_class.updated_at else None
        )
    }


def validate_class_text(data, field, max_length):
    """Validate and normalize a required class text field."""
    value = data.get(field)

    if not isinstance(value, str):
        return None, f"{field} must be a string"

    value = value.strip()

    if not value:
        return None, f"{field} is required"

    if len(value) > max_length:
        return None, (
            f"{field} must be {max_length} characters or fewer"
        )

    return value, None


@academic_admin_bp.route("/classes", methods=["GET"])
def list_academic_classes():
    """List classes for the Coordinator."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    include_archived_value = request.args.get(
        "include_archived",
        "false"
    ).strip().lower()

    if include_archived_value not in ("true", "false"):
        return jsonify({
            "error": "include_archived must be true or false"
        }), 400

    query = AcademicClass.query

    if include_archived_value == "false":
        query = query.filter_by(is_active=True)

    academic_classes = query.order_by(
        AcademicClass.course,
        AcademicClass.branch,
        AcademicClass.section,
        AcademicClass.admission_year
    ).all()

    return jsonify({
        "classes": [
            serialize_academic_class(item)
            for item in academic_classes
        ],
        "total": len(academic_classes)
    }), 200


@academic_admin_bp.route("/classes", methods=["POST"])
def create_academic_class():
    """Create a new academic class."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "A valid JSON object is required"
        }), 400

    course, error = validate_class_text(data, "course", 50)
    if error:
        return jsonify({"error": error}), 400

    branch, error = validate_class_text(data, "branch", 50)
    if error:
        return jsonify({"error": error}), 400

    section, error = validate_class_text(data, "section", 20)
    if error:
        return jsonify({"error": error}), 400

    admission_year = data.get("admission_year")

    if (
        isinstance(admission_year, bool)
        or not isinstance(admission_year, int)
        or not 1900 <= admission_year <= 2100
    ):
        return jsonify({
            "error": (
                "admission_year must be an integer "
                "between 1900 and 2100"
            )
        }), 400

    existing_class = AcademicClass.query.filter_by(
        course=course,
        branch=branch,
        section=section,
        admission_year=admission_year
    ).first()

    if existing_class:
        return jsonify({
            "error": "This academic class already exists"
        }), 409

    new_class = AcademicClass(
        course=course,
        branch=branch,
        section=section,
        admission_year=admission_year,
        is_active=True
    )

    try:
        db.session.add(new_class)
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "This academic class already exists"
        }), 409

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to create academic class at this time"
        }), 500

    return jsonify({
        "message": "Academic class created successfully",
        "class": serialize_academic_class(new_class)
    }), 201


@academic_admin_bp.route(
    "/classes/<int:class_id>",
    methods=["PUT"]
)
def update_academic_class(class_id):
    """Update a class without orphaning assigned students."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "A valid JSON object is required"
        }), 400

    academic_class = db.session.get(AcademicClass, class_id)

    if not academic_class:
        return jsonify({
            "error": "Academic class not found"
        }), 404

    course, error = validate_class_text(data, "course", 50)
    if error:
        return jsonify({"error": error}), 400

    branch, error = validate_class_text(data, "branch", 50)
    if error:
        return jsonify({"error": error}), 400

    section, error = validate_class_text(data, "section", 20)
    if error:
        return jsonify({"error": error}), 400

    admission_year = data.get("admission_year")

    if (
        isinstance(admission_year, bool)
        or not isinstance(admission_year, int)
        or not 1900 <= admission_year <= 2100
    ):
        return jsonify({
            "error": (
                "admission_year must be an integer "
                "between 1900 and 2100"
            )
        }), 400

    identity_changed = (
        academic_class.course != course
        or academic_class.branch != branch
        or academic_class.section != section
        or academic_class.admission_year != admission_year
    )

    if identity_changed:
        assigned_student_count = Student.query.filter_by(
            academic_class_id=academic_class.id
        ).count()

        if assigned_student_count > 0:
            return jsonify({
                "error": (
                    "Class identity cannot be changed while students "
                    "are assigned. Reassign the students first."
                )
            }), 409

    duplicate = AcademicClass.query.filter(
        AcademicClass.id != academic_class.id,
        AcademicClass.course == course,
        AcademicClass.branch == branch,
        AcademicClass.section == section,
        AcademicClass.admission_year == admission_year
    ).first()

    if duplicate:
        return jsonify({
            "error": "Another academic class already has these details"
        }), 409

    academic_class.course = course
    academic_class.branch = branch
    academic_class.section = section
    academic_class.admission_year = admission_year

    try:
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "Another academic class already has these details"
        }), 409

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to update academic class at this time"
        }), 500

    return jsonify({
        "message": "Academic class updated successfully",
        "class": serialize_academic_class(academic_class)
    }), 200


@academic_admin_bp.route("/advisors", methods=["GET"])
def list_active_advisors():
    """
    List active Advisor accounts available for class assignment.

    Pending, rejected, deactivated and non-Advisor accounts are excluded.
    """
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    advisors = User.query.filter_by(
        role=User.ROLE_ADVISOR,
        account_status=User.STATUS_ACTIVE
    ).order_by(
        User.name,
        User.email
    ).all()

    return jsonify({
        "advisors": [
            serialize_advisor(advisor)
            for advisor in advisors
        ],
        "total": len(advisors)
    }), 200


@academic_admin_bp.route(
    "/classes/<int:class_id>/advisor",
    methods=["PUT"]
)
def update_class_advisor(class_id):
    """
    Assign an active Advisor or remove the current Advisor assignment.

    Send an integer advisor_user_id to assign an Advisor.
    Send advisor_user_id: null to remove the assignment.
    """
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "A valid JSON object is required"
        }), 400

    if "advisor_user_id" not in data:
        return jsonify({
            "error": "advisor_user_id is required; use null to unassign"
        }), 400

    advisor_user_id = data.get("advisor_user_id")

    if advisor_user_id is not None and (
        isinstance(advisor_user_id, bool)
        or not isinstance(advisor_user_id, int)
        or advisor_user_id <= 0
    ):
        return jsonify({
            "error": "advisor_user_id must be a positive integer or null"
        }), 400

    academic_class = db.session.get(AcademicClass, class_id)

    if not academic_class:
        return jsonify({
            "error": "Academic class not found"
        }), 404

    if not academic_class.is_active:
        return jsonify({
            "error": "An archived class cannot have its Advisor changed"
        }), 409

    previous_advisor_user_id = academic_class.advisor_user_id

    if advisor_user_id is None:
        linked_student = Student.query.filter_by(
            academic_class_id=academic_class.id
        ).first()

        if linked_student:
            return jsonify({
                "error": (
                    "This class has linked students. Assign a replacement "
                    "Advisor instead of removing the current assignment."
                )
            }), 409

        academic_class.advisor = None
        academic_class.advisor_user_id = None
        success_message = "Advisor assignment removed successfully"

    else:
        advisor = db.session.get(User, advisor_user_id)

        if not advisor:
            return jsonify({
                "error": "Advisor account not found"
            }), 404

        if advisor.role != User.ROLE_ADVISOR:
            return jsonify({
                "error": "The selected account does not have the Advisor role"
            }), 409

        if advisor.account_status != User.STATUS_ACTIVE:
            return jsonify({
                "error": "Only active Advisor accounts can be assigned"
            }), 409

        academic_class.advisor = advisor
        academic_class.advisor_user_id = advisor.id
        success_message = "Advisor assigned successfully"

    try:
        if previous_advisor_user_id != advisor_user_id:
            if advisor_user_id is None:
                action = "class_advisor_removed"
                target_user_id = previous_advisor_user_id
                description = (
                    f"Coordinator removed Advisor {previous_advisor_user_id} "
                    f"from academic class {academic_class.id}"
                )
            elif previous_advisor_user_id is None:
                action = "class_advisor_assigned"
                target_user_id = advisor_user_id
                description = (
                    f"Coordinator assigned Advisor {advisor_user_id} "
                    f"to academic class {academic_class.id}"
                )
            else:
                action = "class_advisor_changed"
                target_user_id = advisor_user_id
                description = (
                    f"Coordinator changed Advisor for academic class "
                    f"{academic_class.id} from "
                    f"{previous_advisor_user_id} to {advisor_user_id}"
                )

            record_activity(
                actor_user_id=session.get("user_id"),
                target_user_id=target_user_id,
                action=action,
                entity_type="academic_class",
                entity_id=academic_class.id,
                description=description
            )

        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to update this Advisor assignment"
        }), 409

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to update this Advisor assignment at this time"
        }), 500

    return jsonify({
        "message": success_message,
        "class": serialize_academic_class(academic_class)
    }), 200


def set_academic_class_archive_status(class_id, is_active):
    """Archive or restore a class without deleting its history."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    academic_class = db.session.get(AcademicClass, class_id)

    if not academic_class:
        return jsonify({
            "error": "Academic class not found"
        }), 404

    if bool(academic_class.is_active) == is_active:
        message = (
            "Academic class is already active"
            if is_active
            else "Academic class is already archived"
        )

        return jsonify({
            "message": message,
            "class": serialize_academic_class(academic_class)
        }), 200

    # Preserve student associations and the existing Advisor assignment.
    academic_class.is_active = is_active

    try:
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()

        action = "restore" if is_active else "archive"

        return jsonify({
            "error": (
                f"Unable to {action} academic class at this time"
            )
        }), 500

    message = (
        "Academic class restored successfully"
        if is_active
        else "Academic class archived successfully"
    )

    return jsonify({
        "message": message,
        "class": serialize_academic_class(academic_class)
    }), 200


@academic_admin_bp.route(
    "/classes/<int:class_id>/archive",
    methods=["PATCH"]
)
def archive_academic_class(class_id):
    """Soft-archive an academic class."""
    return set_academic_class_archive_status(
        class_id,
        False
    )


@academic_admin_bp.route(
    "/classes/<int:class_id>/restore",
    methods=["PATCH"]
)
def restore_academic_class(class_id):
    """Restore a previously archived academic class."""
    return set_academic_class_archive_status(
        class_id,
        True
    )


@academic_admin_bp.route(
    "/classes/<int:class_id>/delete",
    methods=["DELETE"]
)
def delete_academic_class(class_id):
    """
    Permanently delete an archived class only when no records
    reference it. Student history is never deleted by this route.
    """
    from sqlalchemy.exc import IntegrityError, SQLAlchemyError

    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    academic_class = db.session.get(AcademicClass, class_id)

    if academic_class is None:
        return jsonify({
            "error": "Academic class not found"
        }), 404

    if academic_class.is_active:
        return jsonify({
            "error": (
                "Only archived academic classes can be permanently deleted. "
                "Archive the class first."
            )
        }), 409

    try:
        references = find_referencing_records(
            AcademicClass.__tablename__,
            class_id
        )

        if references:
            return jsonify({
                "error": (
                    "This archived class still has linked records and "
                    "cannot be deleted. Student records and other "
                    "institutional history must be preserved."
                ),
                "references": references
            }), 409

        db.session.delete(academic_class)
        db.session.commit()

        return jsonify({
            "message": "Archived academic class permanently deleted.",
            "deleted_id": class_id
        }), 200

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": (
                "Deletion was blocked by a database relationship. "
                "The class has not been deleted."
            )
        }), 409

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "A database error prevented academic class deletion."
        }), 500

@academic_admin_bp.route("/activity-logs", methods=["GET"])
def list_activity_logs():
    """List recent administrative activity for the Coordinator."""
    auth_error = require_coordinator()

    if auth_error:
        return auth_error

    try:
        page = int(request.args.get("page", "1"))
        per_page = int(request.args.get("per_page", "25"))
    except (TypeError, ValueError):
        return jsonify({
            "error": "page and per_page must be valid integers"
        }), 400

    if page < 1:
        return jsonify({"error": "page must be at least 1"}), 400

    if per_page < 1 or per_page > 100:
        return jsonify({
            "error": "per_page must be between 1 and 100"
        }), 400

    query = ActivityLog.query.order_by(
        ActivityLog.created_at.desc(),
        ActivityLog.id.desc()
    )

    total = query.count()

    records = query.offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    activities = []

    for record in records:
        activities.append({
            "id": record.id,
            "actor_user_id": record.actor_user_id,
            "actor_name": (
                record.actor.name if record.actor else None
            ),
            "target_user_id": record.target_user_id,
            "target_name": (
                record.target_user.name
                if record.target_user else None
            ),
            "action": record.action,
            "entity_type": record.entity_type,
            "entity_id": record.entity_id,
            "description": record.description,
            "created_at": (
                record.created_at.isoformat()
                if record.created_at else None
            )
        })

    return jsonify({
        "activities": activities,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (
                (total + per_page - 1) // per_page
            )
        }
    }), 200
