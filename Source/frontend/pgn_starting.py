"""Paint startup feedback before session recovery or CUDA/device preparation."""

from copy import deepcopy


def show_starting(args, context=None, metadata_reader=None, dashboard_type=None, end=None):
    if args.headless or getattr(args, "ui", "live") == "off":
        return None
    # Do not copy controllers, callbacks or locks from a live menu context.
    state = {key: deepcopy(value) for key,value in (context or {}).items()
             if not key.startswith("_")}
    start = None if args.resume else int(args.start)
    requested_end = None if args.resume else (args.end or end or start + int(args.length))
    state.update(position=0, tests=0, gaps=[], gap_count=0, range_statistics=None)
    state.update(
        status="STARTING", start=start, end=requested_end,
        display_rows=args.display_rows, target_merit=float(args.target_merit),
        idle_start_available=False, speed_rate=None, rate=None, average_rate=None,
    )
    if dashboard_type is None:
        from console_ui import Dashboard
        dashboard_type = Dashboard
    dashboard = dashboard_type()
    # This frame precedes even the saved-session read, not only CUDA startup.
    try:
        dashboard.update(state, force=True)
        if args.resume and metadata_reader:
            metadata = metadata_reader(args.resume)
            config = metadata["configuration"]
            state.update(start=int(config["start"]), end=int(config["end"]),
                         position=int(metadata.get("positions",0)), tests=int(metadata.get("tests",0)),
                         configuration=config, target_merit=float(config.get("target_merit",args.target_merit)))
            dashboard.update(state,force=True)
    except BaseException:
        dashboard.finish()
        raise
    return dashboard
