"""Temporal workflow orchestration infrastructure.

This module provides:
- Temporal client connection and caching
- Task queue constants for workflow routing
- Worker setup for activity execution
"""

from app.infrastructure.temporal.client import (
    get_temporal_client,
    ENROLLMENT_TASK_QUEUE,
    COURSE_TASK_QUEUE,
    NOTIFICATION_TASK_QUEUE,
)

__all__ = [
    "get_temporal_client",
    "ENROLLMENT_TASK_QUEUE",
    "COURSE_TASK_QUEUE",
    "NOTIFICATION_TASK_QUEUE",
]
