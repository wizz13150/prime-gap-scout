"""Actual Native memory/threshold plans; templates and legacy fixed800 plans are refused."""

from pathlib import Path
import json, subprocess
from pgn_native_contract import module_metadata, file_sha, bind_plan, require_new_configuration


def query_plan(worker, start, length, environment, child_options, gap_min=960, threshold_pin=None):
    meta = module_metadata(worker)
    before = meta["image_sha256"]
    command = [
        str(worker),
        "--plan",
        "--start",
        str(start),
        "--length",
        str(length),
        "--device",
        "0",
        "--gap-min",
        str(gap_min),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=30,
        **child_options,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError("Native plan query failed: " + result.stderr.strip())
    try:
        raw = json.loads(result.stdout)
    except ValueError:
        raise ValueError("Native plan is not valid JSON") from None
    after = file_sha(worker)
    if before != after:
        raise ValueError("Native image changed during plan query")
    return bind_plan(raw, meta, after, int(start), int(length), int(gap_min), threshold_pin)


def query_endpoints(worker, configuration, environment, child_options):
    f = require_new_configuration(configuration)
    start, end = int(configuration["start"]), int(configuration["end"])
    pin = f["threshold_policy"]
    gap = f["effective_gap_min"]
    first = query_plan(worker, start, 1, environment, child_options, gap, pin)
    last = query_plan(worker, end - 1, 1, environment, child_options, gap, pin)
    if not first["range_valid"] or not last["range_valid"]:
        raise ValueError(
            "Native origin/end/halo admission failed; no search launched: "
            + str(first.get("reason"))
            + " / "
            + str(last.get("reason"))
        )
    return last


def choose_plan(candidates, start, length, query):
    """candidates is [(K,path)]; query is injectable for pure CPU tests."""
    plans = []
    for profile, worker in sorted(candidates, reverse=True):
        plan = query(worker, start, length)
        if plan.get("profile_k") != profile:
            raise ValueError("Native binary/profile identity mismatch")
        plans.append((profile, worker, plan))
        if plan.get("range_valid") and plan.get("fits"):
            return {"worker": worker, "profile_k": profile, "length": length, "plan": plan}
    possible = [
        (int(plan.get("max_length_fit", 0)), profile, worker, plan)
        for profile, worker, plan in plans
        if plan.get("range_valid")
    ]
    if not possible or max(x[0] for x in possible) <= 0:
        reasons = "; ".join(str(x[2].get("reason", "no fit")) for x in plans)
        raise RuntimeError("No supported profile has a usable exact chunk: " + reasons)
    size, profile, worker, _ = max(possible, key=lambda item: (item[0], item[1]))
    size = min(length, size)
    checked = query(worker, start, size)
    if (
        not checked.get("range_valid")
        or not checked.get("fits")
        or checked.get("profile_k") != profile
    ):
        raise RuntimeError("Native proposed chunk did not pass an exact second plan")
    return {"worker": worker, "profile_k": profile, "length": size, "plan": checked}
