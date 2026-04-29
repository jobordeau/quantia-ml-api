Voici la traduction du fichier `README.md` en français :

# Quantia ML API

Service de prédiction de direction crypto. Compagnon de la plateforme web [Quantia](https://github.com/your-org/PA_2025_UPGRADED) — projet de fin d'année pour le Mastère Big Data & IA, ESGI.

L'API expose les données de prix, les prédictions du modèle, la détection de figures en chandeliers (candlestick patterns), des suggestions de trade et un pipeline d'entraînement. Elle est consommée par l'application web Quantia .NET via HTTP et alimente les pages **Prediction**, **Portfolio** et **Technical Analysis**.

---

## Table des matières

- [Aperçu de l'architecture](#aperçu-de-larchitecture)
- [Démarrage rapide](#démarrage-rapide)
- [Endpoints](#endpoints)
- [Configuration](#configuration)
- [Structure du projet](#structure-du-projet)
- [Entraîner un nouveau modèle](#entraîner-un-nouveau-modèle)
- [Tests](#tests)

---

## Aperçu de l'architecture

```text
┌─────────────────────────┐
│  App web Quantia .NET   │
│   (PA_2025_UPGRADED)    │
└────────────┬────────────┘
             │ HTTP (MlApi:BaseUrl)
             ▼
┌─────────────────────────┐    récupère OHLCV   ┌──────────────────────┐
│   Quantia ML API        │ ─────────────────►  │  CandleDataSource    │
│   (ce dépôt)            │                     │  ├─ Binance public   │
│                         │                     │  └─ BigQuery (opt)   │
│  ┌───────────────────┐  │                     └──────────────────────┘
│  │ Prédicteur XGBoost│  │
│  ├───────────────────┤  │ charge au démarrage ┌──────────────────────┐
│  │ Détecteur patterns│  │ ◄──────────────────►│  artifacts/          │
│  ├───────────────────┤  │                     │  ├─ models/*.json    │
│  │ Risque (ATR SL/TP)│  │                     │  └─ patterns/*.csv   │
│  ├───────────────────┤  │                     └──────────────────────┘
│  │ Pipeline entraîne.│  │
│  └───────────────────┘  │
└─────────────────────────┘
```

L'API possède **deux sources de données interchangeables** :

- **Binance public REST** (par défaut) — aucun identifiant requis, idéal pour le développement local, les démos et la soutenance.
- **Google BigQuery** — pour la production, extrait les données depuis la même table `crypto_prices` dans laquelle le pipeline d'ingestion Quantia Airflow écrit (chaque minute).

Changez de source avec une seule variable d'environnement : `DATA_SOURCE=binance` ou `DATA_SOURCE=bigquery`.

---

## Démarrage rapide

### Prérequis

- Docker 24+ avec le plugin Compose v2, **ou** Python 3.11

### Option A — Docker (recommandé)

```bash
git clone https://github.com/jobordeau/quantia-ml-api.git
cd quantia-ml-api
cp .env.example .env

docker compose up --build
```

L'API est maintenant disponible sur [http://localhost:8000](http://localhost:8000).

Test rapide de fonctionnement :

```bash
curl -s http://localhost:8000/health | jq
# {
#   "status": "ok",
#   "utc": "...",
#   "model_loaded": true,
#   "data_source": "binance",
#   "version": "1.0.0"
# }

curl -s "http://localhost:8000/prediction/latest?symbol=BTCUSDT" | jq
curl -s "http://localhost:8000/data/BTCUSDT/last_candle" | jq
```

Ouvrez [http://localhost:8000/docs](http://localhost:8000/docs) pour l'interface Swagger générée automatiquement — chaque endpoint est interactif.

### Option B — Python en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

python scripts/run_api.py
```

URL par défaut : [http://localhost:8000](http://localhost:8000).

---

## Endpoints

Le schéma OpenAPI complet est disponible sur `/docs` et `/openapi.json`. Résumé :

| Méthode | Chemin | Description |
|--------|------|-------------|
| GET    | `/health` | Liveness + statut du modèle |
| GET    | `/data/{symbol}/last_candle` | Bougie (candle) 1m la plus récente |
| GET    | `/data/{symbol}?days=&interval=` | Historique récent des bougies |
| GET    | `/prediction/latest?symbol=` | Dernier signal de direction + SL/TP |
| GET    | `/trade/suggest?symbol=&risk_multiple=` | Suggestion de trade complète |
| GET    | `/pattern/load-data` | Historique des bougies avec les ID de cluster K-Means |
| GET    | `/pattern/load-data-patterns` | Correspondances de patterns significatifs + prévisions |
| GET    | `/pattern/load-data-patterns-classic` | Figures en chandeliers classiques (doji, marteau, ...) |
| POST   | `/refresh-model` | Ré-entraîne sur les dernières données ; promeut si meilleur |
| POST   | `/run_ml_pipeline` | Exécution configurable du pipeline |
| GET    | `/get_model_metrics` | Évalue le modèle actuel (ou un modèle donné) |

### Exemples de réponses

`GET /prediction/latest?symbol=BTCUSDT`
```json
{
  "symbol": "BTCUSDT",
  "timestamp": "2025-04-29T14:32:11.205+00:00",
  "prob_up": 0.563,
  "signal": "LONG",
  "confidence": 0.126,
  "entry": 103420.50,
  "stop_loss": 103180.20,
  "take_profit": 103900.50,
  "note": "atr14=160.247"
}
```

`GET /trade/suggest?symbol=BTCUSDT&risk_multiple=1.5`
```json
{
  "symbol": "BTCUSDT",
  "side": "LONG",
  "EntryPrice": 103420.50,
  "StopLoss": 103060.13,
  "TakeProfit": 104141.25,
  "PositionSize": 0.126,
  "Confidence": 0.126,
  "Timestamp": "2025-04-29T14:32:11.205+00:00"
}
```

La casse pour `EntryPrice / StopLoss / TakeProfit / PositionSize / Confidence / Timestamp` est intentionnelle — elle correspond au record C# `TradeSuggestion` consommé par l'application Quantia .NET.

---

## Configuration

Tous les paramètres peuvent être modifiés via des variables d'environnement (voir `app/config.py` et `.env.example`) :

| Variable | Défaut | Objectif |
|---|---|---|
| `DATA_SOURCE` | `binance` | `binance` ou `bigquery` |
| `BINANCE_BASE_URL` | `https://api.binance.com` | Remplacement pour le proxy Binance |
| `BIGQUERY_PROJECT` | — | Requis si `DATA_SOURCE=bigquery` |
| `BIGQUERY_DATASET` | — | Requis si `DATA_SOURCE=bigquery` |
| `BIGQUERY_TABLE` | — | Requis si `DATA_SOURCE=bigquery` |
| `GOOGLE_APPLICATION_CREDENTIALS` | — | Chemin vers un fichier JSON de compte de service GCP |
| `DEFAULT_SYMBOL` | `BTCUSDT` | Utilisé par `/refresh-model` |
| `RISK_ATR_WINDOW` | `14` | Fenêtre ATR pour le calcul du SL/TP |
| `RISK_ATR_STOP_MULTIPLIER` | `1.5` | Stop = entrée ± mult × ATR |
| `RISK_ATR_TAKE_MULTIPLIER` | `3.0` | Take = entrée ± mult × ATR |
| `ARTIFACTS_DIR` | `artifacts` | Dossier où sont stockés les modèles et les patterns |
| `LOG_LEVEL` | `INFO` | Niveaux de journalisation (logging) standards |
| `CORS_ALLOW_ORIGINS` | `["*"]` | Liste d'autorisation CORS |

---

## Structure du projet

```text
quantia-ml-api/
├── app/
│   ├── api/
│   │   ├── routes/         # health, data, prediction, pattern, trade, model
│   │   ├── router.py       # combine les routeurs
│   │   └── schemas.py      # schémas de réponses Pydantic
│   ├── data/
│   │   ├── base.py         # classe abstraite CandleDataSource
│   │   ├── binance_source.py
│   │   ├── bigquery_source.py
│   │   └── factory.py
│   ├── features/
│   │   ├── indicators.py   # création de 19 variables (feature engineering)
│   │   └── targets.py
│   ├── models/
│   │   ├── predictor.py    # singleton XGBoost, chargement/rechargement thread-safe
│   │   └── risk.py         # SL/TP basé sur l'ATR
│   ├── patterns/
│   │   ├── candles.py      # clustering K-Means
│   │   └── detector.py     # patterns significatifs + classiques
│   ├── training/
│   │   ├── train.py
│   │   ├── evaluate.py     # logloss + accuracy + precision/recall/f1
│   │   └── pipeline.py     # entraîner → évaluer → promotion conditionnelle
│   ├── utils/__init__.py   # journalisation (logging)
│   ├── config.py           # configuration via pydantic-settings
│   └── main.py             # fabrique de l'application FastAPI
├── artifacts/
│   ├── models/xgb_direction.json
│   └── patterns/significant_patterns.csv
├── scripts/
│   ├── run_api.py          # point d'entrée pour le dev local
│   └── train_model.py      # réentraînement en ligne de commande (CLI)
├── tests/                  # tests unitaires + e2e avec des données synthétiques
├── .github/workflows/ci.yml
├── Dockerfile              # image multi-étapes, non-root, avec healthcheck
├── docker-compose.yml
├── pyproject.toml          # configuration pour pytest + ruff
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── LICENSE
└── README.md
```

---

## Entraîner un nouveau modèle

```bash
python scripts/train_model.py --symbol BTCUSDT --days 7
```

Cette commande récupère 7 jours de bougies d'1 minute à partir de la source de données configurée, entraîne un nouveau modèle de direction XGBoost dans `artifacts/models/xgb_direction_candidate.json`, évalue à la fois le candidat et le modèle de production actuel sur les mêmes données, et promeut le candidat **uniquement si son log-loss est strictement inférieur**.

Pour promouvoir le candidat de force malgré tout :

```bash
python scripts/train_model.py --symbol BTCUSDT --days 7 --force
```

La même logique est exposée via l'API :

```bash
curl -X POST http://localhost:8000/refresh-model
curl -X POST http://localhost:8000/run_ml_pipeline \
  -H "content-type: application/json" \
  -d '{"mode":"full","symbol":"BTCUSDT","days":7}'
```

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest --cov=app
```

Les tests utilisent une source de données de bougies synthétique (`tests/conftest.py`) afin qu'ils puissent s'exécuter hors ligne — pas de réseau, pas de GCP, pas de Binance.

---
