from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from datetime import datetime

from api.dependencies import get_current_student_id
from database import AsyncSessionLocal
from pdf.renderer import render_certificate_pdf
from repositories.certificate_repository import CertificateRepository

router = APIRouter(tags=["Certificates"])


class CertificateResponse(BaseModel):
    id: str
    enrollment_id: str
    student_id: str
    student_name: str
    course_id: str
    course_title: str
    completed_at: datetime
    issued_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=list[CertificateResponse])
async def list_certificates(student_id: str = Depends(get_current_student_id)):
    async with AsyncSessionLocal() as session:
        repo = CertificateRepository(session)
        return await repo.list_by_student(student_id)


@router.get("/{certificate_id}/download", response_class=Response)
async def download_certificate(
    certificate_id: str,
    student_id: str = Depends(get_current_student_id),
):
    async with AsyncSessionLocal() as session:
        repo = CertificateRepository(session)
        cert = await repo.get_by_id(certificate_id)

    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found")

    if cert.student_id != student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    pdf_bytes = render_certificate_pdf(cert)

    filename = f"certificate_{cert.course_title.replace(' ', '_')}_{cert.student_name.replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
