# SmartCourse — Implementation Plan

## Completed (Week 1–3)

| Chunk | Feature | Status |
|---|---|---|
| 1–17 | Core API: users, courses, modules, lessons, enrollments, auth, rate limiting | ✅ Complete |
| 18 | Structured logging (structlog) | ✅ Complete |
| 19 | Kafka + Schema Registry + Avro producers | ✅ Complete |
| 20 | Prometheus metrics + `/metrics` endpoint + Grafana dashboard | ✅ Complete |
| 21 | Config externalization (pydantic-settings, .env) | ✅ Complete |
| 22A | Docker full stack (Kafka, Zookeeper, Schema Registry, Pushgateway) | ✅ Complete |
| 22B | Kafka consumers (enrollment.created, course.published) | ✅ Complete |
| 22C | Worker activity metrics via Pushgateway | ✅ Complete |
| 22D | Prometheus + Grafana in Docker Compose | ✅ Complete |
| 23 | Grafana dashboards (6 panels, auto-provisioned) | ✅ Complete |
| 25 | Cleanup — removed hello_workflow, trigger_hello | ✅ Complete |

---

## Remaining Gaps (from requirements)

### Tech Stack gaps
- **Redis** — no caching, no Redis-backed rate limiting, no token blacklist
- **NoSQL DB (MongoDB)** — required for document-oriented course content storage
- **Celery + RabbitMQ** — lightweight async task queue (Temporal handles complex workflows; Celery handles fire-and-forget tasks)
- **Jaeger** — no distributed tracing
- **OpenTelemetry** — no trace instrumentation

### Functional gaps
- **Enrollment prerequisites** — no "must complete course X first" enforcement
- **Enrollment capacity limits** — no max_students per course
- **Kafka consumers are passive** — they log events but don't drive state changes or trigger downstream tasks

---

## Remaining Chunks

---

### Chunk 26 — Redis Integration
**Goal:** Add Redis as a shared caching and reliability layer across the platform.

**Context:** Currently analytics endpoints run expensive DB aggregation queries on every request. Rate limiting uses in-memory state (resets on restart, doesn't work across multiple API instances). JWT logout has no token revocation. Redis fixes all three.

**Sub-chunks:**

**26A — Infrastructure**
1. Add Redis (`redis:7`) to `docker-compose.yml` on port 6379
2. Add `REDIS_URL: str = "redis://localhost:6379/0"` to `app/config.py`
3. Add `redis[asyncio]` to `requirements.txt`

**26B — Analytics Response Cache**
1. Create `app/infrastructure/cache.py` — async Redis client wrapper with `get`, `set`, `delete` helpers
2. In `analytics_service.py` — wrap `get_overview_metrics()` and `get_most_popular_courses()` with a 60-second Redis cache
3. Cache key pattern: `analytics:{method_name}:{params_hash}`

**26C — Redis-backed Rate Limiting**
1. Replace in-memory `slowapi` limiter with `slowapi` Redis storage backend
2. Rate limit state now survives restarts and works across multiple API instances

**26D — JWT Token Blacklist**
1. On `POST /auth/logout` — store the token's `jti` (JWT ID) in Redis with TTL equal to the token's remaining lifetime
2. In the JWT validation dependency — check the `jti` against Redis blacklist before allowing the request
3. Add `logout` endpoint to `app/api/v1/auth.py`

**Acceptance Criteria**
- Analytics endpoints return cached responses; second request does not hit DB
- Rate limit counter persists across API restarts
- Calling `/auth/logout` invalidates the token for subsequent requests

---

### Chunk 27 — Enrollment Business Rules
**Goal:** Implement enrollment capacity limits and course prerequisites.

**Context:** The requirements explicitly call out duplicate handling (done), enrollment limits, and prerequisites as enrollment rules. Currently any student can enroll in any published course with no capacity or prerequisite check.

**Sub-chunks:**

**27A — Course Capacity**
1. Add `max_students: int | None` to the `Course` model (nullable = no limit)
2. Generate Alembic migration
3. Expose `max_students` in `CourseCreate` and `CourseUpdate` schemas
4. In `validate_enrollment_activity` — count current enrollments for the course; raise `ApplicationError(non_retryable=True)` if at capacity

**27B — Enrollment Prerequisites**
1. Add `prerequisites` M2M relationship: `CoursePrerequisite` table (`course_id`, `required_course_id`)
2. Generate Alembic migration
3. Expose `prerequisite_ids: list[UUID]` in `CourseCreate` / `CourseUpdate`
4. In `validate_enrollment_activity` — for each prerequisite, check the student has a `completed` enrollment; raise `ApplicationError(non_retryable=True)` if not

**Acceptance Criteria**
- Enrolling in a full course returns a clear non-retryable error
- Enrolling without completing prerequisites returns a clear non-retryable error
- `max_students=null` means unlimited capacity

---

### Chunk 28 — Celery + RabbitMQ
**Goal:** Add Celery as a lightweight fire-and-forget task queue alongside Temporal.

**Context:** Temporal handles complex multi-step durable workflows (enrollment, publishing). Celery handles simpler async tasks that don't need workflow-level durability: sending emails, updating analytics caches, triggering downstream notifications. RabbitMQ is the message broker for Celery.

**Sub-chunks:**

**28A — Infrastructure**
1. Add `rabbitmq:3-management` to `docker-compose.yml` on ports 5672 (AMQP) and 15672 (management UI)
2. Add `RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"` to `app/config.py`
3. Add `celery[rabbitmq]` to `requirements.txt`

**28B — Celery App Setup**
1. Create `app/worker/celery_app.py` — Celery instance configured with RabbitMQ broker and Redis result backend
2. Create `app/worker/tasks/` directory
3. Create `app/worker/tasks/email_tasks.py`:
   - `send_welcome_email_task(email, course_title)` — replaces the mocked Temporal activity
   - `send_completion_email_task(email, course_title)` — for course completion
4. Create `app/worker/tasks/analytics_tasks.py`:
   - `invalidate_analytics_cache_task()` — deletes Redis analytics keys on enrollment/completion events

**28C — Wire Temporal Activities to Celery**
1. In `send_enrollment_email_activity` — instead of mocking, dispatch `send_welcome_email_task.delay()`
2. Keep the Temporal activity as the durable wrapper; Celery handles the actual send
3. Temporal handles retries at the workflow level; Celery handles execution

**Acceptance Criteria**
- RabbitMQ management UI accessible at `http://localhost:15672` (login: `guest`/`guest`)
- Enrolling a student dispatches a Celery task visible in RabbitMQ queues
- Celery worker processes the task and logs email sent

---

### Chunk 29 — Kafka Consumers Driving State
**Goal:** Make consumers act on events rather than just logging them.

**Context:** Currently `enrollment_consumer.py` and `course_consumer.py` decode events and log them. The event-driven loop is incomplete — nothing downstream reacts to the events. This chunk wires consumers to Celery tasks so events drive actual state changes.

**Tasks:**
1. In `enrollment_consumer.py` — after decoding `enrollment.created`:
   - Dispatch `invalidate_analytics_cache_task.delay()` to bust the analytics Redis cache
   - Dispatch `send_welcome_email_task.delay(...)` if email is available in the event payload
2. In `course_consumer.py` — after decoding `course.published`:
   - Dispatch `invalidate_analytics_cache_task.delay()` to update course count cache
3. Add `app/worker/tasks/__init__.py` exports

**Why Celery and not direct DB writes from the consumer:**
Consumers are synchronous threads. Writing to the DB synchronously inside a consumer blocks the poll loop and risks consumer group rebalancing on slow queries. Dispatching to Celery decouples the I/O.

**Acceptance Criteria**
- Triggering an enrollment → consumer decodes event → Celery task dispatched → analytics cache invalidated
- Next analytics API call hits DB fresh (cache miss), re-populates cache
- Full event-driven loop is traceable in logs

---

### Chunk 30 — MongoDB for Course Content
**Goal:** Store course content (course + modules + lessons as a nested document) in MongoDB for fast single-read retrieval.

**Context:** PostgreSQL requires joining `courses`, `modules`, and `lessons` tables to return a full course content tree. MongoDB stores this as a single document — one read, no joins. The `course.published` Kafka event already fires when a course is published; the consumer can write the denormalized document to MongoDB at that point.

**Sub-chunks:**

**30A — Infrastructure**
1. Add `mongo:7` to `docker-compose.yml` on port 27017
2. Add `MONGODB_URL: str = "mongodb://localhost:27017"` and `MONGODB_DB: str = "smartcourse"` to `app/config.py`
3. Add `motor` (async MongoDB driver) to `requirements.txt`

**30B — MongoDB Client**
1. Create `app/infrastructure/mongodb/client.py` — async Motor client singleton
2. Create `app/infrastructure/mongodb/course_content_repository.py`:
   - `upsert_course_document(course_id, document)` — insert or replace
   - `get_course_document(course_id)` — fetch by course ID
   - `delete_course_document(course_id)` — on course archive

**30C — Content Sync on Publish**
1. Create `app/worker/tasks/content_tasks.py`:
   - `sync_course_content_task(course_id)` — fetches course+modules+lessons from PostgreSQL, writes denormalized document to MongoDB
2. In `course_consumer.py` — dispatch `sync_course_content_task.delay(course_id)` on `course.published`

**30D — Content Retrieval Endpoint**
1. Add `GET /api/v1/courses/{id}/content` endpoint
2. Returns the full course document from MongoDB (modules + lessons nested)
3. Falls back to PostgreSQL if MongoDB document not found

**Acceptance Criteria**
- Publishing a course → Kafka event → consumer → Celery → MongoDB document written
- `GET /courses/{id}/content` returns full nested content from MongoDB in a single read
- Archiving a course removes the MongoDB document

---

### Chunk 31 — OpenTelemetry + Jaeger
**Goal:** Add distributed tracing across FastAPI, Temporal worker, and Kafka events.

**Context:** Logs and metrics tell you what happened and how often. Traces tell you the full journey of a single request — which service it touched, how long each hop took, where it failed. The Kafka event envelope already has a `trace_id` field (currently always `""`).

**Sub-chunks:**

**31A — Infrastructure**
1. Add Jaeger (`jaegertracing/all-in-one:1.57`) to `docker-compose.yml`
   - Port 16686 — Jaeger UI
   - Port 4317 — OTLP gRPC collector
2. Add `OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"` to `app/config.py`
3. Add `opentelemetry-sdk`, `opentelemetry-exporter-otlp`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy` to `requirements.txt`

**31B — FastAPI Instrumentation**
1. Create `app/core/tracing.py` — configure OTel SDK with OTLP exporter pointing at Jaeger
2. In `app/main.py` — call `configure_tracing()` at startup, add `FastAPIInstrumentor`
3. Add `SQLAlchemyInstrumentor` to trace DB queries

**31C — Trace Propagation through Kafka**
1. In `KafkaEventProducer._send()` — extract current span context and write to event's `trace_id` field
2. In `enrollment_consumer` / `course_consumer` — read `trace_id` from event and restore span context before dispatching Celery tasks
3. This links the API trace → Kafka event → consumer → Celery task as a single trace

**31D — Temporal Worker Tracing**
1. Add OTel instrumentation to `app/infrastructure/temporal/worker.py`
2. Each activity creates a child span — visible in Jaeger under the parent API request trace

**Acceptance Criteria**
- Jaeger UI at `http://localhost:16686` shows traces for API requests
- An enrollment request shows a trace spanning: FastAPI → Temporal workflow → activity spans
- `trace_id` in Kafka event links to the originating API request trace

---

## Recommended Execution Order

| Chunk | Feature | Depends On |
|---|---|---|
| 26A | Redis in Docker | — |
| 26B | Analytics cache | 26A |
| 26C | Redis rate limiting | 26A |
| 26D | JWT token blacklist | 26A |
| 27A | Course capacity limits | — |
| 27B | Enrollment prerequisites | 27A |
| 28A | RabbitMQ in Docker | — |
| 28B | Celery app + tasks | 28A, 26A (Redis result backend) |
| 28C | Wire Temporal → Celery | 28B |
| 29 | Consumers drive state | 28B |
| 30A | MongoDB in Docker | — |
| 30B | MongoDB client | 30A |
| 30C | Content sync on publish | 30B, 28B |
| 30D | Content retrieval endpoint | 30B |
| 31A | Jaeger in Docker | — |
| 31B | FastAPI OTel | 31A |
| 31C | Kafka trace propagation | 31B |
| 31D | Temporal tracing | 31B |

## Port Map (full stack)

| Service | Port | Notes |
|---|---|---|
| FastAPI | 8000 | |
| PostgreSQL | 5433 | |
| Kafka | 9092 | |
| Zookeeper | 2181 | |
| Schema Registry | 8081 | |
| Temporal | 7233 | Native |
| Temporal UI | 8233 | Native |
| Pushgateway | 9091 | |
| Prometheus | 9090 | |
| Grafana | 3001 | admin/admin |
| Redis | 6379 | |
| RabbitMQ AMQP | 5672 | |
| RabbitMQ UI | 15672 | guest/guest |
| MongoDB | 27017 | |
| Jaeger UI | 16686 | |
| Jaeger OTLP | 4317 | |
