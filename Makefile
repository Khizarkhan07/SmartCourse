INFRA    := -f docker-compose.yml
MONOLITH := -f app/docker-compose.yml
GATEWAY  := -f services/gateway/docker-compose.yml
NOTIFY   := -f services/notification/docker-compose.yml
CERT     := -f services/certificate/docker-compose.yml
ANALYTICS := -f services/analytics/docker-compose.yml

# ── Shared infra only (Kafka, Redis, RabbitMQ, Jaeger, etc.) ──────────────────
infra-up:
	docker compose $(INFRA) up -d

infra-down:
	docker compose $(INFRA) down

# ── Monolith + infra (no gateway) ─────────────────────────────────────────────
up:
	docker compose $(INFRA) $(MONOLITH) up -d

down:
	docker compose $(INFRA) $(MONOLITH) $(GATEWAY) down

# ── Rebuild all service images ────────────────────────────────────────────────
build:
	docker compose $(INFRA) $(MONOLITH) $(GATEWAY) $(NOTIFY) $(CERT) $(ANALYTICS) build

# ── Rebuild + restart a single service ────────────────────────────────────────
# Example: make rebuild SVC=certificate
rebuild:
	docker compose $(INFRA) $(MONOLITH) $(GATEWAY) $(NOTIFY) $(CERT) $(ANALYTICS) up -d --build $(SVC)

# ── Full stack: infra + monolith + all microservices ──────────────────────────
stack-up:
	docker compose $(INFRA) $(MONOLITH) $(GATEWAY) $(NOTIFY) $(CERT) $(ANALYTICS) up -d

stack-down:
	docker compose $(INFRA) $(MONOLITH) $(GATEWAY) $(NOTIFY) $(CERT) $(ANALYTICS) down

# ── Add a microservice alongside the full stack ────────────────────────────────
# Example: make svc-up SVC=notification
svc-up:
	docker compose $(INFRA) $(MONOLITH) $(GATEWAY) $(NOTIFY) $(CERT) $(ANALYTICS) -f services/$(SVC)/docker-compose.yml up -d

svc-down:
	docker compose $(INFRA) $(MONOLITH) $(GATEWAY) $(NOTIFY) $(CERT) $(ANALYTICS) -f services/$(SVC)/docker-compose.yml down

logs:
	docker compose $(INFRA) $(MONOLITH) $(GATEWAY) $(NOTIFY) $(CERT) $(ANALYTICS) logs -f
