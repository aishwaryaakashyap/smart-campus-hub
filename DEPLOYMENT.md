# Smart Campus Hub - Production Deployment Guide



## 1. Overview



Smart Campus Hub is a Flask application for placement intelligence and campus grievance management.



Technology:

- Python

- Flask

- Flask-SQLAlchemy

- MySQL/MariaDB

- PyMySQL

- Gunicorn

- Flask-WTF CSRF protection



The production WSGI entry point is `wsgi.py`.



The grievance escalation scheduler must run as a separate supervised process.



## 2. Development Setup



### Requirements



- Python

- MySQL or MariaDB

- Git



### Install the application



```bash

git clone <YOUR_REPOSITORY_URL>

cd smart-campus-hub

python -m venv .venv

```



Windows PowerShell:



```powershell

.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

```



Linux:



```bash

source .venv/bin/activate

pip install -r requirements.txt

```



### Environment configuration



Create `.env` using `.env.example` as a template.



Configure:



- `DATABASE_URL`

- `SECRET_KEY`

- `SESSION_COOKIE_SECURE`

- `MAIL_SERVER`

- `MAIL_PORT`

- `MAIL_USE_TLS`

- `MAIL_USERNAME`

- `MAIL_PASSWORD`

- `MAIL_DEFAULT_SENDER`

- `APP_BASE_URL`



Never commit `.env` or real credentials to Git.



For local development, the application can be started with:



```bash

python app.py

```



The development entry point creates missing database tables using `db.create_all()`. This does not update existing tables to match later model changes.



## 3. Production Environment



Production should use a supported Linux server with:



- Python and a virtual environment

- MySQL or MariaDB

- Gunicorn

- A reverse proxy configured for HTTPS

- A process supervisor such as systemd

- A separately supervised grievance scheduler



Do not use Flask's development server for production.



## 4. Production Environment Variables



Set the following values securely in the production environment:



```env

APP_ENV=production

SECRET_KEY=REPLACE_WITH_A_LONG_RANDOM_SECRET

DATABASE_URL=mysql+pymysql://DB_USER:DB_PASSWORD@DB_HOST/DB_NAME

SESSION_COOKIE_SECURE=1

MAIL_SERVER=YOUR_SMTP_SERVER

MAIL_PORT=587

MAIL_USE_TLS=1

MAIL_USERNAME=YOUR_SMTP_USERNAME

MAIL_PASSWORD=YOUR_SMTP_PASSWORD

MAIL_DEFAULT_SENDER=YOUR_VERIFIED_SENDER

APP_BASE_URL=https://YOUR_PUBLIC_DOMAIN

```



Replace every placeholder with the real deployment value.



Generate a strong secret key using:



```bash

python -c "import secrets; print(secrets.token_hex(32))"

```



Use a dedicated database account with only the permissions required by the application.



Protect production environment files so that only the application administrator and service account can read them.



Do not put passwords or secret keys in source code, Git commits, screenshots, or public logs.



## 5. Production Configuration Validation



The application validates production configuration when `APP_ENV=production`.



The checks include:



- Secret key length

- MySQL/MariaDB database URL

- Database host and credentials

- Public HTTPS application URL

- Secure session cookies

- HTTP-only session cookies

- SameSite cookie policy

- CSRF protection

- SMTP server and credentials

- SMTP TLS configuration



The application should not be started in production until these checks pass.



## 6. Database Setup and Migrations



Create the production database and a dedicated database user before deployment.



Back up the database before any schema migration.



The migration scripts are located in:



```text

database/migrations/

```



Important migration rules:



- Migration `001_grievance_sla_escalation.sql` is the original grievance SLA foundation.

- Migration `003_grievance_sla_schema_repair.sql` is an alternative recovery migration for a database where the escalation table already exists but the grievance SLA fields are missing.

- Never execute migrations 001 and 003 together.

- Migrations 002 and 004 through 007 are intended to be applied once, only when the corresponding schema changes are not already present.

- Inspect the existing database schema and migration history before applying anything.

- Do not rerun migrations against an already-updated database.



This project does not currently maintain an automatic migration-version table. Maintain a secure record of applied migrations for each environment.



Do not use `db.create_all()` as a replacement for schema migrations.



Never test migrations directly against production without an approved backup, a tested recovery plan, and deployment approval.



## 7. Database Backup



Create regular database backups and store them outside the application directory.



Example MySQL backup:



```bash

mysqldump -u DB_USER -p DB_NAME > smart_campus_hub_backup.sql

```



Restore example:



```bash

mysql -u DB_USER -p DB_NAME < smart_campus_hub_backup.sql

```



Replace the placeholders with the correct database account and database name.



Protect backup files because they may contain personal and institutional information.



Test restoration periodically in a separate test environment.



## 8. Gunicorn Deployment



Install the requirements in the production virtual environment.



Start Gunicorn from the project directory:



```bash

gunicorn --workers 3 --bind 127.0.0.1:8000 wsgi:app

```



This is an example command. Adjust the worker count and server resources after testing.



Gunicorn should run behind a properly configured HTTPS reverse proxy.



The reverse proxy should:

- Terminate HTTPS.

- Redirect HTTP requests to HTTPS.

- Forward requests to the local Gunicorn service.

- Avoid exposing the Gunicorn port publicly.



Do not expose the application server directly to the internet.



## 9. Grievance Escalation Scheduler



The scheduler is located at:



```text

scripts/run_grievance_scheduler.py

```



Start it as a separate process:



```bash

python scripts/run_grievance_scheduler.py

```



The scheduler:



- Runs an escalation check immediately after startup.

- Repeats the check every five minutes.

- Logs completed cycles and unexpected errors.

- Handles shutdown signals.



The scheduler must use the same production environment configuration and database as the Flask application.



Use systemd or another process supervisor to restart it after failures and start it automatically after server reboots.



Do not start the scheduler inside Flask startup or individual Gunicorn workers.



## 10. HTTPS and Application Security



Production requirements:



- Use HTTPS for all public application traffic.

- Set `SESSION_COOKIE_SECURE=1`.

- Keep HTTP-only cookies enabled.

- Keep CSRF protection enabled.

- Use a strong secret key.

- Protect database and SMTP credentials.

- Restrict database network access.

- Keep Python dependencies updated through reviewed changes.

- Restrict access to uploaded resumes and other private files.

- Do not expose debug mode in production.



The production application URL must use HTTPS.



## 11. Email Configuration



The application uses SMTP for email-related workflows, including student registration OTP and password reset.



Before production launch:



1. Configure a valid SMTP server.

2. Configure the SMTP port and TLS.

3. Configure the sender address.

4. Store SMTP credentials securely.

5. Test registration OTP delivery.

6. Test password reset email delivery.

7. Check application logs if delivery fails.



Do not use a personal email password where the provider requires an application password or another approved authentication method.



## 12. Monitoring and Recovery



Monitor:



- Gunicorn process health

- Grievance scheduler process health

- Database availability

- SMTP delivery failures

- Application errors

- Disk space

- Backup completion

- Scheduler escalation logs



After a failure:



1. Check application and scheduler logs.

2. Confirm database availability.

3. Confirm environment configuration.

4. Restore service through the process supervisor.

5. Verify login and important application workflows.

6. Confirm the scheduler resumes correctly.



Keep database backups and recovery procedures separate from the application server.



## 13. Pre-Deployment Checklist



- [ ] Production database created.

- [ ] Database account configured with appropriate permissions.

- [ ] Existing schema inspected.

- [ ] Required migrations identified and reviewed.

- [ ] Database backup completed.

- [ ] Production environment variables configured.

- [ ] Strong secret key configured.

- [ ] HTTPS configured.

- [ ] Secure cookies enabled.

- [ ] CSRF protection enabled.

- [ ] SMTP tested.

- [ ] Gunicorn startup tested.

- [ ] Grievance scheduler startup tested separately.

- [ ] Application logs monitored.

- [ ] Backup restoration tested.

- [ ] Main student and staff workflows manually tested.



## 14. Testing



Run automated tests before deployment:



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



The development test suite most recently passed 488 tests and 87 subtests. Repeat the full suite after the final project changes and update this count if it changes.



## 15. Important Production Warning



Passing automated tests does not by itself establish production readiness.



Production deployment requires a verified database migration plan, secure infrastructure, HTTPS, working email. Production launch should proceed only after these requirements and the pre-deployment checklist have been verified.
