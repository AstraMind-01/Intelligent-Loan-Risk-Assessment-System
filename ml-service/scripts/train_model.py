"""CLI entry point for the training pipeline.

Examples::

    python scripts/train_model.py
    python scripts/train_model.py --fast
    python scripts/train_model.py --imbalance smote --cv-folds 3
    python scripts/train_model.py --data "../Loan_default - Loan_default (1).csv"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import settings  # noqa: E402
from src.models.train import train  # noqa: E402
from src.utils.logging_config import configure_logging, get_logger  # noqa: E402

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the loan risk model.")
    parser.add_argument("--data", type=str, default=None,
                        help="Path to the training CSV (defaults to the configured dataset).")
    parser.add_argument("--imbalance", type=str, default=None,
                        choices=["class_weight", "smote", "undersample", "smote_tomek", "none"],
                        help="Class imbalance strategy.")
    parser.add_argument("--cv-folds", type=int, default=None, help="Cross-validation folds.")
    parser.add_argument("--tuning-sample", type=int, default=60_000,
                        help="Rows used for hyperparameter search (0 = use all).")
    parser.add_argument("--tuning-iterations", type=int, default=None,
                        help="Randomised search iterations for the advanced models.")
    parser.add_argument("--fast", action="store_true",
                        help="Quick run: 3 folds, 6 search iterations, 25k tuning sample.")
    parser.add_argument("--no-activate", action="store_true",
                        help="Register the model without making it active.")
    parser.add_argument("--notes", type=str, default="", help="Free-text note stored in metadata.")
    return parser.parse_args()


def main() -> int:
    configure_logging("training.log")
    args = parse_args()

    if args.fast:
        settings.cv_folds = 3
        settings.tuning_iterations = 6
        args.tuning_sample = 25_000
        logger.info("Fast mode: 3 folds, 6 search iterations, 25k tuning sample.")

    if args.tuning_iterations:
        settings.tuning_iterations = args.tuning_iterations

    result = train(
        source_path=args.data,
        imbalance_strategy=args.imbalance,
        cv_folds=args.cv_folds,
        tuning_sample=args.tuning_sample or None,
        set_active=not args.no_activate,
        notes=args.notes,
    )

    metrics = result.metadata.metrics
    comparison = result.metadata.baseline_comparison

    print("\n" + "=" * 68)
    print(f"  Model version : {result.version}")
    print(f"  Algorithm     : {result.metadata.algorithm}")
    print(f"  Dataset       : {result.metadata.dataset_version} "
          f"({result.metadata.dataset_rows:,} rows)")
    print(f"  Features      : {result.metadata.feature_count}")
    print("-" * 68)
    print("  TEST SET METRICS")
    print(f"    AUC-ROC             {metrics['roc_auc']:.4f}")
    print(f"    Average precision   {metrics['average_precision']:.4f}")
    print(f"    Accuracy            {metrics['accuracy']:.4f}")
    print(f"    Balanced accuracy   {metrics['balanced_accuracy']:.4f}")
    print(f"    Precision           {metrics['precision']:.4f}")
    print(f"    Recall              {metrics['recall']:.4f}")
    print(f"    F1                  {metrics['f1']:.4f}")
    print(f"    Brier score         {metrics['brier_score']:.4f}")
    cm = metrics["confusion_matrix"]
    print(f"    Confusion matrix    TN={cm['true_negative']:,} FP={cm['false_positive']:,} "
          f"FN={cm['false_negative']:,} TP={cm['true_positive']:,}")
    print("-" * 68)
    print("  BASELINE COMPARISON")
    for name, auc in comparison["all_candidates"].items():
        marker = " <- selected" if name == comparison["selected_model"] else ""
        print(f"    {name:22s} val AUC {auc:.4f}{marker}")
    print(f"    Lift over baseline  {comparison['auc_lift_over_baseline']:+.4f}")
    print("-" * 68)
    print("  RISK BANDS (test set)")
    for level, band in metrics.get("risk_bands", {}).items():
        print(f"    {level:7s} {band['count']:>7,} applications "
              f"({band['share']:.1%}) | observed default rate {band['observed_default_rate']:.2%}")
    print("-" * 68)
    fairness = result.metadata.fairness
    print(f"  FAIRNESS: {fairness.get('summary', 'not computed')}")
    for alert in fairness.get("alerts", [])[:4]:
        print(f"    ! {alert}")
    print("=" * 68 + "\n")

    summary_path = settings.registry_dir / result.version / "summary.json"
    summary_path.write_text(json.dumps({
        "version": result.version,
        "metrics": metrics,
        "baseline_comparison": comparison,
    }, indent=2, default=str), encoding="utf-8")
    logger.info("Summary written to %s", summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
