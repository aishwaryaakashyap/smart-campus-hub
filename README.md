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

## Run Tests
`.\.venv\Scripts\python.exe -m unittest discover -s tests -v`

## Security
- Keep `.env` and database credentials private.
- Role-based access and CSRF protection are included.
- A database unique constraint prevents duplicate applications by the same student to the same placement drive.

## Test Status
The automated test suite passed 96 tests in the current development environment. Manually verify the main workflows before deployment.
