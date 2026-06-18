INFRA    := -f docker-compose.yml
MONOLITH := -f app/docker-compose.yml
GATEWAY  := -f services/gateway/docker-compose.yml

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

# ── Full stack: infra + monolith + gateway ─────────────────────────────────────
stack-up:
	docker compose $(INFRA) $(MONOLITH) $(GATEWAY) up -d

stack-down:
	docker compose $(INFRA) $(MONOLITH) $(GATEWAY) down

# ── Add a microservice alongside the full stack ────────────────────────────────
# Example: make svc-up SVC=certificate
svc-up:
	docker compose $(INFRA) $(MONOLITH) $(GATEWAY) -f services/$(SVC)/docker-compose.yml up -d

svc-down:
	docker compose $(INFRA) $(MONOLITH) $(GATEWAY) -f services/$(SVC)/docker-compose.yml down

logs:
	docker compose $(INFRA) $(MONOLITH) $(GATEWAY) logs -f
