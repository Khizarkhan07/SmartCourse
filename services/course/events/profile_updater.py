from core.logging import get_logger
from database import SyncSessionLocal
from repositories.instructor_profile_repository import SyncInstructorProfileRepository

logger = get_logger(__name__)


def upsert_profile(payload: dict) -> None:
    """Idempotent: upserts the instructor profile denormalization in course-service.

    Called by both the main consumer and the DLQ reprocessor so logic is never
    duplicated. Safe to call multiple times — the repo uses an upsert internally.
    """
    with SyncSessionLocal() as session:
        repo = SyncInstructorProfileRepository(session)
        repo.upsert(
            user_id=payload["user_id"],
            name=payload["name"],
            email=payload["email"],
            is_active=payload["is_active"],
        )
        logger.info("instructor_profile upserted", user_id=payload["user_id"])
