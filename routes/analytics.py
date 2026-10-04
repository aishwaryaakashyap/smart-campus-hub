from flask import Blueprint, jsonify, session, render_template
from models import Company, PlacementDrive, Application, Student, InterviewExperience, InterviewRound, InterviewQuestion, InterviewSkill, StudentSkill, Grievance, GrievanceCategory

analytics_bp = Blueprint('analytics', __name__)


def require_coordinator():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    if session.get('role') != 'coordinator':
        return jsonify({'error': 'Only coordinators can view placement analytics'}), 403

    return None



@analytics_bp.route('/placement', methods=['GET'])
def placement_analytics():
    auth_error = require_coordinator()
    if auth_error:
        return auth_error

    total_students = Student.query.count()
    total_companies = Company.query.count()
    total_drives = PlacementDrive.query.count()

    open_drives = PlacementDrive.query.filter_by(status='Open').count()
    closed_drives = PlacementDrive.query.filter_by(status='Closed').count()

    total_applications = Application.query.count()

    status_counts = {}
    statuses = [
        'Applied',
        'Under Review',
        'Shortlisted',
        'Interview',
        'Selected',
        'Not Selected',
        'Withdrawn'
    ]

    for status in statuses:
        status_counts[status] = Application.query.filter_by(status=status).count()

    selected_count = status_counts['Selected']

    company_analytics = []

    for company in Company.query.all():
        company_drives = PlacementDrive.query.filter_by(company_id=company.id).all()
        drive_ids = [drive.id for drive in company_drives]

        company_applications = (
            Application.query.filter(Application.drive_id.in_(drive_ids)).all()
            if drive_ids
            else []
        )

        company_selected = sum(
            1 for application in company_applications
            if application.status == 'Selected'
        )

        company_selection_rate = (
            round((company_selected / len(company_applications)) * 100, 2)
            if company_applications
            else 0
        )

        company_analytics.append({
            'company_id': company.id,
            'company_name': company.name,
            'drive_count': len(company_drives),
            'application_count': len(company_applications),
            'selected_count': company_selected,
            'selection_rate_percent': company_selection_rate
        })

    selection_rate = (
        round((selected_count / total_applications) * 100, 2)
        if total_applications > 0
        else 0
    )

    return jsonify({
        'total_students': total_students,
        'total_companies': total_companies,
        'total_drives': total_drives,
        'open_drives': open_drives,
        'closed_drives': closed_drives,
        'total_applications': total_applications,
        'application_status_counts': status_counts,
        'selected_count': selected_count,
        'selection_rate_percent': selection_rate,
        'company_analytics': company_analytics
    }), 200


@analytics_bp.route('/dashboard', methods=['GET'])
def analytics_dashboard():
    return render_template('analytics.html')




@analytics_bp.route('/advanced', methods=['GET'])
def advanced_analytics():
    auth_error = require_coordinator()
    if auth_error:
        return auth_error

    # Interview question frequency
    question_counts = {}
    for question in InterviewQuestion.query.all():
        question_text = (question.question_text or '').strip()
        if question_text:
            key = question_text.lower()
            question_counts[key] = question_counts.get(key, 0) + 1

    frequently_asked_questions = [
        {'question': question, 'times_mentioned': count}
        for question, count in sorted(
            question_counts.items(),
            key=lambda item: item[1],
            reverse=True
        )[:10]
    ]

    # Interview skill frequency
    interview_skill_counts = {}
    for skill in InterviewSkill.query.all():
        skill_name = (skill.skill_name or '').strip()
        if skill_name:
            key = skill_name.title()
            interview_skill_counts[key] = interview_skill_counts.get(key, 0) + 1

    frequently_required_skills = [
        {'skill': skill, 'times_mentioned': count}
        for skill, count in sorted(
            interview_skill_counts.items(),
            key=lambda item: item[1],
            reverse=True
        )[:10]
    ]

    # Interview round distribution
    round_counts = {}
    for interview_round in InterviewRound.query.all():
        round_type = (interview_round.round_type or '').strip()
        if round_type:
            round_counts[round_type] = round_counts.get(round_type, 0) + 1

    # Interview difficulty distribution
    difficulty_counts = {
        'Easy': 0,
        'Medium': 0,
        'Hard': 0
    }

    for experience in InterviewExperience.query.all():
        difficulty = (experience.overall_difficulty or '').strip()
        if difficulty in difficulty_counts:
            difficulty_counts[difficulty] += 1

    # Student skill proficiency distribution
    proficiency_counts = {
        'Beginner': 0,
        'Intermediate': 0,
        'Advanced': 0
    }

    skill_counts = {}

    for student_skill in StudentSkill.query.all():
        proficiency = (student_skill.proficiency or '').strip()
        if proficiency in proficiency_counts:
            proficiency_counts[proficiency] += 1

        if student_skill.skill:
            skill_name = student_skill.skill.name
            skill_counts[skill_name] = skill_counts.get(skill_name, 0) + 1

    # Grievance analytics
    grievance_category_counts = {}
    grievance_priority_counts = {}
    grievance_status_counts = {}
    grievance_location_counts = {}

    assigned_grievances = 0
    unassigned_grievances = 0

    for grievance in Grievance.query.all():
        if grievance.category:
            category_name = grievance.category.name
            grievance_category_counts[category_name] = (
                grievance_category_counts.get(category_name, 0) + 1
            )

        priority = (grievance.priority or 'Unknown').strip()
        grievance_priority_counts[priority] = (
            grievance_priority_counts.get(priority, 0) + 1
        )

        status = (grievance.status or 'Unknown').strip()
        grievance_status_counts[status] = (
            grievance_status_counts.get(status, 0) + 1
        )

        location = (grievance.location or 'Not specified').strip()
        grievance_location_counts[location] = (
            grievance_location_counts.get(location, 0) + 1
        )

        if grievance.assigned_to:
            assigned_grievances += 1
        else:
            unassigned_grievances += 1

    # Observed placement-readiness statistics.
    # This is intentionally rule-based and descriptive, not an ML prediction.
    students_with_cgpa = [
        student for student in Student.query.all()
        if student.cgpa is not None
    ]

    readiness_distribution = {
        'Higher CGPA group': 0,
        'Other CGPA group': 0
    }

    if students_with_cgpa:
        cgpas = [student.cgpa for student in students_with_cgpa]
        average_cgpa = sum(cgpas) / len(cgpas)

        for student in students_with_cgpa:
            if student.cgpa >= average_cgpa:
                readiness_distribution['Higher CGPA group'] += 1
            else:
                readiness_distribution['Other CGPA group'] += 1
    else:
        average_cgpa = None

    return jsonify({
        'interview': {
            'total_experiences': InterviewExperience.query.count(),
            'total_rounds': InterviewRound.query.count(),
            'total_questions': InterviewQuestion.query.count(),
            'total_interview_skills': InterviewSkill.query.count(),
            'frequently_asked_questions': frequently_asked_questions,
            'frequently_required_skills': frequently_required_skills,
            'round_type_distribution': round_counts,
            'difficulty_distribution': difficulty_counts
        },
        'student_skills': {
            'total_student_skills': StudentSkill.query.count(),
            'proficiency_distribution': proficiency_counts,
            'skill_distribution': skill_counts
        },
        'grievances': {
            'total_grievances': Grievance.query.count(),
            'category_distribution': grievance_category_counts,
            'priority_distribution': grievance_priority_counts,
            'status_distribution': grievance_status_counts,
            'location_distribution': grievance_location_counts,
            'assigned_count': assigned_grievances,
            'unassigned_count': unassigned_grievances
        },
        'placement_readiness': {
            'students_with_cgpa': len(students_with_cgpa),
            'average_cgpa': round(average_cgpa, 2) if average_cgpa is not None else None,
            'observed_cgpa_group_distribution': readiness_distribution,
            'note': 'Descriptive statistic based on available student CGPA data; not an ML prediction.'
        }
    }), 200
