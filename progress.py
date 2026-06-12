"""Lightweight progress reporting for the GUI (no-op on the CLI)."""

from __future__ import annotations

_callback = None

# Stage weights for an overall 0..1 progress fraction
_STAGES = {
    "parse": (0.00, 0.05),
    "build": (0.05, 0.55),
    "process": (0.55, 0.85),
    "validate": (0.85, 0.90),
    "export": (0.90, 1.00),
}


def set_callback(callback):
    """callback(overall_fraction: float, message: str)"""
    global _callback
    _callback = callback


def report(stage: str, fraction: float = 0.0, message: str = ""):
    if _callback is None:
        return
    start, end = _STAGES.get(stage, (0.0, 1.0))
    overall = start + max(0.0, min(1.0, fraction)) * (end - start)
    try:
        _callback(overall, message)
    except Exception:
        pass
