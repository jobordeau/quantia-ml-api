from __future__ import annotations

import argparse
import json

from app.training.pipeline import run_training_pipeline
from app.utils import setup_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the Quantia direction model")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--output", default=None,
                        help="Override the model output path")
    parser.add_argument("--force", action="store_true",
                        help="Promote the candidate model even if it is worse")
    args = parser.parse_args()

    setup_logging("INFO")
    result = run_training_pipeline(
        symbol=args.symbol,
        days=args.days,
        model_path=args.output,
        promote_only_if_better=not args.force,
    )
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
