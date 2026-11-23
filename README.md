# Smart Campus Hub

AI-Based Placement Intelligence and Automated Campus Grievance Management System

## About
A web application for managing campus placements and student grievances, with tools for coordinators and students.

## Features
- User authentication and role-based access
- Student dashboard and placement drive management
- Placement eligibility checks and applications
- Application status updates and notifications
- Grievance submission, assignment, and tracking
- Placement analytics
- Skill gap analysis and learning priorities
- Interview question intelligence

## Technology Stack
- Python and Flask
- HTML, CSS, JavaScript
- MySQL
- Flask-SQLAlchemy and SQLAlchemy
- PyMySQL
- Python unittest

## Setup
1. Install Python and MySQL.
2. Create a virtual environment: `python -m venv .venv`
3. Activate it: `.\.venv\Scripts\Activate.ps1`
4. Install packages: `pip install -r requirements.txt`
5. Create `.env` based on `.env.example`.
6. Set `DATABASE_URL` and a secure `SECRET_KEY`.
7. Create the configured database and initialize the application tables.
8. Run the application: `python app.py`

## Database Migration Notes

- Migration `001_grievance_sla_escalation.sql` is the original foundation migration. It adds SLA fields and creates `grievance_escalations`.
- Migration `003_grievance_sla_schema_repair.sql` is a recovery script for databases where `grievance_escalations` already exists but the SLA fields are missing.
- These two scripts are alternatives for different starting schemas. Do not run both on the same database.
- Inspect the existing database schema before applying migrations. This project does not currently maintain a migration-version table.

## Run Tests
`python -m pytest -q`

## Security
- Keep `.env` and database credentials private.
- Role-based access and CSRF protection are included.
- A database unique constraint prevents duplicate applications by the same student to the same placement drive.

## Test Status
The automated test suite passed 478 tests and 87 subtests in the current development environment. Manually verify the main workflows before deployment.

## Grievance Escalation Scheduler

The grievance escalation scheduler runs as a separate process. It is not
started automatically by Flask or the WSGI application.

### Start the scheduler

1. Open a separate terminal while the application and database are available.
2. Navigate to the project directory:
   `cd ~/smart-campus-hub`
3. Activate the virtual environment:
   `source venv/bin/activate`
4. Start the scheduler:
   `python scripts/run_grievance_scheduler.py`

The scheduler checks for overdue grievances immediately when it starts and
then repeats the check every five minutes.

### Stop the scheduler

Press `Ctrl+C` in the terminal running the scheduler. It will finish the
current cycle and shut down.

### Escalation rules

- The Advisor SLA is fixed at four working days for every priority, excluding weekends and configured public holidays.
- The SLA starts when a Coordinator assigns the grievance to an Advisor.
- An unresolved overdue grievance is escalated directly to the active primary
  Chairperson.
- If no valid active primary Chairperson is configured, the grievance remains
  eligible for a later scheduler run.
- The scheduler logs completed cycles and unexpected errors to its terminal.

For production deployment, run this scheduler as a separately supervised
service (for example, using systemd or Supervisor). Do not start it inside
Flask application startup or individual Gunicorn workers.
