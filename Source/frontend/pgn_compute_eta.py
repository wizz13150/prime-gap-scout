"""Forecast remaining computation from measured current-epoch throughput."""
import math
import re


def _integer(value):
    if isinstance(value, bool):
        raise ValueError("Boolean counter")
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]{0,159}", value):
        result = int(value)
    else:
        raise ValueError("Exact unsigned counter required")
    if result < 0:
        raise ValueError("Negative counter")
    return result


def forecast_seconds(state):
    """Never synthesize a rate from lifetime elapsed, pauses or error waits."""
    try:
        start, end = _integer(state.get("start")), _integer(state.get("end"))
        completed = _integer(state.get("position", 0))
        total = end - start
        if total <= 0 or completed > total:
            return None
        status = str(state.get("status", "READY")).split("|", 1)[0].strip()
        if status == "COMPLETE":
            return 0.0 if completed == total else None
        if status != "SEARCHING":
            return None
        key = next((key for key in ("eta_rate", "speed_rate", "rate") if key in state), None)
        if key is None or isinstance(state[key], bool):
            return None
        rate = float(state[key])
        if not math.isfinite(rate) or rate <= 0:
            return None
        # Subtract exact integers before any floating-point conversion. At
        # 95-bit starts, converting endpoints first loses the remaining tail.
        return (total - completed) / rate
    except (ValueError, TypeError, OverflowError):
        return None
