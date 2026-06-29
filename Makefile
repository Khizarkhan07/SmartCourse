INFRA     := -f docker-compose.yml
GATEWAY   := -f services/gateway/docker-compose.yml
NOTIFY    := -f services/notification/docker-compose.yml
CERT      := -f services/certificate/docker-compose.yml
ANALYTICS := -f services/analytics/docker-compose.yml
IDENTITY  := -f services/identity/docker-compose.yml
COURSE    := -f services/course/docker-compose.yml
ENROLLMENT := -f services/enrollment/docker-compose.yml

SERVICES := $(GATEWAY) $(NOTIFY) $(CERT) $(ANALYTICS) $(IDENTITY) $(COURSE) $(ENROLLMENT)

# ── Shared infra only (Kafka, Redis, RabbitMQ, Jaeger, etc.) ──────────────────
infra-up:
	docker compose $(INFRA) up -d

infra-down:
	docker compose $(INFRA) down

# ── Full stack: infra + all microservices ─────────────────────────────────────
stack-up:
	docker compose $(INFRA) $(SERVICES) up -d

stack-down:
	docker compose $(INFRA) $(SERVICES) down

# ── Rebuild all service images ────────────────────────────────────────────────
build:
	docker compose $(INFRA) $(SERVICES) build

# ── Rebuild + restart a single service ────────────────────────────────────────
# Example: make rebuild SVC=certificate
rebuild:
	docker compose $(INFRA) $(SERVICES) up -d --build $(SVC)

# ── Add a microservice alongside the full stack ────────────────────────────────
# Example: make svc-up SVC=notification
svc-up:
	docker compose $(INFRA) $(SERVICES) -f services/$(SVC)/docker-compose.yml up -d

svc-down:
	docker compose $(INFRA) $(SERVICES) -f services/$(SVC)/docker-compose.yml down

logs:
	docker compose $(INFRA) $(SERVICES) logs -f
