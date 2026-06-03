import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from temporalio.client import WorkflowFailureError
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from app.database import get_db
from app.models import Course
from app.temporal_client import TASK_QUEUE, get_temporal_client
from app.schemas.course import CourseResponse
from app.auth import require_role
from app.models.user import User, UserRole
from app.workflows.publish_course_workflow import (
    ArchiveCourseWorkflow,
    ArchiveCourseWorkflowInput,
    PublishCourseWorkflow,
    PublishCourseWorkflowInput,
)

router = APIRouter(prefix="/courses", tags=["Publishing"])


@router.post("/{course_id}/publish", response_model=CourseResponse)
async def publish_course(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Publish a course (draft → published).

    Validates:
    - Course has a description
    - Course has at least one lesson
    - Caller is the course owner
    """
    workflow_id = f"publish-{str(course_id)[:8]}"
    client = await get_temporal_client()

    try:
        await client.execute_workflow(
            PublishCourseWorkflow.run,
            PublishCourseWorkflowInput(
                course_id=str(course_id),
                instructor_id=str(current_user.id),
            ),
            id=workflow_id,
            task_queue=TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except WorkflowAlreadyStartedError:
        handle = client.get_workflow_handle(workflow_id)
        await handle.result()
    except WorkflowFailureError as e:
        inner = getattr(e.cause, "cause", e.cause)
        message = getattr(inner, "message", str(inner))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    result = await db.execute(
        select(Course)
        .options(selectinload(Course.instructor))
        .where(Course.id == course_id)
    )
    return result.scalar_one()


@router.patch("/{course_id}/archive", response_model=CourseResponse)
async def archive_course(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Archive a course (published → archived).

    Archived courses are no longer visible to new students.
    Existing enrollments are unaffected.
    """
    workflow_id = f"archive-{str(course_id)[:8]}"
    client = await get_temporal_client()

    try:
        await client.execute_workflow(
            ArchiveCourseWorkflow.run,
            ArchiveCourseWorkflowInput(
                course_id=str(course_id),
                instructor_id=str(current_user.id),
            ),
            id=workflow_id,
            task_queue=TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except WorkflowAlreadyStartedError:
        handle = client.get_workflow_handle(workflow_id)
        await handle.result()
    except WorkflowFailureError as e:
        inner = getattr(e.cause, "cause", e.cause)
        message = getattr(inner, "message", str(inner))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    result = await db.execute(
        select(Course)
        .options(selectinload(Course.instructor))
        .where(Course.id == course_id)
    )
    return result.scalar_one()
