# Integration with the Quantia platform

This guide explains how to plug the Quantia ML API into the existing
Quantia stack so the entire system runs locally with one command.

## Repository layout

The recommended layout is two sibling repositories:

```
your-projects/
├── PA_2025_UPGRADED/      # Quantia web app + sentiment job + Airflow + IaC
└── quantia-ml-api/        # this repo
```

## Steps to integrate

### 1. Build the ML API image once

From the `quantia-ml-api/` directory:

```bash
docker build -t quantia-ml-api:latest .
```

This produces a local image used by the next step.

### 2. Patch the Quantia `docker-compose.yml`

Open `PA_2025_UPGRADED/docker-compose.yml` and replace it with the following
(or merge the highlighted sections into your existing one):

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: quantia-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
      POSTGRES_DB: ${POSTGRES_DB:-quantia}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./scripts/init.sql:/docker-entrypoint-initdb.d/01-init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres} -d ${POSTGRES_DB:-quantia}"]
      interval: 5s
      timeout: 3s
      retries: 10
    networks: [quantia]

  ml-api:
    image: quantia-ml-api:latest
    container_name: quantia-ml-api
    restart: unless-stopped
    ports:
      - "${ML_API_PORT:-8000}:8000"
    environment:
      DATA_SOURCE: ${ML_DATA_SOURCE:-binance}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      DEFAULT_SYMBOL: ${ML_DEFAULT_SYMBOL:-BTCUSDT}
    healthcheck:
      test: ["CMD", "curl", "--fail", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
    networks: [quantia]

  web:
    build:
      context: .
      dockerfile: Quantia/Dockerfile
    container_name: quantia-web
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      ml-api:
        condition: service_healthy
    environment:
      ASPNETCORE_ENVIRONMENT: ${ASPNETCORE_ENVIRONMENT:-Development}
      ASPNETCORE_URLS: http://+:8080
      DOTNET_RUNNING_IN_CONTAINER: "true"
      ConnectionStrings__DefaultConnection: "Host=postgres;Port=5432;Database=${POSTGRES_DB:-quantia};Username=${POSTGRES_USER:-postgres};Password=${POSTGRES_PASSWORD:-changeme}"
      MlApi__BaseUrl: http://ml-api:8000
    ports:
      - "${WEB_PORT:-8080}:8080"
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
    networks: [quantia]

  sentiment-job:
    build:
      context: ./sentiment_job
      dockerfile: Dockerfile
    container_name: quantia-sentiment-job
    profiles: ["jobs"]
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      PG_CONN: postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD:-changeme}@postgres:5432/${POSTGRES_DB:-quantia}
      REDDIT_CLIENT_ID: ${REDDIT_CLIENT_ID:-}
      REDDIT_CLIENT_SECRET: ${REDDIT_CLIENT_SECRET:-}
      USER_AGENT: ${USER_AGENT:-quantia-sentiment-bot/0.1.0}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      ASSET: ${ASSET:-bitcoin}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    networks: [quantia]

volumes:
  postgres-data:
    driver: local

networks:
  quantia:
    driver: bridge
```

### 3. Update the `.env` file

In `PA_2025_UPGRADED/.env` (or create one from `.env.example`):

```env
POSTGRES_PASSWORD=quantia2025
WEB_PORT=8080
ML_API_PORT=8000
ML_DATA_SOURCE=binance
```

> The old line `ML_API_BASE_URL=https://api-test-049u.onrender.com` is no
> longer used inside the compose stack. The web container reads
> `MlApi__BaseUrl` directly from the compose file, pointing at the
> internal `http://ml-api:8000` service. The Render URL can stay in
> `.env.example` as a fallback, but isn't needed for local demos.

### 4. Boot everything with one command

```bash
cd PA_2025_UPGRADED
docker compose up
```

The boot order is enforced by healthchecks:
1. `postgres` becomes healthy (~5s)
2. `ml-api` becomes healthy (~20s — model loaded, Binance reachable)
3. `web` starts (depends on both)

### 5. End-to-end smoke test

```bash
curl -s http://localhost:5432    # Postgres up
curl -s http://localhost:8000/health | jq
curl -s http://localhost:8080/health
```

All three should respond. Open [http://localhost:8080](http://localhost:8080)
and you can register, log in, and use:

- **Portfolio** → live prices via the ML API
- **Trade** → live PnL via the ML API
- **Prediction** → live signal from the local XGBoost model

## Production deployment

In production the ML API runs on GKE alongside the web app. To extend the
existing Quantia Kubernetes manifests:

1. Build & push the `quantia-ml-api` image to Artifact Registry the same way
   the other images are pushed (see `.github/workflows/deploy.yml` in the
   Quantia repo).
2. Add a `Deployment` + `Service` for `quantia-ml-api` under
   `deploy/kubernetes/base/` (mirror `web-deployment.yaml`, expose port 8000).
3. Set `MlApi__BaseUrl` on the web Deployment to
   `http://quantia-ml-api.quantia-prod.svc.cluster.local:8000`.
4. For BigQuery access in prod, set `DATA_SOURCE=bigquery` and bind the
   pod's KSA to a GSA with `roles/bigquery.dataViewer` on the
   `quantia_market` dataset (Workload Identity).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `web` healthcheck fails, predictions empty | `ml-api` not yet ready | Wait 30s; healthchecks enforce order. |
| `/prediction/latest` returns 503 | Model not loaded | Check `artifacts/models/xgb_direction.json` exists in the image. |
| `/prediction/latest` returns 503 with "Not enough candles" | Binance rate-limited | Retry; or set `BINANCE_BASE_URL` to a proxy. |
| `model_loaded: false` in `/health` | Artefact missing | `docker compose exec ml-api python scripts/train_model.py --symbol BTCUSDT --days 3 --force` |
| `connection refused` from web → ml-api | Service name mismatch | Make sure the service is named `ml-api` and `MlApi__BaseUrl=http://ml-api:8000`. |
