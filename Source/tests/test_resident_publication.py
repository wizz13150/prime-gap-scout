"""Windows publication must stay readable across real exclusive-open races."""
from pathlib import Path
import ctypes as C,os,sys,tempfile,threading,unittest,json
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
import pgn_resident as resident

@unittest.skipUnless(os.name=='nt','Windows file sharing contract')
class CommandPublicationTests(unittest.TestCase):
 def kernel(self):
  from ctypes import wintypes as T
  k=C.WinDLL('kernel32',use_last_error=True)
  k.CreateFileW.argtypes=[T.LPCWSTR,T.DWORD,T.DWORD,C.c_void_p,T.DWORD,T.DWORD,T.HANDLE];k.CreateFileW.restype=T.HANDLE;k.CloseHandle.argtypes=[T.HANDLE]
  return k,T
 def test_read_guard_survives_atomic_rename_and_refuses_exclusive_scanner(self):
  k,T=self.kernel()
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'1.args';data=resident.frame(['--plan','--start','160000000000000000000'],'a'*32)
   guard=resident.publish_command(p,data)
   try:
    self.assertEqual(p.read_bytes(),data)
    h=k.CreateFileW(str(p),0x80000000,0,None,3,0x80,None)
    self.assertEqual(h,T.HANDLE(-1).value);self.assertEqual(C.get_last_error(),32)
    h=k.CreateFileW(str(p),0x80000000,3,None,3,0x80,None)
    self.assertNotEqual(h,T.HANDLE(-1).value);k.CloseHandle(h)
   finally:guard.close();guard.close()
   h=k.CreateFileW(str(p),0x80000000,0,None,3,0x80,None)
   self.assertNotEqual(h,T.HANDLE(-1).value);k.CloseHandle(h)
 def test_transient_private_file_lock_is_resolved_before_publication(self):
  k,T=self.kernel()
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'1.args';original=resident.CommandReadGuard;timers=[]
   def briefly_locked(temporary):
    self.assertFalse(p.exists())
    h=k.CreateFileW(str(temporary),0x80000000,0,None,3,0x80,None);self.assertNotEqual(h,T.HANDLE(-1).value)
    timer=threading.Timer(.1,lambda:k.CloseHandle(h));timers.append(timer);timer.start()
    return original(temporary)
   with patch.object(resident,'CommandReadGuard',side_effect=briefly_locked):guard=resident.publish_command(p,b'complete payload')
   try:self.assertEqual(p.read_bytes(),b'complete payload')
   finally:
    guard.close()
    for timer in timers:timer.join()
 def test_existing_command_is_never_overwritten(self):
  with tempfile.TemporaryDirectory()as d:
   p=Path(d)/'1.args';p.write_bytes(b'original')
   with self.assertRaises(resident.ResidentProtocolError):resident.publish_command(p,b'replay')
   self.assertEqual(p.read_bytes(),b'original')

class ReceiptReadTests(unittest.TestCase):
 def test_transient_denial_after_owner_exit_is_not_false_failure(self):
  with tempfile.TemporaryDirectory()as d:
   owner=SimpleNamespace(pid=77,birth='100',poll=lambda:0)
   manager=SimpleNamespace(owner=owner,directory=Path(d),errors=[])
   job=resident.Job(manager,1,'a'*32,['worker']);job.output_closed.set()
   doc=dict(schema='SCOUT_RESIDENT_JOB_V1',sequence=1,nonce='a'*32,pid=77,exit=0,wall_ns=100)
   p=Path(d)/'1.done.json';p.write_text(json.dumps(doc))
   read=Path.read_bytes
   with patch.object(Path,'read_bytes',side_effect=PermissionError('scanner')):
    self.assertIsNone(job.poll());self.assertIsNone(job.poll())
   self.assertEqual(job.poll(),0)
if __name__=='__main__':unittest.main()
