# SmartCourse — Local Setup Guide

## Prerequisites

- Python 3.11+
- Docker Desktop
- [Temporal CLI](https://docs.temporal.io/cli) — for running the Temporal server natively

---

## 1. Clone and install dependencies

```bash
git clone <repo-url>
cd SmartCourse

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

---

## 2. Configure environment

Create a `.env` file in the project root:

```env
# Database
DATABASE_URL=postgresql+asyncpg://smartcourse_user:smartcourse_pass@localhost:5433/smartcourse_db
DATABASE_URL_SYNC=postgresql+psycopg2://smartcourse_user:smartcourse_pass@localhost:5433/smartcourse_db

# App
APP_ENV=development
SECRET_KEY=change-this-to-a-random-secret-in-production
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# JWT
ACCESS_TOKEN_EXPIRE_MINUTES=60
ALGORITHM=HS256

# Temporal
TEMPORAL_HOST=localhost:7233

# Kafka
KAFKA_BROKERS=localhost:9092
SCHEMA_REGISTRY_URL=http://localhost:8081

# Prometheus Pushgateway
PUSHGATEWAY_URL=http://localhost:9091
```

---

## 3. Start infrastructure (Docker)

Starts PostgreSQL, Kafka, Zookeeper, Schema Registry, Pushgateway, Prometheus, and Grafana:

```bash
docker compose up -d
```

Verify all containers are healthy:

```bash
docker compose ps
```

---

## 4. Start Temporal server (native)

Temporal runs natively on the host, not in Docker:

```bash
temporal server start-dev
```

This starts Temporal on `localhost:7233` with the Temporal UI at `http://localhost:8233`.

---

## 5. Run database migrations

```bash
alembic upgrade head
```

---

## 6. Start the FastAPI app

```bash
uvicorn app.main:app --reload --port 8000
```

---

## 7. Start the Temporal worker

In a separate terminal:

```bash
source venv/bin/activate
python -m app.infrastructure.temporal.worker
```

---

## 8. Start the Kafka consumer runner

In a separate terminal:

```bash
source venv/bin/activate
python -m app.events.consumers.runner
```

---

## Service URLs

| Service | URL | Notes |
|---|---|---|
| FastAPI | http://localhost:8000 | |
| Swagger UI | http://localhost:8000/docs | Interactive API docs |
| Metrics endpoint | http://localhost:8000/metrics | Prometheus text format |
| Temporal UI | http://localhost:8233 | Workflow history |
| Schema Registry | http://localhost:8081 | Avro schema store |
| Pushgateway | http://localhost:9091 | Worker metrics store |
| Prometheus | http://localhost:9090 | Metrics query (PromQL) |
| Grafana | http://localhost:3001 | Dashboards — login: `admin` / `admin` |

---

## Processes to run simultaneously

You need **four** things running at the same time:

```
Terminal 1: temporal server start-dev
Terminal 2: uvicorn app.main:app --reload --port 8000
Terminal 3: python -m app.infrastructure.temporal.worker
Terminal 4: python -m app.events.consumers.runner
```

Docker Compose handles everything else.

---

## Resetting the database

```bash
docker compose down -v     # removes volumes — all data lost
docker compose up -d
alembic upgrade head
```

---

## Running migrations after model changes

```bash
alembic revision --autogenerate -m "describe your change"
alembic upgrade head
```
