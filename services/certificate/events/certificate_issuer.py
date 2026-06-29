from datetime import datetime, timezone

from core.logging import get_logger
from database import AsyncSessionLocal
from models.certificate import Certificate
from repositories.certificate_repository import CertificateRepository

logger = get_logger(__name__)


async def issue_certificate(payload: dict) -> None:
    """Idempotent: creates a certificate row for the given completion payload.

    Safe to call multiple times for the same enrollment_id — the second call
    is a no-op guarded by the UNIQUE constraint on enrollment_id.
    """
    enrollment_id = payload["enrollment_id"]

    async with AsyncSessionLocal() as session:
        repo = CertificateRepository(session)

        existing = await repo.get_by_enrollment_id(enrollment_id)
        if existing:
            logger.info(
                "certificate already exists, skipping",
                enrollment_id=enrollment_id,
                certificate_id=existing.id,
            )
            return

        completed_at_str = payload.get("completed_at", "")
        try:
            completed_at = datetime.fromisoformat(completed_at_str)
        except (ValueError, TypeError):
            completed_at = datetime.now(timezone.utc)

        cert = Certificate(
            enrollment_id=enrollment_id,
            student_id=payload["student_id"],
            student_name=payload["student_name"],
            course_id=payload["course_id"],
            course_title=payload["course_title"],
            completed_at=completed_at,
        )
        await repo.create(cert)
        logger.info(
            "certificate issued",
            certificate_id=cert.id,
            enrollment_id=enrollment_id,
            student_id=cert.student_id,
        )
