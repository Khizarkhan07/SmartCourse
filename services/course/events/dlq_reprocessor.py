from smartcourse_kafka.dlq_reprocessor_base import BaseDLQReprocessor
from events.profile_updater import upsert_profile


class UserProfileDLQReprocessor(BaseDLQReprocessor):
    DLQ_TOPIC    = "user.profile_updated.dlq"
    FAILED_TOPIC = "user.profile_updated.failed"
    GROUP_ID     = "course-service-user-profile-dlq-reprocessor"

    def _process(self, payload: dict) -> None:
        upsert_profile(payload)
