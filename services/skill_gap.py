
import re


# Alternative phrases used in placement descriptions.
# Each alias maps to an existing skill in the database.
SKILL_ALIASES = {
    "Database Management": [
        "database",
        "databases",
        "database management",
        "database administration",
        "dbms",
    ],
    "Problem-solving": [
        "problem solving",
        "problem-solving",
        "problem solving abilities",
        "problem-solving abilities",
    ],
    "Machine Learning": [
        "machine learning",
        "ml",
        "ml techniques",
    ],
    "Data Structures": [
        "data structure",
        "data structures",
        "data structures and algorithms",
        "dsa",
    ],
    "API Development": [
        "api development",
        "api",
        "apis",
        "rest api",
        "restful api",
    ],
    "Communication": [
        "communication",
        "communication skills",
        "verbal communication",
    ],
}


def _get_skill_patterns(skill_name):
    """Return the canonical skill name and its recognised aliases."""

    aliases = SKILL_ALIASES.get(skill_name, [])

    phrases = [skill_name] + aliases

    return [
        re.compile(
            r"(?<!\w)" + re.escape(phrase) + r"(?!\w)",
            re.IGNORECASE,
        )
        for phrase in phrases
    ]


def _find_skill_match(skill_name, description):
    """Find a canonical skill name or one of its aliases."""

    for pattern in _get_skill_patterns(skill_name):
        match = pattern.search(description)

        if match:
            return match

    return None


def _get_learning_priority(skill_name, description):
    """Estimate learning priority using the relevant wording."""

    skill_match = _find_skill_match(skill_name, description)

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

    clauses = re.split(
        r"[,.;!?\n]+|\b(?:but|whereas|while)\b",
        description,
        flags=re.IGNORECASE,
    )

    skill_clause = next(
        (
            clause
            for clause in clauses
            if _find_skill_match(skill_name, clause)
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
        local_match = _find_skill_match(skill_name, skill_clause)
        skill_position = local_match.start()

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

    description = job_description or ""

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

        if _find_skill_match(name, description):
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
