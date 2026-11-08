from io import BytesIO
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, session
from werkzeug.utils import secure_filename

from extensions import db
from models import Student, Resume, Skill, PlacementDrive
from services.resume_analysis import (
    ResumeProcessingError,
    extract_pdf_text,
    extract_resume_skills,
    analyze_resume_job_match,
)

resume_bp = Blueprint("resume", __name__)


def require_student():
    if "user_id" not in session:
        return None, (jsonify({"error": "Not logged in"}), 401)

    if session.get("role") != "student":
        return None, (
            jsonify({"error": "Only students can access resume services"}),
            403,
        )

    student = Student.query.filter_by(
        user_id=session["user_id"]
    ).first()

    if not student:
        return None, (
            jsonify({"error": "Student profile not found"}),
            404,
        )

    return student, None


def remove_private_file(path):
    """Remove a private resume file without exposing filesystem details."""
    try:
        if path and path.exists():
            path.unlink()
    except OSError:
        current_app.logger.warning(
            "Unable to remove an obsolete resume file."
        )


def resume_response(resume):
    skills = extract_resume_skills(
        resume.extracted_text,
        Skill.query.all()
    )

    return {
        "id": resume.id,
        "original_filename": resume.original_filename,
        "uploaded_at": (
            resume.uploaded_at.isoformat()
            if resume.uploaded_at else None
        ),
        "extracted_skills": skills,
    }


@resume_bp.route("/", methods=["POST"])
def upload_resume():
    student, error = require_student()
    if error:
        return error

    uploaded_file = request.files.get("resume")

    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "Please select a PDF resume."}), 400

    safe_name = secure_filename(uploaded_file.filename)

    if not safe_name or Path(safe_name).suffix.lower() != ".pdf":
        return jsonify({"error": "Only PDF resume files are accepted."}), 400

    max_bytes = current_app.config.get(
        "RESUME_MAX_BYTES", 5 * 1024 * 1024
    )

    try:
        file_bytes = uploaded_file.read(max_bytes + 1)
    except Exception:
        return jsonify({"error": "Unable to read the uploaded file."}), 400

    if not file_bytes:
        return jsonify({"error": "The uploaded file is empty."}), 400

    if len(file_bytes) > max_bytes:
        return jsonify({
            "error": "Resume file exceeds the 5 MB upload limit."
        }), 413

    if not file_bytes.startswith(b"%PDF-"):
        return jsonify({"error": "The uploaded file is not a valid PDF."}), 400

    try:
        extracted_text = extract_pdf_text(BytesIO(file_bytes))
    except ResumeProcessingError as exc:
        return jsonify({"error": str(exc)}), 400

    max_text_chars = current_app.config.get(
        "RESUME_MAX_TEXT_CHARS", 250000
    )

    if len(extracted_text) > max_text_chars:
        return jsonify({
            "error": "The extracted resume text exceeds the allowed limit."
        }), 413

    existing = Resume.query.filter_by(
        student_id=student.id
    ).first()

    upload_directory = Path(
        current_app.config["RESUME_UPLOAD_FOLDER"]
    )
    upload_directory.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid4().hex}.pdf"
    new_path = upload_directory / stored_filename

    try:
        with new_path.open("xb") as output:
            output.write(file_bytes)
    except OSError:
        return jsonify({
            "error": "Unable to store the resume securely."
        }), 500

    old_path = None
    if existing and existing.stored_filename:
        old_path = upload_directory / Path(
            existing.stored_filename
        ).name

    try:
        if existing:
            existing.original_filename = safe_name[:255]
            existing.stored_filename = stored_filename
            existing.extracted_text = extracted_text
            existing.uploaded_at = datetime.now(timezone.utc).replace(tzinfo=None)
            resume = existing
        else:
            resume = Resume(
                student_id=student.id,
                original_filename=safe_name[:255],
                stored_filename=stored_filename,
                extracted_text=extracted_text,
            )
            db.session.add(resume)

        db.session.commit()

    except Exception:
        db.session.rollback()
        remove_private_file(new_path)
        return jsonify({
            "error": "Unable to save the resume information."
        }), 500

    if old_path and old_path != new_path:
        remove_private_file(old_path)

    return jsonify({
        "message": (
            "Resume replaced successfully."
            if existing else "Resume uploaded successfully."
        ),
        "resume": resume_response(resume),
    }), 200 if existing else 201


@resume_bp.route("/", methods=["GET"])
def get_resume():
    student, error = require_student()
    if error:
        return error

    resume = Resume.query.filter_by(
        student_id=student.id
    ).first()

    if not resume:
        return jsonify({"error": "No resume has been uploaded yet."}), 404

    return jsonify({"resume": resume_response(resume)}), 200


@resume_bp.route("/match/<int:drive_id>", methods=["GET"])
def match_resume_to_drive(drive_id):
    student, error = require_student()
    if error:
        return error

    resume = Resume.query.filter_by(
        student_id=student.id
    ).first()

    if not resume:
        return jsonify({"error": "Upload your resume before matching it."}), 404

    drive = db.session.get(PlacementDrive, drive_id)

    if not drive:
        return jsonify({"error": "Placement drive not found."}), 404

    try:
        result = analyze_resume_job_match(
            resume.extracted_text,
            drive.job_description,
            Skill.query.all(),
        )
    except ResumeProcessingError as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "resume_id": resume.id,
        "drive_id": drive.id,
        "company_name": drive.company.name if drive.company else None,
        "job_role": drive.job_role,
        **result,
    }), 200
