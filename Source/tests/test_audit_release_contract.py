from pathlib import Path
import sys,tempfile,sqlite3,shutil,json,hashlib
from contextlib import closing
D=Path(__file__).resolve().parent;F=D.parent/'frontend'
sys.path.insert(0,str(F))
from pgn_threshold_policy import pin_range,require_backend_binding
from pgn_native_contract import fields
from pgn_index import GapIndex
start=153000000000000000000;end=start+10000
for gap in (720,950):
 p=pin_range(start,end,gap,policy_id='POINTWISE_RETAINED_MERIT_AUDIT_15')
 f=fields(start,end,pin=p)
 assert (f['effective_gap_min'],f['min_gap'],f['count_gap'],f['detail_gap'],f['emit_min_gap'])==(gap,)*5
 require_backend_binding(dict(threshold_schema='PGN_THRESHOLD_BINDING_V1',threshold_policy_sha256=p['sha256'],gap_min=gap),p,start)
 assert f['effective_gap_min']!=800
p=pin_range(start,end,720,policy_id='POINTWISE_RETAINED_MERIT_AUDIT_15')
cfg=dict(start=str(start),end=str(end),min_gap=720,count_gap=720,detail_gap=720,threshold_policy=p,bins=10,report_top=100,target_merit=32)
digest=hashlib.sha256(json.dumps(cfg,sort_keys=True,separators=(',',':')).encode()).hexdigest()
with tempfile.TemporaryDirectory(prefix='scout-last-row-')as folder:
 root=Path(folder);path=root/'index.sqlite3';index=GapIndex(path,'audit-contract',cfg,digest)
 index.apply(dict(type='gap',sequence=1,lower=str(start+100),upper=str(start+820)),100)
 index.apply(dict(type='progress',sequence=2,positions=1000,tests=10),200)
 assert index.checkpoint()['complete']
 reader=sqlite3.connect(path);assert reader.execute('select count(*) from gaps').fetchone()[0]==1
 # The terminal lower prime is owned even when its upper prime lies past END.
 index.apply(dict(type='gap',sequence=3,lower=str(end-100),upper=str(end+850)),300)
 index.apply(dict(type='progress',sequence=4,positions=end-start,tests=20),400)
 before=root/'before.sqlite';shutil.copyfile(path,before)
 with closing(sqlite3.connect(before))as check:assert check.execute('select count(*) from gaps').fetchone()[0]==1
 index.close();after=root/'after.sqlite';shutil.copyfile(path,after)
 with closing(sqlite3.connect(after))as check:
  assert check.execute('select count(*) from gaps').fetchone()[0]==2
  assert check.execute('select gap from gaps order by seq desc limit 1').fetchone()[0]==950
 reader.close()
v=dict(PASS=True,actual_thresholds=[720,950],hidden_800=False,last_gap_copy_before_checkpoint=1,last_gap_copy_after_checkpoint=2,terminal_upper_past_end_preserved=True,real_GPU_execution=False)
(D/'TESTS.json').write_text(json.dumps(v,indent=2));print(json.dumps(v),flush=True)
