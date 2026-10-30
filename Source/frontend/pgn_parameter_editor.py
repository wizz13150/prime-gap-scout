from pgn_terminal_input import terminal_size

"""Shared parameter editor: navigation, inline editing, launch/queue/save actions.

UI-side code owns only a draft and an explicitly selected local launcher file.
Session/queue actions are messages to the coordinator, never database writes.
"""
from pathlib import Path
from decimal import Decimal
import contextlib, io, math, shutil, copy, re
from pgn_input import TerminalInput
from pgn_launcher import GROUPS, DEFAULTS, BOOLS, argv_from_environment, validate_coverage
from pgn_launcher_edit import LauncherDraft
from pgn_parameters import description, placeholder
from pgn_sessions_browser import ArrowList
from pgn_ui_terminal import paint, cursor

QUEUE_FIELDS = frozenset(
    (
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
        "reflow_following",
        "min_gap_requested",
        "count_gap_requested",
        "detail_gap_requested",
        "threshold_policy",
    )
)


_RANGE_LEXEME = re.compile(r"[+-]?(?:[0-9]+|(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)[eE][+-]?[0-9]+)\Z")


def range_integer(text):
    """UI range syntax only; no minimum length beyond the existing contract."""
    source = str(text).strip()
    if not _RANGE_LEXEME.fullmatch(source):
        raise ValueError(
            "Use digits or scientific e/E notation; a plain decimal such as 3.0 is not an accepted format."
        )
    try:
        number = Decimal(source)
        if not number.is_finite() or number != number.to_integral_value():
            raise ValueError("The scientific value must be an exact integer.")
        if abs(number) > (1 << 95):
            raise ValueError("Value is outside the 67..95-bit domain.")
        return int(number)
    except ArithmeticError:
        raise ValueError("Scientific value is outside the 67..95-bit domain.") from None


class ParameterDraft:
    def __init__(self, context, basis="range", configuration=None):
        self.parser = context["_parser_factory"]()
        self.range_validator = context["_range_validator"]
        self.actions = validate_coverage(self.parser)
        self.launcher = None
        self.load_error = None
        self.values = {
            name.upper(): DEFAULTS.get(name, "0" if name in BOOLS else "")
            for _, names in GROUPS
            for name in names
        }
        path = context.get("launcher_path")
        if path:
            try:
                self.launcher = LauncherDraft(path, self.parser, self.range_validator)
                self.values.update(self.launcher.values)
            except (OSError, ValueError, RuntimeError) as problem:
                self.load_error = str(problem)
        self.basis = basis
        self.range_mode = "END" if self.values["END"] else "LENGTH"
        if basis != "launcher":
            from pgn_ui_controller import default_draft

            source = configuration or default_draft(context)
            self.from_configuration(source)

    def from_configuration(self, source):
        from pgn_ui_views import sci

        mapping = {
            "gpu": "GPU",
            "gpu_index": "GPU",
            "min_gap": "MIN_GAP",
            "count_gap": "COUNT_GAP",
            "detail_gap": "DETAIL_GAP",
            "bins": "BINS",
            "report_top": "REPORT_TOP",
            "display_rows": "DISPLAY_ROWS",
            "target_merit": "TARGET_MERIT",
            "name": "NAME",
            "profile": "PROFILE",
            "chunk_length": "CHUNK_LENGTH",
            "output": "OUTPUT",
            "worker": "WORKER",
            "debug": "DEBUG",
            "telemetry": "TELEMETRY",
            "archive": "ARCHIVE",
            "skip_self_test": "SKIP_SELF_TEST",
            "headless": "HEADLESS",
        }
        self.values["START"] = sci(source["start"])
        self.values["LENGTH"] = sci(
            int(source.get("length") or int(source["end"]) - int(source["start"]))
        )
        self.values["END"] = ""
        self.values["RESUME"] = ""
        self.range_mode = "LENGTH"
        for name, target in mapping.items():
            if name in source:
                self.values[target] = (
                    ""
                    if source[name] is None
                    else str(int(source[name])) if name in BOOLS else str(source[name])
                )
        if "min_gap_requested" in source:
            self.values["MIN_GAP"] = str(source["min_gap_requested"])
        if "count_gap_requested" in source:
            self.values["COUNT_GAP"] = (
                "" if source["count_gap_requested"] is None else str(source["count_gap_requested"])
            )
        if "detail_gap_requested" in source:
            self.values["DETAIL_GAP"] = (
                ""
                if source["detail_gap_requested"] is None
                else str(source["detail_gap_requested"])
            )
        self.frozen_threshold_pin = source.get("threshold_policy")
        if "count_gap" not in source and "count_gap_requested" not in source:
            self.values["COUNT_GAP"] = ""
        if "detail_gap" not in source and "detail_gap_requested" not in source:
            self.values["DETAIL_GAP"] = ""
        for name in ("HELP", "VERSION", "LIST_GPUS", "SELF_TEST", "FERMAT_DIAGNOSTIC"):
            self.values[name] = "0"

    def parse(self, search=True):
        if not self.values["START"] and not self.values["RESUME"]:
            raise ValueError("START is required; for example 2e20.")
        if self.range_mode == "END" and not self.values["END"] and not self.values["RESUME"]:
            raise ValueError("END mode requires an exclusive END value.")
        if not self.values["RESUME"]:
            for name in ("START", "LENGTH" if self.range_mode == "LENGTH" else "END"):
                range_integer(self.values[name])
        for name in BOOLS:
            if self.values[name.upper()] not in ("0", "1"):
                raise ValueError(name.upper() + " accepts 0 or 1.")
        if search and any(
            self.values[name] == "1"
            for name in ("HELP", "VERSION", "LIST_GPUS", "SELF_TEST", "FERMAT_DIAGNOSTIC")
        ):
            raise ValueError(
                "Action-mode flags are for the next program launch. Save launcher to use them; disable them for Search/Queue."
            )
        capture = io.StringIO()
        try:
            with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                args = self.parser.parse_args(argv_from_environment(self.values))
                saved = getattr(self, "frozen_threshold_pin", None)
                if saved and str(args.start) == saved["start"]:
                    raw_end = args.start + args.length if args.length is not None else args.end
                    if raw_end is not None and str(raw_end) == saved["end"]:
                        from pgn_native_contract import requested_gap, override_gap

                        if (
                            requested_gap(args.min_gap) == saved["requested"]
                            and override_gap(args.count_gap) == saved["count_override"]
                            and override_gap(args.detail_gap) == saved["detail_override"]
                        ):
                            args._threshold_pin = saved
                end = self.range_validator(args, self.parser)
        except SystemExit:
            raise ValueError(
                capture.getvalue().strip() or "Choose valid parameter values."
            ) from None
        if not math.isfinite(args.target_merit) or args.target_merit <= 0:
            raise ValueError("TARGET_MERIT must be finite and greater than 0.")
        return args, end

    def validation(self, editing=None):
        """Check the visible buffer without accepting it into committed values."""
        integer = range_integer
        staged = copy.copy(self)
        staged.values = dict(self.values)
        if editing:
            staged.values[editing["name"].upper()] = editing["text"]
        errors = {}
        numeric = ["START", "LENGTH" if self.range_mode == "LENGTH" else "END"]
        if not staged.values.get("RESUME"):
            for name in numeric:
                try:
                    value = integer(staged.values[name])
                    if value <= 0:
                        raise ValueError("Use a positive exact integer.")
                except (ValueError, ArithmeticError, TypeError) as problem:
                    errors[name.lower()] = name + ": " + str(problem)
            if not errors:
                start = integer(staged.values["START"])
                end = (
                    integer(staged.values["END"])
                    if self.range_mode == "END"
                    else start + integer(staged.values["LENGTH"])
                )
                if not (1 << 66) <= start < (1 << 95):
                    errors["start"] = "START is outside the67..95-bit domain."
                if not start < end <= (1 << 95):
                    errors["end" if self.range_mode == "END" else "length"] = (
                        "Range must increase inside67..95 bits; Native window/halo admission is still required."
                    )
        if not errors:
            try:
                if self.basis == "launcher" and self.launcher is not None:
                    launcher = copy.copy(self.launcher)
                    launcher.values = dict(staged.values)
                    launcher.validate()
                else:
                    staged.parse(search=self.basis != "launcher")
            except (ValueError, ArithmeticError, TypeError) as problem:
                errors[(editing or {}).get("name", "parameters")] = str(problem)
        return errors

    def save_launcher(self):
        if self.range_mode == "END" and not self.values["END"] and not self.values["RESUME"]:
            raise ValueError("END mode requires an exclusive END value.")
        if self.launcher is None:
            raise ValueError(
                "No writable current LOCAL launcher was loaded: "
                + str(self.load_error or "choose a launcher file")
            )
        self.launcher.values = dict(self.values)
        return self.launcher.save()

    def request(self, kind, context):
        from pgn_menu import MenuAction

        args, end = self.parse()
        if args.resume:
            if kind != "new":
                raise ValueError(
                    "RESUME cannot be queued as a new range. Clear RESUME to add a range."
                )
            return MenuAction("resume", {"folder": str(args.resume)})
        values = {
            name: getattr(args, name)
            for name in (
                "gpu",
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
                "debug",
                "telemetry",
                "archive",
                "skip_self_test",
                "headless",
                "menu",
            )
        }
        values.update(
            min_gap_requested=args.min_gap_requested,
            count_gap_requested=args.count_gap_requested,
            detail_gap_requested=args.detail_gap_requested,
            threshold_policy=args.threshold_policy,
        )
        values.update(
            start=args.start,
            end=end,
            length=end - args.start,
            output=str(args.output) if args.output else None,
            worker=str(args.worker) if args.worker else None,
        )
        if kind == "queue":
            tail = int(
                context.get("queue_tail_end")
                or (context.get("active_session") or context.get("selected_session") or context)[
                    "end"
                ]
            )
            values.update(start=tail, end=tail + values["length"])
            values.pop(
                "threshold_policy", None
            )  # New linked range must pin its own exact interval.
            if args.worker:
                raise ValueError("Queue uses the packaged trusted profile; clear WORKER override.")
            parent = context.get("output_root")
            if (
                args.output is not None
                and parent
                and Path(args.output).expanduser().resolve() != Path(parent).resolve()
            ):
                raise ValueError(
                    "Queued ranges keep the current results root. Use Start now for a different OUTPUT."
                )
            values = {key: value for key, value in values.items() if key in QUEUE_FIELDS}
        return MenuAction(kind, values)


def event(events=None):
    if events is not None:
        from pgn_interaction import translate

        return translate(next(events))
    from pgn_ui_service import refresh_context_snapshot

    refresh_context_snapshot()
    with TerminalInput() as reader:
        return reader.read()


def draft_queue(context):
    return context.setdefault("_ui_state", {}).setdefault("draft_queue", [])


def prepare_browser_queue(context, action):
    """Explicit local UI drafts, never edits to the read-only saved WIZZ data."""
    import uuid

    items = draft_queue(context)
    if action.kind == "queue":
        items.append(
            {
                "child_session_id": uuid.uuid4().hex,
                "status": "DRAFT — NOT SUBMITTED",
                "configuration": dict(action.values),
            }
        )
    else:
        index = next(
            i
            for i, item in enumerate(items)
            if item["child_session_id"] == action.values["child_session_id"]
        )
        if action.kind == "queue_edit":
            old = items[index]["configuration"]
            new = dict(action.values)
            if int(new["start"]) != int(old["start"]):
                raise ValueError(
                    "Pending START is linked to the preceding range; change LENGTH or END."
                )
            items[index]["configuration"] = new
        elif action.kind == "queue_delete":
            items.pop(index)
        for position in range(index + 1 if action.kind == "queue_edit" else index, len(items)):
            previous_end = (
                int(items[position - 1]["configuration"]["end"])
                if position
                else int(action.values["start"])
            )
            cfg = items[position]["configuration"]
            length = int(cfg["end"]) - int(cfg["start"])
            cfg.update(start=previous_end, end=previous_end + length)
    from pgn_native_contract import fields

    for item in items:
        cfg = item["configuration"]
        cfg.update(
            fields(
                int(cfg["start"]),
                int(cfg["end"]),
                cfg.get("min_gap_requested", cfg.get("min_gap", "auto")),
                cfg.get("count_gap_requested"),
                cfg.get("detail_gap_requested"),
            )
        )
    context["queued_ranges"] = list(items)
    if items:
        context["queue_tail_end"] = int(items[-1]["configuration"]["end"])
    else:
        context["queue_tail_end"] = int(
            (context.get("active_session") or context.get("selected_session") or context)["end"]
        )
    return "Local draft queue updated. No active calculation was changed."


def render_editor(
    context, draft, names, selected, offset, editing=None, error=None, queue_edit=None
):
    from rich import box
    from rich.console import Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from pgn_ui_views import page

    width = terminal_size(fallback=(100, 30)).columns
    value_width = max(25, width - 36)
    table = Table.grid(expand=False, padding=(0, 1))
    table.add_column(width=3)
    table.add_column(width=23)
    table.add_column(width=value_width)
    for index, name in enumerate(names):
        actual = offset + index
        focused = actual == selected
        value = placeholder(name, draft.values) if name != "range_mode" else draft.range_mode
        if editing and editing["name"] == name:
            value = editing["text"]
            position = editing["cursor"]
            left = max(0, position - value_width + 3)
            value = ("…" if left else "") + value[left:position] + "▏" + value[position:]
        label = "RANGE MODE" if name == "range_mode" else name.upper()
        table.add_row(
            "›" if focused else "",
            Text(label, style="bold white" if focused else "white"),
            Text(
                value,
                style="bold cyan" if editing and editing.get("all") and focused else "white",
                no_wrap=True,
                overflow="ellipsis",
            ),
            style="on #12334b" if focused else "",
        )
    current_name = (
        names[selected - offset] if names and 0 <= selected - offset < len(names) else "start"
    )
    help_text = (
        "Choose LENGTH or END explicitly. LENGTH shows its computed exclusive END. Enter toggles mode."
        if current_name == "range_mode"
        else description(current_name, draft.actions[current_name])
    )
    active = context.get("active_session")
    current = (
        (
            "Running"
            if active.get("job_active")
            else {"PAUSED": "Paused", "COMPLETE": "Complete", "FAILED": "Failed"}.get(
                active.get("status"), "Idle"
            )
        )
        if active
        else "Idle"
    )
    queued = context.get("queued_ranges") or []
    queue_text = (
        ("Local draft queue: " if context.get("browser_only") else "Queue: ")
        + str(len(queued))
        + " range(s)"
    )
    notice = context.get("_queue_edit_notice", "") if queue_edit else ""
    body = Group(
        Text(current, style="cyan"),
        Text(queue_text + " · V View/edit queue", style="yellow"),
        table,
        Panel(Text(help_text, style="cyan"), title="Field help", height=6, box=box.SIMPLE),
        Text(notice, style="yellow"),
        Text(
            str(error or "Draft only. Current search/filter bindings never change."),
            style="yellow" if error else "dim",
        ),
    )
    footer = (
        "↑↓/Tab · Enter/E Edit · Ctrl+S Save · G Start · A Add · V Queue · T Advanced · R Results"
    )
    if queue_edit:
        footer = "↑↓/Tab Field · Enter Edit/replace · Ctrl+S Apply pending edit · Esc Back"
    from pgn_range_eta import estimate_values

    staged_values = dict(draft.values)
    if editing:
        staged_values[editing["name"].upper()] = editing["text"]
    range_eta = estimate_values(staged_values, draft.range_mode, context)
    validation_errors = draft.validation(editing)
    range_preview = None
    try:
        integer = range_integer
        preview_start = integer(staged_values["START"])
        preview_end = (
            integer(staged_values["END"])
            if draft.range_mode == "END"
            else preview_start + integer(staged_values["LENGTH"])
        )
        if (1 << 66) <= preview_start < preview_end <= (1 << 95):
            range_preview = {
                "start": preview_start,
                "end": preview_end,
                "positions": preview_end - preview_start,
            }
    except (ValueError, ArithmeticError, KeyError, TypeError):
        pass
    if range_preview is None:
        range_eta = {
            "available": False,
            "label": "ETA unavailable: enter a valid range.",
            "short_label": "ETA unavailable",
        }

    def displayed_value(name):
        if editing and editing["name"] == name:
            return editing["text"]
        if name == "range_mode":
            return draft.range_mode
        if range_preview is None and (
            (name == "end" and draft.range_mode == "LENGTH")
            or (name == "length" and draft.range_mode == "END")
        ):
            return "—"
        return placeholder(name, staged_values)

    def choice_options(name):
        current = draft.range_mode if name == "range_mode" else draft.values.get(name.upper())
        if name == "range_mode":
            pairs = [("LENGTH", "Length"), ("END", "End")]
        elif name in BOOLS:
            pairs = [("0", "Off"), ("1", "On")]
        else:
            pairs = [
                (str(value), str(value).title() if str(value) == "auto" else str(value))
                for value in (getattr(draft.actions.get(name), "choices", None) or ())
            ]
        return [
            {
                "label": label,
                "value": value,
                "active": current == value,
                "key": "SET:" + name + ":" + value,
            }
            for value, label in pairs
        ]

    from pgn_threshold_policy import safe_view

    threshold_preview = (
        safe_view(
            {
                "min_gap_requested": staged_values.get("MIN_GAP") or "auto",
                "count_gap_requested": staged_values.get("COUNT_GAP") or None,
                "detail_gap_requested": staged_values.get("DETAIL_GAP") or None,
            },
            range_preview["start"],
            range_preview["end"],
        )
        if range_preview is not None and draft.basis != "launcher"
        else None
    )
    model = {
        "threshold_preview": threshold_preview,
        "range_preview": range_preview,
        "validation_errors": validation_errors,
        "validation_error": next(iter(validation_errors.values()), ""),
        "basis": draft.basis,
        "launcher_path": (
            str(draft.launcher.path)
            if draft.launcher
            else str(context.get("launcher_path") or "No launcher selected")
        ),
        "save_kind": (
            "pending_edit" if queue_edit else "launcher" if draft.basis == "launcher" else "draft"
        ),
        "eta": range_eta,
        "rows": [
            {
                "index": offset + i,
                "name": name,
                "label": "RANGE MODE" if name == "range_mode" else name.upper(),
                "value": displayed_value(name),
                "choices": choice_options(name),
                "choice_value": (
                    draft.range_mode if name == "range_mode" else draft.values.get(name.upper())
                ),
                "selected": offset + i == selected,
                "editing": bool(editing and editing["name"] == name),
                "selected_all": bool(editing and editing.get("all") and offset + i == selected),
                "caret": editing["cursor"] if editing and editing["name"] == name else None,
                "cursor": editing["cursor"] if editing and editing["name"] == name else None,
                "edit_buffer": editing["text"] if editing and editing["name"] == name else None,
                "can_pick_folder": name in ("output", "resume"),
                "browse_key": "PICK_FOLDER" if name in ("output", "resume") else None,
                "invalid": bool(validation_errors.get(name)),
                "error": validation_errors.get(name),
                "readonly": bool(
                    (queue_edit and name == "start")
                    or (name == "end" and draft.range_mode == "LENGTH")
                    or (name == "length" and draft.range_mode == "END")
                ),
            }
            for i, name in enumerate(names)
        ],
        "selected": selected,
        "offset": offset,
        "total": context.get("_parameter_total", len(names)),
        "field_help": help_text,
        "status_note": str(error or notice or ""),
        "status_kind": context.get("_parameter_status_kind", "message"),
        "queue_edit": queue_edit,
        "current_status": current,
        "workspace": context.get("workspace"),
        "footer": footer,
        "advanced": context.get("_parameter_advanced", False),
        "range_mode": draft.range_mode,
    }
    import pgn_ui_views

    renderer = getattr(pgn_ui_views, "render_parameter_editor", None)
    return (
        renderer(model, context)
        if callable(renderer)
        else page("Search parameters", body, context, footer)
    )


def parameter_editor(
    context,
    *,
    basis="range",
    configuration=None,
    queue_edit=None,
    draft_id=None,
    new_draft=False,
    events=None,
):
    cache = context.setdefault("_ui_state", {})
    identity = (
        "queue:" + queue_edit
        if queue_edit
        else (
            "draft:" + draft_id
            if draft_id
            else "launcher_parameters" if basis == "launcher" else "new_parameters"
        )
    )
    if new_draft:
        cache.pop(identity, None)
    stored = cache.get(identity)
    draft = stored["draft"] if stored else ParameterDraft(context, basis, configuration)
    if queue_edit and stored:
        from pgn_ui_views import sci

        new_start = int(configuration["start"])
        old_start = int(Decimal(draft.values["START"]))
        if new_start != old_start:
            if draft.range_mode == "END":
                draft.values["END"] = sci(int(Decimal(draft.values["END"])) + new_start - old_start)
            draft.values["START"] = sci(new_start)
    expanded = stored.get("expanded", False) if stored else False
    selected = stored.get("selected", 0) if stored else 0
    offset = stored.get("offset", 0) if stored else 0
    manual_scroll = False
    page_size = None
    from pgn_start_failures import start_failure_note

    editing = None
    error = draft.load_error or (start_failure_note(context) if basis != "launcher" else "")
    context["_parameter_status_kind"] = "message"
    if stored and not draft_id:
        draft_id = stored.get("saved_draft_id")

    def persist():
        cache[identity] = {
            "draft": draft,
            "selected": selected,
            "offset": offset,
            "expanded": expanded,
            "saved_draft_id": draft_id,
        }

    def commit():
        nonlocal editing, error
        if editing:
            problems = draft.validation(editing)
            if problems:
                error = None
                context["_parameter_status_kind"] = "validation"
                return False
            draft.values[editing["name"].upper()] = editing["text"]
            editing = None
        return True

    def browse_folder(name):
        nonlocal error, selected, manual_scroll
        if name not in ("output", "resume"):
            return
        current = (
            editing["text"]
            if editing and editing["name"] == name
            else draft.values.get(name.upper(), "")
        )
        if not current:
            from pgn_output import default_output_base

            current = (
                str(context.get("folder") or context.get("output_root") or default_output_base())
                if name == "resume"
                else str(context.get("output_root") or default_output_base())
            )
        try:
            from pgn_folder_picker import choose_folder

            result = choose_folder(
                initial=current,
                title="Select "
                + ("OUTPUT folder" if name == "output" else "RESUME session folder"),
                field=name.upper(),
            )
            if not isinstance(result, dict):
                raise ValueError("Folder chooser returned an invalid response.")
            status = result.get("status")
            if status == "cancelled":
                return
            if status != "selected":
                error = (
                    name.upper()
                    + " folder chooser "
                    + str(status or "error")
                    + ": "
                    + str(result.get("message") or "Continue entering the path manually.")
                )
                return
            chosen = result.get("path")
            if not isinstance(chosen, str) or not chosen or not Path(chosen).is_dir():
                raise ValueError("The chosen path is not an existing folder.")
            if editing and editing["name"] == name:
                editing.update(text=chosen, cursor=len(chosen), all=False)
            else:
                draft.values[name.upper()] = chosen
                if editing is None:
                    selected = names.index(name)
                    manual_scroll = False
            error = name.upper() + " folder selected. Save remains explicit."
        except (ImportError, OSError, ValueError, RuntimeError) as problem:
            error = (
                name.upper()
                + " folder chooser unavailable: "
                + str(problem)
                + " Enter the path manually."
            )

    def set_choice(name, value):
        nonlocal error
        if name == "range_mode":
            if value == draft.range_mode:
                return True
            if value not in ("LENGTH", "END"):
                return False
            integer = range_integer
            from pgn_ui_views import sci

            try:
                start = integer(draft.values["START"])
                end = (
                    integer(draft.values["END"])
                    if draft.range_mode == "END"
                    else start + integer(draft.values["LENGTH"])
                )
                if not (1 << 66) <= start < end <= (1 << 95):
                    raise ValueError("Choose a valid range before changing Length / End mode.")
            except (ValueError, ArithmeticError) as problem:
                error = str(problem)
                return False
            if value == "END":
                draft.values.update(END=sci(end), LENGTH="")
            else:
                draft.values.update(LENGTH=sci(end - start), END="")
            draft.range_mode = value
            return True
        options = (
            ["0", "1"]
            if name in BOOLS
            else [str(item) for item in (getattr(draft.actions.get(name), "choices", None) or ())]
        )
        if value not in options:
            error = "Choose one of the displayed options."
            return False
        draft.values[name.upper()] = value
        return True

    def send(kind):
        nonlocal draft_id
        if context.get("_ui_state", {}).get("pending_worker_request"):
            raise ValueError("A worker request is pending; wait for its safe boundary.")
        if basis == "launcher":
            raise ValueError(
                "Launcher defaults never start or queue a search. Save launcher or go Back."
            )
        action = draft.request("new" if queue_edit else kind, context)
        if queue_edit:
            action.kind = "queue_edit"
            action.values = {
                key: value for key, value in action.values.items() if key in QUEUE_FIELDS
            }
            action.values.update(child_session_id=queue_edit, reflow_following=True)
        if action.kind == "new" and not queue_edit:
            from pgn_draft_plans import save

            draft_id = save(context, action.values, draft_id)
            action.values["plan_id"] = draft_id
            action.values["plan_root"] = context.get("output_root")
            context["prepared_request_saved_id"] = draft_id
        if context.get("browser_only"):
            if action.kind in ("queue", "queue_edit"):
                return prepare_browser_queue(context, action)
            context["prepared_request"] = dict(action.values)
            context.pop("prepared_request_saved_id", None)
            context["prepared_kind"] = action.kind
            return "Prepared " + action.kind.upper() + " only. No GPU job was started."
        if context.get("_submit_action"):
            reply = context["_submit_action"](action)
            return reply["message"] if isinstance(reply, dict) else reply
        return action

    cursor(False)
    try:
        while True:
            from pgn_ui_service import refresh_context_snapshot

            refresh_context_snapshot(context)
            names = ["range_mode"] + [
                name
                for index, (_, group) in enumerate(GROUPS)
                for name in group
                if expanded or index < 2
            ]
            if queue_edit:
                names = [name for name in names if name == "range_mode" or name in QUEUE_FIELDS]
            selected = min(selected, len(names) - 1)
            offset = max(0, min(offset, len(names) - 1))
            if queue_edit:
                old_length = int(configuration["end"]) - int(configuration["start"])
                try:
                    integer = range_integer
                    staged = dict(draft.values)
                    if editing:
                        staged[editing["name"].upper()] = editing["text"]
                    length = (
                        integer(staged["LENGTH"])
                        if draft.range_mode == "LENGTH"
                        else integer(staged["END"]) - integer(staged["START"])
                    )
                    delta = length - old_length
                    context["_queue_edit_notice"] = (
                        "Apply explicitly shifts following pending ranges by "
                        + ("+" if delta >= 0 else "")
                        + str(delta)
                        + " positions; IDs stay stable."
                    )
                except ValueError:
                    context["_queue_edit_notice"] = (
                        "A valid length change will explicitly shift following pending ranges. Ctrl+S applies; Esc goes back."
                    )
            from pgn_interaction import focus_panel, pointer
            from pgn_terminal_input import bounded_scroll

            focus_panel("parameters")
            context["_parameter_total"] = len(names)
            context["_parameter_advanced"] = expanded
            first_offset = offset
            first_count = page_size or len(names)
            frame = render_editor(
                context,
                draft,
                names[offset : offset + first_count],
                selected,
                offset,
                editing,
                error,
                queue_edit,
            )
            available = getattr(frame, "pgn_parameter_capacity", None)
            if not isinstance(available, int) or available < 1:
                # Compatibility with a renderer lacking the explicit viewport
                # contract: use only actually painted field rows, reserve the
                # final border row. The current renderer publishes the exact cap.
                painted = {
                    r.get("index")
                    for r in getattr(frame, "pgn_hit_regions", ())
                    if r.get("target") == "parameters" and r.get("key") == "ENTER"
                }
                available = max(1, len(painted) - 1)
            page_size = max(1, min(len(names), available))
            offset = min(offset, max(0, len(names) - page_size))
            if editing or not manual_scroll:
                if selected < offset:
                    offset = selected
                if selected >= offset + page_size:
                    offset = selected - page_size + 1
            if offset != first_offset or len(names[offset : offset + first_count]) != len(
                names[offset : offset + page_size]
            ):
                frame = render_editor(
                    context,
                    draft,
                    names[offset : offset + page_size],
                    selected,
                    offset,
                    editing,
                    error,
                    queue_edit,
                )
            paint(frame)
            pressed = event(events)
            routed = pointer()
            if pressed == "PICK_FOLDER" or (
                editing is None
                and pressed.lower() == "b"
                and names[selected] in ("output", "resume")
            ):
                pick_index = selected
                if routed is not None:
                    if routed.target not in ("parameters", "footer"):
                        continue
                    if routed.index is not None:
                        if not isinstance(routed.index, int) or not 0 <= routed.index < len(names):
                            continue
                        pick_index = routed.index
                browse_folder(names[pick_index])
                continue
            if routed is not None and routed.target == "parameters":
                if routed.key == "SCROLL":
                    offset = bounded_scroll(offset, len(names), page_size, routed.dy)
                    manual_scroll = True
                    continue
                if routed.index is not None:
                    target = max(0, min(len(names) - 1, int(routed.index)))
                    if routed.key == "HOVER" and editing:
                        continue
                    if editing and editing["name"] != names[target] and not commit():
                        continue
                    selected = target
                    manual_scroll = False
            if pressed.startswith("SET:"):
                parts = pressed.split(":", 2)
                if len(parts) == 3 and (editing is None or commit()):
                    set_choice(parts[1], parts[2])
                continue
            if pressed in ("UP", "DOWN", "TAB", "HOME", "END", "PGUP", "PGDN"):
                manual_scroll = False
            if pressed in ("ESC", "0") and editing is None:
                persist()
                return None
            if pressed == "ESC":
                persist()
                return None
            if pressed in ("SAVE", "\x13") or (editing is None and pressed.lower() == "s"):
                context["_parameter_status_kind"] = "message"
                if not commit():
                    continue
                try:
                    if draft.validation():
                        raise ValueError(next(iter(draft.validation().values())))
                    if queue_edit:
                        result = send("queue")
                        if not isinstance(result, str):
                            persist()
                            return result
                        error = result
                    elif basis == "launcher":
                        backup = draft.save_launcher()
                        error = "Launcher saved. Backup: " + str(backup)
                        try:
                            defaults = copy.copy(draft)
                            defaults.values = dict(draft.values)
                            defaults.values["RESUME"] = ""
                            for flag in (
                                "HELP",
                                "VERSION",
                                "LIST_GPUS",
                                "SELF_TEST",
                                "FERMAT_DIAGNOSTIC",
                            ):
                                defaults.values[flag] = "0"
                            action = defaults.request("new", context)
                            from pgn_ui_workflow import set_global_defaults

                            set_global_defaults(context, action.values)
                            error += " · New ranges use these global defaults; the current range stays pinned."
                        except (ValueError, TypeError, ArithmeticError) as problem:
                            error += " · Search defaults were not updated: " + str(problem)
                    else:
                        from pgn_draft_plans import save

                        action = draft.request("new", context)
                        if action.kind != "new":
                            raise ValueError(
                                "A NEW draft cannot contain RESUME. Clear RESUME or use My sessions."
                            )
                        draft_id = save(context, action.values, draft_id)
                        context["prepared_request"] = dict(action.values)
                        context["prepared_request_saved_id"] = draft_id
                        persist()
                        return (
                            None  # Saved card is immediately visible and focused in Search ranges.
                        )
                except (ValueError, OSError, RuntimeError) as problem:
                    if draft.validation():
                        error = None
                        context["_parameter_status_kind"] = "validation"
                    else:
                        error = str(problem)
                persist()
                continue
            if editing:
                text = editing["text"]
                position = editing["cursor"]
                if pressed in ("SELECT_ALL", "\x01"):
                    editing.update(all=True, cursor=len(text))
                elif pressed == "ENTER":
                    commit()
                elif pressed in ("UP", "DOWN", "TAB"):
                    if commit():
                        selected = (selected + (-1 if pressed == "UP" else 1)) % len(names)
                elif pressed in ("CLEAR", "BACKSPACE") and (pressed == "CLEAR" or editing["all"]):
                    editing.update(text="", cursor=0, all=False)
                elif pressed == "BACKSPACE" and position:
                    editing.update(
                        text=text[: position - 1] + text[position:], cursor=position - 1, all=False
                    )
                elif pressed == "DELETE":
                    editing.update(
                        text="" if editing["all"] else text[:position] + text[position + 1 :],
                        cursor=0 if editing["all"] else position,
                        all=False,
                    )
                elif pressed == "LEFT":
                    editing.update(cursor=max(0, position - 1), all=False)
                elif pressed == "RIGHT":
                    editing.update(cursor=min(len(text), position + 1), all=False)
                elif pressed == "HOME":
                    editing.update(cursor=0, all=False)
                elif pressed == "END":
                    editing.update(cursor=len(text), all=False)
                elif len(pressed) == 1 and pressed.isprintable():
                    editing.update(
                        text=(
                            pressed
                            if editing["all"]
                            else text[:position] + pressed + text[position:]
                        ),
                        cursor=1 if editing["all"] else position + 1,
                        all=False,
                    )
                continue
            name = names[selected]
            choices = (
                ["LENGTH", "END"]
                if name == "range_mode"
                else (
                    ["0", "1"]
                    if name in BOOLS
                    else [
                        str(item)
                        for item in (getattr(draft.actions.get(name), "choices", None) or ())
                    ]
                )
            )
            if pressed in ("LEFT", "RIGHT") and choices:
                current = (
                    draft.range_mode if name == "range_mode" else draft.values.get(name.upper())
                )
                at = choices.index(current) if current in choices else 0
                set_choice(
                    name,
                    choices[max(0, min(len(choices) - 1, at + (-1 if pressed == "LEFT" else 1)))],
                )
                continue
            if pressed in ("UP", "DOWN", "TAB"):
                selected = (selected + (-1 if pressed == "UP" else 1)) % len(names)
            elif pressed == "HOME":
                selected = 0
            elif pressed == "END":
                selected = len(names) - 1
            elif pressed.lower() == "t" and not queue_edit:
                expanded = not expanded
                selected = min(selected, 11)
                offset = 0
            elif pressed.lower() == "l" and not queue_edit and basis != "launcher":
                parameter_editor(context, basis="launcher", events=events)
            elif pressed.lower() == "v" and not queue_edit and basis != "launcher":
                queue_page(context, events=events)
            elif pressed in ("ENTER", "e", "E"):
                name = names[selected]
                if queue_edit and name == "start":
                    error = "Pending START is linked to its predecessor. Edit LENGTH or END."
                    continue
                if name == "end" and draft.range_mode == "LENGTH":
                    error = "END is computed in LENGTH mode. Change RANGE MODE to END to edit it."
                    continue
                if name == "length" and draft.range_mode == "END":
                    error = (
                        "LENGTH is computed in END mode. Change RANGE MODE to LENGTH to edit it."
                    )
                    continue
                if choices:
                    current = (
                        draft.range_mode if name == "range_mode" else draft.values.get(name.upper())
                    )
                    at = choices.index(current) if current in choices else 0
                    set_choice(name, choices[(at + 1) % len(choices)])
                else:
                    editing = {
                        "name": name,
                        "text": draft.values[name.upper()],
                        "cursor": len(draft.values[name.upper()]),
                        "all": False,
                    }
            elif pressed.lower() == "r" and not queue_edit and basis != "launcher":
                from pgn_menu import open_local

                if context.get("folder"):
                    try:
                        open_local(context["folder"])
                    except OSError as problem:
                        error = str(problem)
            elif pressed.lower() in ("g", "a") and basis == "launcher":
                error = "Launcher defaults only. Ctrl+S saves this file for the NEXT launch; Esc returns. No job is started."
            elif pressed.lower() in ("g", "a") and not queue_edit:
                try:
                    result = send("new" if pressed.lower() == "g" else "queue")
                    if not isinstance(result, str):
                        persist()
                        return result
                    error = result
                except (ValueError, OSError, RuntimeError) as problem:
                    error = str(problem)
    finally:
        persist()
        cursor(False)


def queue_page(context, events=None):
    from pgn_menu import MenuAction
    from pgn_ui_controller import render_arrow_list
    from pgn_ui_views import range_text, length_text

    cache = context.setdefault("_ui_state", {})
    state = cache.setdefault("queue_browser", {})
    selected = state.get("selected", 0)
    offset = state.get("offset", 0)
    message = None
    manual = False
    while True:
        from pgn_ui_service import refresh_context_snapshot

        refresh_context_snapshot(context)
        items = context.get("queued_ranges") or []
        model = ArrowList(
            items, page_size=max(2, (terminal_size(fallback=(100, 30)).lines - 12) // 2)
        )
        model.selected = min(selected, max(0, len(items) - 1))
        model.offset = offset
        if not manual:
            model.move("IGNORE")
        rows = []
        for index, item in enumerate(model.visible(), start=model.offset + 1):
            cfg = item["configuration"]
            rows.append(
                {
                    "label": str(index)
                    + " · "
                    + str(item.get("status", "PENDING"))
                    + " · "
                    + length_text(int(cfg["end"]) - int(cfg["start"]))
                    + " · GPU "
                    + str(cfg.get("gpu_index", cfg.get("gpu", 0))),
                    "detail": range_text(cfg["start"], cfg["end"]),
                }
            )
        title = "Local draft queue" if context.get("browser_only") else "Pending queue"
        if message:
            rows.append({"label": message, "detail": ""})
        from pgn_interaction import focus_panel, pointer
        from pgn_terminal_input import bounded_scroll

        focus_panel("list")
        paint(
            render_arrow_list(
                title,
                rows,
                model.selected,
                model.offset,
                len(items),
                context,
                "↑↓ Select · Enter/E Edit · Delete Remove · Esc Back",
            )
        )
        pressed = event(events)
        routed = pointer()
        if routed is not None and routed.target in ("list", "queue"):
            if routed.key == "SCROLL":
                offset = bounded_scroll(offset, len(items), model.page_size, routed.dy)
                manual = True
                continue
            if routed.index is not None:
                model.selected = max(0, min(len(items) - 1, int(routed.index)))
                selected = model.selected
                manual = False
        if pressed in ("ESC", "0"):
            state.update(selected=model.selected, offset=model.offset)
            return
        if pressed in ("UP", "DOWN", "PGUP", "PGDN", "HOME", "END"):
            model.move(pressed)
            selected = model.selected
            offset = model.offset
            manual = False
        elif pressed in ("ENTER", "e", "E") and model.current():
            item = model.current()
            if item.get("status") not in ("PENDING", "DRAFT — NOT SUBMITTED"):
                message = "Only pending plans may be edited."
                continue
            parameter_editor(
                context,
                configuration=item["configuration"],
                queue_edit=item["child_session_id"],
                events=events,
            )
        elif pressed == "DELETE" and model.current():
            item = model.current()
            index = model.selected
            cfg = item["configuration"]
            length = int(cfg["end"]) - int(cfg["start"])
            following = len(items) - index - 1
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
                    "Confirm queue removal",
                    [
                        {
                            "label": notice,
                            "detail": "Stable session IDs are preserved. No active range is changed.",
                        }
                    ],
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
                        "child_session_id": item["child_session_id"],
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
                        message = "Queue changes require the live coordinator."
                except (ValueError, OSError, RuntimeError) as problem:
                    message = str(problem)
