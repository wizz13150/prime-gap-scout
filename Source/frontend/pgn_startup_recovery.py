"""Opening the same interrupted search never silently creates a duplicate run."""

from pathlib import Path


def recover_closed_sessions(output_root):
    """Import sealed orphan prefixes before drawing cards; no GPU discovery."""
    from pgn_sessions_browser import discover_sessions
    from pgn_session import SessionStore, SessionControllerLock
    from pgn_owner_recovery import recover

    result = []
    for item in discover_sessions([str(Path(output_root).resolve())])[:32]:
        if item.readonly_mirror or not (item.folder / "native-owner-recovery.json").is_file():
            continue
        lock = None
        store = None
        try:
            lock = SessionControllerLock(item.folder)
            store = SessionStore.load(item.folder)
            if recover(store):
                result.append(str(item.folder))
        except (OSError, ValueError, RuntimeError):
            # Keep the original metadata/trusted CP. Explicit Resume displays
            # the exact rejection instead of silently starting another range.
            pass
        finally:
            if store:
                store.close()
            if lock:
                lock.release()
    return result


def pending_same_range(args, end, output_root):
    if getattr(args, "resume", None) or getattr(args, "headless", False):
        return None
    if any(getattr(args, name, False) for name in ("list_gpus", "self_test", "fermat_diagnostic")):
        return None
    from pgn_sessions_browser import discover_sessions

    for item in discover_sessions([str(Path(output_root).resolve())]):
        if getattr(item, "readonly_mirror", False):
            continue
        config = item.configuration
        if config.get("native_protocol") != "PGN_NATIVE_GAP_RUNTIME_V1":
            continue
        if int(config.get("start", -1)) != int(args.start) or int(config.get("end", -1)) != int(
            end
        ):
            continue
        status = str(item.status).upper()
        if status not in ("COMPLETE", "CHUNK_COMPLETE", "DIAGNOSTIC_COMPLETE"):
            return str(item.folder)
    return None
