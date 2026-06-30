from datetime import datetime, timezone

from core.logging import get_logger
from database import SyncSessionLocal
from models.course_fact import CourseFact
from repositories.course_fact_repository import SyncCourseFactRepository

logger = get_logger(__name__)


def upsert_course_fact(payload: dict) -> None:
    """Idempotent: upserts a course_fact row."""
    try:
        published_at = datetime.fromisoformat(payload.get("published_at", ""))
    except (ValueError, TypeError):
        published_at = datetime.now(timezone.utc)

    fact = CourseFact(
        course_id=payload["course_id"],
        title=payload["title"],
        instructor_id=payload["instructor_id"],
        status=payload.get("status", "published"),
        published_at=published_at,
        updated_at=datetime.now(timezone.utc),
    )
    with SyncSessionLocal() as session:
        repo = SyncCourseFactRepository(session)
        repo.upsert(fact)
        logger.info("course_fact upserted", course_id=fact.course_id, title=fact.title)
