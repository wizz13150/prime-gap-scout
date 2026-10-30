"""Sticky, bounded search-start failures. This module never launches a process."""

from pathlib import Path
import datetime as dt, json, uuid


def remember_start_failure(context, error, stage, folder=None):
    record = {
        "schema": "PGN_START_FAILURE_V1",
        "id": str(uuid.uuid4()),
        "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "stage": str(stage),
        "message": str(error)[:8192],
        "configuration": dict(context.get("configuration") or {}),
    }
    target = (
        Path(folder or context.get("output_root") or ".").expanduser().resolve()
        / "last-start-error.json"
    )
    record["path"] = str(target)
    context["startup_error"] = record
    try:
        from pgn_session import atomic_bytes

        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_bytes(target, (json.dumps(record, indent=2, default=str) + "\n").encode("utf-8"))
    except (OSError, ValueError, TypeError) as problem:
        record["persistence_error"] = str(problem)
    return record


def restore_start_failure(context):
    p = Path(context.get("output_root") or ".").expanduser().resolve() / "last-start-error.json"
    try:
        if not p.is_file() or p.stat().st_size > 32768:
            return
        r = json.loads(p.read_text(encoding="utf-8"))
        cfg = r.get("configuration") or {}
        if (
            r.get("schema") == "PGN_START_FAILURE_V1"
            and isinstance(r.get("message"), str)
            and str(cfg.get("start")) == str(context.get("start"))
            and str(cfg.get("end")) == str(context.get("end"))
        ):
            context.setdefault("startup_error", r)
    except (OSError, ValueError, TypeError):
        pass


def start_failure_note(context):
    e = context.get("startup_error")
    if not isinstance(e, dict):
        return ""
    return (
        "SEARCH NOT STARTED / FAILED — "
        + str(e.get("stage", "start"))
        + "\n"
        + str(e.get("message", "Unknown failure"))
        + "\nRange and plans retained. Edit/retry explicitly. Details: "
        + str(e.get("path", "summary.log"))
    )
