"""Logging setup shared by the training scripts and the API."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import settings

_CONFIGURED = False


def configure_logging(log_file: Optional[str] = "ml-service.log") -> None:
    """Attach a console handler (and optionally a file handler) to the root logger."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root.addHandler(console)

    if log_file:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(settings.log_dir / log_file, encoding="utf-8")
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

    # SHAP and numba are extremely chatty at DEBUG level.
    logging.getLogger("shap").setLevel(logging.WARNING)
    logging.getLogger("numba").setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


class PredictionAuditLog:
    """Append-only JSONL log of prediction requests and responses.

    Every scored application lands here so the Admin panel's audit trail and the
    drift monitor have a common source of truth.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else settings.log_dir / "predictions.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, request: Dict[str, Any], response: Dict[str, Any],
              model_version: str, latency_ms: float) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "model_version": model_version,
            "latency_ms": round(latency_ms, 2),
            "request": request,
            "response": response,
        }
        try:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=str) + "\n")
        except OSError as exc:  # never let logging break a prediction
            get_logger(__name__).warning("Could not write prediction log: %s", exc)

    def read_all(self) -> list[Dict[str, Any]]:
        if not self.path.exists():
            return []
        records = []
        with open(self.path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records


prediction_log = PredictionAuditLog()
