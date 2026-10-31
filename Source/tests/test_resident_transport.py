from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"frontend"))
import unittest,tempfile,queue,threading,json,time,uuid
from pgn_resident import Resident,ResidentProtocolError,atomic,frame
class Owner:
 pid=777;birth='134379000000000001'
 def __init__(self):self.q=queue.Queue();self.code=None;self.resumed=False;self.committed=False;self.closed=False
 @property
 def stdout(self):
  while True:
   line=self.q.get()
   if line is None:return
   yield line
 def poll(self):return self.code
 def commit_identity(self,path):self.committed=True
 def resume(self):self.resumed=True
 def wait(self,timeout=None):
  self.code=0;self.q.put(None);return 0
 def close(self,force=False):self.closed=True
 def terminate(self):self.code=9;self.q.put(None)
class ResidentTests(unittest.TestCase):
 def test_verified_receipt_releases_command_guard_once(self):
  with tempfile.TemporaryDirectory()as d:
   worker,owner=self.setup_worker(d);job=worker.current;closed=[]
   from types import SimpleNamespace
   job._input_guard=SimpleNamespace(close=lambda:closed.append(True))
   self.done(worker,job)
   self.assertEqual(job.result()['exit'],0);self.assertEqual(job.result()['exit'],0)
   self.assertEqual(closed,[True]);self.assertIsNone(job._input_guard)
   worker.shutdown(force=True)
 def test_invalid_receipt_keeps_guard_until_owner_closes(self):
  with tempfile.TemporaryDirectory()as d:
   worker,owner=self.setup_worker(d);job=worker.current;closed=[]
   from types import SimpleNamespace
   job._input_guard=SimpleNamespace(close=lambda:closed.append(True))
   self.done(worker,job,nonce='f'*32)
   with self.assertRaises(ResidentProtocolError):job.result()
   self.assertEqual(closed,[])
   worker.shutdown(force=True);self.assertEqual(closed,[True])
 def setup_worker(self,d):
  owner=Owner();worker=Resident(owner,d,['worker-k64','--start','150000000000000000000','--length','1000'],uuid.uuid4().hex);return worker,owner
 def done(self,worker,job,marker=True,pid=None,nonce=None):
  atomic(worker.directory/f'{job.sequence}.done.json',json.dumps(dict(schema='SCOUT_RESIDENT_JOB_V1',sequence=job.sequence,nonce=nonce or job.nonce,pid=pid or job.pid,exit=0,wall_ns=100)).encode())
  if marker:worker.owner.q.put('[phase0-gpu] --- end ---\n')
 def identity(self,d,nonce):
  p=Path(d)/'owner.json';p.write_text(json.dumps({'pid':777,'birth':'134379000000000001','job_nonce':nonce}));return p
 def finish(self,w):
  try:w.shutdown()
  except ResidentProtocolError:pass
 def test_three_jobs_keep_one_owner_and_exact_unicode_arguments(self):
  with tempfile.TemporaryDirectory()as d:
   w,o=self.setup_worker(d)
   try:
    j=w.current;j.commit_identity(self.identity(d,j.nonce));j.resume();self.done(w,j);self.assertEqual(j.wait(1),0);list(j.stdout);j.close();self.assertIsNone(o.poll());self.assertFalse(j.process_exited())
    for bits,start in [(95,'20000000000000000000000000000'),(67,'100000000000000000000')]:
     j=w.next(['worker-k64','--start',start,'--length','1000','--state','space é/state.bin']);j.commit_identity(self.identity(d,j.nonce));j.resume();wire=(Path(d)/f'{j.sequence}.args').read_bytes();self.assertIn('space é/state.bin'.encode(),wire);self.done(w,j);self.assertEqual(j.wait(1),0);list(j.stdout);j.close();self.assertEqual(j.pid,777);self.assertIsNone(o.poll())
   finally:self.finish(w)
   self.assertTrue(o.closed);self.assertFalse(w.reader.is_alive())
 def test_science_cannot_dispatch_before_wal(self):
  with tempfile.TemporaryDirectory()as d:
   w,o=self.setup_worker(d)
   try:
    with self.assertRaises(ResidentProtocolError):w.current.resume()
    self.assertFalse(o.resumed)
   finally:self.finish(w)
 def test_done_file_before_output_does_not_credit_early(self):
  with tempfile.TemporaryDirectory()as d:
   w,o=self.setup_worker(d)
   try:
    self.done(w,w.current,marker=False);self.assertIsNone(w.current.poll());o.q.put('[phase0-gpu] --- end ---\n');self.assertEqual(w.current.wait(1),0)
   finally:self.finish(w)
 def test_wrong_pid_and_nonce_are_rejected(self):
  for wrong in ('pid','nonce'):
   with tempfile.TemporaryDirectory()as d:
    w,o=self.setup_worker(d)
    try:
     self.done(w,w.current,pid=778 if wrong=='pid'else None,nonce='0'*32 if wrong=='nonce'else None)
     with self.assertRaises(ResidentProtocolError):w.current.poll()
    finally:self.finish(w)
 def test_truncated_output_is_not_success(self):
  with tempfile.TemporaryDirectory()as d:
   w,o=self.setup_worker(d)
   try:
    self.done(w,w.current,marker=False);o.code=0;o.q.put(None);w.reader.join(1)
    with self.assertRaises(ResidentProtocolError):w.current.poll()
   finally:self.finish(w)
 def test_profile_module_change_requires_a_new_owner(self):
  with tempfile.TemporaryDirectory()as d:
   w,o=self.setup_worker(d)
   try:
    self.done(w,w.current);w.current.wait(1);list(w.current.stdout);w.current.close()
    with self.assertRaises(ResidentProtocolError):w.next(['worker-k32','--plan'])
   finally:self.finish(w)
 def test_stale_wal_nonce_cannot_dispatch_another_job(self):
  with tempfile.TemporaryDirectory()as d:
   w,o=self.setup_worker(d)
   try:
    j=w.current;stale=self.identity(d,'0'*32)
    with self.assertRaises(ResidentProtocolError):j.commit_identity(stale)
    self.assertFalse(j.committed);self.assertFalse(o.resumed)
    j.commit_identity(self.identity(d,j.nonce));j.resume();self.done(w,j);j.wait(1);list(j.stdout);j.close()
    old=j.nonce;j=w.next(['worker-k64','--start','150000000000000001000','--length','1000'])
    with self.assertRaises(ResidentProtocolError):j.commit_identity(self.identity(d,old))
    with self.assertRaises(ResidentProtocolError):j.resume()
    self.assertFalse((Path(d)/'1.args').exists())
   finally:self.finish(w)

 def test_wire_budgets_and_nul_are_rejected(self):
  for args in ([],['a']*97,['a\0b'],['x'*32769]):
   with self.assertRaises(ResidentProtocolError):frame(args,'a'*32)
if __name__=='__main__':unittest.main()
