"""A completed resident job is durable without inventing process closure."""
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from pgn_session import SessionStore
from pgn_native_contract import fields
from pgn_resident import WorkReceipt

class ResidentJournalTests(unittest.TestCase):
 def setup_store(self,folder):
  start=150000000000000000000
  cfg=dict(start=str(start),end=str(start+10000),bins=10,target_merit=32,report_top=100,**fields(start,start+10000,960))
  store=SessionStore.create(folder,cfg,{'uuid':'cpu-resident-journal'})
  pin=cfg['threshold_policy']
  store.bind_chunk(start=start,length=10000,worker=Path(folder)/'worker',worker_sha256='A'*64,profile_k=64,gap_min=960,threshold_policy_sha256=pin['sha256'],worker_source_sha256='B'*64)
  store.started(777,'134379000000000001',job_nonce='a'*32)
  cmd=('worker','--start',str(start),'--length','10000','--gap-min','960')
  return store,WorkReceipt(777,'134379000000000001','a'*32,0,cmd,0)

 def test_completed_job_replays_without_claiming_process_exit(self):
  with tempfile.TemporaryDirectory()as d:
   s,r=self.setup_store(d)
   s.closed('CHUNK_COMPLETE',1.2,0,chunk_complete=True,instance_closed=False,work_receipt=r)
   closed=s.meta['closed_chunks'][-1]
   self.assertFalse(closed['instance']['closed']);self.assertTrue(closed['instance']['work_closed'])
   s.close();s=SessionStore.load(d)
   try:
    self.assertIsNone(s.meta['current_chunk']);self.assertEqual(s.meta['completed_chunk_count'],1)
    self.assertEqual(s.meta['state'],'CHUNK_COMPLETE')
   finally:s.close()

 def test_missing_or_wrong_receipt_cannot_advance_durable_state(self):
  with tempfile.TemporaryDirectory()as d:
   s,r=self.setup_store(d)
   try:
    for receipt in(None,WorkReceipt(778,r.birth,r.nonce,0,r.command,0),WorkReceipt(r.pid,r.birth,'b'*32,0,r.command,0),WorkReceipt(r.pid,r.birth,r.nonce,0,r.command[:-1]+('962',),0)):
     sequence=s.sequence
     with self.assertRaises(ValueError):s.closed('CHUNK_COMPLETE',1,0,True,False,receipt)
     self.assertEqual(s.sequence,sequence);self.assertIsNotNone(s.meta['current_chunk'])
   finally:s.close()

 def test_receipt_after_journal_fault_is_recovered_exactly_once(self):
  with tempfile.TemporaryDirectory()as d:
   s,r=self.setup_store(d)
   original=s.gaps.apply
   def fail_chunk(event,offset):
    if event['type']=='chunk_closed':raise OSError('interrupted after fsynced journal')
    return original(event,offset)
   with patch.object(s.gaps,'apply',side_effect=fail_chunk):
    with self.assertRaises(OSError):s.closed('CHUNK_COMPLETE',1.2,0,True,False,r)
   s.close();s=SessionStore.load(d)
   try:
    self.assertIsNone(s.meta['current_chunk']);self.assertEqual(s.meta['completed_chunk_count'],1)
   finally:s.close()

if __name__=='__main__':unittest.main()
