from pgn_terminal_input import terminal_size

"""Terminal page controllers. Mirrors are read-only; no session/GPU launch here."""
from pathlib import Path
import math, os, shutil, sys, time
from pgn_input import TerminalInput, form
from pgn_sessions_browser import ArrowList, discover_sessions, session_from_folder
from pgn_ui_terminal import paint, cursor
from pgn_launcher_edit import LauncherDraft
from pgn_launcher import GROUPS


def _project(name, *args, **kwargs):
    import pgn_ui_views

    return getattr(pgn_ui_views, name)(*args, **kwargs)


def render_arrow_list(*args, **kwargs):
    return _project("render_arrow_list", *args, **kwargs)


def render_search(*args, **kwargs):
    return _project("render_search", *args, **kwargs)


def render_details(*args, **kwargs):
    return _project("render_details", *args, **kwargs)


def render_launcher(*args, **kwargs):
    return _project("render_launcher", *args, **kwargs)


def render_report(*args, **kwargs):
    return _project("render_report", *args, **kwargs)


def event(events=None):
    from pgn_ui_service import refresh_context_snapshot

    refresh_context_snapshot()
    if events is not None:
        from pgn_interaction import translate

        return translate(next(events))
    with TerminalInput() as reader:
        return reader.read()


def catalog_sessions(context):
    roots = context.get("session_roots", [])
    if context.get("output_root"):
        roots = [context["output_root"], *roots]
    signature = (tuple(map(str, roots)), repr(context.get("sessions_catalog")))
    state = context.setdefault("_ui_state", {})
    cached = state.get("_session_catalog_cache")
    now = time.monotonic()
    if cached and cached[0] == signature and now - cached[1] < 0.5:
        context["catalog_warning"] = cached[3] if len(cached) > 3 else ""
        return cached[2]
    errors = []
    rows = discover_sessions(roots, catalog=context.get("sessions_catalog"), errors=errors)
    context["session_catalog_errors"] = errors
    warning = (
        (
            "Unreadable "
            + Path(errors[0]["path"]).name
            + ": "
            + errors[0]["reason"]
            + (" (" + str(len(errors)) + " notices)" if len(errors) > 1 else "")
        )
        if errors
        else ""
    )
    context["catalog_warning"] = warning
    state["_session_catalog_cache"] = (signature, now, rows, warning)
    return rows


def selected_session(context, sessions=None):
    if sessions is None:
        sessions = catalog_sessions(context)
    wanted = context.get("selected_session_id")
    selected = next(
        (item for item in sessions if item.session_id == wanted), sessions[0] if sessions else None
    )
    if selected:
        context["selected_session_id"] = selected.session_id
        info = selected.context()
        info["next_range"] = resolve_next(info.get("next_range"), sessions)
        context["selected_session"] = info
        context.setdefault("_ui_state", {})["selected_session_id"] = selected.session_id
    return selected


def resolve_next(entry, sessions=()):
    if not entry:
        return None
    result = dict(entry)
    child = next(
        (item for item in sessions if item.session_id == entry.get("child_session_id")), None
    )
    if child:
        result["resolved_status"] = child.status
        result["resolved_origin"] = child.host
    else:
        folder = Path(str(entry.get("folder", "")))
        if folder.is_dir() and (folder / "run.json").is_file():
            try:
                from pgn_sessions_browser import read_json

                result["resolved_status"] = read_json(folder / "run.json").get(
                    "status", "SAVED SNAPSHOT"
                )
            except (OSError, ValueError):
                pass
    if "resolved_status" not in result:
        result["resolved_status"] = (
            "PENDING" if entry.get("status") == "PENDING" else "PREPARED / saved pointer"
        )
    return result


def refresh_context(context):
    from pgn_ui_service import refresh_context_snapshot

    refresh_context_snapshot(context)
    sessions = catalog_sessions(context)
    selected_session(context, sessions)
    if context.get("active_session"):
        active = dict(context["active_session"])
        active["next_range"] = resolve_next(active.get("next_range"), sessions)
        context["active_session"] = active
    context["next_range"] = resolve_next(context.get("next_range"), sessions)
    from pgn_range_eta import saved_session_measurement, retain

    evidence = dict(context.get("eta_evidence") or {})
    evidence.setdefault("gpu_uuid", context.get("gpu_uuid"))
    if evidence.get("gpu_uuid") and not evidence.get("worker_paths"):
        known_gpu = next(
            (item.gpu for item in sessions if item.gpu.get("uuid") == evidence["gpu_uuid"]), {}
        )
        evidence.setdefault("gpu_index", known_gpu.get("index", context.get("gpu_index", 0)))
        cc = context.get("compute_capability") or (
            str(known_gpu["cc_major"]) + "." + str(known_gpu["cc_minor"])
            if "cc_major" in known_gpu
            else None
        )
        if cc:
            from pgn68 import resolve_worker

            paths = {}
            for profile in (8, 16, 32, 64):
                try:
                    paths[str(profile)] = str(
                        resolve_worker(None, "sm" + str(cc).replace(".", ""), profile)
                    )
                except RuntimeError:
                    pass
            evidence["worker_paths"] = paths
    history = list(evidence.get("history") or [])
    cache = context.setdefault("_ui_state", {}).setdefault("eta_saved_cache", {})
    for saved in sessions[:32]:
        if saved.gpu.get("uuid") != evidence.get("gpu_uuid"):
            continue
        report = saved.folder / (
            "GapReport_details_ge"
            + str(saved.configuration.get("detail_gap", saved.configuration.get("min_gap", 960)))
            + ".txt"
        )
        try:
            stamp = report.stat().st_mtime_ns
        except OSError:
            stamp = 0
        cache_key = (
            saved.session_id,
            saved.run.get("positions"),
            saved.run.get("active_seconds"),
            saved.metadata.get("journal_sequence"),
            stamp,
        )
        if cache_key not in cache:
            cache[cache_key] = saved_session_measurement(saved)
        history = retain(history, cache[cache_key])
    evidence["history"] = history
    if len(cache) > 64:
        cache.clear()
    context["eta_evidence"] = evidence
    from pgn_draft_plans import load

    try:
        context["saved_drafts"] = load(context)
        context.pop("draft_plans_error", None)
    except (OSError, ValueError, KeyError) as problem:
        context["draft_plans_error"] = str(problem)
    from pgn_workspace import build_workspace

    context["workspace"] = build_workspace(
        context,
        sessions,
        columns=max(20, terminal_size(fallback=(100, 30)).columns - 12),
        focus=context.get("workspace_focus"),
    )
    return context


def session_row(item, context=None):
    from pgn_ui_views import range_text, length_text, gpu_short, date_short

    active = (context or {}).get("active_session") or {}
    current = active.get("session_id") == item.session_id
    position = int(active.get("position", item.position)) if current else item.position
    status = (
        ("Running" if active.get("job_active") else str(active.get("status", item.status)).title())
        if current
        else item.status.title()
    )
    length = item.end - item.start
    percent = 100 * position / length if length else 0
    return {
        "path": str(item.folder),
        "label": f'{date_short(item.date)}  ·  {status}  ·  {length_text(length)}  ·  {gpu_short(item.gpu.get("model"))}  ·  {percent:.1f}%',
        "detail": range_text(item.start, item.end),
    }


def open_path_page(context, path, events=None):
    from pgn_menu import open_local

    try:
        open_local(path)
    except (OSError, RuntimeError) as error:
        paint(
            render_arrow_list(
                "Open problem",
                [{"label": str(error), "detail": "No data has been changed."}],
                0,
                0,
                1,
                context,
                "Esc Back",
            )
        )
        while event(events) not in ("ESC", "0"):
            pass


def files_page(context, session=None, events=None):
    # Normal result navigation is session folders, never an internal-file listing.
    sessions = catalog_sessions(context)
    state = context.setdefault("_ui_state", {}).setdefault("result_folders", {})
    filter_text = state.get("filter", "")
    all_sessions = sessions

    def matches(item, text):
        row = session_row(item)
        return text.lower() in (row["label"] + " " + row["detail"]).lower()

    model = ArrowList(
        [item for item in sessions if matches(item, filter_text)],
        page_size=max(3, (terminal_size(fallback=(100, 30)).lines - 12) // 2),
    )
    wanted = state.get("session_id") or (
        session.session_id if session else context.get("selected_session_id")
    )
    model.selected = next(
        (i for i, item in enumerate(model.entries) if item.session_id == wanted), 0
    )
    model.offset = state.get("offset", 0)
    model.move("IGNORE")
    while True:
        model.page_size = max(3, (terminal_size(fallback=(100, 30)).lines - 12) // 2)
        paint(
            render_arrow_list(
                "Result folders",
                [session_row(item) for item in model.visible()],
                model.selected,
                model.offset,
                len(model.entries),
                context,
                "↑↓ Select · Enter Open folder · PgUp/PgDn/Home/End · / Filter",
            )
        )
        pressed = event(events)
        if pressed in ("ESC", "0"):
            state.update(
                session_id=model.current().session_id if model.current() else None,
                offset=model.offset,
                filter=filter_text,
            )
            return
        if pressed in ("UP", "DOWN", "PGUP", "PGDN", "HOME", "END"):
            model.move(pressed)
        elif pressed == "ENTER" and model.current():
            item = model.current()
            context["selected_session_id"] = item.session_id
            context["selected_session"] = item.context()
            context["_ui_state"]["selected_session_id"] = item.session_id
            open_path_page(context, item.folder, events)
        elif pressed == "/":
            value = form(
                "Filter result folders",
                [
                    (
                        "filter",
                        "Filter text",
                        filter_text,
                        "Date, status, GPU or scientific range. Esc leaves the filter unchanged.",
                    )
                ],
                lambda values: values["filter"],
                context=context,
            )
            if value is not None:
                filter_text = value
                model = ArrowList(
                    [item for item in all_sessions if matches(item, value)], model.page_size
                )


def sessions_page(context, events=None):
    sessions = catalog_sessions(context)
    model = ArrowList(
        sessions, page_size=max(3, (terminal_size(fallback=(100, 30)).lines - 12) // 2)
    )
    state = context.setdefault("_ui_state", {}).get("sessions")
    if state:
        model.selected = min(state["selected"], max(0, len(sessions) - 1))
        model.offset = state["offset"]
    filter_text = ""
    all_sessions = sessions
    while True:
        painted_sessions = tuple((item.session_id, str(item.folder)) for item in model.entries)
        entries = [session_row(item, context) for item in model.visible()]
        from pgn_interaction import focus_panel

        focus_panel("list")
        paint(
            render_arrow_list(
                "My sessions",
                entries,
                model.selected,
                model.offset,
                len(model.entries),
                context,
                "↑↓ Select · Enter Open · R Open results · / Filter · O Other folder"
                + (" · " + context["catalog_warning"] if context.get("catalog_warning") else ""),
            )
        )
        pressed = event(events)
        from pgn_interaction import pointer

        routed = pointer()
        clicked_results = None
        if routed is not None and routed.target in ("list", "sessions"):
            if routed.key == "SCROLL":
                model.selected = max(0, min(len(model.entries) - 1, model.selected + routed.dy))
                model.move("IGNORE")
                pressed = "TICK"
            elif routed.index is not None and 0 <= int(routed.index) < len(painted_sessions):
                model.selected = int(routed.index)
                if pressed.lower() == "r":
                    clicked_results = painted_sessions[model.selected]
        if pressed in ("ESC", "0"):
            context["_ui_state"]["sessions"] = {"selected": model.selected, "offset": model.offset}
            return None
        if pressed in ("UP", "DOWN", "PGUP", "PGDN", "HOME", "END"):
            model.move(pressed)
        elif pressed == "ENTER" and model.current():
            selected = model.current()
            context["selected_session_id"] = selected.session_id
            context["selected_session"] = selected.context()
            context.setdefault("_ui_state", {})["selected_session_id"] = selected.session_id
            result = session_details(context, selected, events)
            if result:
                return result
        elif pressed.lower() == "r" and model.current():
            open_path_page(
                context, clicked_results[1] if clicked_results else model.current().folder, events
            )
        elif pressed == "/":
            value = form(
                "Filter sessions",
                [
                    (
                        "filter",
                        "Filter text",
                        filter_text,
                        "Matches status, GPU, origin, ID or range.",
                    )
                ],
                lambda values: values["filter"],
                context=context,
            )
            if value is not None:
                filter_text = value
                model = ArrowList(
                    [
                        item
                        for item in all_sessions
                        if value.lower()
                        in (
                            " ".join(
                                (
                                    item.status,
                                    item.host,
                                    item.session_id,
                                    item.gpu.get("model", ""),
                                    str(item.start),
                                    str(item.end),
                                )
                            )
                        ).lower()
                    ],
                    model.page_size,
                )
        elif pressed.lower() == "o":
            value = form(
                "Other local session folder",
                [
                    (
                        "folder",
                        "Session folder",
                        "",
                        "Choose a real local R5 folder; no shell or remote access.",
                    )
                ],
                lambda values: str(Path(values["folder"]).expanduser()),
                context=context,
            )
            if value:
                try:
                    local = session_from_folder(value)
                    context.setdefault("session_roots", []).append(str(local.folder))
                    context["selected_session_id"] = local.session_id
                    context["selected_session"] = local.context()
                    result = session_details(context, local, events)
                    if result:
                        return result
                except (OSError, ValueError, KeyError):
                    pass


def session_details(context, session, events=None):
    from pgn_menu import MenuAction

    while True:
        active = context.get("active_session") or {}
        live = active.get("session_id") == session.session_id and active.get("job_active")
        primary = (
            "Return to live results"
            if live
            else (
                "Resume" if session.resumable and not context.get("browser_only") else "View report"
            )
        )
        context["_session_primary_action"] = primary
        paint(render_details(session, context))
        pressed = event(events)
        if pressed in ("ESC", "0"):
            return None
        if pressed == "ENTER":
            if live:
                return MenuAction("return")
            if primary == "Resume":
                return MenuAction("resume", {"folder": str(session.folder)})
            results_page(context, session, events)
        elif pressed.lower() in ("r", "f"):
            open_path_page(context, session.folder, events)
        elif pressed.lower() == "c":
            counts = next(
                (
                    item["path"]
                    for item in session.entries()
                    if Path(item["path"]).name.startswith("counts_")
                    and str(item["path"]).endswith(".csv")
                ),
                None,
            )
            if counts:
                open_path_page(context, counts, events)


def results_page(context, session, events=None):
    # Actual report content, not a simulated dashboard or a new job.
    entries = session.entries()
    report = next(
        (Path(item["path"]) for item in entries if Path(item["path"]).name.startswith("GapReport")),
        None,
    )
    lines = (
        report.read_text(encoding="utf-8").splitlines()
        if report and report.stat().st_size <= 1024 * 1024
        else ["No actual report file was found."]
    )
    model = ArrowList(
        [{"label": line, "detail": ""} for line in lines],
        page_size=max(3, terminal_size(fallback=(100, 30)).lines - 17),
    )
    while True:
        from pgn_interaction import focus_panel

        focus_panel("report")
        paint(
            render_report(
                [item["label"] for item in model.visible()],
                model.selected,
                model.offset,
                len(model.entries),
                context,
            )
        )
        pressed = event(events)
        from pgn_interaction import apply_pointer

        pressed = apply_pointer(model, "report", pressed)
        if pressed in ("ESC", "0"):
            return
        if pressed in ("UP", "DOWN", "PGUP", "PGDN", "HOME", "END"):
            model.move(pressed)
        elif pressed.lower() in ("r", "f"):
            open_path_page(context, session.folder, events)


def default_draft(context):
    from pgn_ui_workflow import new_defaults

    return new_defaults(context)


def edit_search(context, draft, kind="NEW"):
    from pgn_menu import integer

    fields = [
        ("start", "Start", str(draft["start"]), "Exact integer or scientific notation."),
        (
            "length",
            "Length",
            str(draft["length"]),
            "Set Length OR End. Ctrl+U clears;0 remains a number.",
        ),
        ("end", "End (optional)", "", "Auto is shown while Length is set."),
        (
            "min_gap",
            "MIN_GAP",
            str(draft["min_gap"]),
            "New session only. Current filters stay immutable.",
        ),
        (
            "gpu",
            "GPU index",
            str(draft["gpu"]),
            "Actual local GPU selection is validated by the backend.",
        ),
        ("bins", "Count bins", str(draft["bins"]), "1..1000000; complete CSV keeps every count."),
        (
            "report_top",
            "Human report top",
            str(draft["report_top"]),
            "Detailed human limit, default100.",
        ),
        (
            "target_merit",
            "Display merit goal",
            str(draft["target_merit"]),
            "Visual positive finite goal only.",
        ),
    ]

    def validate(values):
        start = integer(values["start"])
        if bool(values["length"]) == bool(values["end"]):
            raise ValueError("Fill exactly one of Length or End.")
        end = integer(values["end"]) if values["end"] else start + integer(values["length"])
        if not (1 << 66) <= start < end <= (1 << 95):
            raise ValueError(
                "67..95-bit range required; actual Native plan also checks low64 window and halo."
            )
        result = {name: integer(values[name]) for name in ("gpu", "bins", "report_top")}
        from pgn_native_contract import requested_gap

        result["min_gap"] = requested_gap(values["min_gap"])
        # MIN_GAP Auto/manual has already been validated by the canonical contract.
        if not 1 <= result["bins"] <= 1000000 or not 1 <= result["report_top"] <= 1000000:
            raise ValueError("Bins/report top must be1..1000000.")
        goal = float(values["target_merit"])
        if not math.isfinite(goal) or goal <= 0:
            raise ValueError("Merit goal must be positive finite.")
        return dict(result, start=start, end=end, length=end - start, target_merit=goal)

    return form("Search ranges > " + kind + " range", fields, validate, context=context)


def search_page(context, events=None):
    return workspace_page(context, events=events)


def workspace_page(context, events=None):
    from pgn_parameter_editor import parameter_editor, prepare_browser_queue
    from pgn_workspace import build_workspace, range_cards
    from pgn_interaction import focus_panel, pointer
    from pgn_terminal_input import bounded_scroll
    from pgn_menu import MenuAction
    from pgn_ui_views import range_text, length_text

    state = context.setdefault("_ui_state", {}).setdefault("workspace", {})
    selected = state.get("selected", 0)
    offset = state.get("offset", 0)
    manual = False
    message = None
    while True:
        refresh_context(context)
        workspace = build_workspace(
            context,
            catalog_sessions(context),
            columns=max(20, terminal_size(fallback=(100, 30)).columns - 12),
            focus=context.get("workspace_focus"),
        )
        tasks = range_cards(workspace)
        focus_id = state.pop("focus_id", None)
        if focus_id:
            selected = next(
                (index for index, item in enumerate(tasks) if item["id"] == focus_id), selected
            )
            manual = False
        if context.get("draft_plans_error"):
            message = "Local drafts unavailable: " + context["draft_plans_error"]
        elif context.get("catalog_warning"):
            message = context["catalog_warning"]
        workspace["tasks"] = tasks
        context["workspace"] = workspace
        selected = min(selected, max(0, len(tasks) - 1))
        page_size = max(2, (terminal_size(fallback=(100, 30)).lines - 17) // 3)
        if not manual:
            if selected < offset:
                offset = selected
            if selected >= offset + page_size:
                offset = selected - page_size + 1
        focus_panel("workspace")
        import pgn_ui_views

        renderer = getattr(pgn_ui_views, "render_workspace", None)
        if callable(renderer):
            paint(renderer(context, workspace, selected, offset, message))
        else:
            rows = [
                {
                    "label": item["status"] + " · " + length_text(item["end"] - item["start"]),
                    "detail": range_text(item["start"], item["end"]),
                }
                for item in tasks[offset : offset + page_size]
            ]
            paint(
                render_arrow_list(
                    "Search ranges",
                    rows,
                    selected,
                    offset,
                    len(tasks),
                    context,
                    "N New · Enter/E Edit · R Results · Delete Remove",
                )
            )
        pressed = event(events)
        routed = pointer()
        if routed is not None and routed.target == "workspace":
            if routed.key == "SCROLL":
                selected = max(0, min(max(0, len(tasks) - 1), selected + routed.dy))
                manual = False
                continue
            if routed.index is not None and routed.key != "HOVER":
                selected = max(0, min(len(tasks) - 1, int(routed.index)))
                manual = False
            if routed.key == "SELECT":
                continue
        if pressed in ("ESC", "0"):
            state.update(selected=selected, offset=offset)
            return None
        if pressed in ("UP", "DOWN", "PGUP", "PGDN", "HOME", "END"):
            step = (
                -page_size
                if pressed == "PGUP"
                else page_size if pressed == "PGDN" else -1 if pressed == "UP" else 1
            )
            selected = (
                0
                if pressed == "HOME"
                else (
                    max(0, len(tasks) - 1)
                    if pressed == "END"
                    else max(0, min(max(0, len(tasks) - 1), selected + step))
                )
            )
            manual = False
        item = tasks[selected] if tasks else None
        if item:
            context["workspace_focus"] = item["id"]
        if pressed.lower() == "n":
            result = parameter_editor(context, new_draft=True, events=events)
            if result:
                return result
        elif pressed.lower() == "l":
            result = parameter_editor(context, basis="launcher", events=events)
            if result:
                return result
        elif pressed in ("ENTER", "ACTIVATE", "s", "S"):
            from pgn_ui_workflow import primary

            operation = primary(item, context)
            if not operation.get("enabled"):
                message = operation.get("reason", "This action is unavailable.")
                continue
            try:
                kind = operation["kind"]
                if kind == "new_form":
                    result = parameter_editor(context, new_draft=True, events=events)
                    if result:
                        return result
                    continue
                if kind == "edit":
                    result = parameter_editor(
                        context,
                        configuration=item.get("configuration") or {},
                        draft_id=(
                            item.get("id") if item.get("draft_source") == "local_saved" else None
                        ),
                        events=events,
                    )
                    if result:
                        return result
                    continue
                if kind == "results":
                    if item.get("folder"):
                        open_path_page(context, item["folder"], events)
                    continue
                if kind == "new":
                    from pgn_parameter_editor import ParameterDraft

                    action = ParameterDraft(context, configuration=item["configuration"]).request(
                        "new", context
                    )
                    plan_id = operation.get("plan_id")
                    if not plan_id:
                        from pgn_draft_plans import save

                        plan_id = save(context, action.values)
                    action.values["plan_id"] = plan_id
                    action.values["plan_root"] = context.get("output_root")
                else:
                    action = MenuAction(kind, dict(operation.get("values") or {}))
                if action.kind == "return":
                    return action
                if context.get("_submit_action"):
                    reply = context["_submit_action"](action)
                    if isinstance(reply, MenuAction):
                        return reply
                    if not isinstance(reply, dict):
                        raise RuntimeError(
                            "Invalid coordinator response; the search was not started."
                        )
                    message = reply.get("message", "Request sent.")
                else:
                    return action
            except (OSError, ValueError, RuntimeError) as problem:
                message = str(problem)
        elif pressed in ("e", "E") and item:
            if not item.get("can_edit"):
                message = "This range is pinned. Use New to prepare different settings."
                continue
            if item.get("kind") == "queued":
                entry = next(
                    (
                        e
                        for e in context.get("queued_ranges", [])
                        if e["child_session_id"] == item["id"]
                    ),
                    None,
                )
                if entry:
                    result = parameter_editor(
                        context,
                        configuration=entry["configuration"],
                        queue_edit=item["id"],
                        events=events,
                    )
                    if result:
                        return result
            else:
                result = parameter_editor(
                    context,
                    configuration=item.get("configuration") or {},
                    draft_id=item["id"] if item.get("draft_source") == "local_saved" else None,
                    events=events,
                )
                if result:
                    return result
        elif pressed.lower() == "m":
            state["show_map"] = not state.get("show_map", False)
        elif pressed.lower() == "p":
            from pgn_ui_workflow import pause_control, phase

            control = pause_control(context)
            if not control["enabled"]:
                message = "The current worker is not ready for this control."
                continue
            active = context.get("active_session") or {}
            if phase(context) in ("PAUSED", "IDLE"):
                folder = (
                    active.get("folder") or context.get("folder") or context.get("resume_folder")
                )
                if not folder:
                    message = "No local resume folder is available."
                    continue
                action = MenuAction("resume", {"folder": str(folder)})
            else:
                action = MenuAction("pause", {})
            try:
                if context.get("_submit_action"):
                    reply = context["_submit_action"](action)
                    if isinstance(reply, MenuAction):
                        return reply
                    if not isinstance(reply, dict):
                        raise RuntimeError(
                            "Invalid coordinator response; the search state was not changed."
                        )
                    message = reply.get("message", "Request sent.")
                else:
                    return action
            except (OSError, ValueError, RuntimeError) as problem:
                message = str(problem)
        elif pressed.lower() == "r" and item and item.get("can_results"):
            saved = next(
                (
                    session
                    for session in catalog_sessions(context)
                    if session.session_id == item["id"]
                ),
                None,
            )
            path = saved.folder if saved else context.get("folder")
            if path:
                open_path_page(context, path, events)
        elif pressed == "DELETE" and item and item.get("can_remove"):
            if item.get("draft_source") == "local_saved":
                from pgn_draft_plans import remove

                try:
                    remove(context, item["id"])
                    message = "Local draft removed. No current search or pending queue changed."
                except (OSError, ValueError) as problem:
                    message = str(problem)
                continue
            entries = context.get("queued_ranges") or []
            index = next(
                i for i, entry in enumerate(entries) if entry["child_session_id"] == item["id"]
            )
            cfg = entries[index]["configuration"]
            length = int(cfg["end"]) - int(cfg["start"])
            following = len(entries) - index - 1
            notice = (
                "Remove "
                + length_text(length)
                + " and move "
                + str(following)
                + " following pending range(s) earlier by "
                + length_text(length)
                + "?"
            )
            paint(
                render_arrow_list(
                    "Remove pending range",
                    [{"label": notice, "detail": "No current range is changed."}],
                    0,
                    0,
                    1,
                    context,
                    "Y Remove and shift · Esc Cancel",
                )
            )
            confirm = event(events)
            if confirm.lower() == "y":
                action = MenuAction(
                    "queue_delete",
                    {
                        "child_session_id": item["id"],
                        "start": cfg["start"],
                        "reflow_following": True,
                    },
                )
                try:
                    if context.get("browser_only"):
                        message = prepare_browser_queue(context, action)
                    elif context.get("_submit_action"):
                        message = context["_submit_action"](action)["message"]
                    else:
                        message = "Queue changes require the local coordinator."
                except (OSError, ValueError, RuntimeError) as problem:
                    message = str(problem)


def display_settings_page(context, events=None):
    from pgn_menu import MenuAction
    from pgn_ui_options import display_rows

    current = context.get(
        "display_rows", (context.get("configuration") or {}).get("display_rows", 10)
    )
    value = form(
        "Display settings",
        [
            (
                "display_rows",
                "DISPLAY_ROWS",
                str(current),
                "Integer10..30. BOTH Best and Recent. No report/CSV/science limit changes.",
            )
        ],
        lambda values: display_rows(values["display_rows"]),
        events=events,
        context=context,
    )
    if value is None:
        return
    submit = context.get("_submit_action")
    if callable(submit):
        submit(MenuAction("display_rows", {"display_rows": value}))
    context["display_rows"] = value


def diagnostics_page(context, events=None):
    from pgn_interaction import focus_panel, pointer
    from pgn_menu import MenuAction

    selected = 0
    message = None
    while True:
        refresh_context(context)
        state = context.get("developer_diagnostics") or {
            "status": "Stopped",
            "recording": False,
            "folder": None,
        }
        available = (
            not context.get("browser_only")
            and bool(context.get("gpu_uuid"))
            and callable(context.get("_submit_action"))
        )
        rows = [
            {
                "label": "Start recording",
                "detail": (
                    "Temporary local technical report. No tuning or upload."
                    if available
                    else "Available in the local application with a selected GPU."
                ),
            },
            {"label": "Stop recording", "detail": state.get("status", "Stopped")},
            {"label": "Open folder", "detail": str(state.get("folder") or "No recording yet.")},
        ]
        context["_diagnostics_selected"] = selected
        focus_panel("list")
        import pgn_ui_views

        renderer = getattr(pgn_ui_views, "render_diagnostics", None)
        paint(
            renderer(context, state, message)
            if callable(renderer)
            else render_arrow_list(
                "Developer diagnostics",
                rows,
                selected,
                0,
                3,
                context,
                "S Start · T Stop · R Open folder",
            )
        )
        pressed = event(events)
        routed = pointer()
        if (
            routed is not None
            and routed.target in ("list", "diagnostics")
            and routed.index is not None
        ):
            selected = max(0, min(2, int(routed.index)))
        if pressed in ("ESC", "0"):
            return None
        if pressed in ("UP", "DOWN"):
            selected = (selected + (-1 if pressed == "UP" else 1)) % 3
        if pressed == "ENTER":
            pressed = ("s", "t", "r")[selected]
        if pressed.lower() == "r":
            if state.get("folder"):
                open_path_page(context, state["folder"], events)
        elif pressed in ("SAVE", "s", "S", "t", "T"):
            if not available:
                message = "Recording is unavailable in this read-only browser."
                continue
            try:
                reply = context["_submit_action"](
                    MenuAction(
                        "diagnostic_start" if pressed in ("SAVE", "s", "S") else "diagnostic_stop",
                        {},
                    )
                )
                message = reply.get("message", "Stopped")
            except (ValueError, OSError, RuntimeError) as problem:
                message = str(problem)


def launcher_page(context, events=None):
    path = context.get("launcher_path")
    parser_factory = context.get("_parser_factory")
    range_validator = context.get("_range_validator")
    if not path or not Path(path).is_file() or not parser_factory:
        paint(
            render_arrow_list(
                "Local launcher not selected",
                [
                    {
                        "label": "No real LOCAL launcher selected.",
                        "detail": "Read-only saved sessions are never modified.",
                    }
                ],
                0,
                0,
                1,
                context,
                "Esc Back",
            )
        )
        while event(events) not in ("ESC", "0"):
            pass
        return
    cache = context.setdefault("_ui_state", {})
    draft = cache.get("launcher_draft")
    if draft is None or draft.path != Path(path).resolve():
        try:
            draft = LauncherDraft(path, parser_factory(), range_validator)
            cache["launcher_draft"] = draft
        except (OSError, ValueError, RuntimeError) as problem:
            paint(
                render_arrow_list(
                    "Local launcher > Cannot read",
                    [
                        {
                            "label": str(problem),
                            "detail": "No file was changed. Any previous cached draft is retained.",
                        }
                    ],
                    0,
                    0,
                    1,
                    context,
                    "Esc Back",
                )
            )
            while event(events) not in ("ESC", "0"):
                pass
            return
    old_view = cache.get("launcher_view", {})
    expanded = old_view.get("expanded", False)
    error = None
    model = None
    while True:
        names = [
            name
            for index, (_, group) in enumerate(GROUPS)
            for name in group
            if expanded or index < 2
        ]
        rows = [
            {
                "variable": name.upper(),
                "value": draft.values[name.upper()],
                "dest": name,
                "help": draft.actions[name].help,
            }
            for name in names
        ]
        if model is None:
            model = ArrowList(rows, max(3, terminal_size(fallback=(100, 30)).lines - 20))
            model.selected = min(old_view.get("selected", 0), max(0, len(rows) - 1))
            model.offset = old_view.get("offset", 0)
            model.move("IGNORE")
        else:
            model.entries = rows
            model.selected = min(model.selected, len(rows) - 1)
        paint(
            render_launcher(
                context,
                draft.path,
                model.visible(),
                model.selected,
                model.offset,
                len(rows),
                error,
                expanded,
            )
        )
        pressed = event(events)
        if pressed in ("ESC", "0"):
            cache["launcher_view"] = {
                "expanded": expanded,
                "selected": model.selected,
                "offset": model.offset,
            }
            return
        if pressed in ("UP", "DOWN", "PGUP", "PGDN", "HOME", "END"):
            model.move(pressed)
        elif pressed.lower() == "a":
            expanded = not expanded
            model = None
        elif pressed == "ENTER" and model.current():
            row = model.current()
            name = row["variable"]
            action = draft.actions[row["dest"]]
            edited = form(
                "Edit LOCAL launcher > " + name,
                [(name, name, draft.values[name], action.help)],
                lambda values: values[name],
                context=context,
            )
            if edited is not None:
                draft.values[name] = edited
                error = "Draft changed. S explicitly saves; current session is unaffected."
        elif pressed.lower() == "s":
            try:
                backup = draft.save()
                error = "Saved LOCAL launcher. Backup: " + str(backup)
            except Exception as problem:
                error = "Not saved. Draft kept: " + str(problem)
