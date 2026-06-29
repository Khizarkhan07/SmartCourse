import uuid

import httpx
from opentelemetry.propagate import inject

from config import settings
from core.exceptions import NotFoundError, ValidationError
from core.logging import get_logger

logger = get_logger(__name__)


class CourseClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict:
        headers: dict = {}
        inject(headers)  # injects traceparent/tracestate for Jaeger cross-service linking
        return headers

    async def check_course_published(self, course_id: uuid.UUID) -> None:
        """Raises NotFoundError or ValidationError if the course can't be enrolled in."""
        url = f"{self._base_url}/courses/{course_id}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self._headers(), timeout=5.0)
        except httpx.RequestError as exc:
            logger.warning("course-service unreachable", url=url, error=str(exc))
            raise ValidationError("Course service is unavailable") from exc

        if resp.status_code == 404:
            raise NotFoundError(f"Course {course_id} not found")
        resp.raise_for_status()

        data = resp.json()
        if data.get("status") != "published":
            raise ValidationError(
                f"Course is not published (status: {data.get('status')})"
            )

    async def get_lesson_course(self, lesson_id: uuid.UUID) -> uuid.UUID:
        """Returns the course_id that owns this lesson. Raises NotFoundError if absent."""
        url = f"{self._base_url}/internal/lessons/{lesson_id}"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self._headers(), timeout=5.0)
        except httpx.RequestError as exc:
            logger.warning("course-service unreachable", url=url, error=str(exc))
            raise NotFoundError("Course service is unavailable") from exc

        if resp.status_code == 404:
            raise NotFoundError(f"Lesson {lesson_id} not found")
        resp.raise_for_status()
        return uuid.UUID(resp.json()["course_id"])

    async def count_course_lessons(self, course_id: uuid.UUID) -> int:
        """Returns total lesson count for progress calculation. Returns 0 on failure (graceful)."""
        url = f"{self._base_url}/internal/courses/{course_id}/lesson-count"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=self._headers(), timeout=5.0)
        except httpx.RequestError as exc:
            logger.warning("course-service unreachable", url=url, error=str(exc))
            return 0
        if resp.status_code != 200:
            return 0
        return int(resp.json().get("total_lessons", 0))


def get_course_client() -> CourseClient:
    return CourseClient(settings.COURSE_SERVICE_URL)
