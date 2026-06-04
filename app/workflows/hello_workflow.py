"""
Chunk 11: Activities with Retry Policies

Key concepts added:
- RetryPolicy: configure how many times and how often to retry
- Flaky activity: simulates a real-world failure (email server down, etc.)
- start_to_close_timeout: max time the activity is allowed to run
"""

from datetime import timedelta
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from app.temporal_client import NOTIFICATION_TASK_QUEUE


# ─────────────────────────────────────────
# ACTIVITY 1: Simple (from Chunk 10)
# ─────────────────────────────────────────

@activity.defn
async def say_hello(name: str) -> str:
    """Simple activity — always succeeds."""
    print(f"[Activity] Running say_hello for: {name}")
    return f"Hello, {name}! Welcome to SmartCourse."


# ─────────────────────────────────────────
# ACTIVITY 2: Flaky — fails first 2 times
# ─────────────────────────────────────────

# This counter simulates a temporarily unavailable service
_attempt_count = 0


@activity.defn
async def send_welcome_email(email: str) -> str:
    """
    Simulates sending a welcome email.

    Fails on the first 2 attempts (like an email server being temporarily down),
    then succeeds on the 3rd.

    Temporal will automatically retry this based on the RetryPolicy
    configured in the workflow.
    """
    global _attempt_count
    _attempt_count += 1

    print(f"[Activity] send_welcome_email attempt #{_attempt_count} for {email}")

    if _attempt_count < 3:
        print(f"[Activity] ❌ Email server unavailable — attempt {_attempt_count} failed")
        raise Exception(f"Email server unavailable (simulated failure #{_attempt_count})")

    print(f"[Activity] ✅ Email sent successfully on attempt #{_attempt_count}")
    _attempt_count = 0  # reset for next run
    return f"Welcome email sent to {email}"


# ─────────────────────────────────────────
# WORKFLOW: orchestrates both activities
# ─────────────────────────────────────────

@workflow.defn
class HelloWorldWorkflow:
    """
    Updated workflow that calls 2 activities:
    1. say_hello — always succeeds
    2. send_welcome_email — flaky, retried automatically by Temporal
    """

    @workflow.run
    async def run(self, name: str) -> dict:
        # Activity 1: always works
        greeting = await workflow.execute_activity(
            say_hello,
            name,
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Activity 2: flaky — will fail 2 times, then succeed
        # RetryPolicy tells Temporal how to handle failures
        email_result = await workflow.execute_activity(
            send_welcome_email,
            f"{name.lower()}@example.com",
            start_to_close_timeout=timedelta(seconds=30),
            task_queue=NOTIFICATION_TASK_QUEUE,
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),   # wait 1s before first retry
                backoff_coefficient=2.0,                 # double wait each retry: 1s, 2s, 4s...
                maximum_attempts=5,                      # give up after 5 total attempts
            ),
        )

        return {
            "greeting": greeting,
            "email": email_result,
        }

