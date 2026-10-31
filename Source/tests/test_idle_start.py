from pathlib import Path
import json,subprocess,sys,tempfile,time,unittest
from unittest.mock import patch
F=Path(__file__).resolve().parents[1]/'frontend';sys.path.insert(0,str(F))
from pgn_idle_device import IdleDeviceProbe
from pgn_ui_workflow import pause_control
import pgn68
DEVICE={'index':0,'model':'UNIT TEST GPU','uuid':'GPU-11111111-2222-3333-4444-555555555555','cc_major':8,'cc_minor':6,'vram_bytes':24*1024**3}
INFO={'driver_version':13030,'devices':[DEVICE]}
class Tests(unittest.TestCase):
 def test_real_readonly_child_and_invalid_json(self):
  for body,valid in [(json.dumps(INFO),True),('broken JSON',False)]:
   p=IdleDeviceProbe([sys.executable,'-I','-c','print('+repr(body)+')'])
   try:
    end=time.monotonic()+4
    while not p.finished and time.monotonic()<end:p.poll();time.sleep(.01)
    self.assertTrue(p.finished);self.assertEqual(p.result is not None,valid)
    if valid:self.assertEqual(p.result[1][0]['model'],DEVICE['model'])
    else:self.assertIn('device JSON',p.error)
   finally:p.close()
 def test_timeout_and_close_reap_only_owned_host_child(self):
  p=IdleDeviceProbe([sys.executable,'-I','-c','import time;time.sleep(30)'],timeout=.08)
  started=time.monotonic()
  while not p.finished:p.poll();time.sleep(.01)
  self.assertIn('timed out',p.error);self.assertIsNotNone(p.process.poll());self.assertLess(time.monotonic()-started,3);p.close()
 def test_deadline_survives_paused_dashboard_menu(self):
  p=IdleDeviceProbe([sys.executable,'-I','-c','import time;time.sleep(30)'],timeout=.08)
  try:
   time.sleep(.3)  # Simulate a menu: no dashboard poll occurs.
   self.assertIsNotNone(p.process.poll());self.assertIn('timed out',p.error)
  finally:p.close()
 def test_idle_primary_and_resume(self):
  self.assertEqual(pause_control({'status':'Idle','idle_start_available':True})['key'],'s')
  self.assertEqual(pause_control({'status':'Idle','resume_folder':'saved'})['label'],'Resume')
  self.assertEqual(pause_control({'status':'Searching'})['label'],'Pause')
 def test_idle_discovery_then_start_same_config_without_menu_or_mining(self):
  frames=[];probes=[]
  class Dashboard:
   def update(self,state,**kwargs):frames.append(dict(state))
   def finish(self):pass
  class Keys:
   available=True
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def poll(self):return 's'
  class Probe:
   error=None
   def __init__(self,*args,**kwargs):self.closed=False;probes.append(self)
   def poll(self):return INFO,[DEVICE]
   def close(self):self.closed=True
  class Clocks:
   def __init__(self,*args):pass
   def snapshot(self):return {'sm_mhz':1500,'memory_mhz':5001}
   def finish(self):pass
  with tempfile.TemporaryDirectory()as folder:
   parser=pgn68.argument_parser();args=parser.parse_args(['--idle','--start','2e20','--length','1e12','--output',folder])
   with (patch.object(pgn68,'Dashboard',Dashboard),patch.object(pgn68,'PauseKeys',Keys),patch.object(pgn68,'resolve_worker',lambda _:Path('unit-worker')),
    patch('pgn_idle_device.IdleDeviceProbe',Probe),patch('pgn_gpu_monitor.GpuClockMonitor',Clocks),patch('pgn_ui_controller.catalog_sessions',lambda _:[])):
    action=pgn68.idle_menu_before_gpu(args,parser)
   self.assertEqual(action.kind,'new');self.assertEqual(action.values['start'],2*10**20);self.assertEqual(action.values['end'],2*10**20+10**12)
   self.assertEqual(frames[-1]['gpu_name'],DEVICE['model']);self.assertEqual(frames[-1]['clock_mem_mhz'],5001);self.assertTrue(frames[-1]['idle_start_available']);self.assertTrue(probes[0].closed)
 def test_prepared_range_matches_idle_preview_before_start(self):
  frames=[]
  class Dashboard:
   def update(self,state,**kwargs):frames.append(dict(state))
   def finish(self):pass
  class Keys:
   available=True
   def __init__(self):self.events=iter(['m','s'])
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def poll(self):return next(self.events)
  class Probe:
   error=None
   def __init__(self,*args,**kwargs):pass
   def poll(self):return INFO,[DEVICE]
   def close(self):pass
  class Clocks:
   def __init__(self,*args):pass
   def snapshot(self):return{}
   def finish(self):pass
  def menu(context):
   from pgn_menu import MenuAction
   from pgn_ui_workflow import new_defaults
   context['prepared_request']={**new_defaults(context),'start':2*10**28,'end':2*10**28+10**12,'min_gap':'auto','count_gap':None,'detail_gap':None}
   return MenuAction('return')
  with tempfile.TemporaryDirectory()as folder:
   parser=pgn68.argument_parser();args=parser.parse_args(['--idle','--start','2e20','--length','1e12','--output',folder])
   with(patch.object(pgn68,'Dashboard',Dashboard),patch.object(pgn68,'PauseKeys',Keys),patch.object(pgn68,'resolve_worker',lambda _:Path('unit-worker')),patch('pgn_idle_device.IdleDeviceProbe',Probe),patch('pgn_gpu_monitor.GpuClockMonitor',Clocks),patch('pgn_ui_controller.catalog_sessions',lambda _:[]),patch('pgn_menu.menu',menu)):
    action=pgn68.idle_menu_before_gpu(args,parser)
   self.assertEqual(action.values['start'],frames[-1]['start']);self.assertEqual(action.values['end'],frames[-1]['end']);self.assertEqual(frames[-1]['minimum_gap'],1336)
if __name__=='__main__':unittest.main(verbosity=2)
