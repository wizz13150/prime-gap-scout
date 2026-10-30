"""One public parameter description/placeholder policy for CLI and editor."""

from pgn_launcher import DEFAULTS, BOOLS, validate_coverage
from pgn_output import default_output_base

BOUNDS = {
    "gpu": "integer 0 or greater; choose a visible index from List GPUs",
    "start": "exact67..95-bit integer; Native plan also checks class30 origin, one low64 window and halo",
    "length": "positive exact integer; mutually exclusive with END",
    "end": "exclusive67..95-bit endpoint; mutually exclusive with LENGTH",
    "min_gap": "Auto or integer954..2147483647",
    "count_gap": "blank inherits per-segment policy, or integer954..2147483647",
    "detail_gap": "blank inherits per-segment policy, or integer954..2147483647",
    "display_rows": "integer10..30; BOTH Best and Recent, independent of reports",
    "bins": "integer 1..1000000",
    "report_top": "integer 1..1000000",
    "target_merit": "finite number greater than 0; display only",
    "chunk_length": "blank for actual memory planning, or a positive exact integer",
    "output": "local directory path; no silent fallback if not writable",
    "resume": "blank for a new session, or a genuine durable local session folder",
    "worker": "blank for packaged profile selection, or an explicit trusted local worker file",
    "name": "text printed in the report",
}
EXAMPLES = {
    "gpu": "0",
    "start": "2e20",
    "length": "1e15",
    "end": "2.00001e20",
    "min_gap": "auto",
    "count_gap": "1000",
    "detail_gap": "1100",
    "display_rows": "20",
    "bins": "100",
    "report_top": "100",
    "target_merit": "32",
    "chunk_length": "2e12",
    "output": "D:/PGN-results or /home/robert/PGN-results",
    "resume": "results/<actual-session-folder>",
    "worker": "bin/pgn68-worker-sm120-k64",
    "name": "Robert",
    "profile": "auto",
}


def description(name, action):
    default = DEFAULTS.get(name, "0" if name in BOOLS else "") or "blank"
    if name == "output":
        default = "blank → results beside this program"
    elif name in ("count_gap", "detail_gap"):
        default = "blank → MIN_GAP"
    elif name == "resume":
        default = "blank → new run"
    elif name == "end":
        default = "blank → START+LENGTH (or START+1e15)"
    choices = (
        "0 off / 1 on"
        if name in BOOLS
        else (
            ", ".join(map(str, action.choices))
            if action.choices
            else BOUNDS.get(name, "local text")
        )
    )
    example = EXAMPLES.get(name, "1 to enable, 0 to disable" if name in BOOLS else default)
    scope = (
        " Queue inherits the running process logging/mode flags; Start now or Save launcher applies this setting."
        if name in BOOLS or name == "worker"
        else ""
    )
    return (
        f"Role: {action.help}. Default: {default}. Choices/bounds: {choices}. Example: {example}."
        + scope
    )


def placeholder(name, values):
    value = values.get(name.upper(), "")
    if value:
        return value
    if name == "output":
        return "blank → " + str(default_output_base())
    if name == "resume":
        return "blank → new run"
    if name in ("count_gap", "detail_gap"):
        return "blank → MIN_GAP " + values.get("MIN_GAP", "960")
    if name == "end":
        try:
            from decimal import Decimal
            from pgn_ui_views import sci

            end = int(Decimal(values["START"])) + int(Decimal(values.get("LENGTH") or "1e15"))
            return "blank → " + sci(end) + " (AUTO)"
        except (ValueError, ArithmeticError, KeyError):
            return "blank → AUTO from START + LENGTH"
    if name == "length":
        return "blank → use END; if END also blank, 1e15"
    if name == "worker":
        return "blank → packaged worker for the selected GPU/profile"
    if name == "chunk_length":
        return "blank → actual memory plan"
    return "(blank)"


def validate_descriptions(parser):
    actions = validate_coverage(parser)
    for name, action in actions.items():
        text = description(name, action)
        if not all(token in text for token in ("Role:", "Default:", "Choices/bounds:", "Example:")):
            raise ValueError(name)
    return actions
