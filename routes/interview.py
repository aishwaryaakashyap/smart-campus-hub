from flask import Blueprint, request, jsonify, session
from extensions import db
from models import (Student, Company, InterviewExperience, InterviewRound,
                    InterviewQuestion, StudentAnswer, InterviewSkill,
                    PreparationResource)

interview_bp = Blueprint('interview', __name__)

VALID_SELECTION = ['Selected', 'Not Selected']
VALID_DIFFICULTY = ['Easy', 'Medium', 'Hard']
VALID_ROUND_TYPES = ['Aptitude', 'Coding', 'Technical', 'HR',
                     'Group Discussion', 'Managerial', 'Other']
VALID_ANSWER_STATUS = ['Correct', 'Partially Correct', 'Incorrect', 'Not Evaluated']


def require_student():
    if 'user_id' not in session:
        return None, (jsonify({'error': 'Not logged in'}), 401)
    if session.get('role') != 'student':
        return None, (jsonify({'error': 'Only students can perform this action'}), 403)
    student = Student.query.filter_by(user_id=session['user_id']).first()
    if not student:
        return None, (jsonify({'error': 'Student profile not found. Create your profile first.'}), 404)
    return student, None


@interview_bp.route('/', methods=['POST'])
def submit_experience():
    student, error = require_student()
    if error:
        return error

    data = request.get_json()

    for field in ['company_id', 'selection_status']:
        if field not in data or not data[field]:
            return jsonify({'error': f'{field} is required'}), 400

    if not Company.query.get(data['company_id']):
        return jsonify({'error': 'Company not found'}), 404
    if data['selection_status'] not in VALID_SELECTION:
        return jsonify({'error': f'selection_status must be one of {VALID_SELECTION}'}), 400
    if data.get('overall_difficulty') and data['overall_difficulty'] not in VALID_DIFFICULTY:
        return jsonify({'error': f'overall_difficulty must be one of {VALID_DIFFICULTY}'}), 400

    exp = InterviewExperience(
        student_id=student.id,
        company_id=data['company_id'],
        job_role=data.get('job_role'),
        year=data.get('year'),
        selection_status=data['selection_status'],
        overall_difficulty=data.get('overall_difficulty'),
        preparation_summary=data.get('preparation_summary'),
        selection_factors=data.get('selection_factors')
    )
    db.session.add(exp)
    db.session.flush()  # gives exp.id without committing yet

    for i, r in enumerate(data.get('rounds', []), start=1):
        if r.get('round_type') and r['round_type'] not in VALID_ROUND_TYPES:
            db.session.rollback()
            return jsonify({'error': f'round_type must be one of {VALID_ROUND_TYPES}'}), 400
        rnd = InterviewRound(
            experience_id=exp.id,
            round_number=r.get('round_number', i),
            round_type=r.get('round_type'),
            mode=r.get('mode'),
            duration_minutes=r.get('duration_minutes'),
            difficulty=r.get('difficulty'),
            remarks=r.get('remarks')
        )
        db.session.add(rnd)
        db.session.flush()

        for q in r.get('questions', []):
            if not q.get('question_text'):
                db.session.rollback()
                return jsonify({'error': 'question_text is required for every question'}), 400
            question = InterviewQuestion(
                round_id=rnd.id,
                question_text=q['question_text'],
                topic=q.get('topic'),
                difficulty=q.get('difficulty')
            )
            db.session.add(question)
            db.session.flush()

            if q.get('student_answer') or q.get('reference_answer'):
                status = q.get('answer_status', 'Not Evaluated')
                if status not in VALID_ANSWER_STATUS:
                    db.session.rollback()
                    return jsonify({'error': f'answer_status must be one of {VALID_ANSWER_STATUS}'}), 400
                db.session.add(StudentAnswer(
                    question_id=question.id,
                    student_answer=q.get('student_answer'),
                    answer_status=status,
                    reference_answer=q.get('reference_answer')
                ))

    for s in data.get('skills', []):
        if not s.get('skill_name'):
            db.session.rollback()
            return jsonify({'error': 'skill_name is required for every skill'}), 400
        db.session.add(InterviewSkill(
            experience_id=exp.id,
            skill_name=s['skill_name'],
            importance_rating=s.get('importance_rating')
        ))

    for res in data.get('resources', []):
        if not res.get('resource_name'):
            db.session.rollback()
            return jsonify({'error': 'resource_name is required for every resource'}), 400
        db.session.add(PreparationResource(
            experience_id=exp.id,
            resource_type=res.get('resource_type'),
            resource_name=res['resource_name'],
            url=res.get('url'),
            description=res.get('description')
        ))

    db.session.commit()
    return jsonify({'message': 'Interview experience submitted successfully', 'id': exp.id}), 201


@interview_bp.route('/company/<int:company_id>', methods=['GET'])
def list_for_company(company_id):
    if not Company.query.get(company_id):
        return jsonify({'error': 'Company not found'}), 404

    experiences = InterviewExperience.query.filter_by(company_id=company_id).all()
    return jsonify([{
        'id': e.id,
        'job_role': e.job_role,
        'year': e.year,
        'selection_status': e.selection_status,
        'overall_difficulty': e.overall_difficulty,
        'round_count': len(e.rounds)
    } for e in experiences]), 200


@interview_bp.route('/<int:experience_id>', methods=['GET'])
def get_experience(experience_id):
    e = InterviewExperience.query.get(experience_id)
    if not e:
        return jsonify({'error': 'Experience not found'}), 404

    rounds = []
    for r in sorted(e.rounds, key=lambda x: x.round_number):
        rounds.append({
            'round_number': r.round_number,
            'round_type': r.round_type,
            'mode': r.mode,
            'duration_minutes': r.duration_minutes,
            'difficulty': r.difficulty,
            'remarks': r.remarks,
            'questions': [{
                'question_text': q.question_text,
                'topic': q.topic,
                'difficulty': q.difficulty,
                'answers': [{
                    'student_answer': a.student_answer,
                    'answer_status': a.answer_status,
                    'reference_answer': a.reference_answer
                } for a in q.answers]
            } for q in r.questions]
        })

    return jsonify({
        'id': e.id,
        'company_name': e.company.name,
        'job_role': e.job_role,
        'year': e.year,
        'selection_status': e.selection_status,
        'overall_difficulty': e.overall_difficulty,
        'preparation_summary': e.preparation_summary,
        'student_reported_selection_factors': e.selection_factors,
        'rounds': rounds,
        'skills': [{'skill_name': s.skill_name, 'importance_rating': s.importance_rating} for s in e.skills],
        'resources': [{'resource_type': r.resource_type, 'resource_name': r.resource_name,
                       'url': r.url, 'description': r.description} for r in e.resources]
    }), 200