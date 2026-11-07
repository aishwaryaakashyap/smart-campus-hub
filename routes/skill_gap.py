
from flask import Blueprint, jsonify, session
from extensions import db
from models import User, Student, StudentSkill, Skill, PlacementDrive
from services.skill_gap import analyze_skill_gap

skill_gap_bp = Blueprint("skill_gap", __name__)


@skill_gap_bp.route("/<int:drive_id>", methods=["GET"])
def get_skill_gap(drive_id):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    if session.get("role") != "student":
        return jsonify({"error": "Only students can view their skill gap"}), 403

    student = Student.query.filter_by(
        user_id=session["user_id"]
    ).first()

    if not student:
        return jsonify({"error": "Student profile not found"}), 404

    drive = PlacementDrive.query.get(drive_id)

    if not drive:
        return jsonify({"error": "Placement drive not found"}), 404

    student_skills = [
        {
            "skill_name": entry.skill.name,
            "proficiency": entry.proficiency
        }
        for entry in StudentSkill.query.filter_by(
            student_id=student.id
        ).all()
        if entry.skill
    ]

    available_skills = [
        {"name": skill.name}
        for skill in Skill.query.all()
    ]

    result = analyze_skill_gap(
        drive.job_description,
        student_skills,
        available_skills
    )

    return jsonify({
        "student_id": student.id,
        "drive_id": drive.id,
        "job_role": drive.job_role,
        **result
    }), 200


@skill_gap_bp.route("/coordinator/<int:drive_id>", methods=["GET"])
def get_coordinator_skill_gap(drive_id):
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    if session.get("role") != "coordinator":
        return jsonify({
            "error": "Only coordinators can view overall skill gap analysis"
        }), 403

    coordinator = db.session.get(User, session["user_id"])

    if not coordinator or coordinator.role != "coordinator":
        session.clear()
        return jsonify({"error": "Invalid coordinator session"}), 401

    drive = PlacementDrive.query.get(drive_id)

    if not drive:
        return jsonify({"error": "Placement drive not found"}), 404

    students = Student.query.all()
    skills = Skill.query.all()
    student_skill_entries = StudentSkill.query.all()

    available_skills = [
        {"name": skill.name}
        for skill in skills
    ]

    # Identify the skills required by this placement drive.
    drive_analysis = analyze_skill_gap(
        drive.job_description,
        [],
        available_skills
    )

    required_skills = drive_analysis["required_skills"]

    # Build a map of registered skills for each student.
    student_skills = {}

    for entry in student_skill_entries:
        if not entry.skill:
            continue

        student_skills.setdefault(entry.student_id, []).append({
            "skill_name": entry.skill.name,
            "proficiency": entry.proficiency
        })

    total_students = len(students)
    skill_report = []
    total_skill_matches = 0

    for skill_name in required_skills:
        students_with_skill = set()
        proficiency_counts = {
            "Beginner": 0,
            "Intermediate": 0,
            "Advanced": 0
        }

        for student in students:
            entries = student_skills.get(student.id, [])

            matching_entries = [
                entry for entry in entries
                if entry["skill_name"].strip().lower()
                == skill_name.strip().lower()
            ]

            if matching_entries:
                students_with_skill.add(student.id)

                # Count each student once per skill.
                proficiency = matching_entries[0]["proficiency"]
                if proficiency in proficiency_counts:
                    proficiency_counts[proficiency] += 1

        available_count = len(students_with_skill)
        missing_count = total_students - available_count
        total_skill_matches += available_count

        skill_report.append({
            "skill_name": skill_name,
            "students_with_skill": available_count,
            "students_missing_skill": missing_count,
            "proficiency_counts": proficiency_counts
        })

    total_skill_requirements = total_students * len(required_skills)

    readiness_percentage = (
        round(total_skill_matches / total_skill_requirements * 100, 2)
        if total_skill_requirements else None
    )

    skill_report.sort(
        key=lambda item: (
            -item["students_missing_skill"],
            item["skill_name"].lower()
        )
    )

    return jsonify({
        "drive_id": drive.id,
        "job_role": drive.job_role,
        "company_name": drive.company.name if drive.company else None,
        "total_students": total_students,
        "total_required_skills": len(required_skills),
        "overall_skill_readiness": readiness_percentage,
        "required_skills": required_skills,
        "skill_report": skill_report,
        "method": "Aggregate rule-based matching against registered student skills"
    }), 200
