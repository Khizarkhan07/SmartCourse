import uuid

from sqlalchemy.orm import Session

from models.instructor_profile import InstructorProfile
from datetime import datetime, timezone


class SyncInstructorProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, user_id: str, name: str, email: str, is_active: bool) -> None:
        profile = self.session.get(InstructorProfile, uuid.UUID(user_id))
        if profile:
            profile.name = name
            profile.email = email
            profile.is_active = is_active
            profile.updated_at = datetime.now(timezone.utc)
        else:
            profile = InstructorProfile(
                id=uuid.UUID(user_id),
                name=name,
                email=email,
                is_active=is_active,
            )
            self.session.add(profile)
        self.session.commit()
