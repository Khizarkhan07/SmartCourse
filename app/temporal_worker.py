"""
Temporal Worker — runs workflows and activities.

The worker is a long-running process that:
1. Connects to the Temporal server
2. Registers which workflows and activities it can handle
3. Listens on a task queue for work
4. Executes tasks as they arrive

Run this with:
    python -m app.temporal_worker

Keep it running alongside FastAPI.
"""

import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

from app.workflows.hello_workflow import HelloWorldWorkflow, say_hello, send_welcome_email

# Task queue name — FastAPI will use this same name when starting workflows
TASK_QUEUE = "smartcourse-queue"


async def main():
    # Connect to the Temporal server
    client = await Client.connect("localhost:7233")

    print(f"✅ Connected to Temporal server")
    print(f"📋 Listening on task queue: '{TASK_QUEUE}'")
    print(f"🔄 Registered workflows: HelloWorldWorkflow")
    print(f"⚡ Registered activities: say_hello, send_welcome_email")
    print(f"\nWaiting for tasks... (Ctrl+C to stop)\n")

    # Start the worker
    # workflows = list of workflow classes this worker handles
    # activities = list of activity functions this worker handles
    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[HelloWorldWorkflow],
        activities=[say_hello, send_welcome_email],
    ):
        await asyncio.Future()  # run forever until Ctrl+C


if __name__ == "__main__":
    asyncio.run(main())
