"""Real nested Windows Jobs, preserving the outer host's process limits."""
from pathlib import Path
import json, os, sys, tempfile, unittest, time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "frontend"))
from pgn_owned import WindowsOwnedProcess, GpuLease, image_hash, _kernel, windows_birth
from pgn_detached_worker import atomic


@unittest.skipUnless(os.name == "nt", "Windows nested Job contract")
class NestedOwnerTests(unittest.TestCase):
    def exercise_nested_owner(self, terminate_host):
        self.maxDiff = None
        with tempfile.TemporaryDirectory(prefix="scout-nested-cpu-") as directory:
            root = Path(directory)
            child = root / "inside_job.py"
            frontend = str(Path(__file__).resolve().parents[1] / "frontend")
            child.write_text('''from pathlib import Path
import sys,os,json
sys.path.insert(0,sys.argv[1])
from pgn_owned import image_hash
from pgn_detached_worker import DetachedWindowsProcess,atomic
root=Path(sys.argv[2]);fixture=root/'fixture.py';hold=sys.argv[3]=='hold'
fixture.write_text("import time;time.sleep(120)\\n" if hold else "print('NESTED_CPU_COMPLETE',flush=True)\\n")
p=DetachedWindowsProcess([sys.executable,'-I',str(fixture),'--state',str(root/'checkpoint'),'--stop-file',str(root/'stop')],dict(os.environ),'CPU-NESTED-INNER',registry_root=root/'inner-lease')
try:
 assert p.controller_job_mode=='inherited-parent-job'
 identity=root/'native-owner-current.json'
 atomic(identity,{'pid':p.pid,'birth':p.birth,'image_sha256':image_hash(sys.executable),'configuration_sha256':'A'*64,'wal_sequence':1})
 p.commit_identity(identity);p.resume()
 if hold:
  atomic(root/'holding.json',{'pid':p.pid,'birth':p.birth,'controller':p.controller.pid})
  p.wait(120)
 assert list(p.stdout)==['NESTED_CPU_COMPLETE\\n']
 assert p.wait(20)==0
 assert json.loads((p.root/'done.json').read_text())['closed']
 print('NESTED_OWNERS_CLOSED',flush=True)
finally:p.close(force=True)
''',encoding="utf-8")
            lease = GpuLease("CPU-NESTED-OUTER", registry_root=root/"outer-lease").acquire()
            outer = None
            try:
                outer = WindowsOwnedProcess([sys.executable,"-I",str(child),frontend,str(root),"hold" if terminate_host else "complete"],dict(os.environ),lease)
                identity = root/"outer-identity.json"
                atomic(identity,dict(pid=outer.pid,birth=outer.birth,image_sha256=image_hash(sys.executable),configuration_sha256="B"*64,wal_sequence=1))
                outer.commit_identity(identity);outer.resume()
                if terminate_host:
                    deadline=time.monotonic()+10
                    while not(root/'holding.json').exists()and time.monotonic()<deadline:time.sleep(.01)
                    record=json.loads((root/'holding.json').read_text())
                    kernel,types=_kernel();handles=[]
                    try:
                        for pid in (record['pid'],record['controller']):
                            handle=kernel.OpenProcess(0x100000|0x1000,False,pid);self.assertTrue(handle);handles.append(handle)
                        self.assertEqual(windows_birth(kernel,types,handles[0]),record['birth'])
                        outer.close(force=True)
                        for handle in handles:self.assertEqual(kernel.WaitForSingleObject(handle,5000),0)
                    finally:
                        for handle in handles:kernel.CloseHandle(handle)
                else:
                    self.assertEqual(list(outer.stdout), ["NESTED_OWNERS_CLOSED\n"])
                    self.assertEqual(outer.wait(30),0)
            finally:
                if outer:outer.close(force=True)
                if outer and outer.stdout:outer.stdout.close()
                lease.release()

    def test_controller_inherits_a_job_that_forbids_breakaway(self):
        self.exercise_nested_owner(False)

    def test_host_termination_closes_nested_controller_and_child(self):
        self.exercise_nested_owner(True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
