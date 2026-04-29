# Architecture

## Service responsibility

The Quantia ML API is a thin, stateless service whose responsibility is
**price-direction prediction and pattern detection** for crypto pairs. It
holds no user state — that lives in the Quantia web app's PostgreSQL
database. The only persistent assets here are the **model artefact** and
the **pattern library**, both versioned together with the code under
`artifacts/`.

## Components

```
┌──────────────────────────────────────────────────────────────┐
│  app/                                                        │
│                                                              │
│  ┌────────────┐   ┌─────────────┐   ┌─────────────────────┐ │
│  │  api/      │   │  models/    │   │  data/              │ │
│  │  ┌──────┐  │   │  ┌────────┐ │   │  ┌──────────────┐   │ │
│  │  │routes│──┼──►│  │predict │◄┼───┤  │CandleData    │   │ │
│  │  └──────┘  │   │  └────────┘ │   │  │Source (ABC)  │   │ │
│  │  ┌──────┐  │   │  ┌────────┐ │   │  └──────────────┘   │ │
│  │  │schema│  │   │  │  risk  │ │   │     ▲       ▲       │ │
│  │  └──────┘  │   │  └────────┘ │   │     │       │       │ │
│  └─────┬──────┘   └─────────────┘   │  ┌──┴──┐ ┌──┴────┐  │ │
│        │                            │  │Binan│ │BigQry │  │ │
│        │            ┌─────────────┐ │  └─────┘ └───────┘  │ │
│        ├───────────►│  patterns/  │ └─────────────────────┘ │
│        │            │  ┌────────┐ │                          │
│        │            │  │candles │ │       ┌───────────────┐  │
│        │            │  ├────────┤ │       │  features/    │  │
│        │            │  │detect  │ │       │  ┌─────────┐  │  │
│        │            │  └────────┘ │       │  │indicat. │  │  │
│        │            └─────────────┘       │  ├─────────┤  │  │
│        │                                  │  │targets  │  │  │
│        │            ┌─────────────┐       │  └─────────┘  │  │
│        └───────────►│  training/  │──────►└───────────────┘  │
│                     │  ┌────────┐ │                          │
│                     │  │train   │ │                          │
│                     │  ├────────┤ │                          │
│                     │  │evaluate│ │                          │
│                     │  ├────────┤ │                          │
│                     │  │pipeline│ │                          │
│                     │  └────────┘ │                          │
│                     └─────────────┘                          │
└──────────────────────────────────────────────────────────────┘
```

### Data layer (`app/data/`)

- `CandleDataSource` is an ABC with three methods: `fetch_recent`,
  `fetch_range`, `fetch_last_candle`.
- `BinanceSource` paginates through the public `/api/v3/klines` endpoint,
  honouring the 1000-row limit per request, and normalises the response
  into a canonical OHLCV dataframe.
- `BigQuerySource` issues a parameterised SQL query against a configurable
  table. It uses `db-dtypes` and `pyarrow` for fast deserialisation.
- `factory.get_data_source()` is `lru_cache`-decorated, so each process
  has exactly one data-source instance.

### Feature engineering (`app/features/`)

`add_all_features()` produces the **exact 19 columns in the exact order**
required by the trained XGBoost booster:

```
open, high, low, close, volume, quote_volume, nb_trades,
sma_5, sma_10, ema_5, ema_10, rsi_14,
macd, macd_signal, macd_diff,
bb_upper, bb_lower, bb_width,
atr_14
```

Indicators come from the [`ta`](https://technical-analysis-library-in-python.readthedocs.io/)
library. Order is preserved via the `FEATURE_COLUMNS` constant — both
training and inference import the same list, so feature drift between
the two is impossible.

### Model layer (`app/models/`)

- `Predictor` lazily loads `artifacts/models/xgb_direction.json` on first
  use and caches the booster in a thread-safe singleton. `reload()` is
  used after a successful retraining run.
- `risk.suggest_levels()` computes ATR-based stop-loss and take-profit
  distances. Defaults are `1.5 × ATR` for SL and `3.0 × ATR` for TP, both
  multiplied by the user-supplied `risk_multiple`. If ATR isn't available
  (insufficient data), it falls back to fixed percentages of entry price.

### Pattern layer (`app/patterns/`)

- `candles.py` extracts 8 normalised features per candle (body size, wick
  ratios, direction, volume z-score) and runs `scipy.cluster.vq.kmeans2`
  with a fixed seed (42) to assign reproducible cluster IDs.
- `PatternDetector` loads `significant_patterns.csv` (sequences of 1–3
  candle types statistically biased toward bullish or bearish moves) and
  matches them against the clustered series. Matches are deduplicated by
  sequence + direction and filtered to leave at least 2 minutes between
  consecutive hits.
- `detect_classic_patterns` is a separate, rule-based detector for
  human-recognisable formations (doji, hammer, shooting star, bullish/
  bearish engulfing). It's used by the Technical Analysis page in the web
  app.

### Training layer (`app/training/`)

- `train.py` — single function `train_direction_model()` that persists a
  booster as JSON.
- `evaluate.py` — log-loss + accuracy + precision/recall/F1 + raw
  confusion counts. Pure Python (no scikit-learn) so the runtime image
  stays slim.
- `pipeline.py` — the full **train → evaluate → conditional promote**
  loop. The candidate model is only promoted if its log-loss is strictly
  lower than the production model's on the same dataset. After promotion
  the predictor singleton is hot-reloaded.

### API layer (`app/api/`)

- One file per concern: `health`, `data`, `prediction`, `pattern`,
  `trade`, `model`. Routers are mounted by `app/api/router.py`.
- All response shapes are pydantic models in `schemas.py`. The
  `TradeSuggestion` schema uses field aliases (`EntryPrice`, `StopLoss`,
  ...) to match the C# casing expected by the Quantia .NET app — this
  keeps the .NET deserializer happy without any custom converters.
- Global exception handler in `main.py` catches anything not handled and
  returns a clean `500` JSON instead of a stack trace.

## Lifecycle

```
docker compose up
       │
       ▼
  uvicorn imports app.main
       │
       ▼
  FastAPI lifespan starts
   ├─ setup_logging()
   ├─ get_predictor()   ── loads xgb_direction.json   ◄── may warn if missing
   └─ get_pattern_detector() ── loads significant_patterns.csv
       │
       ▼
  /health returns model_loaded=true
       │
       ▼
  Quantia web → /prediction/latest → CandleDataSource.fetch_recent()
                                  → add_all_features()
                                  → predictor.predict_proba_up()
                                  → risk.suggest_levels()
                                  → JSON response
```

## Why two data sources

Local demo and the soutenance **must work without GCP credentials**. Binance
public REST is the path of least resistance. In production the same code
reads from the same `crypto_prices` BigQuery table that the Quantia Airflow
ingestion pipeline writes to every minute — single source of truth, no
data drift.

## Why preserve the existing model artefact

The original repo shipped a trained `xgb_direction.json` (479 KB). I kept
it. The 19-feature contract is fully respected by the new
`add_all_features` so the booster works as-is — no retraining needed for
the API to function. Calling `POST /refresh-model` on a fresh deployment
will train a new candidate; if it's worse than the bundled artefact, the
bundled one stays. That is exactly the behaviour you want for a
portfolio-grade demo.
