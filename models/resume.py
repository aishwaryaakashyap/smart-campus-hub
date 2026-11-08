from datetime import datetime, timezone

from extensions import db


def utcnow_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Resume(db.Model):
    __tablename__ = "resumes"

    id = db.Column(db.Integer, primary_key=True)

    # Each student can have one current resume.
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        unique=True
    )

    # Keep the original name for display and a private generated name for storage.
    original_filename = db.Column(
        db.String(255),
        nullable=False
    )

    stored_filename = db.Column(
        db.String(255),
        nullable=False,
        unique=True
    )

    extracted_text = db.Column(
        db.Text,
        nullable=False
    )

    uploaded_at = db.Column(
        db.DateTime,
        default=utcnow_naive,
        nullable=False
    )

    student = db.relationship(
        "Student",
        backref=db.backref("resume", uselist=False)
    )

    def __repr__(self):
        return f"<Resume student_id={self.student_id}>"
