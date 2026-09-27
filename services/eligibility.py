def check_eligibility(student, drive):
    """
    Compares a student's profile against a placement drive's requirements.
    Returns (is_eligible: bool, reasons: list of strings)
    """
    reasons = []

    if drive.min_cgpa is not None:
        if student.cgpa is None or student.cgpa < drive.min_cgpa:
            reasons.append(f'CGPA requirement not met (required: {drive.min_cgpa}, yours: {student.cgpa})')

    if drive.eligible_branches:
        allowed_branches = [b.strip().upper() for b in drive.eligible_branches.split(',')]
        student_branch = (student.branch or '').strip().upper()
        if student_branch not in allowed_branches:
            reasons.append(f'Branch not eligible (allowed: {drive.eligible_branches}, yours: {student.branch})')

    if drive.eligible_semester is not None:
        if student.semester != drive.eligible_semester:
            reasons.append(f'Semester requirement not met (required: {drive.eligible_semester}, yours: {student.semester})')

    is_eligible = len(reasons) == 0
    return is_eligible, reasons