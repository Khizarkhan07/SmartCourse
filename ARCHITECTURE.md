# SmartCourse — Architecture Snapshot

> Current state as of M3 Chunk 10. Updated each milestone.

---

## Diagrams

### Target Architecture — All Services

> ✅ = extracted · 🔧 = skeleton · 📋 = planned
> Solid arrows = sync HTTP · Dashed arrows = async Kafka events

```mermaid
graph TD
    classDef done      fill:#22c55e,color:#fff,stroke:#16a34a
    classDef skeleton  fill:#f59e0b,color:#fff,stroke:#d97706
    classDef planned   fill:#94a3b8,color:#fff,stroke:#64748b
    classDef gateway   fill:#8b5cf6,color:#fff,stroke:#7c3aed
    classDef db        fill:#dbeafe,color:#1e40af,stroke:#3b82f6
    classDef infra     fill:#fef9c3,color:#713f12,stroke:#ca8a04
    classDef worker    fill:#f1f5f9,color:#334155,stroke:#94a3b8

    Client(["👤 Client"])
    GW["API Gateway\n:8080"]:::gateway

    subgraph SVC ["Services"]
        direction LR
        ID["identity-service\nauth · users · JWT\n🔧 M3"]:::skeleton
        COURSE["course-service\ncourses · modules\nlessons · publish\n📋 M4"]:::planned
        ENR["enrollment-service\nenrollments\nlesson completions\nsaga\n📋 M5"]:::planned
        CERT["certificate-service\ncertificates\nPDF renderer\n✅ M1.5"]:::done
        ANA["analytics-service\nenrollment_facts\ncourse_facts\n✅ M2"]:::done
    end

    subgraph WORKERS ["Background Workers"]
        direction LR
        NOTIFY["notification-service\nCelery workers\n✅ M1"]:::worker
        CERTCON["certificate-consumer\n✅ M1.5"]:::worker
        ANACON["analytics-consumer\n✅ M2"]:::worker
    end

    subgraph DBS ["Per-Service Databases"]
        direction LR
        IDDB[("identity-db\n:5436")]:::db
        COURSEDB[("course-db")]:::db
        ENRDB[("enrollment-db")]:::db
        CERTDB[("certificate-db\n:5434")]:::db
        ANADB[("analytics-db\n:5435")]:::db
    end

    subgraph INFRA ["Shared Infrastructure"]
        direction LR
        KAFKA[["Kafka"]]:::infra
        RABBIT[["RabbitMQ"]]:::infra
        REDIS[("Redis")]:::infra
        TEMP[["Temporal"]]:::infra
    end

    %% Client → Gateway → Services
    Client --> GW
    GW -->|"/auth /users"| ID
    GW -->|"/courses /modules /lessons"| COURSE
    GW -->|"/enrollments"| ENR
    GW -->|"/certificates"| CERT
    GW -->|"/analytics"| ANA

    %% Service → DB
    ID --- IDDB
    COURSE --- COURSEDB
    ENR --- ENRDB
    CERT --- CERTDB
    ANA --- ANADB

    %% Sync HTTP between services
    ENR -->|"validate course exists\nHTTP sync"| COURSE

    %% Async via Kafka
    COURSE -.->|"course.published\ncourse.archived"| KAFKA
    ENR -.->|"enrollment.created\nenrollment.completed"| KAFKA
    KAFKA -.->|"enrollment.completed"| CERTCON
    KAFKA -.->|"enrollment.*\ncourse.*"| ANACON
    CERTCON --- CERTDB
    ANACON --- ANADB

    %% Async via RabbitMQ
    ENR -->|"email tasks"| RABBIT
    RABBIT --> NOTIFY

    %% Saga orchestration
    ENR --- TEMP
    COURSE --- TEMP

    %% Cache
    ANA --- REDIS
    ID --- REDIS
```

---

### Kafka Event Flows

```mermaid
flowchart LR
    subgraph "Producer"
        MON["Monolith"]
    end

    subgraph "Topics"
        T1(["enrollment.created"])
        T2(["enrollment.completed\n— via Temporal workflow"])
        T3(["course.published\n— via Temporal workflow"])
    end

    subgraph "analytics-consumer"
        AC1["upsert enrollment_facts\nstatus = active"]
        AC2["update enrollment_facts\nstatus = completed\nsets completed_at"]
        AC3["upsert course_facts"]
    end

    subgraph "certificate-consumer"
        CC["issue certificate row\nidempotent on enrollment_id\nPDF rendered on GET"]
    end

    MON -->|"on enroll"| T1
    MON -->|"on 100% lesson progress"| T2
    MON -->|"on course publish"| T3

    T1 --> AC1
    T2 --> AC2
    T2 --> CC
    T3 --> AC3
```

---

### Gateway Routing

```mermaid
flowchart LR
    C(["Client\nrequest"])

    GW{{"API Gateway\n:8080\n\nroutes by first\npath segment"}}

    CERT["certificate-service\n:8002\n\nGET /\nGET /:id/download"]
    ANA["analytics-service\n:8003\n\nGET /overview\nGET /enrollments\nGET /courses\nGET /workflows"]
    ID["identity-service\n:8004\n\nGET /health\n(Chunk 11 adds more)"]
    MON["Monolith\n:8000\n\n/auth · /users\n/courses · /modules\n/lessons · /enrollments\n/publishing"]

    C --> GW
    GW -->|"/certificates/*\n→ strip prefix"| CERT
    GW -->|"/analytics/*\n→ strip prefix"| ANA
    GW -->|"/identity/*\n→ strip prefix"| ID
    GW -->|"no match\n→ pass through"| MON
```

---

## Extraction Status

| Domain | Owns | Status | DB port | API port |
|---|---|---|---|---|
| **Monolith** | auth, users, courses, modules, lessons, enrollments, publishing | Still serving everything not yet cut over | 5433 | 8000 (host) |
| **notification-service** | Celery email workers | ✅ Extracted (M1) | none | — |
| **certificate-service** | certificates table, PDF renderer | ✅ Extracted (M1.5) | 5434 | 8002 |
| **analytics-service** | enrollment_facts, course_facts (read model) | ✅ Extracted (M2) | 5435 | 8003 |
| **identity-service** | users, auth, JWT issuing | 🔧 Skeleton only (Chunk 10) | 5436 | 8004 |
| **course-service** | courses, modules, lessons, publish workflow | 📋 Planned (M4) | — | — |
| **enrollment-service** | enrollments, lesson_completions, saga | 📋 Planned (M5) | — | — |

---

## Request Routing

All public traffic enters through the **API Gateway** on port 8080.
The gateway routes by the **first URL path segment**:

```
Client
  │
  ▼
┌─────────────────────────────────────────────────────┐
│  API Gateway  :8080                                 │
│                                                     │
│  /certificates/* ──strip prefix──► certificate:8002 │
│  /analytics/*    ──strip prefix──► analytics:8003   │
│  /identity/*     ──strip prefix──► identity:8004    │
│  (anything else) ──────────────► monolith:8000      │
└─────────────────────────────────────────────────────┘
```

"Strip prefix" means `/certificates/abc/download` becomes `/abc/download`
on the certificate service. Each service's router has **no URL prefix** of its own.

---

## Service Map

```
                          ┌──────────────────────────────────────────────────┐
                          │                  SHARED INFRA                    │
                          │  Kafka · Schema Registry · Redis · RabbitMQ      │
                          │  Temporal · Jaeger · Prometheus · Grafana        │
                          └────────────────────┬─────────────────────────────┘
                                               │ (all services connect here)
         ┌─────────────────────────────────────┼────────────────────────────────────┐
         │                                     │                                    │
         ▼                                     ▼                                    ▼
┌─────────────────┐                  ┌──────────────────┐               ┌──────────────────────┐
│    MONOLITH     │                  │ notification-svc  │               │   certificate-svc    │
│  host:8000      │──Celery tasks──►│  (Celery worker)  │               │  :8002               │
│                 │                  │  RabbitMQ + Redis │               │  certificate-db:5434 │
│  /auth/*        │                  └──────────────────┘               │                      │
│  /users/*       │                                                      │  consumer:           │
│  /courses/*     │                                                      │  enrollment.completed│
│  /modules/*     │                                                      └──────────────────────┘
│  /lessons/*     │
│  /enrollments/* │                  ┌──────────────────┐               ┌──────────────────────┐
│  /publishing/*  │                  │  analytics-svc   │               │   identity-svc       │
│                 │                  │  :8003           │               │  :8004               │
│  postgres:5433  │                  │  analytics-db    │               │  identity-db:5436    │
└────────┬────────┘                  │  :5435           │               │                      │
         │                           │                  │               │  skeleton only —     │
         │  produces Kafka events     │  consumers:      │               │  no routes yet       │
         │                           │  enrollment.*    │               └──────────────────────┘
         │                           │  course.published│
         └──────────────────────────►│                  │
                                     └──────────────────┘
```

---

## Kafka Event Flows

### Producer
The monolith produces all events today. Future: each extracted service produces its own.

| Topic | Produced by | When |
|---|---|---|
| `enrollment.created` | monolith | student enrolls in a course |
| `enrollment.completed` | monolith (via Temporal `CourseCompletionWorkflow`) | student completes all lessons |
| `course.published` | monolith (via Temporal `PublishCourseWorkflow`) | instructor publishes a course |

### Consumers

| Topic | Consumer service | What it does |
|---|---|---|
| `enrollment.created` | analytics-consumer | upserts row in `enrollment_facts` (status=active) |
| `enrollment.completed` | analytics-consumer | updates `enrollment_facts` row (status=completed, sets completed_at) |
| `enrollment.completed` | certificate-consumer | issues a certificate row (idempotent on enrollment_id) |
| `course.published` | analytics-consumer | upserts row in `course_facts` |

### Avro + Schema Registry
All events use **Confluent wire format**: `[0x00][4-byte schema_id][avro bytes]`.
Each consumer has its own `avro_decoder.py` that fetches the schema from Schema Registry
(`http://schema-registry:8081`) and decodes the payload. No shared library — each
service is independently deployable.

---

## Data Ownership

**Rule:** no service reads another service's database tables. All cross-service
data flows through Kafka events or HTTP calls through the gateway.

| Service | Database | Key tables |
|---|---|---|
| monolith | smartcourse_db (postgres:5433) | users, courses, modules, lessons, enrollments, lesson_completions |
| certificate-service | certificate_db (postgres:5434) | certificates |
| analytics-service | analytics_db (postgres:5435) | enrollment_facts, course_facts |
| identity-service | identity_db (postgres:5436) | *(empty — Chunk 11 moves users here)* |

---

## Auth Flow (current)

JWT tokens are **issued by the monolith** and **validated locally** by each service
using the shared `SECRET_KEY` from the root `.env`.

```
Client ──POST /auth/login──► Gateway ──► Monolith ──issues JWT──► Client

Client ──GET /certificates (Bearer token)──► Gateway
  ──► certificate-service (validates JWT locally with SECRET_KEY)
```

After M3: the monolith's auth endpoints move to identity-service. The local
validation logic stays the same — services still verify JWTs with the shared
secret; they just won't call identity on every request.

---

## What the Monolith Still Owns (cut-over targets)

| Path prefix | Target service | Milestone |
|---|---|---|
| `/auth/*`, `/users/*` | identity-service | M3 |
| `/courses/*`, `/modules/*`, `/lessons/*`, `/publishing/*` | course-service | M4 |
| `/enrollments/*` | enrollment-service | M5 |

---

## Port / URL Quick Reference

| Component | Host port | Docker-internal URL |
|---|---|---|
| API Gateway | 8080 | — |
| Monolith | 8000 | `http://host.docker.internal:8000` |
| certificate-service | 8002 | `http://smartcourse_certificate:8000` |
| analytics-service | 8003 | `http://smartcourse_analytics:8000` |
| identity-service | 8004 | `http://smartcourse_identity:8000` |
| monolith postgres | 5433 | `smartcourse_postgres:5432` |
| certificate-db | 5434 | `certificate-db:5432` |
| analytics-db | 5435 | `analytics-db:5432` |
| identity-db | 5436 | `identity-db:5432` |
| Kafka | 9092 (host) | `kafka:29092` (containers) |
| Schema Registry | 8081 | `schema-registry:8081` |
| Redis | 6379 | `redis:6379` |
| RabbitMQ | 5672 / 15672 | `rabbitmq:5672` |
| Temporal | 7233 | `temporal:7233` |
| Jaeger UI | 16686 | — |
| Grafana | 3001 | — |
| Prometheus | 9090 | — |
