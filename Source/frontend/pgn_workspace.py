"""Integer-only range workspace projection. No database, Driver, or worker API.

The H10 arithmetic window is distinct from Native origin/halo admission. The
conservative endpoint below is the already checked four-BlockNumbers margin;
the remaining upper edge is never presented as admitted without Native --plan.
"""

H10_LO = 1 << 66
H10_HI = 1 << 95
BLOCK_NUMBERS = 1006632960
GUARANTEED_LO = H10_LO
GUARANTEED_HI = H10_HI


def interval(start, end, position=0):
    if start is None or end is None or position is None:
        return None
    try:
        start, end, position = int(start), int(end), int(position)
    except (ValueError, TypeError):
        return None
    if not start < end or not 0 <= position <= end - start:
        return None
    return start, end, position


def pixel_interval(start, end, lower, upper, columns):
    """Return integer coordinates; a compressed tiny interval gets one marker."""
    columns = max(1, int(columns))
    span = int(upper) - int(lower)
    if span <= 0:
        raise ValueError("Invalid workspace viewport")
    first = max(int(start), int(lower))
    last = min(int(end), int(upper))
    if first >= last:
        return None
    x = (first - int(lower)) * columns // span
    right = ((last - int(lower)) * columns + span - 1) // span
    return {
        "column": min(columns - 1, x),
        "width": max(1, min(columns, right) - x),
        "tiny": (last - first) * columns < span,
        "start": first,
        "end": last,
    }


def range_cards(workspace):
    from pgn_ui_workflow import category

    cards = [
        c
        for c in workspace.get("cards", ())
        if c.get("kind") in ("current", "queued", "draft") or c.get("can_resume")
    ]
    order = {"Processing": 0, "Ready": 1, "Queued": 2, "Suspended": 3, "Failed": 4, "Complete": 5}
    return sorted(cards, key=lambda c: order.get(category(c), 9))


def build_workspace(context, sessions=(), columns=72, focus=None):
    from pgn_ui_workflow import phase

    cards = []
    current = context.get("active_session") or {}
    current_id = current.get("session_id")
    current_span = (
        interval(current.get("start"), current.get("end"), current.get("position", 0))
        if current
        else None
    )
    live = phase(context)
    if current_span:
        start, end, position = current_span
        folder = current.get("folder") or context.get("folder")
        saved = next((s for s in sessions if s.session_id == current_id), None)
        resumable = bool(saved.resumable) if saved else live == "PAUSED" and bool(folder)
        config = dict(current.get("configuration") or context.get("configuration") or {})
        cards.append(
            dict(
                id=current_id,
                kind="current",
                status=live,
                backend_status=live,
                start=start,
                end=end,
                position=position,
                folder=str(folder) if folder else None,
                can_resume=resumable and not context.get("browser_only"),
                read_only=False,
                can_edit=False,
                can_remove=False,
                can_results=True,
                origin="local",
                configuration=config,
                plan_id=current.get("plan_id") or config.get("plan_id"),
            )
        )
    for session in sessions:
        if session.session_id == current_id or session.status == "REPLACED_BEFORE_START":
            continue
        span = interval(session.start, session.end, session.position)
        if span is None:
            continue
        start, end, position = span
        cards.append(
            dict(
                id=session.session_id,
                kind="saved",
                status=session.status,
                backend_status=session.status,
                start=start,
                end=end,
                position=position,
                read_only=session.readonly_mirror,
                can_edit=False,
                can_remove=False,
                can_results=True,
                origin=session.host,
                configuration=dict(session.configuration),
                can_resume=bool(session.resumable) and not context.get("browser_only"),
                folder=str(session.folder),
                plan_id=session.configuration.get("plan_id"),
            )
        )
    for item in context.get("queued_ranges") or ():
        cfg = item["configuration"]
        span = interval(cfg.get("start"), cfg.get("end"))
        if span is None:
            continue
        start, end, _ = span
        cards.append(
            dict(
                id=item.get("child_session_id"),
                kind="queued",
                status="QUEUED",
                start=start,
                end=end,
                position=0,
                read_only=False,
                can_edit=True,
                can_remove=True,
                can_results=False,
                origin="local",
                configuration=dict(cfg),
                parent_folder=item.get("parent_folder")
                or current.get("folder")
                or context.get("folder"),
                parent_session_id=item.get("parent_session_id")
                or current_id
                or context.get("session_id"),
            )
        )
    linked = {
        c.get("plan_id")
        for c in cards
        if c.get("can_resume")
        or c.get("kind") == "current"
        and live in ("STARTING", "SEARCHING", "PAUSING", "PAUSED")
    }
    for plan in context.get("saved_drafts") or ():
        if plan["id"] in linked:
            continue  # Plan remains durable; its Current/Suspended card owns this view.
        cfg = plan["configuration"]
        span = interval(cfg.get("start"), cfg.get("end"))
        if span is None:
            continue
        start, end, _ = span
        cards.append(
            dict(
                id=plan["id"],
                kind="draft",
                draft_source="local_saved",
                status="READY",
                start=start,
                end=end,
                position=0,
                configuration=dict(cfg),
                read_only=False,
                can_edit=True,
                can_remove=True,
                can_results=False,
                origin="local",
            )
        )
    draft = context.get("draft_range") or (
        context.get("prepared_request") if not context.get("prepared_request_saved_id") else None
    )
    if draft and interval(draft.get("start"), draft.get("end")) is not None:
        start, end, _ = interval(draft["start"], draft["end"])
        cards.append(
            dict(
                id="parameter-draft",
                kind="draft",
                status="READY",
                start=start,
                end=end,
                position=0,
                read_only=False,
                can_edit=True,
                can_remove=False,
                can_results=False,
                origin="local",
                configuration=dict(draft),
            )
        )
    from pgn_range_eta import estimate

    configs = {
        item.get("child_session_id"): item["configuration"]
        for item in context.get("queued_ranges") or ()
    }
    for card in cards:
        if card["kind"] in ("queued", "draft"):
            cfg = card.get("configuration") or configs.get(
                card["id"], context.get("configuration") or {}
            )
            if card["id"] == "parameter-draft":
                cfg = {
                    **(context.get("configuration") or {}),
                    **(context.get("draft_range") or context.get("prepared_request") or {}),
                }
            card["eta"] = estimate(card["start"], card["end"], cfg, context)
        card["overview"] = pixel_interval(
            card["start"], card["end"], GUARANTEED_LO, GUARANTEED_HI, columns
        )
    focused = next((card for card in cards if card["id"] == focus), None)
    focused = (
        focused
        or next((card for card in cards if card["kind"] == "current"), None)
        or (cards[0] if cards else None)
    )
    zoom = None
    if focused:
        extent = focused["end"] - focused["start"]
        padding = max(1, extent // 20)
        lower = max(GUARANTEED_LO, focused["start"] - padding)
        upper = min(H10_HI, focused["end"] + padding)
        zoom = {"lower": lower, "upper": upper, "focus": focused["id"], "cards": []}
        for card in cards:
            pixels = pixel_interval(card["start"], card["end"], lower, upper, columns)
            if pixels:
                zoom["cards"].append({"id": card["id"], "kind": card["kind"], "pixels": pixels})
    return {
        "status": live,
        "math_window": {"lower": H10_LO, "upper_exclusive": H10_HI, "bits": [67, 95]},
        "supported_window": {
            "lower": GUARANTEED_LO,
            "upper_exclusive": GUARANTEED_HI,
            "kind": "public syntax; Native window/halo plan required",
        },
        "unpaid_low64_seam_adapter": True,
        "exact_native_endpoint_preflight_required": True,
        "cards": cards,
        "zoom": zoom,
    }
