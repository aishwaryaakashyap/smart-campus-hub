
from collections import Counter, defaultdict

from flask import Blueprint, jsonify

from models import Company, InterviewExperience


intelligence_bp = Blueprint("intelligence", __name__)


def build_preparation_recommendations(
    topic_counter,
    skill_details,
    round_type_counter,
    average_difficulty_score,
):
    """Build rule-based preparation advice from reported interview data."""
    recommendations = []

    if topic_counter:
        topic, count = topic_counter.most_common(1)[0]
        recommendations.append({
            "category": "Topic",
            "title": f"Practise {topic}",
            "reason": (
                f"This topic appeared in {count} recorded interview "
                f"question(s)."
            ),
            "priority": "High",
        })

    if skill_details:
        highest_skill = max(
            skill_details,
            key=lambda item: (
                item["average_importance_rating"]
                if item["average_importance_rating"] is not None
                else 0,
                item["times_mentioned"],
            ),
        )
        recommendations.append({
            "category": "Skill",
            "title": f"Revise {highest_skill['skill']}",
            "reason": (
                "This skill has a high student-reported importance "
                "rating or appears frequently in the recorded experiences."
            ),
            "priority": "High",
        })

    if round_type_counter:
        round_type, count = round_type_counter.most_common(1)[0]
        round_advice = {
            "Aptitude": "Practise quantitative, logical reasoning, and verbal questions.",
            "Coding": "Solve coding problems and practise explaining your approach.",
            "Technical": "Revise core concepts, projects, and technical fundamentals.",
            "HR": "Practise your introduction, strengths, and behavioural questions.",
            "Group Discussion": "Practise clear communication and respectful discussion.",
            "Managerial": "Prepare examples of teamwork, decisions, and problem-solving.",
        }
        advice = round_advice.get(
            round_type,
            f"Review the format and questions reported for the {round_type} round.",
        )
        recommendations.append({
            "category": "Interview Round",
            "title": f"Prepare for {round_type}",
            "reason": f"{count} recorded experience(s) included this round. {advice}",
            "priority": "Medium",
        })

    if average_difficulty_score is not None:
        if average_difficulty_score >= 2.5:
            recommendations.append({
                "category": "Difficulty",
                "title": "Plan extra practice time",
                "reason": (
                    "Reported interview difficulty is relatively high. "
                    "Practise timed questions and review weak areas."
                ),
                "priority": "High",
            })
        elif average_difficulty_score >= 1.75:
            recommendations.append({
                "category": "Difficulty",
                "title": "Strengthen your fundamentals",
                "reason": (
                    "Reported interview difficulty is moderate. "
                    "Review core concepts and solve practice questions."
                ),
                "priority": "Medium",
            })

    if not recommendations:
        recommendations.append({
            "category": "General",
            "title": "Start with interview fundamentals",
            "reason": (
                "Add more interview questions, topics, and skills "
                "to generate company-specific preparation advice."
            ),
            "priority": "Medium",
        })

    return recommendations


@intelligence_bp.route("/company/<int:company_id>", methods=["GET"])
def company_intelligence(company_id):
    company = Company.query.get(company_id)

    if not company:
        return jsonify({"error": "Company not found"}), 404

    experiences = InterviewExperience.query.filter_by(
        company_id=company_id
    ).all()

    if not experiences:
        return jsonify({
            "company_name": company.name,
            "total_experiences": 0,
            "message": (
                "No interview experiences recorded yet for this company"
            ),
            "recommended_topics": [],
            "skill_priorities": [],
            "preparation_recommendations": [],
            "preparation_resources": [],
        }), 200

    total = len(experiences)

    selected_count = sum(
        1 for experience in experiences
        if experience.selection_status == "Selected"
    )
    not_selected_count = total - selected_count

    difficulty_map = {"Easy": 1, "Medium": 2, "Hard": 3}
    difficulty_values = [
        difficulty_map[experience.overall_difficulty.strip().title()]
        for experience in experiences
        if isinstance(experience.overall_difficulty, str)
        and experience.overall_difficulty.strip().title() in difficulty_map
    ]

    average_difficulty_score = (
        round(sum(difficulty_values) / len(difficulty_values), 2)
        if difficulty_values else None
    )

    round_type_counter = Counter()
    question_counter = Counter()
    topic_counter = Counter()
    skill_counter = Counter()
    skill_importance = defaultdict(list)
    resources_by_key = {}

    for experience in experiences:
        for interview_round in (getattr(experience, "rounds", None) or []):
            round_type = getattr(interview_round, "round_type", None)

            if isinstance(round_type, str) and round_type.strip():
                round_type_counter[round_type.strip().title()] += 1

            for question in (
                getattr(interview_round, "questions", None) or []
            ):
                question_text = getattr(question, "question_text", None)

                if isinstance(question_text, str) and question_text.strip():
                    question_counter[question_text.strip().lower()] += 1

                topic = getattr(question, "topic", None)
                if isinstance(topic, str) and topic.strip():
                    topic_counter[topic.strip().title()] += 1

        for skill in (getattr(experience, "skills", None) or []):
            skill_name = getattr(skill, "skill_name", None)

            if not isinstance(skill_name, str) or not skill_name.strip():
                continue

            normalized_skill = skill_name.strip().title()
            skill_counter[normalized_skill] += 1

            rating = getattr(skill, "importance_rating", None)
            if isinstance(rating, int) and not isinstance(rating, bool):
                if 1 <= rating <= 5:
                    skill_importance[normalized_skill].append(rating)

        for resource in (getattr(experience, "resources", None) or []):
            resource_name = getattr(resource, "resource_name", None)

            if not isinstance(resource_name, str) or not resource_name.strip():
                continue

            resource_url = getattr(resource, "url", None)
            resource_type = getattr(resource, "resource_type", None)

            key = (
                resource_name.strip().casefold(),
                resource_url.strip() if isinstance(resource_url, str) else "",
            )

            if key not in resources_by_key:
                resources_by_key[key] = {
                    "resource_name": resource_name.strip(),
                    "resource_type": resource_type,
                    "url": resource_url,
                    "description": getattr(resource, "description", None),
                }

    frequently_asked_questions = [
        {"question": question, "times_mentioned": count}
        for question, count in question_counter.most_common(10)
    ]

    frequently_required_skills = [
        {"skill": skill, "times_mentioned": count}
        for skill, count in skill_counter.most_common(10)
    ]

    skill_priorities = [
        {
            "skill": skill,
            "times_mentioned": count,
            "average_importance_rating": (
                round(sum(skill_importance[skill]) / len(skill_importance[skill]), 2)
                if skill_importance[skill] else None
            ),
        }
        for skill, count in skill_counter.most_common(10)
    ]

    recommended_topics = [
        {"topic": topic, "times_mentioned": count}
        for topic, count in topic_counter.most_common(10)
    ]

    preparation_resources = list(resources_by_key.values())[:10]

    preparation_recommendations = build_preparation_recommendations(
        topic_counter=topic_counter,
        skill_details=skill_priorities,
        round_type_counter=round_type_counter,
        average_difficulty_score=average_difficulty_score,
    )

    return jsonify({
        "company_name": company.name,
        "total_experiences": total,
        "selected_count": selected_count,
        "not_selected_count": not_selected_count,
        "average_difficulty_score": average_difficulty_score,
        "average_difficulty_note": (
            "1 = Easy, 2 = Medium, 3 = Hard (student-reported)"
        ),
        "round_type_distribution": dict(round_type_counter),
        "frequently_asked_questions": frequently_asked_questions,
        "frequently_required_skills": frequently_required_skills,
        "recommended_topics": recommended_topics,
        "skill_priorities": skill_priorities,
        "preparation_recommendations": preparation_recommendations,
        "preparation_resources": preparation_resources,
    }), 200
