from flask import Blueprint, jsonify
from models import Company, InterviewExperience
from collections import Counter

intelligence_bp = Blueprint('intelligence', __name__)


@intelligence_bp.route('/company/<int:company_id>', methods=['GET'])
def company_intelligence(company_id):
    company = Company.query.get(company_id)
    if not company:
        return jsonify({'error': 'Company not found'}), 404

    experiences = InterviewExperience.query.filter_by(company_id=company_id).all()

    if not experiences:
        return jsonify({
            'company_name': company.name,
            'total_experiences': 0,
            'message': 'No interview experiences recorded yet for this company'
        }), 200

    total = len(experiences)
    selected_count = sum(1 for e in experiences if e.selection_status == 'Selected')
    not_selected_count = total - selected_count

    difficulty_map = {'Easy': 1, 'Medium': 2, 'Hard': 3}
    difficulty_values = [difficulty_map[e.overall_difficulty] for e in experiences if e.overall_difficulty in difficulty_map]
    avg_difficulty_score = round(sum(difficulty_values) / len(difficulty_values), 2) if difficulty_values else None

    round_type_counter = Counter()
    question_counter = Counter()
    skill_counter = Counter()

    for e in experiences:
        for r in e.rounds:
            if r.round_type:
                round_type_counter[r.round_type] += 1
            for q in r.questions:
                question_counter[q.question_text.strip().lower()] += 1
        for s in e.skills:
            skill_counter[s.skill_name.strip().title()] += 1

    frequently_asked_questions = [
        {'question': q, 'times_mentioned': c}
        for q, c in question_counter.most_common(10)
    ]

    frequently_required_skills = [
        {'skill': s, 'times_mentioned': c}
        for s, c in skill_counter.most_common(10)
    ]

    round_type_distribution = dict(round_type_counter)

    return jsonify({
        'company_name': company.name,
        'total_experiences': total,
        'selected_count': selected_count,
        'not_selected_count': not_selected_count,
        'average_difficulty_score': avg_difficulty_score,
        'average_difficulty_note': '1 = Easy, 2 = Medium, 3 = Hard (student-reported)',
        'round_type_distribution': round_type_distribution,
        'frequently_asked_questions': frequently_asked_questions,
        'frequently_required_skills': frequently_required_skills
    }), 200