from pathlib import Path
import json,sqlite3,sys,tempfile,shutil
from contextlib import closing
D=Path(__file__).resolve().parent;sys.path.insert(0,str(D.parent/'frontend'))
from pgn_session import SessionStore
from pgn_native_contract import fields
from pgn_projection import Projection
MISSING=[
 (954,153002999806485841567),(960,153002999731762183543),
 (992,153002999665956092357),(956,153002999607586679861),
 (954,153002999481929684207),(962,153002999207685514649),
 (990,153002998962354866137),(982,153002998790622390379),
 (984,153002998739946562073),(954,153002998594421965607),
 (956,153002998590149944937),(1070,153002998290330706503)]
baseline=[(153002998210154873587,153002998210154874577,990)]
assert all(lo>baseline[-1][0]for gap,lo in MISSING)
start=153000000000000000000;end=153003000000000000000
cfg=dict(start=str(start),end=str(end),bins=100,target_merit=32,report_top=100,**fields(start,end,954))
def read(path):
 with closing(sqlite3.connect(path))as db:
  assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
  return {int.from_bytes(lo,'big'):int.from_bytes(hi,'big')for lo,hi in db.execute('SELECT lo,hi FROM gaps')}
with tempfile.TemporaryDirectory(prefix='scout-robert12-')as tmp:
 root=Path(tmp);store=SessionStore.create(root/'session',cfg,{'uuid':'owned-cpu-regression-only'})
 # Fast fixture construction only: the supplied baseline is already accepted data.
 # The twelve new records below use the real fsynced SessionStore.record_gap path.
 with store.gaps.db:
  for i,(lo,hi,gap)in enumerate(baseline,1):
   assert hi-lo==gap
   store.gaps.projection.value=store.gaps._insert_gap(lo,hi,i)
  store.gaps.put_meta('projection',store.gaps.projection.value)
 store.gaps.checkpoint()
 dbpath=root/'session/session-index.sqlite3'
 reader=sqlite3.connect(dbpath);assert reader.execute('SELECT COUNT(*) FROM gaps').fetchone()[0]==len(baseline)
 for gap,lo in sorted(MISSING,key=lambda row:row[1]):assert store.record_gap(lo,lo+gap,'Robert supplied terminal row')
 store.accepted_progress(end-start,0)
 before=root/'before.sqlite';shutil.copyfile(dbpath,before);prior=read(before)
 assert len(prior)==len(baseline) and all(lo not in prior for gap,lo in MISSING)
 store.closed('COMPLETE',1.0,0.0)
 after=root/'after.sqlite';shutil.copyfile(dbpath,after);fixed=read(after)
 assert len(fixed)==len(baseline)+12 and all(fixed.get(lo)==lo+gap for gap,lo in MISSING)
 assert all(fixed[lo]==hi for lo,hi,gap in baseline)
 assert store.gaps.policy_count('count',end)==len(baseline)+12
 checkpoint=dict(store.meta['sqlite_checkpoint']);assert checkpoint['complete']
 reader.close();store.close();reloaded=SessionStore.load(root/'session')
 try:
  assert len(reloaded.gaps)==len(baseline)+12 and reloaded.gaps.policy_count('count',end)==len(baseline)+12
 finally:reloaded.close()
v=dict(PASS=True,baseline_rows=len(baseline),supplied_terminal_rows=12,before_standalone_copy_rows=len(baseline),after_closed_standalone_copy_rows=len(baseline)+12,missing_after_fix=0,all_original_rows_preserved=True,SQLite_integrity='ok',reopen_rows=len(baseline)+12,actual_production_journal_and_close_path=True,checkpoint=checkpoint,original_SQLite_and_WAL_not_supplied=True)
(D/'ROBERT12-TEST.json').write_text(json.dumps(v,indent=2));print(json.dumps(v),flush=True)
