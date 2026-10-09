import re


def analyze_skill_gap(job_description, student_skills, available_skills):
    """
    Compare a student's recorded skills with skills mentioned
    in a placement job description.
    """

    description = (job_description or "").lower()

    student_skill_names = {
        item["skill_name"].strip().lower()
        for item in student_skills
        if item.get("skill_name", "").strip()
    }

    required_skills = []

    for skill in available_skills:
        name = skill["name"].strip()

        if not name:
            continue

        pattern = r"(?<!\w)" + re.escape(name.lower()) + r"(?!\w)"

        if re.search(pattern, description):
            required_skills.append(name)

    matched_skills = [
        name for name in required_skills
        if name.lower() in student_skill_names
    ]

    missing_skills = [
        name for name in required_skills
        if name.lower() not in student_skill_names
    ]

    total_required = len(required_skills)

    match_percentage = (
        round(len(matched_skills) / total_required * 100, 2)
        if total_required
        else None
    )

    return {
        "required_skills": required_skills,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "total_required_skills": total_required,
        "match_percentage": match_percentage,
        "method": "Rule-based matching against the existing skill catalog"
    }