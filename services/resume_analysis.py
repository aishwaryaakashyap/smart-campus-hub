import re
from pypdf import PdfReader
from services.skill_gap import _find_skill_match, analyze_skill_gap


class ResumeProcessingError(ValueError):
    """Raised when a resume PDF cannot be processed."""


def extract_pdf_text(file_stream):
    """Extract and normalize text from an unlocked PDF."""
    if not callable(getattr(file_stream, "read", None)) or not callable(
        getattr(file_stream, "seek", None)
    ):
        raise ResumeProcessingError("A readable PDF file is required.")

    try:
        file_stream.seek(0)
        signature = file_stream.read(5)
        file_stream.seek(0)
    except Exception as exc:
        raise ResumeProcessingError("Unable to read the uploaded file.") from exc

    if signature != b"%PDF-":
        raise ResumeProcessingError("The uploaded file is not a valid PDF.")

    try:
        reader = PdfReader(file_stream, strict=False)

        if reader.is_encrypted:
            raise ResumeProcessingError(
                "Password-protected PDFs are not supported. Upload an unlocked PDF."
            )

        pages = reader.pages

        if len(pages) == 0:
            raise ResumeProcessingError("The PDF does not contain any pages.")

        extracted_pages = []

        for page_number, page in enumerate(pages, start=1):
            try:
                page_text = page.extract_text()
            except Exception as exc:
                raise ResumeProcessingError(
                    f"Unable to extract text from PDF page {page_number}."
                ) from exc

            if isinstance(page_text, str) and page_text.strip():
                extracted_pages.append(page_text)

        raw_text = "\n".join(extracted_pages)
        raw_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw_text)

        normalized_lines = [
            re.sub(r"[ \t]+", " ", line).strip()
            for line in raw_text.replace("\r", "\n").splitlines()
        ]

        cleaned_text = "\n".join(
            line for line in normalized_lines if line
        ).strip()

        if not cleaned_text:
            raise ResumeProcessingError(
                "No selectable text was found. Scanned/image-only PDFs are not supported."
            )

        return cleaned_text

    except ResumeProcessingError:
        raise
    except Exception as exc:
        raise ResumeProcessingError(
            "Unable to read the PDF. The file may be damaged or unsupported."
        ) from exc
    finally:
        try:
            file_stream.seek(0)
        except Exception:
            pass


def extract_resume_skills(resume_text, available_skills):
    """Extract canonical skill names using the existing skill-gap matcher.

    Does not modify the student's registered skills.
    """
    if not isinstance(resume_text, str) or not resume_text.strip():
        raise ResumeProcessingError(
            "Resume text is required for skill extraction."
        )

    if not isinstance(available_skills, (list, tuple)):
        raise ResumeProcessingError(
            "The available skill catalogue must be a list."
        )

    extracted = []
    seen = set()

    for item in available_skills:
        if isinstance(item, dict):
            name = item.get("name")
        else:
            name = getattr(item, "name", None)

        if not isinstance(name, str) or not name.strip():
            continue

        canonical_name = name.strip()
        normalized_name = canonical_name.casefold()

        if normalized_name in seen:
            continue

        if _find_skill_match(canonical_name, resume_text):
            extracted.append(canonical_name)
            seen.add(normalized_name)

    return extracted


def analyze_resume_job_match(resume_text, job_description, available_skills):
    """Compare resume-extracted skills with a job description.

    The percentage measures catalogue skill coverage, not an ATS score.
    """
    if not isinstance(resume_text, str) or not resume_text.strip():
        raise ResumeProcessingError(
            "Resume text is required for job matching."
        )

    if job_description is not None and not isinstance(job_description, str):
        raise ResumeProcessingError("Job description must be text.")

    if not isinstance(available_skills, (list, tuple)):
        raise ResumeProcessingError(
            "The available skill catalogue must be a list."
        )

    catalogue = []

    for item in available_skills:
        if isinstance(item, dict):
            name = item.get("name")
        else:
            name = getattr(item, "name", None)

        if isinstance(name, str) and name.strip():
            catalogue.append({"name": name.strip()})

    resume_skills = extract_resume_skills(resume_text, catalogue)

    result = analyze_skill_gap(
        job_description or "",
        [{"skill_name": name, "proficiency": None}
         for name in resume_skills],
        catalogue,
    )

    return {
        "resume_skills": resume_skills,
        "required_skills": result["required_skills"],
        "matched_skills": result["matched_skills"],
        "missing_skills": result["missing_skills"],
        "total_required_skills": result["total_required_skills"],
        "match_percentage": result["match_percentage"],
        "learning_priorities": result["learning_priorities"],
        "method": (
            "Rule-based keyword and alias matching against the existing "
            "skill catalogue."
        ),
        "match_note": (
            "The percentage measures matched catalogue skills among the "
            "skills detected in the job description. It is not an ATS score "
            "or semantic similarity prediction."
        ),
    }
