"""R5 finite Native-session controller. GPU work exists only in its owned child.

Memory comes from Native --plan. Checkpoint replay is conservative; journals
deduplicate by lower prime, and an unknown crash lifetime never becomes a rate.
"""
from pathlib import Path
import copy
import ctypes
import datetime as dt
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

from pgn_menu import menu, read_key, final_screen_text, file_menu
from pgn_output import files_context,write_index_counts
from pgn_plan import choose_plan, query_plan,query_endpoints
from pgn_native_contract import PROTOCOL,require_new_configuration,module_metadata
from pgn_session import SessionStore, atomic_bytes, file_hash
from pgn_owned import create_owned
from pgn_queue import enqueue_next,pending_ranges,queue_tail_end,update_pending,remove_pending
from pgn_ui_service import MenuService
from pgn_developer_diag import DeveloperRecorder
from pgn_range_eta import measurement,retain
from pgn_queue_control import apply_queue_request


def profile_candidates(args,device,api):
    arch=f"sm{device['cc_major']}{device['cc_minor']}"
    expected_arch=int(str(device['cc_major'])+str(device['cc_minor']))
    paths=[]
    if args.worker:paths=[api.resolve_worker(args.worker)]
    else:
        for k in (64,32,16,8):
            if args.profile!='auto' and int(args.profile)!=k:continue
            try:paths.append(api.resolve_worker(None,arch,k))
            except RuntimeError:
                if args.profile!='auto':raise
    result=[];seen=set()
    for path in paths:
        m=module_metadata(path);actual=int(m['profile_k'])
        if m['build_arch']!=expected_arch:raise ValueError('Worker metadata architecture differs from selected GPU')
        if args.profile!='auto' and actual!=int(args.profile):raise ValueError('Requested profile differs from actual worker metadata')
        identity=(m['image_sha256'],actual,m['build_arch'])
        if identity in seen:continue
        seen.add(identity);result.append((actual,path))
    if not result:raise RuntimeError('No actual metadata-bound Native K-profile is installed')
    return result


def live_instance(instance):
    pid = int(instance.get("pid", 0));expected = str(instance.get("birth", ""))
    if not pid:
        return False
    if os.name != "nt":
        try:
            parts = Path(f"/proc/{pid}/stat").read_text().rsplit(")",1)[1].split()
            return str(parts[19]) == expected and parts[0] != "Z"
        except FileNotFoundError:
            return False
        except OSError:
            return True  # Unknown must not admit a second worker.
    from ctypes import wintypes as T
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.argtypes=[T.DWORD,T.BOOL,T.DWORD];k.OpenProcess.restype=T.HANDLE
    k.GetProcessTimes.argtypes=[T.HANDLE]+[ctypes.POINTER(T.FILETIME)]*4
    k.WaitForSingleObject.argtypes=[T.HANDLE,T.DWORD];k.WaitForSingleObject.restype=T.DWORD
    k.CloseHandle.argtypes=[T.HANDLE]
    handle=k.OpenProcess(0x100000|0x1000,False,pid)
    if not handle:
        return ctypes.get_last_error() != 87
    try:
        values=[T.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(handle,*[ctypes.byref(v) for v in values]):return True
        birth=str((values[0].dwHighDateTime<<32)|values[0].dwLowDateTime)
        return birth==expected and k.WaitForSingleObject(handle,0)==258
    finally:k.CloseHandle(handle)


def process_birth(process, clock):
    if os.name == "nt":return str(clock._creation)
    return Path(f"/proc/{process.pid}/stat").read_text().rsplit(")",1)[1].split()[19]


def original_emission_floor(store,args):
    config=store.meta["configuration"]
    require_new_configuration(config)
    for name in ("min_gap","count_gap","detail_gap"):
        original=int(config.get(name,config.get("min_gap",960)))
        if int(getattr(args,name))!=original:
            raise ValueError("Current session filters are immutable; Settings apply only to a NEW session: "+name)
    floor=store.original_floor
    if not 954<=floor<=2147483647:raise ValueError("Invalid durable original emission floor")
    return floor


def run(store, args, device, environment, gpu_info, api):
    original_floor=original_emission_floor(store,args)
    folder=store.folder;config=store.meta["configuration"]
    threshold=require_new_configuration(config);pin=threshold["threshold_policy"];effective=threshold["effective_gap_min"]
    start,end=int(config["start"]),int(config["end"]);total=end-start
    args._session_id=store.meta["session_id"]
    stop_file=folder/"stop.request";native_checkpoint=folder/"native-checkpoint.bin"
    records=store.gaps
    from pgn_publications import PublicationQueue,WorkRates
    work_rates=WorkRates()
    status="PREPARING";failure=None;startup_error=None;dashboard=api.Dashboard()
    active=0.0 if not store.meta.get("timing_complete",True) else float(store.meta.get("active_seconds",0))
    paused=float(store.meta.get("paused_seconds",0));rate_positions=0
    rate_unknown=not store.meta.get("timing_complete",True)
    position=int(store.meta.get("positions",0));tests=int(store.meta.get("tests",0))
    started=dt.datetime.fromisoformat(store.meta["created_utc"]);ended=dt.datetime.now(dt.timezone.utc)
    next_action=None;process=None;intent=None;clock=None;keys=api.PauseKeys();keys.__enter__()
    ui_state={}
    ui=MenuService();ui_keys_released=False
    developer=DeveloperRecorder()
    ui.ui_state=getattr(api,"_menu_saved_state",{})
    suppress_auto_next=False;unknown_current_wall=False
    checked_this_process=set()
    eta_worker_paths={}
    for eta_k in (8,16,32,64):
        try:eta_worker_paths[str(eta_k)]=str(api.resolve_worker(None,f"sm{device['cc_major']}{device['cc_minor']}",eta_k))
        except RuntimeError:pass
    report=folder/f"GapReport_details_ge{args.detail_gap}.txt"
    telemetry=api.Telemetry(folder,device['uuid'],True) if args.telemetry else None
    summary=(folder/"summary.log").open("a",encoding="utf-8")
    debug=(folder/"native-debug.log").open("a",encoding="utf-8") if args.debug else None

    view_cache={}
    cache_warning_seen=None
    def ui_view():
        key=(position,store.sequence,args.display_rows)
        if view_cache.get("key")!=key:
            below=start+position
            best=records.top(args.count_gap,below,args.display_rows)
            recent=records.recent(args.count_gap,below,args.display_rows)
            recent_lows={r[2] for r in recent}
            view_cache.update(key=key,count=records.count_rows(args.count_gap,below),
                              rows=[r for r in best if r[2] not in recent_lows]+list(reversed(recent)))
        return view_cache

    def context():
        current_eta=None
        if clock is not None and process is not None and process.poll() is None:
            current_eta=measurement(gpu_uuid=device['uuid'],worker_sha256=identity['worker_sha256'],profile_k=identity['profile_k'],configuration=config,
                positions=native_position-initial_native_position,seconds=clock.elapsed(),observed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                source="current session "+store.meta['session_id'],driver_api=device.get('cuda_driver_api_version'))
        active_info={'session_id':store.meta['session_id'],'status':status,'start':start,'end':end,'position':position,'tests':tests,
                'gpu_name':device['model'],'gpu_index':args.gpu,'gpu_uuid':device['uuid'],'folder':str(folder),'plan_id':store.meta.get('plan_id',config.get('plan_id')),
                'created_utc':store.meta['created_utc'],'started_utc':started.isoformat(),'ended_utc':ended.isoformat(),
                'job_active':process is not None and process.poll() is None,'next_range':store.meta.get('next_range')}
        diagnostic_fields={'startup_error':startup_error,'gpu_uuid':device['uuid'],'compute_capability':f"{device['cc_major']}.{device['cc_minor']}",
            'configuration':dict(config),'native_identity':(store.meta.get('current_chunk') or {}).get('identity'),
            'native_plan':(store.meta.get('current_chunk') or {}).get('plan'),'native_resources':getattr(api,'native_resources',None),
            'worker_active_seconds':None if unknown_current_wall else active+(clock.elapsed() if clock else 0),
            'rate_positions':rate_positions if rate_unknown else position,'rate_scope':'SINCE_RESUME' if rate_unknown else 'ACTIVE_WORKER_WALL',
            **work_rates.view(),
            'developer_diagnostics':developer.state() if developer.folder else getattr(api,'_developer_last',developer.state())}
        diagnostic_fields['eta_evidence']={'gpu_uuid':device['uuid'],'driver_api':device.get('cuda_driver_api_version'),'worker_paths':eta_worker_paths,'current':current_eta,'history':list(store.meta.get('eta_samples',[])),'profile_hint':next((sample.get('profile_k') for sample in reversed(store.meta.get('eta_samples',[])) if sample.get('configured_profile')=='auto'),None)}
        return {**files_context(folder,metadata=store.meta),**diagnostic_fields,"session_id":store.meta["session_id"],"status":status,
                "start":start,"end":end,"position":position,"tests":tests,
                "gpu_name":device["model"],"gpu_index":args.gpu,"min_gap":args.min_gap,"bins":args.bins,"top":args.report_top,"display_rows":args.display_rows,
                "next_range":store.meta.get('next_range'),'active_session':active_info,'output_root':str(folder.parent),'queued_ranges':pending_ranges(store),'queue_tail_end':queue_tail_end(store),
                'global_defaults':dict(ui_state.get('global_defaults_override',getattr(api,'_global_defaults',{}))),'_ui_state':ui_state,'_parser_factory':getattr(api,'argument_parser',None),'_range_validator':getattr(api,'validate_range',None)}

    def publish(force=False):
        nonlocal cache_warning_seen
        warning=getattr(store,'cache_error',None)
        if warning!=cache_warning_seen:
            if warning:summary.write('METADATA CACHE WARNING (committed SQLite remains authoritative): '+warning+'\n');summary.flush()
            cache_warning_seen=warning
        ui.publish(context())
        if ui.visible.is_set() or ui_keys_released:return
        elapsed=active+(clock.elapsed() if clock else 0)
        numerator=rate_positions if rate_unknown else position
        if args.headless or not sys.stdout.isatty():
            if force:print(f"[session] id={store.meta['session_id']} status={status} positions={position} tests={tests} counted={ui_view()['count']} output={folder}")
            return
        dashboard.update({"session_id":store.meta["session_id"],"gpu_name":device["model"],"gpu_index":args.gpu,
          "gpu_uuid":device["uuid"],"compute_capability":f"{device['cc_major']}.{device['cc_minor']}",
          "vram_mib":int(device["vram_bytes"])//(1024*1024),"driver":"CUDA API "+str(gpu_info.get("driver_version","--")),
          "host":"local","status":status+(' | NEXT queued' if store.meta.get('next_range',{}).get('status')=='PENDING' else ''),"start":start,"end":end,"position":position,"tests":tests,
          "elapsed":None if unknown_current_wall else elapsed,"rate":None if unknown_current_wall else numerator/elapsed if elapsed>0 else None,"paused_seconds":paused,
          "timing_unknown":unknown_current_wall,
          "rate_scope":"since resume, replay included" if rate_unknown else "active worker wall, initialization included",
          "minimum_gap":args.count_gap,"detailed_min_gap":args.detail_gap,"gap_count":ui_view()["count"],
          "gap_threshold_counts":{int(k):v for k,v in records.projection.value['threshold_counts'].items()},
          "gaps":ui_view()["rows"],"configuration":dict(config),"threshold_binding":(store.meta.get("current_chunk") or {}).get("threshold_binding") or store.meta.get("last_threshold_binding"),"display_rows":args.display_rows,"target_merit":args.target_merit,"outputfile":str(report),
          "clock_sm_mhz":telemetry.latest.get('sm_mhz') if telemetry and telemetry.thread and telemetry.thread.is_alive() else None,
          "clock_mem_mhz":telemetry.latest.get('memory_mhz') if telemetry and telemetry.thread and telemetry.thread.is_alive() else None,
          "queued_next":store.meta.get('next_range'),
          **work_rates.view(),
          "key_help":"M menu | F files | Q quit" if status=="COMPLETE" else "P pause/resume | M menu | F files | Q safe quit"},force=force)

    def outputs():
        below=start+position
        count_total=records.count_rows(args.count_gap,below)
        detail_total=records.count_rows(args.detail_gap,below)
        detail_rows=records.top(args.detail_gap,below,args.report_top)
        args._detail_total_count=detail_total
        files=write_index_counts(folder,args,end,position,status,records,api.atomic_text)
        report_text=api.brian_report(args.name,started,ended,device,args,end,position,status,active,detail_rows,paused,count_total)
        if unknown_current_wall:report_text += "\nTiming note: current worker wall is UNKNOWN; current rates are unavailable. The numeric active-seconds field above contains only the known component.\n"
        elif rate_unknown:report_text += "\nTiming note: historical crash wall is UNKNOWN; displayed active time/rates are since this resume only, replay included.\n"
        api.atomic_text(report,report_text)
        screen=final_screen_text(context())+"\nBEST / COUNTED GAPS\nGAP MERIT LOWER_PRIME\n"
        screen += "".join(f"{g} {m:.4f} {n}\n" for g,m,n in records.top(args.count_gap,below,args.display_rows))
        screen += "\nRECENT GAPS\n"+"".join(f"{g} {m:.4f} {n}\n" for g,m,n in records.recent(args.count_gap,below,args.display_rows))
        api.atomic_text(folder/"finalscreen.txt",screen)
        api.atomic_text(folder/"run.json",json.dumps({"schema":"PGN68_R5_RUN_V1","session_id":store.meta["session_id"],
          "status":status,"selected_gpu":device,"positions":position,"tests":tests,"active_seconds":None if unknown_current_wall else active,"known_active_seconds":active,
          "paused_seconds":paused,"timing_complete":not rate_unknown,"current_worker_wall_unknown":unknown_current_wall,"rate_scope":"SINCE_RESUME" if rate_unknown else "SESSION_ACTIVE",
          "count_gap":args.count_gap,"detail_gap":args.detail_gap,"threshold_policy":pin,"native_protocol":PROTOCOL,"threshold_binding":store.meta.get("last_threshold_binding"),"report_top":args.report_top,"display_rows":args.display_rows,"files":files,
          "failure":failure,"no_network_pgn":True},indent=2)+"\n")

    def add_gap(lower,upper,source):store.record_gap(lower,upper,source)

    def save_next(action):
        check=None  # Prepared queue; actual Native threshold binding is checked at Start.
        select_uuid=(lambda index:api.select_gpu(gpu_info['devices'],index)[0]['uuid']) if isinstance(gpu_info.get('devices'),list) else None
        entry=apply_queue_request(store,action,args.gpu,check,select_uuid)
        summary.write('QUEUE '+action.kind+' tail='+str(queue_tail_end(store))+' pending='+str(len(pending_ranges(store)))+'\n');summary.flush()
        publish(True);return entry


    def boundary(processed_end):
        if processed_end<=start:return
        low,high=api.final_boundary_pair(processed_end)
        if low>=start and high-low>=min(args.count_gap,args.detail_gap):add_gap(low,high,"exact_CPU_boundary")

    def release_menu_terminal():
        nonlocal dashboard,keys,ui_keys_released
        if ui_keys_released and not ui.visible.is_set():
            if ui.thread:ui.thread.join()
            keys=api.PauseKeys();keys.__enter__();dashboard=api.Dashboard();ui_keys_released=False
        for problem in ui.errors():
            summary.write('MENU ERROR (worker continues): '+problem+'\n');summary.flush()

    def dashboard_key():
        # Even one poll could steal a queued submenu command. The coordinator
        # must not consume input while the menu owns the terminal.
        if ui.visible.is_set() or ui_keys_released:return None
        return keys.poll()

    def open_live_menu(entry='menu'):
        nonlocal ui_keys_released
        if ui.visible.is_set():return
        release_menu_terminal()
        dashboard.finish();keys.__exit__(None,None,None);ui_keys_released=True
        ui.open(context(),entry=entry,runner=getattr(api,'_menu_runner',None))

    def close_live_menu():
        ui.close();release_menu_terminal()

    def start_developer():
        nonlocal telemetry
        if developer.state()['recording']:return developer.state()
        if telemetry:
            telemetry.finish()
            if telemetry.thread and telemetry.thread.is_alive():raise RuntimeError('The existing sampler is still stopping; no second reader was started.')
            telemetry=None
        state=developer.start(context());publish(True);return state

    def stop_developer(restore_normal=True):
        nonlocal telemetry
        state=developer.stop(context())
        if restore_normal and args.telemetry and not state['recording'] and telemetry is None:
            sample_folder=folder/('telemetry-'+str(time.time_ns()));sample_folder.mkdir(exist_ok=False)
            telemetry=api.Telemetry(sample_folder,device['uuid'],True)
        api._developer_last=state;publish(True);return state

    def menu_requests():
        # This function runs only on the worker/SQLite coordinator thread.
        release_menu_terminal();drain=None
        for request in ui.pending():
            action=SimpleNamespace(kind=request.kind,values=request.values)
            if action.kind in ('diagnostic_start','diagnostic_stop'):
                try:
                    state=start_developer() if action.kind=='diagnostic_start' else stop_developer()
                    ui.respond(request,ok=True,message=state['status']+(': '+str(state['error']) if state.get('error') else ''))
                except (OSError,ValueError,RuntimeError) as problem:ui.respond(request,ok=False,message=str(problem))
            elif action.kind=='display_rows':
                try:
                    from pgn_ui_options import display_rows
                    args.display_rows=display_rows(action.values['display_rows']);view_cache.clear()
                    ui.respond(request,ok=True,message='Display rows applied to Best and Recent; worker and exports unchanged.')
                except Exception as error:ui.respond(request,ok=False,message=str(error))
            elif action.kind in ('queue','queue_edit','queue_delete'):
                if drain is not None or (process is not None and intent is not None):
                    ui.respond(request,ok=False,message='A safe session transition is already pending.');continue
                try:
                    save_next(action)
                    ui.respond(request,ok=True,message='Queue saved. The current worker continues; pending ranges run in order after it.')
                except Exception as problem:ui.respond(request,ok=False,message=str(problem))
            elif drain is None:
                if process is not None and intent is not None and action.kind not in ('quit','stop'):
                    ui.respond(request,ok=False,message='A safe session transition is already pending. Wait for its checkpoint before requesting another range.');continue
                drain=action
                ui.respond(request,ok=True,message='Explicit '+action.kind.upper()+' accepted; the worker will stop cooperatively.')
            else:ui.respond(request,ok=False,message='A safe session transition is already pending.')
        return drain

    def hold_results():
        nonlocal next_action
        if args.headless or not sys.stdin.isatty():return
        while True:
            publish()
            action=menu_requests()
            if action:
                next_action=action;close_live_menu();return
            if store.meta.get('next_range',{}).get('status')=='PENDING':
                next_action=SimpleNamespace(kind='activate_next',values={});return
            if not ui.visible.is_set():
                key=dashboard_key()
                if key=='m':open_live_menu()
                elif key=='f':open_live_menu('files')
                elif key=='q':next_action=SimpleNamespace(kind='quit',values={});return
            time.sleep(.05)


    def recover_previous():
        nonlocal position,tests
        chunk=store.meta.get("current_chunk");instance=chunk.get("instance") if chunk else None
        if instance and not instance.get("closed") and live_instance(instance):
            stop_file.write_text("durable resume requests old bound worker to drain\n")
            until=time.monotonic()+90
            while live_instance(instance) and time.monotonic()<until:time.sleep(.1)
            if live_instance(instance):raise RuntimeError("The previous exact-bound worker is still live; refusing a second worker")
        if instance:instance["closed"]=True
        if os.name=='nt':
            from pgn_owner_recovery import recover
            if recover(store):
                position=int(store.meta['positions']);tests=int(store.meta['tests'])

    def select_chunk():
        chunk=store.meta.get("current_chunk")
        if chunk and (chunk.get("instance") or {}).get("closed") and chunk.get("trusted_checkpoint") and int(chunk["identity"]["length"])>64*10**12:
            native_prefix,native_prefix_tests=store.restore_checkpoint(native_checkpoint)
            boundary(int(chunk["identity"]["start"])+native_prefix)
            store.retire_closed_prefix(native_prefix,native_prefix_tests)
            chunk=None
        if chunk:
            identity=chunk["identity"]
            # Serialized paths do not grant permission to execute an arbitrary
            # file. Re-resolve only the installed/package K-profile and hash it.
            trusted=api.resolve_checkpoint_worker(identity,f"sm{device['cc_major']}{device['cc_minor']}",identity["profile_k"])
            store.trusted_worker_path(trusted)
            checked=query_plan(identity["worker"],int(identity["start"]),int(identity["length"]),environment,api.child_options(),identity["gap_min"],pin)
            if not checked.get("range_valid") or not checked.get("fits") or checked.get("profile_k")!=identity["profile_k"]:
                raise RuntimeError("Pinned resume profile does not fit actual current bytes: "+str(checked.get("reason")))
            if checked.get("worker_source_sha256")!=identity["worker_source_sha256"]:raise ValueError("Resume source fingerprint differs")
            chunk["plan"]=checked;chunk["threshold_binding"]=checked["threshold_binding"];store.meta["last_threshold_binding"]=checked["threshold_binding"];store.save()
            return chunk
        remaining=total-position
        probe=min(remaining,64*10**12,(4194304-2)*1006632960,int(pin["segments"][0]["end"])-(start+position),(1<<64)-((start+position)&((1<<64)-1)))
        if args.chunk_length is not None:probe=min(probe,args.chunk_length)
        candidates=profile_candidates(args,device,api)
        query=lambda worker,first,length:query_plan(worker,first,length,environment,api.child_options(),effective,pin)
        if candidates and candidates[0][0] is None:
            first_plan=query(candidates[0][1],start+position,probe)
            candidates=[(int(first_plan["profile_k"]),candidates[0][1])]
        chosen=choose_plan(candidates,start+position,probe,query)
        plan=chosen["plan"]
        plan_note=f"Memory plan: K{chosen['profile_k']}, required {plan['required_device_bytes']} bytes / free {plan['free_device_bytes']} bytes; chunk {chosen['length']} positions"
        summary.write(plan_note+'\n');summary.flush()
        if args.headless or not sys.stdout.isatty():print(plan_note)
        chunk=store.bind_chunk(start=start+position,length=chosen["length"],worker=chosen["worker"],
              worker_sha256=file_hash(chosen["worker"]),profile_k=chosen["profile_k"],base_positions=position,base_tests=tests,
               gap_min=effective,threshold_policy_sha256=pin["sha256"],worker_source_sha256=plan["worker_source_sha256"])
        if not plan.get("threshold_binding"):raise ValueError("Native threshold plan was not admitted")
        chunk["plan"]=plan;chunk["threshold_binding"]=plan["threshold_binding"];store.meta["last_threshold_binding"]=plan["threshold_binding"];store.save();return chunk

    try:
        recover_previous()
        if store.meta.get("current_chunk"):
            restore_pos,restore_tests=store.restore_checkpoint(native_checkpoint)
            identity=store.meta["current_chunk"]["identity"]
            position=identity["base_positions"]+restore_pos
            tests=identity["base_tests"]+restore_tests
            if (position,tests)!=(store.meta['positions'],store.meta['tests']):
                store.recovery_rewind(position,tests,unknown_wall=rate_unknown)
        # Both endpoints are checked by Native without search allocations.
        endpoints=profile_candidates(args,device,api)
        checker=endpoints[0][1]
        last=query_endpoints(checker,config,environment,api.child_options())
        while position<total or store.meta.get("current_chunk"):
            chunk=select_chunk();identity=chunk["identity"]
            if getattr(args,"_confirm_plan",False) and not args.headless and sys.stdin.isatty():
                print(f"Range {start} -> {end}; {total} positions. ETA requires measured throughput; no estimate is invented.")
                print("Press1 to start this planned range, or0 to return without launch.")
                if read_key("01")=="0":
                    status="PREPARED";next_action=SimpleNamespace(kind="return",values={});break
                args._confirm_plan=False
            native_position,native_tests=store.restore_checkpoint(native_checkpoint)
            initial_native_position=native_position;initial_native_tests=native_tests
            stop_file.unlink(missing_ok=True)
            emit=original_floor
            if identity.get("gap_min")!=effective or identity.get("threshold_policy_sha256")!=pin["sha256"]:raise ValueError("Frozen threshold binding changed")
            if identity.get("emit_min_gap")!=original_floor:
                raise ValueError("Checkpoint/chunk original emission-floor binding changed")
            command=[identity["worker"],"--engine","walk","--start",identity["start"],"--length",identity["length"],
                     "--gap-min",str(identity["gap_min"]),"--emit-min-gap",str(emit),"--device","0","--no-records",
                     "--state",str(native_checkpoint),"--stop-file",str(stop_file)]
            if args.debug:command.extend(("--log",str(folder/"native-debug-gaps.log")))
            paid=store.meta.setdefault("self_tests",{})
            if identity["worker_sha256"] not in checked_this_process:
                if args.skip_self_test:paid[identity["worker_sha256"]]={"status":"SKIPPED_USER"}
                else:
                    diag=folder/("self-test-"+identity["worker_sha256"][:12]+"-"+str(time.time_ns()))
                    paid[identity["worker_sha256"]]=api.run_diagnostic(Path(identity["worker"]),environment,diag)
                store.save()
                checked_this_process.add(identity["worker_sha256"])
            store.before_launch();before=time.monotonic();utc=dt.datetime.now(dt.timezone.utc)
            factory=getattr(api,'create_owned',create_owned)
            process=factory(command,environment,device['uuid'])
            clock=api.ProcessClock(process,before,utc)
            birth=getattr(process,'birth',None) or process_birth(process,clock)
            store.started(process.pid,birth)
            owner_file=folder/"native-owner-current.json"
            api.atomic_text(owner_file,json.dumps({'pid':process.pid,'birth':str(birth),'image_sha256':identity['worker_sha256'],
                           'configuration_sha256':store.configuration_hash(),'wal_sequence':store.sequence,
                           'session_id':store.meta['session_id'],'profile_k':identity['profile_k'],'emit_min_gap':original_floor},indent=2)+'\n')
            process.commit_identity(owner_file)
            process.resume()  # Windows entrypoint cannot reach CUDA before WAL.
            events=PublicationQueue(maxsize=64)
            work_rates.begin_instance()
            reader_stop=threading.Event()
            def enqueue(value):
                while not reader_stop.is_set():
                    try:events.put(value,timeout=.1);return
                    except queue.Full:pass
            def receive(current):
                try:
                    for line in current.stdout:
                        if reader_stop.is_set():break
                        if len(line)>65536:raise ValueError('Oversized Native output line')
                        enqueue(line.rstrip("\r\n"))
                except Exception as error:enqueue(('reader_error',str(error)))
                finally:enqueue(None)
            reader=threading.Thread(target=receive,args=(process,),daemon=True);reader.start()
            watcher_done=threading.Event();watcher_errors=[]
            def observe(current,current_clock):
                try:current.wait();current_clock.finish()
                except Exception as error:
                    watcher_errors.append(str(error));enqueue(('clock_error',str(error)))
                finally:watcher_done.set()
            watcher=threading.Thread(target=observe,args=(process,clock),daemon=True);watcher.start()
            status="STARTING";intent=None;deadline=None;reader_done=False;last_summary=time.monotonic()
            summary.write(f"START chunk={chunk['index']} K={identity['profile_k']} worker_sha={identity['worker_sha256']} input={identity['start']}+{identity['length']} emit={emit}\n");summary.flush()
            if getattr(api,'_menu_reopen',False):
                api._menu_reopen=False;open_live_menu(getattr(api,'_menu_reopen_entry','menu'))
            while not(reader_done and watcher_done.is_set() and process.poll() is not None and events.empty()):
                try:
                    action=menu_requests()
                    if action is not None and intent is None:
                        if action.kind in ('new','resume','activate_queued'):next_action=action;intent='switch'
                        elif action.kind in ('pause','stop','quit'):intent=action.kind
                        close_live_menu()
                    elif action is not None and action.kind in ('quit','stop'):
                        # An explicit stop overrides a planned switch while the
                        # same worker drains; it must never launch that next range.
                        intent=action.kind;next_action=None;status='STOP REQUESTED';close_live_menu()
                    key=dashboard_key() if not ui.visible.is_set() else None
                    if key in ('m','f'):open_live_menu('menu' if key=='m' else 'files')
                    elif key=='q' and intent is None:intent='quit'
                    elif key=='p' and intent is None and status in ('SEARCHING','RUNNING'):intent='pause'
                    if intent is not None and deadline is None:
                        stop_file.write_text(intent+"\n");deadline=time.monotonic()+90
                        status="PAUSING" if intent in ('pause','switch') else "STOP REQUESTED"
                    try:line=events.get(timeout=.1)
                    except queue.Empty:line=""
                    if isinstance(line,tuple):raise RuntimeError('Native '+line[0]+': '+line[1])
                    if line is None:reader_done=True
                    elif line:
                        if debug:debug.write(line+"\n");debug.flush()
                        for match in api.GAP.finditer(line):
                            _,gap,low,high=match.groups();gap,low,high=int(gap),int(low),int(high)
                            if high-low!=gap:raise ValueError("Native gap endpoint conflict")
                            add_gap(low,high,"Native_verified")
                        samples=getattr(line,"samples",())
                        if samples:work_rates.add(samples)
                        match=api.COUNTERS.search(line)
                        if match:
                            new_position,new_tests=map(int,match.groups())
                            if intent is None:status="SEARCHING"
                            plan_id=config.get('plan_id')
                            if plan_id and not store.meta.get('plan_claimed'):
                                try:
                                    from pgn_draft_plans import remove
                                    remove({'output_root':config.get('plan_root')or str(folder.parent)},plan_id)
                                    store.meta['plan_claimed']=True;store.meta['plan_id']=plan_id;store.save()
                                except (OSError,ValueError) as problem:
                                    store.meta['plan_claim_error']=str(problem)
                            if not native_position<=new_position<=int(identity["length"]) or new_tests<native_tests:raise ValueError("Native counters retreated")
                            rate_positions+=new_position-native_position
                            native_position,native_tests=new_position,new_tests
                            position=max(position,identity["base_positions"]+native_position)
                            tests=max(tests,identity["base_tests"]+native_tests)
                            store.accepted_progress(position,tests)
                        if "PGN CUDA" in line or "failed" in line.lower():summary.write(line+"\n");summary.flush()
                    if deadline and time.monotonic()>=deadline and process.poll() is None:
                        api.terminate_owned(process);raise RuntimeError("Worker did not drain within90 seconds")
                    if time.monotonic()-last_summary>=10:
                        summary.write(f"PROGRESS positions={position} tests={tests}\n");summary.flush();last_summary=time.monotonic()
                    publish()
                except KeyboardInterrupt:
                    intent="stop";stop_file.write_text("interrupt\n");deadline=deadline or time.monotonic()+90;status="STOP REQUESTED"
            code=process.wait();reader.join();watcher.join()
            if watcher_errors:raise RuntimeError('Native clock_error: '+watcher_errors[0])
            duration,ended=clock.finish();active+=duration;clock=None
            summary.write(f"CLOSED pid={process.pid} exit={code} seconds={duration:.7f} native_positions={native_position} native_tests={native_tests}\n");summary.flush()
            process.close();process=None
            if code:raise RuntimeError(f"Native worker exited{code}; inspect summary.log"+(" and native-debug.log" if args.debug else ""))
            closed_eta=measurement(gpu_uuid=device['uuid'],worker_sha256=identity['worker_sha256'],profile_k=identity['profile_k'],configuration=config,
                positions=native_position-initial_native_position,seconds=duration,observed_utc=ended.isoformat(),source="saved session "+store.meta['session_id'],closed=True,driver_api=device.get('cuda_driver_api_version'))
            store.meta['eta_samples']=retain(store.meta.get('eta_samples',[]),closed_eta)
            boundary(int(identity["start"])+native_position)
            complete=native_position==int(identity["length"])
            if not complete:store.capture_closed_checkpoint(native_checkpoint,native_position,native_tests)
            store.closed("PAUSED" if not complete else "CHUNK_COMPLETE",active,paused,chunk_complete=complete)
            if complete and position==total:
                status='COMPLETE'
                if intent=='quit':next_action=SimpleNamespace(kind='quit',values={})
                if intent in ('quit','stop','switch'):suppress_auto_next=True
                break
            if intent in ('pause','quit','stop','switch') or not complete:
                status='PAUSED';outputs();publish(True);pause_start=time.monotonic()
                if intent=='switch':break
                if intent=='quit':status='STOPPED';next_action=SimpleNamespace(kind='quit',values={});break
                if intent=='stop':status='STOPPED';store.closed(status,active,paused);break
                while True:
                    action=menu_requests()
                    if action:
                        if action.kind in ('new','resume','activate_queued','quit','stop'):
                            next_action=action;close_live_menu();break
                    if not ui.visible.is_set():
                        key=dashboard_key()
                        if key=='p':break
                        if key=='m':open_live_menu()
                        elif key=='f':open_live_menu('files')
                        elif key=='q':next_action=SimpleNamespace(kind='quit',values={});break
                    publish();time.sleep(.05)
                paused+=time.monotonic()-pause_start
                if next_action:break
        if next_action is None and position==total:
            status="COMPLETE";boundary(end);store.closed(status,active,paused)
        elif next_action is not None:status="PAUSED" if position<total else "COMPLETE"
        else:store.closed(status,active,paused)
        outputs();publish(True)
        if next_action is not None and next_action.kind=='queue':
            save_next(next_action);next_action=SimpleNamespace(kind='activate_next',values={}) if status=='COMPLETE' else SimpleNamespace(kind='resume_current',values={})
        if status=='COMPLETE' and next_action is None and store.meta.get('next_range',{}).get('status')=='PENDING' and not suppress_auto_next:
            next_action=SimpleNamespace(kind='activate_next',values={})
        if next_action is None:hold_results()
        if next_action is not None and next_action.kind=='queue':
            save_next(next_action);next_action=SimpleNamespace(kind='activate_next',values={}) if status=='COMPLETE' else SimpleNamespace(kind='resume_current',values={})
    except Exception as error:
        failure=str(error);status="FAILED"
        if 'reader_stop' in locals():reader_stop.set()
        if process is not None and process.poll() is None:api.terminate_owned(process)
        if clock:
            try:
                duration,ended=clock.finish();active+=duration
            except Exception as timing_error:
                unknown_current_wall=True;rate_unknown=True;store.meta['timing_complete']=False
                failure += '; worker wall UNKNOWN: '+str(timing_error)
            finally:clock=None
        if process is not None:process.close();process=None
        if callable(getattr(api,'remember_start_failure',None)):
            startup_error=api.remember_start_failure(context(),error,'search worker',folder)
        else:startup_error={'message':failure,'stage':'search worker','path':str(folder/'summary.log')}
        store.closed(status,active,paused);outputs();publish(True)
        summary.write("SESSION ERROR: "+failure+"\n");summary.flush()
        if args.headless or not sys.stdout.isatty():print("Session error:",failure,file=sys.stderr)
        else:open_live_menu()
        hold_results()
        if next_action is not None and next_action.kind=='queue':save_next(next_action);next_action=SimpleNamespace(kind='resume_current',values={})
    finally:
        # Closing a UI page never writes stop.request. A pending explicit
        # transition uses the existing worker drain before reaching here.
        reopen=ui.visible.is_set() and next_action is not None and next_action.kind in ('activate_next','resume_current')
        close_live_menu()
        api._menu_saved_state=ui.ui_state
        api._menu_reopen=reopen
        api._menu_reopen_entry='menu'
        if 'reader_stop' in locals():reader_stop.set()
        if process is not None and process.poll() is None:api.terminate_owned(process)
        if process is not None:process.close()
        publish(True);dashboard.finish();keys.__exit__(None,None,None);summary.close()
        if telemetry:telemetry.finish()
        if developer.collector:
            try:api._developer_last=developer.stop(context())
            except (OSError,RuntimeError,ValueError):pass
        if debug:debug.close()
    return {"status":status,"action":next_action,"folder":folder,"failure":failure}
