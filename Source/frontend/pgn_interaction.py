"""Route pointer input to the same keyboard commands and item models."""

import threading
from pgn_terminal_input import MouseEvent, HitMap, get_hit_map, set_hit_map, bounded_scroll

_state = threading.local()


def focus_panel(target):
    _state.focused = target


def translate(event):
    _state.pointer = None
    if event == "RESIZE":
        set_hit_map(HitMap(0, 0))
        return "TICK"
    if not isinstance(event, MouseEvent):
        return event
    routed = get_hit_map().route(event, focused=getattr(_state, "focused", None))
    _state.pointer = routed
    if routed.key in ("\x03", "INTERRUPT"):
        raise KeyboardInterrupt()
    return routed.key


def pointer():
    value = getattr(_state, "pointer", None)
    _state.pointer = None
    return value


def apply_pointer(model, target, pressed):
    routed = pointer()
    accepted = (target, "list") if target in ("sessions", "queue", "folders") else (target,)
    if routed is None or routed.target not in accepted:
        return pressed
    if routed.key == "SCROLL":
        model.offset = bounded_scroll(model.offset, len(model.entries), model.page_size, routed.dy)
        return "TICK"
    if routed.index is not None and model.entries:
        model.selected = max(0, min(len(model.entries) - 1, int(routed.index)))
    return pressed


def focused_panel():
    return getattr(_state, "focused", None)
