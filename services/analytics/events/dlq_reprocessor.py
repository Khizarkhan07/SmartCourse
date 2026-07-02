from smartcourse_kafka.dlq_reprocessor_base import BaseDLQReprocessor
from events.enrollment_fact_handler import create_enrollment_fact, complete_enrollment_fact
from events.course_fact_handler import upsert_course_fact


class EnrollmentCreatedDLQReprocessor(BaseDLQReprocessor):
    DLQ_TOPIC    = "enrollment.created.dlq"
    FAILED_TOPIC = "enrollment.created.failed"
    GROUP_ID     = "analytics-service-enrollment-created-dlq-reprocessor"

    def _process(self, payload: dict) -> None:
        create_enrollment_fact(payload)


class EnrollmentCompletedDLQReprocessor(BaseDLQReprocessor):
    DLQ_TOPIC    = "enrollment.completed.dlq"
    FAILED_TOPIC = "enrollment.completed.failed"
    GROUP_ID     = "analytics-service-enrollment-completed-dlq-reprocessor"

    def _process(self, payload: dict) -> None:
        complete_enrollment_fact(payload)


class CoursePublishedDLQReprocessor(BaseDLQReprocessor):
    DLQ_TOPIC    = "course.published.dlq"
    FAILED_TOPIC = "course.published.failed"
    GROUP_ID     = "analytics-service-course-published-dlq-reprocessor"

    def _process(self, payload: dict) -> None:
        upsert_course_fact(payload)
