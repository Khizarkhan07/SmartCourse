"""
Trigger script — starts a HelloWorldWorkflow from the terminal.

This simulates what FastAPI will do when a client hits an endpoint.

Run with:
    python -m scripts.trigger_hello
"""

import asyncio
from temporalio.client import Client
from app.workflows.hello_workflow import HelloWorldWorkflow

TASK_QUEUE = "smartcourse-queue"


async def main():
    # Connect to Temporal server
    client = await Client.connect("localhost:7233")

    print("🚀 Starting HelloWorldWorkflow...\n")

    # Start the workflow and wait for result
    result = await client.execute_workflow(
        HelloWorldWorkflow.run,
        "Khizar",
        id="hello-workflow-3",
        task_queue=TASK_QUEUE,
    )

    print(f"✅ Workflow completed!")
    print(f"📨 Result: {result}")
    print(f"\nCheck the Web UI to see the retries: http://localhost:8233")


if __name__ == "__main__":
    asyncio.run(main())
