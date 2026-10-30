"""Coordinator-only durable NEXT FIFO, compatible with V7's next_range WAL."""

from pathlib import Path
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
import hashlib, json, math, re, uuid
from pgn_session import SessionStore, SessionControllerLock


def configuration_hash(config):
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _integer(value):
    if isinstance(value, (bool, float)):
        raise ValueError("Use an exact whole number, not a binary float")
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("Use an exact whole number") from error
    if not number.is_finite() or number.adjusted() > 39 or number != number.to_integral_value():
        raise ValueError("Use an exact bounded whole number")
    return int(number)


def _destination(parent, entry):
    identity = entry.get("child_session_id")
    if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{32}", identity):
        raise ValueError("Untrusted NEXT child session ID")
    output_parent = parent.folder.parent.resolve()
    expected = (output_parent / ("pgn68-next-" + identity)).resolve()
    if (
        expected.parent != output_parent
        or expected.name != "pgn68-next-" + identity
        or Path(entry.get("folder", "")).resolve() != expected
    ):
        raise ValueError("Untrusted NEXT output path")
    return expected


def _queue(parent):
    head = parent.meta.get("next_range")
    if not head:
        return []
    if not isinstance(head, dict):
        raise ValueError("Untrusted NEXT queue")
    following = head.get("following", [])
    if not isinstance(following, list):
        raise ValueError("Untrusted NEXT queue tail")
    rows = [deepcopy(head)] + deepcopy(following)
    rows[0].pop("following", None)
    predecessor = parent.meta["session_id"]
    end = _integer(parent.meta["configuration"]["end"])
    ids = set()
    for i, entry in enumerate(rows):
        if not isinstance(entry, dict) or "following" in entry:
            raise ValueError("Nested NEXT queue is invalid")
        _destination(parent, entry)
        identity = entry["child_session_id"]
        if identity in ids:
            raise ValueError("Duplicate NEXT child session ID")
        ids.add(identity)
        if entry.get("status") not in (("PENDING", "ACTIVE") if i == 0 else ("PENDING",)):
            raise ValueError("Invalid NEXT queue status")
        config = entry.get("configuration")
        if not isinstance(config, dict) or configuration_hash(config) != entry.get(
            "configuration_sha256"
        ):
            raise ValueError("NEXT configuration binding changed")
        start, stop = _integer(config["start"]), _integer(config["end"])
        from pgn_native_contract import admitted_range, require_new_configuration

        admitted_range(start, stop)
        require_new_configuration(config)
        if entry.get("parent_session_id", predecessor) != predecessor:
            raise ValueError("NEXT predecessor/session binding changed")
        entry["parent_session_id"] = predecessor
        predecessor = identity
        end = stop
    return rows


def _pack(rows):
    if not rows:
        return {}
    head = deepcopy(rows[0])
    head["following"] = deepcopy(rows[1:])
    return head


def _publish(store, rows):
    rows = _queue(
        SimpleNamespace(folder=store.folder, meta=dict(store.meta, next_range=_pack(rows)))
    )
    entry = _pack(rows)
    record = {"sequence": store.sequence + 1, "type": "next_range", "entry": entry}
    if len(json.dumps(record, separators=(",", ":")).encode()) + 1 > 1024 * 1024:
        raise ValueError("NEXT queue exceeds the existing durable journal record limit")
    store.append("next_range", entry=entry)
    store.meta["next_range"] = entry
    store.save()


def pending_ranges(parent):
    """Read-only defensive copies; excludes a head already activated."""
    rows = _queue(parent)
    return (
        []
        if rows and rows[0]["status"] == "ACTIVE"
        else [deepcopy(entry) for entry in rows if entry["status"] == "PENDING"]
    )


def activation_entry(parent, selected_child=None):
    """Read-only bound target; retries may follow the SAME durable ACTIVE head."""
    rows = _queue(parent)
    if not rows:
        raise ValueError("No durable NEXT entry")
    if selected_child is not None:
        if not isinstance(selected_child, str) or not re.fullmatch(r"[0-9a-f]{32}", selected_child):
            raise ValueError("Invalid queued child ID")
        target = next((e for e in rows if e["child_session_id"] == selected_child), None)
        if target is None:
            raise ValueError("Queued range ID is not owned by this session")
    else:
        target = rows[0]
    if rows[0]["status"] == "ACTIVE":
        if target["child_session_id"] != rows[0]["child_session_id"]:
            raise ValueError("Queue already transferred to its active child")
        if not SessionStore.exists(_destination(parent, target)):
            raise ValueError(
                "ACTIVE child files are missing; recover explicitly, never recreate silently"
            )
    return deepcopy(target)


def queue_tail_end(parent):
    """Exact start for the next appended range, with no rebase or clamping."""
    rows = _queue(parent)
    return _integer((rows[-1]["configuration"] if rows else parent.meta["configuration"])["end"])


def _configuration(parent, base, values, gpu_index, gpu_uuid, preserve=False):
    allowed = {
        "start",
        "end",
        "length",
        "min_gap",
        "count_gap",
        "detail_gap",
        "bins",
        "report_top",
        "display_rows",
        "target_merit",
        "name",
        "profile",
        "chunk_length",
        "output",
        "gpu",
        "queued",
        "reflow_following",
        "min_gap_requested",
        "count_gap_requested",
        "detail_gap_requested",
        "threshold_policy",
    }
    if set(values) - allowed:
        raise ValueError("Unknown NEXT fields: " + ", ".join(sorted(set(values) - allowed)))
    config = deepcopy(base)
    start, end = _integer(values.get("start", config["start"])), _integer(
        values.get("end", config["end"])
    )
    if values.get("length") not in (None, "") and _integer(values["length"]) != end - start:
        raise ValueError("NEXT length/end disagree")
    from pgn_native_contract import fields, require_new_configuration, rebase_pin

    require_new_configuration(parent.meta["configuration"])
    selected = _integer(values.get("gpu", gpu_index))
    if selected < 0:
        raise ValueError("Invalid NEXT GPU index")
    minimum = values.get(
        "min_gap_requested",
        values.get("min_gap", config.get("min_gap_requested", config["min_gap"])),
    )
    count = values.get(
        "count_gap_requested", values.get("count_gap", config.get("count_gap_requested"))
    )
    detail = values.get(
        "detail_gap_requested", values.get("detail_gap", config.get("detail_gap_requested"))
    )
    frozen = None
    oldpin = config.get("threshold_policy")
    if (
        preserve
        and oldpin
        and minimum == oldpin["requested"]
        and count == oldpin["count_override"]
        and detail == oldpin["detail_override"]
    ):
        frozen = rebase_pin(oldpin, start, end)
    resolved = fields(start, end, minimum, count, detail, frozen)
    config.update(start=str(start), end=str(end), gpu_index=selected, **resolved)
    if "display_rows" in values:
        from pgn_ui_options import display_rows

        try:
            config["display_rows"] = display_rows(values["display_rows"])
        except Exception as error:
            raise ValueError(str(error)) from error
    for key in ("bins", "report_top"):
        if key in values:
            number = _integer(values[key])
            if not 1 <= number <= 1000000:
                raise ValueError("Invalid NEXT " + key)
            config[key] = number
    if "target_merit" in values:
        goal = float(values["target_merit"])
        if not math.isfinite(goal) or goal <= 0:
            raise ValueError("Invalid NEXT target merit")
        config["target_merit"] = goal
    if "name" in values:
        config["name"] = str(values["name"])
    if "profile" in values:
        profile = str(values["profile"])
        if profile not in ("auto", "8", "16", "32", "64"):
            raise ValueError("Invalid NEXT profile")
        config["profile"] = profile
    if "chunk_length" in values:
        raw = values["chunk_length"]
        chunk = None if raw in (None, "") else _integer(raw)
        if chunk is not None and chunk <= 0:
            raise ValueError("Invalid NEXT chunk length")
        config["chunk_length"] = chunk
    if (
        values.get("output") not in (None, "")
        and Path(values["output"]).expanduser().resolve() != parent.folder.parent.resolve()
    ):
        raise ValueError(
            "NEXT output must stay in this session output parent; use NEW for another output folder"
        )
    selected_uuid = (
        gpu_uuid
        if gpu_uuid is not None
        else config.get("gpu_uuid", parent.meta.get("device", {}).get("uuid"))
    )
    if selected_uuid is not None:
        if not isinstance(selected_uuid, str) or not selected_uuid:
            raise ValueError("Invalid NEXT GPU UUID")
        config["gpu_uuid"] = selected_uuid
    return config


def enqueue_next(parent, values, gpu_index, gpu_uuid=None):
    rows = _queue(parent)
    if rows and rows[0]["status"] == "ACTIVE":
        raise ValueError(
            "This queue was transferred to its activated child. Add from that session, or save a separate Ready plan."
        )
    config = _configuration(parent, parent.meta["configuration"], values, gpu_index, gpu_uuid)
    start, end = _integer(config["start"]), _integer(config["end"])
    # Duplicate submission is checked before tail adjacency, including retries
    # of an earlier item after more items have been appended.
    for entry in rows:
        previous = entry["configuration"]
        if (_integer(previous["start"]), _integer(previous["end"])) == (start, end):
            if previous == config:
                return deepcopy(entry)
            raise ValueError("The same NEXT interval already has a different configuration")
    expected = queue_tail_end(parent)
    if start != expected:
        raise ValueError("NEXT must begin at the last queued end; use NEW for another start")
    child_id = uuid.uuid4().hex
    folder = parent.folder.parent / ("pgn68-next-" + child_id)
    entry = {
        "status": "PENDING",
        "native_admission": "PENDING_ACTUAL_START",
        "child_session_id": child_id,
        "folder": str(folder),
        "parent_session_id": rows[-1]["child_session_id"] if rows else parent.meta["session_id"],
        "configuration": config,
        "configuration_sha256": configuration_hash(config),
    }
    rows.append(entry)
    _publish(parent, rows)
    return deepcopy(entry)


def _mutable(parent, rows):
    if (parent.meta.get("next_range") or {}).get("status") == "ACTIVE":
        raise ValueError(
            "This queue was transferred to its activated child; edit that session queue instead."
        )
    for entry in rows:
        if entry["status"] != "PENDING":
            raise ValueError("An ACTIVE NEXT cannot be edited or removed")
        folder = _destination(parent, entry)
        if any(
            (folder / name).exists()
            for name in ("session.json", "session-index.sqlite3", "session-events.jsonl")
        ):
            raise ValueError(
                "NEXT child is already materialized; recover that activation before editing it"
            )


def _reflow(parent, rows, first, allowed):
    for i in range(first, len(rows)):
        start = (
            _integer(rows[i - 1]["configuration"]["end"])
            if i
            else _integer(parent.meta["configuration"]["end"])
        )
        entry = rows[i]
        old = entry["configuration"]
        prior_start = _integer(old["start"])
        predecessor = rows[i - 1]["child_session_id"] if i else parent.meta["session_id"]
        if start != prior_start or entry["parent_session_id"] != predecessor:
            if not allowed:
                entry["parent_session_id"] = predecessor
                continue
            _mutable(parent, [entry])
            config = deepcopy(old)
            config.update(start=str(start), end=str(start + _integer(old["end"]) - prior_start))
            from pgn_native_contract import fields, rebase_pin

            frozen = rebase_pin(old["threshold_policy"], int(config["start"]), int(config["end"]))
            config.update(fields(int(config["start"]), int(config["end"]), pin=frozen))
            entry.update(
                configuration=config,
                configuration_sha256=configuration_hash(config),
                parent_session_id=predecessor,
            )


def update_pending(parent, child_session_id, values, gpu_index, gpu_uuid=None):
    rows = _queue(parent)
    index = next((i for i, e in enumerate(rows) if e["child_session_id"] == child_session_id), None)
    if index is None:
        raise ValueError("No matching pending NEXT")
    entry = rows[index]
    _mutable(parent, [entry])
    old = entry["configuration"]
    config = _configuration(parent, old, values, gpu_index, gpu_uuid, preserve=True)
    if _integer(config["start"]) != _integer(old["start"]):
        raise ValueError("A pending NEXT start is fixed by its predecessor")
    entry.update(configuration=config, configuration_sha256=configuration_hash(config))
    _reflow(parent, rows, index + 1, values.get("reflow_following") is True)
    _publish(parent, rows)
    return deepcopy(rows[index])


def remove_pending(parent, child_session_id, reflow_following=False):
    rows = _queue(parent)
    index = next((i for i, e in enumerate(rows) if e["child_session_id"] == child_session_id), None)
    if index is None:
        raise ValueError("No matching pending NEXT")
    _mutable(parent, [rows[index]])
    removed = rows.pop(index)
    _reflow(parent, rows, index, reflow_following is True)
    _publish(parent, rows)
    return deepcopy(removed)


def _same_identity(left, right):
    return all(
        left.get(key) == right.get(key)
        for key in (
            "child_session_id",
            "folder",
            "parent_session_id",
            "configuration",
            "configuration_sha256",
        )
    )


def _transfer(child, incoming):
    current = _queue(child)
    for old, new in zip(current, incoming):
        if not _same_identity(old, new):
            raise ValueError("Existing child NEXT chain conflicts with the parent transfer")
    # A repeated parent activation cannot erase an extension already queued by
    # the child coordinator, nor reset its ACTIVE head back to PENDING.
    if len(current) >= len(incoming):
        return
    merged = current + deepcopy(incoming[len(current) :])
    _publish(child, merged)


def activate_next(
    parent, actual_device, after_create=None, *, selected_child=None, allow_incomplete=False
):
    rows = _queue(parent)
    if not rows:
        raise ValueError("No durable NEXT entry")
    config = parent.meta["configuration"]
    if allow_incomplete:
        instance = (parent.meta.get("current_chunk") or {}).get("instance") or {}
        if instance and not instance.get("closed"):
            raise ValueError("Current worker must close before switching a queued range")
        if parent.meta.get("state") in ("FAILED", "UNKNOWN"):
            raise ValueError("Resolve failed current session before queued activation")
    elif (
        parent.meta["positions"] != _integer(config["end"]) - _integer(config["start"])
        or parent.meta.get("current_chunk") is not None
        or parent.meta.get("state") in ("FAILED", "UNKNOWN")
    ):
        raise ValueError("Current range is not complete; NEXT cannot launch")
    chosen = activation_entry(parent, selected_child)
    if (
        chosen["configuration"].get("gpu_uuid")
        and actual_device.get("uuid") != chosen["configuration"]["gpu_uuid"]
    ):
        raise ValueError("NEXT actual GPU UUID differs from the queued selection")
    if selected_child:
        index = next(
            (i for i, e in enumerate(rows) if e["child_session_id"] == selected_child), None
        )
        if index is None:
            raise ValueError("Queued range ID is not owned by this session")
        if rows[0]["status"] == "ACTIVE" and index != 0:
            raise ValueError("Queue already transferred to its active child")
        if index:
            chosen = rows.pop(index)
            rows.insert(0, chosen)
            predecessor = parent.meta["session_id"]
            for e in rows:
                e["parent_session_id"] = predecessor
                predecessor = e["child_session_id"]
            _publish(parent, rows)
    entry = rows[0]
    expected = _destination(parent, entry)
    expected.mkdir(parents=True, exist_ok=True)
    lock = SessionControllerLock(expected)
    child = None
    try:
        if SessionStore.exists(expected):
            child = SessionStore.load(expected)
            if (
                child.meta["session_id"] != entry["child_session_id"]
                or child.configuration_hash() != entry["configuration_sha256"]
            ):
                raise ValueError("Existing NEXT child identity/configuration conflicts")
            if (
                child.meta.get("parent_session_id", parent.meta["session_id"])
                != parent.meta["session_id"]
            ):
                raise ValueError("Existing NEXT child belongs to another parent")
        else:
            child = SessionStore.create(
                expected,
                entry["configuration"],
                actual_device,
                session_id=entry["child_session_id"],
            )
        if child.meta.get("device", {}).get("uuid") != actual_device.get("uuid"):
            raise ValueError("Existing NEXT child GPU identity conflicts")
        if child.meta.get("parent_session_id") != parent.meta["session_id"]:
            child.meta["parent_session_id"] = parent.meta["session_id"]
            child.save()
        _transfer(child, rows[1:])
    finally:
        if child is not None:
            child.close()
        lock.release()
    # Existing CPU-only seam: child and transferred tail are durable before
    # parent activation. Retrying after this seam preserves IDs and extensions.
    if after_create:
        after_create()
    if rows[0]["status"] != "ACTIVE":
        rows[0]["status"] = "ACTIVE"
        _publish(parent, rows)
    return expected
