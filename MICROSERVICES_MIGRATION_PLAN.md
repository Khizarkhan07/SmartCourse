# SmartCourse — Microservices Migration Plan

## Guiding principle: Strangler Fig, not Big Bang

We do **not** stop and rewrite. We extract one service at a time from the existing
monolith, route traffic to it, verify, then extract the next. The monolith keeps
serving everything not yet extracted. At any point we can stop and still have a
working system.

Why: a big-bang rewrite means weeks with nothing shippable and a high-risk cutover.
The strangler approach keeps the system live and lets us learn the hard parts
(cross-service data, auth, distributed transactions) on the *least* risky service first.

---

## Step 0 — Where we are today (the honest starting point)

We have a **modular monolith** with most of the async plumbing already in place:

- One FastAPI app, one PostgreSQL database, one set of SQLAlchemy models
- Kafka + Avro + Schema Registry (event backbone — already built)
- Temporal (workflow orchestration — already built)
- Celery + RabbitMQ (background tasks — already built)
- Redis (cache, rate limit, JWT blacklist)
- OpenTelemetry + Jaeger (distributed tracing — already built)

The infrastructure that usually makes microservices hard (messaging, tracing,
orchestration) is **already done**. The remaining work is about **data ownership
and boundaries**, not plumbing.

### Current coupling that blocks a clean split

These are the seams we have to cut. All are foreign keys today:

| Foreign Key | Crosses boundary |
|---|---|
| `enrollments.student_id → users.id` | Enrollment → Identity |
| `enrollments.course_id → courses.id` | Enrollment → Course |
| `courses.instructor_id → users.id` | Course → Identity |
| `modules.course_id → courses.id` | (within Course) |
| `lessons.module_id → modules.id` | (within Course) |
| `lesson_completions.user_id → users.id` | Enrollment → Identity |
| `lesson_completions.lesson_id → lessons.id` | Enrollment → Course |

Plus: **analytics** joins across `enrollments + courses + users` in one query, and
`enrollment_service` imports the `Course` and `User` models directly.

---

## Step 1 — Define service boundaries (decide before coding)

Five services, drawn along the domain boundaries that already exist in the code:

```
┌─────────────────┐   ┌──────────────────┐   ┌────────────────────┐
│ identity-service│   │  course-service  │   │ enrollment-service │
│  users, auth,   │   │ courses, modules,│   │ enrollments,       │
│  JWT issuing    │   │ lessons, publish │   │ lesson_completions │
└─────────────────┘   └──────────────────┘   └────────────────────┘
        │                      │                       │
        └──────────────────────┴───────────────────────┘
                          Kafka events
                               │
                  ┌────────────┴────────────┐
                  │                          │
        ┌───────────────────┐   ┌────────────────────────┐
        │ analytics-service │   │ notification-service    │
        │ read model fed by │   │ Celery email workers    │
        │ events (no joins) │   │ (already standalone)    │
        └───────────────────┘   └────────────────────────┘
```

**Why these five:**
- They map 1:1 to the `app/services/*` modules we already have.
- `notification-service` is already nearly standalone (Celery workers).
- `analytics-service` already consumes Kafka events and only reads — perfect first
  target for the read-model pattern.

**Each service owns its own database.** No service reads another service's tables.
This is the rule that makes it microservices and not a distributed monolith.

---

## Step 2 — Extraction order (least risky first)

### 2a. Notification service (warm-up, ~lowest risk)
Already a separate Celery worker process. Give it its own repo/deployable + its own
config. It has no database of its own and only reacts to events/task messages.
**Goal: prove the deploy pipeline and service template with the easiest case.**

### 2b. Analytics service (read-only, event-fed)
This is the template for "killing cross-service joins."
- Today analytics does live SQL joins across enrollments + courses + users.
- After: analytics keeps its **own denormalized read model** (its own DB), built by
  consuming `enrollment.created`, `course.published`, etc. from Kafka.
- The API endpoints move to the new service; the monolith stops serving `/analytics`.
- No distributed transaction needed — it's eventually consistent by design, which is
  fine for dashboards.

### 2c. Identity service (everyone depends on it — extract once analytics proves the pattern)
- Owns `users`, login, JWT issuing.
- **Key decision**: other services must NOT call identity on every request. Instead
  they validate the JWT locally with the shared public key / secret. Identity is only
  hit at login and token refresh. (Our stateless-JWT choice already supports this.)
- The Redis JWT blacklist becomes shared infra or moves behind an identity endpoint.

### 2d. Course service
- Owns `courses, modules, lessons`. Publish/archive Temporal workflows move here.
- Emits `course.published`, `course.archived` events (already does).

### 2e. Enrollment service (extract last — most cross-service dependencies)
- Owns `enrollments, lesson_completions`.
- This is where distributed transactions actually bite (see Step 4).

---

## Step 3 — Killing the cross-service foreign keys

When `enrollments` and `courses` live in different databases, the DB-level FK
`enrollments.course_id → courses.id` **cannot exist**. Options:

1. **Store the ID without an FK + validate via API/event** (chosen default).
   `enrollment-service` stores `course_id` as a plain UUID. On enroll, it either:
   - calls `course-service` synchronously to confirm the course is published, OR
   - relies on a locally-cached projection of "published courses" built from
     `course.published` events.
   We already do the validation step inside the Temporal `validate_enrollment_activity` —
   it just changes from a local DB read to a cross-service check.

2. **Data duplication via events (read model).**
   Enrollment-service keeps a tiny local copy of the fields it needs (course title,
   status) updated by Kafka events. Trades storage + eventual consistency for not
   having to call course-service on every operation.

**Rule of thumb:** synchronous call when you need strong consistency *right now*
(can this student enroll?); event-driven projection when eventual consistency is fine
(showing the course title on a dashboard).

---

## Step 4 — Distributed transactions (the genuinely hard part)

Today, enrolling a student is one Temporal workflow doing: validate → write DB →
email → emit event. All in one process against one database.

After the split, "validate" lives in course-service, "write enrollment" in
enrollment-service, "email" in notification-service. We can no longer rely on a single
DB transaction.

**Solution: Saga pattern via Temporal** (we already use Temporal — this is its sweet spot).
- Each step is an activity that calls the owning service.
- Each step has a **compensating action** if a later step fails.
- Example: if enrollment is written but a required downstream step hard-fails, the
  compensation marks the enrollment cancelled / emits `enrollment.cancelled`.

Temporal already gives us durable retries; the new work is writing the *compensation*
activities. This is the single biggest code change in the whole migration.

---

## Step 5 — Cross-cutting infrastructure

| Concern | Decision |
|---|---|
| **Routing** | API Gateway in front (FastAPI gateway or nginx/Traefik). One public entry point; routes `/courses/*` → course-service, etc. |
| **Auth** | JWT validated locally in each service (shared secret/public key). Identity only issues tokens. No per-request call to identity. |
| **Service-to-service** | Kafka for async (already have it). Synchronous calls only where strong consistency is required. |
| **Tracing** | Already solved — OTel context propagates via Kafka headers and HTTP headers across services. This is why we built it now. |
| **Per-service DB** | Each service gets its own PostgreSQL schema/instance. Migrations split per service. |
| **Local dev** | docker-compose grows to N app services + their DBs. Consider a Makefile / Tilt to manage it. |
| **Config** | Each service has its own settings; shared values (Kafka brokers, JWT secret) via env. |

---

## Step 6 — What we explicitly do NOT change

- Kafka, Avro, Schema Registry — reused as-is, now the inter-service contract.
- Temporal — reused, now orchestrates cross-service sagas.
- OpenTelemetry/Jaeger — reused, now traces across service boundaries.
- Redis — reused (cache stays per-service; JWT blacklist becomes shared or identity-owned).

The Week 3 observability work pays off here: we can watch a request cross all five
services in one Jaeger trace from day one of the migration.

---

## Risks & honest tradeoffs

- **Eventual consistency** becomes user-visible (e.g. analytics lags a few seconds).
  Acceptable for dashboards; must be called out for anything users expect to be instant.
- **Operational weight** roughly 5x: five deploys, five DBs, five sets of migrations,
  gateway, more to run locally. This is the real cost the mentor is trading for
  independent scaling/deployment.
- **Saga compensations** are new code and new failure modes. Test them hard.
- **Distributed debugging** — mitigated by the tracing we already have, but still harder
  than a monolith.

---

## Suggested milestones

1. **M1** — Service template + gateway skeleton; extract notification-service.
2. **M2** — Extract analytics-service with its own event-fed read model.
3. **M3** — Extract identity-service; switch all services to local JWT validation.
4. **M4** — Extract course-service; move publish/archive workflows.
5. **M5** — Extract enrollment-service; implement enrollment saga + compensations.
6. **M6** — Remove dead code from the (now empty) monolith; gateway is the only entry.

Each milestone is independently shippable and leaves the system working.

---

# Chunked Execution Plan

Each chunk is small, independently testable, and leaves the system working. We go one
at a time. Numbering is sequential so "the next chunk" is always unambiguous.

> **Golden rule for every chunk:** the monolith keeps serving whatever hasn't been
> extracted yet. If a chunk breaks something, we can revert just that chunk.

---

## Milestone 1 — Foundation + Notification service

### Chunk 1 — Repo & directory strategy
- **Goal:** Decide monorepo layout and create the skeleton without moving any code.
- **Steps:** Create top-level `services/` dir. Move current app conceptually to
  `services/monolith/` (or leave in place and add `services/` alongside — decide now).
  Add a root `docker-compose.yml` that still runs the monolith unchanged.
- **Done when:** `docker compose up` runs the monolith exactly as before; `services/`
  exists and is empty/scaffolded.

### Chunk 2 — Service template (the reusable skeleton)
- **Goal:** One minimal FastAPI service we copy for every future service.
- **Steps:** `services/_template/` with: `main.py` (FastAPI + `/health`), `config.py`,
  `Dockerfile`, `requirements.txt`, and `configure_tracing()` wired to Jaeger.
- **Done when:** `docker build` succeeds, `curl /health` → `{"status":"ok"}`, and a
  span for the request shows up in Jaeger under the template's service name.

### Chunk 3 — API Gateway skeleton
- **Goal:** A single public entry point that can forward to a backend service.
- **Steps:** Stand up gateway (FastAPI reverse-proxy or Traefik) in compose. Add one
  route that forwards to the template service from Chunk 2.
- **Done when:** Hitting the gateway URL returns the template service's `/health`, and
  the Jaeger trace shows gateway → template as one trace (two spans).

### Chunk 4 — Extract notification-service
- **Goal:** Move the Celery email workers into their own deployable.
- **Steps:** Copy template → `services/notification/`. Move `app/worker/tasks/email_tasks.py`
  + Celery app config in. Point it at the existing RabbitMQ + Redis. Remove the worker
  responsibility from the monolith (monolith still *dispatches* tasks, doesn't run them).
- **Done when:** Enroll a student → welcome email task is executed by the standalone
  notification worker (check its logs), and the monolith no longer runs that worker.

---

## Milestone 1.5 — Certificate service (new feature)

> **Why here:** This is a greenfield service. It only needs the service template
> (Chunk 2), the gateway (Chunk 3), and an `enrollment.completed` event. It does **not**
> depend on the other extractions, so it can be built right after M1 while the rest of
> the app is still the monolith.
>
> **Design:** Event-driven. On course completion the monolith emits `enrollment.completed`
> carrying a snapshot (student name, course title, completed-at). The certificate-service
> consumes it, writes a certificate row with those denormalized fields, and renders a
> **simple PDF on demand** from that row — no cross-service calls at download time. The
> DB row is the source of truth; the PDF is derived. No public verification (MVP).

### Chunk C1 — Emit `enrollment.completed` event
- **Goal:** Publish a durable event when a student completes a course.
- **Steps:** Add an Avro schema `enrollment_completed.avsc` (enrollment_id, student_id,
  student_name, course_id, course_title, completed_at). Add an emit activity to the
  `CourseCompletionWorkflow` (mirrors `emit_enrollment_created_event_activity`). Ensure
  the workflow input carries student name + course title to put in the snapshot.
- **Done when:** Completing a course publishes `enrollment.completed` to Kafka (visible in
  logs / a test consumer / Jaeger).

### Chunk C2 — Certificate service skeleton + own database
- **Steps:** Copy the service template → `services/certificate/`. Add `certificate-db`
  to compose. Wire `/health` through the gateway.
- **Done when:** Service boots, `/health` works via the gateway, connects to its own empty DB.

### Chunk C3 — Certificate schema + issue-on-event consumer
- **Goal:** Issue a certificate record when the completion event arrives.
- **Steps:** `certificates` table — `id` (cert UUID), `enrollment_id` (UNIQUE → idempotency),
  `student_id`, `student_name`, `course_id`, `course_title`, `issued_at`. Add a Kafka
  consumer for `enrollment.completed` that upserts a row (idempotent on `enrollment_id`).
- **Done when:** Completing a course creates exactly one certificate row; re-delivery of
  the same event does not create a duplicate.

### Chunk C4 — PDF rendering
- **Goal:** Turn a certificate row into a PDF.
- **Steps:** Add a renderer (e.g. `reportlab` or `weasyprint`) that lays out student name,
  course title, issued date, and cert ID. Pure function: row → PDF bytes.
- **Done when:** Given a row, the function writes a valid PDF (save to `/tmp`, open it).

### Chunk C5 — Download endpoint + authorization
- **Goal:** A student downloads their own certificate; nobody else's.
- **Steps:** `GET /certificates` (list the caller's certs) and
  `GET /certificates/{id}/download` (stream the PDF, rendered on demand). JWT-protected via
  the shared auth dependency; enforce that `student_id` on the cert matches the token.
- **Done when:** A completed student downloads their PDF via the gateway; a different user
  gets 403; a student with no completion has no certificate to download.

### Chunk C6 — Routing cutover + end-to-end verification
- **Steps:** Gateway routes `/certificates/*` to certificate-service.
- **Done when:** Full flow works: complete course → `enrollment.completed` → cert row →
  download PDF, all visible as one Jaeger trace crossing the boundary.

---

## Milestone 2 — Analytics service (the read-model pattern)

### Chunk 5 — Analytics service skeleton + own database
- **Goal:** Stand up `services/analytics/` with its own Postgres instance.
- **Steps:** Copy template. Add `analytics-db` to compose. Wire the service to it.
- **Done when:** Service boots, `/health` works through the gateway, connects to its own
  empty DB (visible in Jaeger as a separate service + DB).

### Chunk 6 — Read-model schema
- **Goal:** Denormalized tables that need no cross-service joins.
- **Steps:** Design + migrate tables like `course_stats`, `enrollment_facts` that hold
  pre-joined fields (course title, status, student count) the dashboards need.
- **Done when:** Migrations apply to analytics-db; tables exist and are empty.

### Chunk 7 — Event consumers populate the read model
- **Goal:** Build the read model from Kafka, not from joins.
- **Steps:** Add consumers in analytics-service for `enrollment.created` and
  `course.published` that upsert into the read-model tables.
- **Done when:** Enroll a student / publish a course → rows appear in analytics-db,
  and the consumer span links into the same Jaeger trace.

### Chunk 8 — Move analytics endpoints to the service
- **Goal:** Serve `/analytics/*` from the new service, reading the read model.
- **Steps:** Port the analytics API handlers; they now query local read-model tables
  (no joins across enrollments/courses/users). Keep Redis cache per-service.
- **Done when:** Calling analytics endpoints directly on the service returns correct
  numbers sourced from the read model.

### Chunk 9 — Cut over routing, remove from monolith
- **Goal:** Gateway sends `/analytics/*` to analytics-service; monolith stops serving it.
- **Steps:** Add gateway route. Delete analytics router + analytics service/repo from monolith.
- **Done when:** `/analytics/*` through the gateway hits the new service; monolith no
  longer has analytics code; everything else still works.

---

## Milestone 3 — Identity service

### Chunk 10 — Identity service skeleton + own users database
- **Done when:** `services/identity/` boots with its own `identity-db`, `/health` via gateway.

### Chunk 11 — Move users model + auth endpoints
- **Goal:** Login, register, logout, and the `User` model live in identity-service.
- **Steps:** Move `users` table + migrations + `auth.py`/`users.py` endpoints + JWT issuing.
- **Done when:** Register + login against identity-service returns a valid JWT.

### Chunk 12 — Shared local JWT validation
- **Goal:** Other services validate JWTs locally — no per-request call to identity.
- **Steps:** Build a shared `get_current_user` dependency that verifies the JWT signature
  with the shared secret/public key. Put it in the service template so all services reuse it.
- **Done when:** The template/another service accepts a token issued by identity-service
  without calling identity.

### Chunk 13 — JWT blacklist decision
- **Goal:** Logout/revocation still works across services.
- **Steps:** Make the Redis blacklist shared infra (or expose an identity `/introspect`
  endpoint). Wire the shared auth dependency to check it.
- **Done when:** Logout → that token is rejected by a *different* service.

### Chunk 14 — Cut over routing, remove from monolith
- **Done when:** `/auth/*` and `/users/*` go through gateway to identity; monolith has no
  auth/user code; protected routes elsewhere still authorize correctly.

---

## Milestone 4 — Course service

### Chunk 15 — Course service skeleton + own database
- **Done when:** `services/course/` boots with its own `course-db`, `/health` via gateway.

### Chunk 16 — Move course/module/lesson models + CRUD
- **Goal:** The content hierarchy lives in course-service.
- **Steps:** Move `courses, modules, lessons` tables + migrations + their CRUD endpoints.
  `modules→courses` and `lessons→modules` FKs stay (same DB, same service).
- **Done when:** Course/module/lesson CRUD works against course-service directly.

### Chunk 17 — Break the `courses.instructor_id → users.id` FK
- **Goal:** Remove the cross-service FK to identity.
- **Steps:** Drop the DB FK; keep `instructor_id` as a plain UUID. Validate the instructor
  exists/has the role via identity at write time (or trust the JWT claims).
- **Done when:** Creating a course no longer depends on a users table in the same DB;
  instructor validation happens via token/identity call.

### Chunk 18 — Move publish/archive workflows
- **Goal:** Temporal publish/archive workflows run in a course-service worker.
- **Steps:** Move `publish_course_workflow.py` + its activities into course-service.
  It still emits `course.published`/`course.archived` to Kafka.
- **Done when:** Publishing a course via course-service drives the workflow and emits the
  event (visible end-to-end in Jaeger).

### Chunk 19 — Cut over routing, remove from monolith
- **Done when:** `/courses`, `/modules`, `/lessons`, `/publishing` go through gateway to
  course-service; monolith has no course code.

---

## Milestone 5 — Enrollment service (the saga)

### Chunk 20 — Enrollment service skeleton + own database
- **Done when:** `services/enrollment/` boots with its own `enrollment-db`, `/health` via gateway.

### Chunk 21 — Move enrollment + completion models + endpoints
- **Steps:** Move `enrollments, lesson_completions` tables + endpoints. The
  `enrollments↔lesson_completions` stay local.
- **Done when:** Enrollment + completion endpoints work against enrollment-service.

### Chunk 22 — Break cross-service FKs (`course_id`, `student_id`, `lesson_id`)
- **Goal:** Remove all FKs pointing at courses/users/lessons.
- **Steps:** Convert them to plain UUIDs. Keep the `(student_id, course_id)` unique
  constraint (it's local — still the idempotency guarantee).
- **Done when:** Enrollment-db has no FK to any other service's tables.

### Chunk 23 — Cross-service validation
- **Goal:** `validate_enrollment` checks the course via course-service, not a local join.
- **Steps:** Change the validate activity to call course-service ("is this course
  published?") or read a local event-fed projection of published courses.
- **Done when:** Enrolling in an unpublished/missing course is rejected, with the check
  crossing the service boundary (visible in Jaeger).

### Chunk 24 — Enrollment saga + compensations
- **Goal:** The enrollment workflow becomes a cross-service saga with rollback.
- **Steps:** Each step (validate → write enrollment → notify → emit event) is an activity
  hitting the owning service. Add compensating actions (e.g. cancel enrollment / emit
  `enrollment.cancelled`) for failures after the DB write.
- **Done when:** Forcing a downstream step to fail triggers the compensation and leaves
  no orphaned enrollment; the saga + compensation are visible as one Jaeger trace.

### Chunk 25 — Cut over routing, remove from monolith
- **Done when:** `/enrollments/*` and completions go through gateway to enrollment-service;
  monolith has no enrollment code.

---

## Milestone 6 — Cleanup & final verification

### Chunk 26 — Decommission the monolith
- **Steps:** Remove now-empty monolith routers/services/models. The monolith either
  disappears or becomes a thin shell.
- **Done when:** Gateway is the only public entry point; nothing routes to the monolith.

### Chunk 27 — Full end-to-end trace verification
- **Goal:** Prove the whole thing observably works.
- **Steps:** Run a full enroll flow. Confirm one Jaeger trace spans gateway → identity
  (auth) → enrollment → course (validate) → Kafka → notification → analytics consumer.
- **Done when:** A single trace shows the request crossing all five services, and all
  per-service dashboards/health are green.

---

## How to use this list
Pick a chunk, implement it, run its "Done when" test, commit, move to the next. We never
hold more than one chunk's worth of half-finished work, and the system is shippable
between every chunk.
</content>
</invoke>
