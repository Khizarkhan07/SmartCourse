from datetime import datetime, timezone

from core.logging import get_logger
from database import SyncSessionLocal
from models.enrollment_fact import EnrollmentFact
from repositories.enrollment_fact_repository import SyncEnrollmentFactRepository

logger = get_logger(__name__)


def create_enrollment_fact(payload: dict) -> None:
    """Idempotent: creates an enrollment_fact row if one does not already exist."""
    enrollment_id = payload["enrollment_id"]
    with SyncSessionLocal() as session:
        repo = SyncEnrollmentFactRepository(session)
        if repo.get_by_enrollment_id(enrollment_id):
            logger.info("enrollment_fact already exists, skipping", enrollment_id=enrollment_id)
            return

        try:
            enrolled_at = datetime.fromisoformat(payload.get("enrolled_at", ""))
        except (ValueError, TypeError):
            enrolled_at = datetime.now(timezone.utc)

        fact = EnrollmentFact(
            enrollment_id=enrollment_id,
            student_id=payload["student_id"],
            course_id=payload["course_id"],
            course_title="",
            status="active",
            enrolled_at=enrolled_at,
            completed_at=None,
            updated_at=datetime.now(timezone.utc),
        )
        repo.create(fact)
        logger.info("enrollment_fact created", enrollment_id=enrollment_id)


def complete_enrollment_fact(payload: dict) -> None:
    """Idempotent: marks an existing enrollment_fact as completed."""
    enrollment_id = payload["enrollment_id"]
    try:
        completed_at = datetime.fromisoformat(payload.get("completed_at", ""))
    except (ValueError, TypeError):
        completed_at = datetime.now(timezone.utc)

    with SyncSessionLocal() as session:
        repo = SyncEnrollmentFactRepository(session)
        updated = repo.mark_completed(
            enrollment_id=enrollment_id,
            completed_at=completed_at,
            course_title=payload.get("course_title", ""),
        )
        if updated:
            logger.info("enrollment_fact marked completed", enrollment_id=enrollment_id)
        else:
            logger.warning(
                "enrollment_fact not found for completion — fact may arrive out of order",
                enrollment_id=enrollment_id,
            )
