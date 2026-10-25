
import re


def _get_learning_priority(skill_name, description):
    """Estimate priority using the closest relevant wording for a skill."""

    skill_pattern = re.compile(
        r"(?<!\w)" + re.escape(skill_name) + r"(?!\w)",
        re.IGNORECASE,
    )
    skill_match = skill_pattern.search(description)

    if not skill_match:
        return "Medium"

    high_pattern = re.compile(
        r"\brequired\b|\bmandatory\b|\bessential\b|"
        r"\bmust[\s-]+have\b|\bproficient in\b|"
        r"\bstrong knowledge of\b",
        re.IGNORECASE,
    )

    low_pattern = re.compile(
        r"\bpreferred\b|\bbonus\b|\bnice to have\b|"
        r"\boptional\b|\bgood to have\b|\badded advantage\b",
        re.IGNORECASE,
    )

    # Find the clause containing this skill.
    # Conjunctions and punctuation separate nearby skill requirements.
    clauses = re.split(
        r"[,.;!?\n]+|\b(?:but|whereas|while)\b",
        description,
        flags=re.IGNORECASE,
    )

    skill_clause = next(
        (
            clause
            for clause in clauses
            if skill_pattern.search(clause)
        ),
        "",
    )

    has_high = bool(high_pattern.search(skill_clause))
    has_low = bool(low_pattern.search(skill_clause))

    if has_high and not has_low:
        return "High"

    if has_low and not has_high:
        return "Low"

    if has_high and has_low:
        # If both terms occur in the same clause, use the closest term.
        local_skill_match = skill_pattern.search(skill_clause)
        skill_position = local_skill_match.start()

        priority_matches = []

        for priority, pattern in (
            ("High", high_pattern),
            ("Low", low_pattern),
        ):
            for match in pattern.finditer(skill_clause):
                distance = min(
                    abs(skill_position - match.end()),
                    abs(skill_position - match.start()),
                )
                priority_matches.append((distance, priority))

        if priority_matches:
            priority_matches.sort(key=lambda item: item[0])
            return priority_matches[0][1]

    return "Medium"


def analyze_skill_gap(job_description, student_skills, available_skills):
    """Compare student skills with job requirements and suggest priorities."""

    description = (job_description or "").lower()

    student_skill_names = {
        (item.get("skill_name") or "").strip().lower()
        for item in student_skills
        if (item.get("skill_name") or "").strip()
    }

    required_skills = []
    seen_skills = set()

    for skill in available_skills:
        name = (skill.get("name") or "").strip()

        if not name:
            continue

        normalized_name = name.lower()

        if normalized_name in seen_skills:
            continue

        pattern = r"(?<!\w)" + re.escape(normalized_name) + r"(?!\w)"

        if re.search(pattern, description):
            required_skills.append(name)
            seen_skills.add(normalized_name)

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

    learning_priorities = []

    for name in missing_skills:
        priority = _get_learning_priority(name, description)

        if priority == "High":
            suggestion = "Start learning this skill first."
        elif priority == "Low":
            suggestion = "Consider learning this after essential skills."
        else:
            suggestion = "Add this skill to your learning plan."

        learning_priorities.append({
            "skill_name": name,
            "priority": priority,
            "suggestion": suggestion,
        })

    return {
        "required_skills": required_skills,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "total_required_skills": total_required,
        "match_percentage": match_percentage,
        "method": "Rule-based matching against the existing skill catalog",
        "learning_priorities": learning_priorities,
    }
