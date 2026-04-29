# Soutenance — full-stack demo guide

End-to-end procedure to demonstrate the entire Quantia platform during the
soutenance, including the local ML API (this repository).

This document assumes both repositories are checked out side-by-side:

```
your-projects/
├── PA_2025_UPGRADED/      # Quantia: web + sentiment + Airflow + IaC
└── quantia-ml-api/        # this repo
```

---

## Prerequisites

```bash
docker --version             # 24+
docker compose version       # v2 plugin
terraform -version           # 1.5+ (optional, for IaC demo)
kubectl version --client     # for K8s demo
```

---

## One-time setup (5 min)

### 1. Build the ML API image

```bash
cd quantia-ml-api
docker build -t quantia-ml-api:latest .
```

### 2. Patch the Quantia compose file

Apply the patch from
[`docs/integration-with-quantia.md`](./integration-with-quantia.md) to the
`PA_2025_UPGRADED/docker-compose.yml`. The minimum changes are:
- Add a `ml-api` service using the `quantia-ml-api:latest` image
- Set `MlApi__BaseUrl: http://ml-api:8000` on the `web` service
- Add `ml-api` to the `web` service's `depends_on`

### 3. Configure environment

```bash
cd PA_2025_UPGRADED
cp .env.example .env
$EDITOR .env
# minimum: set POSTGRES_PASSWORD
```

### 4. Boot the stack

```bash
docker compose up
```

Boot order is enforced by healthchecks:
1. Postgres healthy (~5s)
2. ml-api healthy (~20s, model loaded)
3. web starts

---

## Demo data injection (1 min)

Inject sentiment data so the Sentiment Analysis page isn't empty.

```bash
TODAY=$(date -u +"%Y-%m-%dT01:00:00+00:00")

docker exec -i quantia-postgres psql -U postgres -d quantia <<SQL
INSERT INTO sentiment_scores (ts, ts_hour, score, price_btc, price_eth)
VALUES ('$TODAY', '$TODAY', 0.685, 103420.50, 3876.20)
ON CONFLICT (ts_hour) DO UPDATE
  SET score=EXCLUDED.score, price_btc=EXCLUDED.price_btc, price_eth=EXCLUDED.price_eth;

INSERT INTO sentiment_details (ts_hour, json_payload)
VALUES ('$TODAY', '{
  "global_index": 0.685,
  "google_trend": 0.62,
  "market_index": 0.71,
  "price_btc": 103420.50,
  "price_eth": 3876.20,
  "asset": "bitcoin",
  "reddit_index": 0.693,
  "clusters": [
    {
      "topic": "institutional bitcoin acquisition",
      "avg": 0.77, "freq": 847, "delta": 1.683,
      "summary": "Surge in corporate Bitcoin acquisitions signals strong institutional confidence.",
      "examples": ["MicroStrategy bought another 10,100 BTC for 1B USD."],
      "urls": ["https://www.reddit.com/r/Bitcoin/comments/example1"]
    },
    {
      "topic": "hardware wallet security",
      "avg": 0.74, "freq": 312, "delta": 0.92,
      "summary": "Growing interest in self-custody and long-term hodling.",
      "examples": ["Switched to Coldcard for open-source Bitcoin-only custody."],
      "urls": ["https://www.reddit.com/r/Bitcoin/comments/example2"]
    },
    {
      "topic": "bull market outlook 2025",
      "avg": 0.731, "freq": 564, "delta": 0.78,
      "summary": "Community sentiment strongly bullish through 2025.",
      "examples": ["NVT ratio still healthy, ETFs absorbing supply daily."],
      "urls": ["https://www.reddit.com/r/CryptoCurrency/comments/example3"]
    }
  ]
}')
ON CONFLICT (ts_hour) DO UPDATE SET json_payload=EXCLUDED.json_payload;
SQL
```

---

## Pre-soutenance verification

Run this 5 minutes before walking into the room.

```bash
# Containers up?
docker compose ps
# Expect: postgres healthy, ml-api healthy, web healthy

# Web?
curl -s http://localhost:8080/health
# {"status":"ok","utc":"..."}

# ML API?
curl -s http://localhost:8000/health | python3 -m json.tool
# Expect: model_loaded: true, data_source: "binance"

# Real prediction (uses the bundled XGBoost model)?
curl -s "http://localhost:8000/prediction/latest?symbol=BTCUSDT" | python3 -m json.tool
# Expect: prob_up, signal LONG/SHORT, entry/stop_loss/take_profit

# Sentiment data injected?
docker exec quantia-postgres psql -U postgres -d quantia \
  -c "SELECT ts_hour, score FROM sentiment_scores ORDER BY ts_hour DESC LIMIT 1;"
```

If everything responds, you're ready.

---

## Demo sequence (≈25 minutes)

### Part 1 — Intro and architecture (5 min)

1. Pitch business: trading aid for crypto traders, multi-source signals.
2. Open `PA_2025_UPGRADED/docs/architecture.md` — walk the diagram.
3. Show the two repositories: `PA_2025_UPGRADED/` and `quantia-ml-api/` — explain
   that the ML API is a separate, language-different service consumed by the
   .NET app via HTTP, with Binance as default data source so it works
   anywhere.

### Part 2 — Live demo (10 min)

Open [http://localhost:8080](http://localhost:8080).

1. **Auth flow** — Register, log in.
2. **Portfolio** → Simulate Buy → `BTCUSDT` qty `0.5` → live price comes from
   the ML API's `/data/{symbol}/last_candle`. Add `ETHUSDT` qty `2`.
3. **Trade** → New Trade → `BTCUSDT` buy `103000` qty `0.1` SL `101000` TP
   `108000` → Save. Live PnL via `/data/{symbol}/last_candle`. Close at
   `105000` → realised PnL.
4. **Trade History** → shows the closed trade.
5. **Sentiment Analysis** ⭐ — Global index 0.685, three clusters, summaries.
6. **Prediction** ⭐⭐ — Live XGBoost signal from your trained model. Switch
   to `ETHUSDT`. Equity curve. Stats.
7. **Technical Analysis** — Rule-based signals (doji, hammer, engulfing).
8. **Settings** → Save name change.

### Part 3 — Show the ML API directly (3 min)

Open [http://localhost:8000/docs](http://localhost:8000/docs).

```bash
# Same prediction the UI just used
curl -s "http://localhost:8000/prediction/latest?symbol=BTCUSDT" | python3 -m json.tool

# Trade suggestion (the C# casing matters)
curl -s "http://localhost:8000/trade/suggest?symbol=BTCUSDT&risk_multiple=1.5" \
  | python3 -m json.tool

# Classic candlestick patterns
curl -s "http://localhost:8000/pattern/load-data-patterns-classic?symbol=BTCUSDT&start_date=2025-04-28T00:00&end_date=2025-04-29T00:00&atr_min_pct=0.05" \
  | python3 -m json.tool

# Model metrics on real data
curl -s "http://localhost:8000/get_model_metrics?symbol=BTCUSDT&days=2" \
  | python3 -m json.tool
```

Talking points:
- `Predictor` singleton, lazy-loaded XGBoost booster.
- Feature contract: 19 columns in a fixed order, same constant used at
  training and inference.
- ATR-based SL/TP with configurable multipliers.
- Two interchangeable data sources behind one ABC (`CandleDataSource`).

### Part 4 — Pipelines (4 min)

```bash
# Crypto ingestion DAG
cat PA_2025_UPGRADED/airflow/dags/crypto_ingestion_dag.py

# Sentiment DAG
cat PA_2025_UPGRADED/airflow/dags/sentiment_pipeline_dag.py

# Sentiment job structure
ls PA_2025_UPGRADED/sentiment_job/
```

Talking points:
- Binance → BigQuery, 1-minute partitioned table, clustered by symbol
- Sentiment: PRAW → CryptoBERT → HDBSCAN → GPT-4o-mini summaries
- Both DAGs are version-controlled; the Airflow VM clones them at boot

### Part 5 — Infrastructure (4 min)

```bash
cd PA_2025_UPGRADED/infra/terraform/environments/dev
cp terraform.tfvars.example terraform.tfvars
terraform init -backend=false
terraform validate

cd ../../../..
kustomize build deploy/kubernetes/overlays/prod | grep "kind:" | sort | uniq -c
```

Talking points:
- 6 Terraform modules (VPC, GKE, Cloud SQL, BigQuery, Airflow VM, Artifact
  Registry), 3 environments
- Kustomize base + overlays per env
- WIF-based GitHub Actions deploy (no static keys)

---

## In case of trouble

| Problem | Fix |
|---|---|
| `docker compose up` fails | Free port 8080 / 8000 / 5432; `docker compose down -v` to reset |
| Page blank / 500 | `docker compose logs web` |
| `Sentiment Analysis` empty | Re-run the `psql` snippet above |
| `Prediction` says model not loaded | `docker exec quantia-ml-api python scripts/train_model.py --symbol BTCUSDT --days 3 --force` |
| Prices `N/A` in Portfolio | `docker exec quantia-ml-api curl -s "http://localhost:8000/data/BTCUSDT/last_candle"` to verify Binance is reachable from inside the container |
| Login redirect loop | The cookie auth requires HTTP in dev; the Docker-aware code in `Program.cs` handles this. If broken, ensure `DOTNET_RUNNING_IN_CONTAINER=true` is set on the web container |

---

## What to say if asked

**"Why not call the public ML API instead?"**
Reproducibility. The Render deployment can be cold or down. The local API
runs from a 479 KB committed model artefact, on Binance public data, and is
identical in behaviour to the deployed one (same code, same feature
engineering).

**"Why two data sources?"**
Decoupling. Binance for local + demos (no credentials), BigQuery for prod
(reads the same table the Airflow ingestion writes — single source of
truth). The choice is one env var.

**"How does the .NET app talk to a Python service?"**
HTTP. The .NET app uses a named `HttpClient("MLApi")` whose base URL is
configured via `MlApi:BaseUrl`. In Docker that's `http://ml-api:8000`; in
production that's a Kubernetes ClusterIP service.

**"Could you retrain on stage?"**
`POST /refresh-model` does it live. The pipeline trains a candidate, scores
both candidate and incumbent on the same data, promotes only if the
candidate's log-loss is strictly lower, then hot-reloads the predictor
singleton.
