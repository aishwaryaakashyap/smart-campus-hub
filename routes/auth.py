import re
import secrets
import hashlib
import hmac

from datetime import datetime, timedelta

from flask import (
    Blueprint, request, jsonify, session,
    render_template, redirect, url_for, current_app
)

from extensions import db
from models import User, Student, AcademicClass, StudentRegistrationOTP
from services.email_service import send_student_otp_email


auth_bp = Blueprint('auth', __name__)


def _utc_now():
    return datetime.utcnow()


def _otp_hash(user_id, otp):
    secret = current_app.config.get('SECRET_KEY')

    if not secret:
        raise RuntimeError("SECRET_KEY is not configured.")

    message = f"{user_id}:{otp}".encode("utf-8")

    return hmac.new(
        str(secret).encode("utf-8"),
        message,
        hashlib.sha256
    ).hexdigest()


def _create_student_otp(user):
    now = _utc_now()

    otp = f"{secrets.randbelow(1000000):06d}"

    # Invalidate all previously issued, unused codes.
    StudentRegistrationOTP.query.filter_by(
        user_id=user.id,
        used_at=None
    ).update(
        {"used_at": now},
        synchronize_session=False
    )

    expiry_minutes = current_app.config.get(
        "STUDENT_OTP_MINUTES", 10
    )

    record = StudentRegistrationOTP(
        user_id=user.id,
        otp_hash=_otp_hash(user.id, otp),
        created_at=now,
        expires_at=now + timedelta(minutes=expiry_minutes),
        attempts=0
    )

    db.session.add(record)

    return otp, expiry_minutes


@auth_bp.route('/registration-classes', methods=['GET'])
def registration_classes():
    """Return active classes that have an active assigned Advisor."""

    classes = (
        AcademicClass.query
        .join(
            User,
            AcademicClass.advisor_user_id == User.id
        )
        .filter(
            AcademicClass.is_active.is_(True),
            User.role == User.ROLE_ADVISOR,
            User.account_status == User.STATUS_ACTIVE
        )
        .order_by(
            AcademicClass.course,
            AcademicClass.branch,
            AcademicClass.section
        )
        .all()
    )

    return jsonify({
        "classes": [
            {
                "id": item.id,
                "course": item.course,
                "branch": item.branch,
                "section": item.section,
                "admission_year": item.admission_year
            }
            for item in classes
        ]
    }), 200


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'A valid JSON object is required'
        }), 400

    required_fields = ['name', 'email', 'password', 'role']

    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({
                'error': f'{field} is required'
            }), 400

    # Public registration is restricted to students.
    if (
        not isinstance(data['role'], str)
        or data['role'] != User.ROLE_STUDENT
    ):
        return jsonify({
            'error': 'Only student registration is allowed'
        }), 400

    if not all(
        isinstance(data[field], str)
        for field in ['name', 'email', 'password']
    ):
        return jsonify({
            'error': 'Name, email, and password must be strings'
        }), 400

    name = data['name'].strip()
    raw_email = data['email'].strip()
    password = data['password']

    if not name or not raw_email:
        return jsonify({
            'error': 'Name and email cannot be blank'
        }), 400

    if len(name) > 100:
        return jsonify({
            'error': 'Name must be 100 characters or fewer'
        }), 400

    if len(raw_email) > 120:
        return jsonify({
            'error': 'Email must be 120 characters or fewer'
        }), 400

    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', raw_email):
        return jsonify({
            'error': 'Please provide a valid email address'
        }), 400

    if len(password) < 8:
        return jsonify({
            'error': 'Password must be at least 8 characters long'
        }), 400

    if len(password) > 128:
        return jsonify({
            'error': 'Password must be 128 characters or fewer'
        }), 400

    # New required student profile fields.
    register_number = data.get('register_number')

    if not isinstance(register_number, str) or not register_number.strip():
        return jsonify({
            'error': 'Register number is required'
        }), 400

    register_number = register_number.strip()

    if len(register_number) > 30:
        return jsonify({
            'error': 'Register number must be 30 characters or fewer'
        }), 400

    try:
        academic_class_id = int(data.get('academic_class_id'))
    except (TypeError, ValueError):
        return jsonify({
            'error': 'Please select a valid academic class'
        }), 400

    if isinstance(data.get('academic_class_id'), bool):
        return jsonify({
            'error': 'Please select a valid academic class'
        }), 400

    academic_class = db.session.get(
        AcademicClass,
        academic_class_id
    )

    if (
        not academic_class
        or not academic_class.is_active
        or not academic_class.advisor
        or academic_class.advisor.role != User.ROLE_ADVISOR
        or academic_class.advisor.account_status != User.STATUS_ACTIVE
    ):
        return jsonify({
            'error': 'Selected class is unavailable'
        }), 400

    email = raw_email.lower()

    if User.query.filter_by(email=email).first():
        return jsonify({
            'error': 'Email already registered'
        }), 409

    if Student.query.filter_by(
        register_number=register_number
    ).first():
        return jsonify({
            'error': 'Register number already registered'
        }), 409

    # Validate optional student fields.
    semester = data.get('semester')

    if semester not in (None, ''):
        try:
            semester = int(semester)
        except (TypeError, ValueError):
            return jsonify({
                'error': 'Semester must be a valid number'
            }), 400

        if not 1 <= semester <= 12:
            return jsonify({
                'error': 'Semester must be between 1 and 12'
            }), 400
    else:
        semester = None

    cgpa = data.get('cgpa')

    if cgpa not in (None, ''):
        try:
            cgpa = float(cgpa)
        except (TypeError, ValueError):
            return jsonify({
                'error': 'CGPA must be a valid number'
            }), 400

        if not 0 <= cgpa <= 10:
            return jsonify({
                'error': 'CGPA must be between 0 and 10'
            }), 400
    else:
        cgpa = None

    phone = data.get('phone')

    if phone is not None:
        if not isinstance(phone, str) or len(phone.strip()) > 15:
            return jsonify({
                'error': 'Phone number must be 15 characters or fewer'
            }), 400

        phone = phone.strip() or None

    graduation_year = data.get('graduation_year')

    if graduation_year not in (None, ''):
        try:
            graduation_year = int(graduation_year)
        except (TypeError, ValueError):
            return jsonify({
                'error': 'Graduation year must be a valid year'
            }), 400
    else:
        graduation_year = None

    new_user = User(
        name=name,
        email=email,
        role=User.ROLE_STUDENT,
        account_status=User.STATUS_PENDING
    )
    new_user.set_password(password)

    try:
        db.session.add(new_user)
        db.session.flush()

        student = Student(
            user_id=new_user.id,
            register_number=register_number,
            course=academic_class.course,
            branch=academic_class.branch,
            semester=semester,
            cgpa=cgpa,
            phone=phone,
            graduation_year=graduation_year,
            academic_class_id=academic_class.id
        )

        db.session.add(student)

        otp, expiry_minutes = _create_student_otp(new_user)

        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Student registration database operation failed"
        )

        return jsonify({
            'error': 'Unable to register student'
        }), 500

    # Send email after the database transaction succeeds.
    try:
        send_student_otp_email(
            new_user.email,
            otp,
            expiry_minutes
        )
    except Exception:
        current_app.logger.exception(
            "Student registration OTP email could not be sent"
        )

        return jsonify({
            'message': (
                'Registration was saved, but the verification email '
                'could not be sent. Please try resending the OTP.'
            ),
            'email': new_user.email,
            'email_sent': False
        }), 503

    return jsonify({
        'message': 'Registration successful. Verify your email using the OTP sent to you.',
        'user_id': new_user.id,
        'email': new_user.email,
        'email_sent': True,
        'otp_expiry_minutes': expiry_minutes
    }), 201


@auth_bp.route('/verify-registration-otp', methods=['POST'])
def verify_registration_otp():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'A valid JSON object is required'
        }), 400

    email = data.get('email')
    otp = data.get('otp')

    if not isinstance(email, str) or not email.strip():
        return jsonify({
            'error': 'Email is required'
        }), 400

    if not isinstance(otp, str) or not re.fullmatch(r'\d{6}', otp):
        return jsonify({
            'error': 'A valid six-digit OTP is required'
        }), 400

    user = User.query.filter_by(
        email=email.strip().lower(),
        role=User.ROLE_STUDENT
    ).first()

    if not user:
        return jsonify({
            'error': 'Invalid email or OTP'
        }), 400

    if user.email_verified_at:
        return jsonify({
            'message': 'Email is already verified'
        }), 200

    if user.account_status != User.STATUS_PENDING:
        return jsonify({
            'error': 'This registration cannot be verified'
        }), 400

    record = (
        StudentRegistrationOTP.query
        .filter_by(user_id=user.id, used_at=None)
        .order_by(StudentRegistrationOTP.created_at.desc())
        .first()
    )

    if not record:
        return jsonify({
            'error': 'No active OTP found. Please request a new OTP.'
        }), 400

    now = _utc_now()

    if record.expires_at <= now:
        record.used_at = now
        db.session.commit()

        return jsonify({
            'error': 'OTP has expired. Please request a new OTP.'
        }), 400

    max_attempts = current_app.config.get(
        'STUDENT_OTP_MAX_ATTEMPTS', 5
    )

    if record.attempts >= max_attempts:
        record.used_at = now
        db.session.commit()

        return jsonify({
            'error': 'Maximum OTP attempts reached. Please request a new OTP.'
        }), 429

    record.attempts += 1

    expected_hash = _otp_hash(user.id, otp)

    if not hmac.compare_digest(record.otp_hash, expected_hash):
        if record.attempts >= max_attempts:
            record.used_at = now

        db.session.commit()

        return jsonify({
            'error': 'Incorrect OTP'
        }), 400

    record.used_at = now
    user.email_verified_at = now

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

        return jsonify({
            'error': 'Unable to verify email. Please try again.'
        }), 500

    return jsonify({
        'message': 'Email verified successfully. Your account is awaiting Advisor approval.',
        'email_verified': True,
        'account_status': user.account_status
    }), 200


@auth_bp.route('/resend-registration-otp', methods=['POST'])
def resend_registration_otp():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'A valid JSON object is required'
        }), 400

    email = data.get('email')

    if not isinstance(email, str) or not email.strip():
        return jsonify({
            'error': 'Email is required'
        }), 400

    user = User.query.filter_by(
        email=email.strip().lower(),
        role=User.ROLE_STUDENT
    ).first()

    # Do not disclose whether an email is registered.
    if (
        not user
        or user.email_verified_at
        or user.account_status != User.STATUS_PENDING
    ):
        return jsonify({
            'message': 'If the registration needs verification, an OTP will be sent.'
        }), 200

    now = _utc_now()

    latest = (
        StudentRegistrationOTP.query
        .filter_by(user_id=user.id)
        .order_by(StudentRegistrationOTP.created_at.desc())
        .first()
    )

    cooldown = current_app.config.get(
        'STUDENT_OTP_RESEND_SECONDS', 60
    )

    if latest and (now - latest.created_at).total_seconds() < cooldown:
        return jsonify({
            'error': 'Please wait before requesting another OTP.'
        }), 429

    hourly_limit = current_app.config.get(
        'STUDENT_OTP_MAX_RESENDS_PER_HOUR', 5
    )

    recent_count = StudentRegistrationOTP.query.filter(
        StudentRegistrationOTP.user_id == user.id,
        StudentRegistrationOTP.created_at >= now - timedelta(hours=1)
    ).count()

    if recent_count >= hourly_limit:
        return jsonify({
            'error': 'OTP resend limit reached. Please try again later.'
        }), 429

    try:
        otp, expiry_minutes = _create_student_otp(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Unable to create replacement student OTP"
        )

        return jsonify({
            'error': 'Unable to generate a new OTP'
        }), 500

    try:
        send_student_otp_email(
            user.email,
            otp,
            expiry_minutes
        )
    except Exception:
        current_app.logger.exception(
            "Unable to send replacement student OTP email"
        )

        return jsonify({
            'error': 'Unable to send OTP email. Please try again later.'
        }), 503

    return jsonify({
        'message': 'A new verification OTP has been sent.',
        'email_sent': True,
        'otp_expiry_minutes': expiry_minutes
    }), 200


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            'error': 'A valid JSON object is required'
        }), 400

    if (
        not isinstance(data.get('email'), str)
        or not isinstance(data.get('password'), str)
        or not data['email'].strip()
        or not data['password']
    ):
        return jsonify({
            'error': 'Email and password are required'
        }), 400

    email = data['email'].strip().lower()

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(data['password']):
        return jsonify({
            'error': 'Invalid email or password'
        }), 401

    if user.account_status == User.STATUS_PENDING:
        if (
            user.role == User.ROLE_STUDENT
            and not user.email_verified_at
        ):
            return jsonify({
                'error': 'Please verify your email before logging in.'
            }), 403

        return jsonify({
            'error': 'Your account is awaiting Advisor approval.'
        }), 403

    if user.account_status == User.STATUS_REJECTED:
        return jsonify({
            'error': 'Your registration was rejected. Please contact your institution.'
        }), 403

    if user.account_status != User.STATUS_ACTIVE:
        return jsonify({
            'error': 'This account is not active. Contact the Coordinator.'
        }), 403

    session.clear()
    session['user_id'] = user.id
    session['role'] = user.role

    return jsonify({
        'message': 'Login successful',
        'user_id': user.id,
        'name': user.name,
        'role': user.role
    }), 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()

    return jsonify({
        'message': 'Logged out successfully'
    }), 200


@auth_bp.route('/me', methods=['GET'])
def me():
    if 'user_id' not in session:
        return jsonify({
            'error': 'Not logged in'
        }), 401

    user = db.session.get(User, session['user_id'])

    if (
        not user
        or user.account_status != User.STATUS_ACTIVE
    ):
        session.clear()
        return jsonify({
            'error': 'Not logged in or account is not active'
        }), 401

    return jsonify({
        'user_id': user.id,
        'name': user.name,
        'email': user.email,
        'role': user.role
    }), 200


@auth_bp.route('/register-page', methods=['GET'])
def register_page():
    return render_template('register.html')

@auth_bp.route('/login-page', methods=['GET'])
def login_page():
    return render_template('login.html')


@auth_bp.route('/student-dashboard', methods=['GET'])
def student_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login_page'))

    if session.get('role') != 'student':
        return jsonify({
            'error': 'Only students can access this dashboard'
        }), 403

    user = db.session.get(User, session['user_id'])

    if (
        not user
        or user.role != 'student'
        or user.account_status != User.STATUS_ACTIVE
    ):
        session.clear()
        return redirect(url_for('auth.login_page'))

    return render_template(
        'student_dashboard.html',
        user=user
    )
