from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.certificate import Certificate


class CertificateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_enrollment_id(self, enrollment_id: str) -> Certificate | None:
        result = await self.session.execute(
            select(Certificate).where(Certificate.enrollment_id == enrollment_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, certificate_id: str) -> Certificate | None:
        result = await self.session.execute(
            select(Certificate).where(Certificate.id == certificate_id)
        )
        return result.scalar_one_or_none()

    async def list_by_student(self, student_id: str) -> list[Certificate]:
        result = await self.session.execute(
            select(Certificate).where(Certificate.student_id == student_id)
        )
        return list(result.scalars().all())

    async def create(self, certificate: Certificate) -> Certificate:
        self.session.add(certificate)
        await self.session.commit()
        await self.session.refresh(certificate)
        return certificate
