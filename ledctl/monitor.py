from __future__ import annotations

import logging


def log_metric(name: str, value: float) -> None:
    """Lightweight metric logger placeholder."""
    message = f"metric {name}={value:.3f}"
    try:
        logging.info(message)
    except Exception as exc:
        # Last resort to avoid raising from monitoring paths
        print(message)  # noqa: T201
        print(f"monitoring-log-error: {exc}")  # noqa: T201


