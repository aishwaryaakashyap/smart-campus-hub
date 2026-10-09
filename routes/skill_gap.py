from flask import Blueprint, jsonify, session
from models import Student, StudentSkill, Skill, PlacementDrive
from services.skill_gap import analyze_skill_gap

skill_gap_bp = Blueprint("skill_gap", **name**)

@skill_gap_bp.route("/[int:drive_id](int:drive_id)", methods=["GET"])
def get_skill_gap(drive_id):
if "user_id" not in session:
return jsonify({"error": "Not logged in"}), 401

```
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
```
