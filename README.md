# Smart Campus Hub

**AI-Based Placement Intelligence and Automated Campus Grievance Management System**

## 1. About

Smart Campus Hub is a web application for managing campus placements and student grievances, with dedicated features for students, Coordinators, Advisors, and Chairpersons.

## 2. Features

- User authentication and role-based access
- Student registration with institutional email OTP verification
- Advisor approval workflow
- Student dashboard and placement drive management
- Placement eligibility checks and applications
- Application status updates and notifications
- Grievance submission, assignment, and tracking
- Four-working-day Advisor grievance SLA
- Automatic escalation to the active primary Chairperson
- Administrative activity logs
- Placement analytics
- Skill gap analysis and learning priorities
- Interview question intelligence

## 3. Technology Stack

- Python
- Flask
- HTML, CSS, JavaScript
- MySQL/MariaDB
- Flask-SQLAlchemy
- SQLAlchemy
- PyMySQL
- Flask-WTF
- Gunicorn
- pytest

## 4. Development Setup

### Requirements

- Python
- MySQL or MariaDB
- Git

### Installation

1. Clone the project repository.
2. Open the project directory.
3. Create a virtual environment:

   ```bash
   python -m venv .venv
   ```

4. Activate the environment.

   Windows PowerShell:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   Linux:

   ```bash
   source .venv/bin/activate
   ```

5. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

6. Create a `.env` file using `.env.example` as a template.
7. Configure the database connection and secret key.
8. Create the required database and apply the appropriate reviewed migrations.

### Start the development server

```bash
python app.py
```

The development entry point uses `db.create_all()` to create missing tables. It does not update existing database tables when models change. Use the reviewed SQL migrations for schema changes.

## 5. Environment Configuration

Important environment variables:

- `APP_ENV`
- `SECRET_KEY`
- `DATABASE_URL`
- `SESSION_COOKIE_SECURE`
- `MAIL_SERVER`
- `MAIL_PORT`
- `MAIL_USE_TLS`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `MAIL_DEFAULT_SENDER`
- `APP_BASE_URL`

Keep `.env` private. Never commit real credentials or secret keys.

For production, configure a strong secret key, MySQL/MariaDB, HTTPS, secure cookies, and valid SMTP credentials.

## 6. Database Migration Notes

Migration scripts are located in:

`database/migrations/`

Available migrations:

1. `001_grievance_sla_escalation.sql`
2. `002_password_reset_tokens.sql`
3. `003_grievance_sla_schema_repair.sql`
4. `004_academic_structure_and_account_status.sql`
5. `005_chairperson_settings.sql`
6. `006_student_registration_otp.sql`
7. `007_activity_logs.sql`

Important rules:

- Migrations 001 and 003 are alternatives for different database starting conditions. Never apply both.
- Migration 003 is a recovery script for an existing escalation table with missing grievance SLA fields.
- Apply migrations 002 and 004–007 only when their corresponding schema changes are not already present.
- Back up the database before applying migrations.
- Inspect the existing schema before deciding which migrations are required.
- Do not execute a migration more than once.
- This project does not currently maintain an automatic migration-version table.

Do not apply migrations directly to production without an approved backup and recovery plan.

## 7. Run Automated Tests

Run the complete test suite:

```bash
python -m pytest -q
```

Run Python compilation checks:

```bash
python -m compileall -q .
```

Check Git whitespace errors:

```bash
git diff --check
```

## 8. Test Status

The latest recorded automated test run passed:

- 488 tests
- 87 subtests
- 201 warnings

Run the complete test suite again after final changes and update this section if the results change.

## 9. Grievance Escalation Scheduler

The grievance escalation scheduler runs as a separate process. It is not started automatically by Flask or the WSGI application.

Script location:

`scripts/run_grievance_scheduler.py`

### Start the scheduler on Windows

Open a separate PowerShell terminal:

```powershell
cd C:\Users\bg375\smart-campus-hub
.\.venv\Scripts\Activate.ps1
python scripts\run_grievance_scheduler.py
```

### Start the scheduler on Linux

Open a separate terminal:

```bash
cd smart-campus-hub
source .venv/bin/activate
python scripts/run_grievance_scheduler.py
```

### Scheduler behavior

- Checks overdue grievances immediately after starting.
- Repeats checks every five minutes.
- Logs completed cycles and unexpected errors.
- Handles shutdown signals.

### Escalation rules

- The Advisor SLA is four working days for every priority.
- Weekends and configured public holidays are excluded.
- The SLA starts when a Coordinator assigns the grievance to an Advisor.
- An unresolved overdue grievance is escalated directly to the active primary Chairperson.
- There is no Vice-Chairperson fallback.
- If no valid active primary Chairperson is configured, the grievance remains eligible for a later scheduler run.

### Stop the scheduler

Press `Ctrl+C` in the terminal running the scheduler.

For production, run the scheduler as a separately supervised service using systemd or another process supervisor. Never start it inside Flask application startup or individual Gunicorn workers.

## 10. Production Deployment

The production WSGI entry point is:

`wsgi.py`

Gunicorn is included in the project dependencies.

Production requires:

- MySQL/MariaDB
- Secure environment configuration
- HTTPS
- Secure session cookies
- CSRF protection
- SMTP configuration
- Gunicorn behind an HTTPS reverse proxy
- A separately supervised grievance scheduler
- Database backups and recovery procedures

Refer to `DEPLOYMENT.md` for the detailed production deployment guide.

## 11. Security

- Keep `.env` and database credentials private.
- Use strong production secret keys.
- Enable HTTPS and secure session cookies.
- Keep CSRF protection enabled.
- Use role-based access control.
- Protect uploaded resumes and private student information.
- Use database constraints to prevent duplicate applications.
- Back up the database before schema changes.

## 12. Deployment Reminder

Passing automated tests does not by itself establish production readiness. Verify database migrations, email delivery, HTTPS, backups, scheduler operation, and important student and staff workflows before deployment.
