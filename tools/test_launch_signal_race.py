"""Actual SIGTERM while child is paused before exec; virtual devices, host QEMU bridge."""
from pathlib import Path
import argparse,contextlib,hashlib,io,json,os,runpy,shutil,signal,subprocess,tempfile,time
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--expect-reproduction',action='store_true');options=parser.parse_args()
with contextlib.redirect_stdout(io.StringIO()):base=runpy.run_path(str(ROOT/'tools/test_native_full_loop.py'))
work=ROOT/'work/launch-signal-race';work.mkdir(exist_ok=True);lib=base['lib']
fixture=base['fixture']
injection=r'''
  long marker=__real_x1000_oabi_call(5,(long)"before-exec",577,384,0,0,0);
  assert(marker>=0);assert(__real_x1000_oabi_call(4,marker,(long)"WAIT",4,0,0,0)==4);
  assert(__real_x1000_oabi_call(6,marker,0,0,0,0,0)==0);
  long delay[2]={5,0};__real_x1000_oabi_call(162,(long)delay,0,0,0,0,0);
'''
fixture=fixture.replace(' if(n==11) {',' if(n==11) {'+injection).replace('last_wait_status==0','last_wait_status==15')
generated=work/'race.c';generated.write_text(base['prefix']+fixture)
sources=[str(generated),*base['sources'][1:]];artifact=work/'race.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--wrap=x1000_oabi_call',*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='apps-',dir=work) as temporary:
 apps=Path(temporary);folder=apps/'cooperative';folder.mkdir();app=folder/'app';shutil.copyfile(base['child'],app)
 data=app.read_bytes();(folder/'app.ini').write_text('api=1\nid=cooperative\nname=Race Test\nversion=0.0.0\ntarget=sony-nw-x1000-jp\nexec=app\nbytes='+str(len(data))+'\nsha256='+hashlib.sha256(data).hexdigest()+'\n')
 process=subprocess.Popen(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(artifact),str(apps),'s'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 known=[];timed_out=False;ready_after_signal=False;stdout=stderr=''
 try:
  deadline=time.monotonic()+8
  while process.poll() is None and time.monotonic()<deadline:
   try:
    if (folder/'before-exec').read_bytes()==b'WAIT':break
   except FileNotFoundError:pass
   time.sleep(.01)
  assert (folder/'before-exec').read_bytes()==b'WAIT'
  children=Path(f'/proc/{process.pid}/task/{process.pid}/children');known=children.read_text().split()
  process.send_signal(signal.SIGTERM)
  try:stdout,stderr=process.communicate(timeout=2)
  except subprocess.TimeoutExpired:
   timed_out=True;ready_after_signal=(folder/'ready').exists()
 finally:
  children=Path(f'/proc/{process.pid}/task/{process.pid}/children');remaining=children.read_text().split() if children.exists() else []
  for value in set(known+remaining):
   try:
    command=Path('/proc')/value/'cmdline'
    if command.exists() and str(apps).encode() in command.read_bytes():os.kill(int(value),signal.SIGKILL)
   except (ProcessLookupError,FileNotFoundError):pass
  if process.poll() is None:process.kill()
  final_stdout,final_stderr=process.communicate(timeout=5)
  if timed_out:stdout,stderr=final_stdout,final_stderr
 if options.expect_reproduction:
  assert timed_out and ready_after_signal,'Expected lost-stop reproduction did not occur'
  report={'bug_reproduced':True,'all_bounded_checks_passed':False,'parent_wait_timed_out':True,'child_executed_after_stop':True,'trace':stderr,'app_process_sha256':hashlib.sha256((ROOT/'runtime/native/app_process.c').read_bytes()).hexdigest()}
  (work/'before-fix.json').write_text(json.dumps(report,indent=2)+'\n')
  print('Reproduced: inherited handler consumed stop before exec; child then started and parent kept waiting.')
 else:
  assert not timed_out and process.returncode==0 and not stdout,(process.returncode,timed_out,stderr[-12000:])
  assert not (folder/'ready').exists() and 'execve(' not in stderr
  tracked=[Path(__file__),ROOT/'tools/test_native_full_loop.py',generated,artifact,lib/'libc.so.6',lib/'ld-linux.so.3',*[ROOT/s for s in sources[1:] if not Path(s).is_absolute()],*list((ROOT/'runtime/native').glob('*.h'))]
  report={'all_bounded_checks_passed':True,'physical_device_access':False,'signal_in_pre_exec_window':True,'child_terminated_by_default_SIGTERM':True,'child_program_not_started':True,'parent_returned_and_reaped':True,'trace':stderr,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'limits':['Pause before exec is injected by test; actual fork/group signal/wait use QEMU and host processes.','No physical USB/display, Sony IPC or arbitrary launch-race qualification.']}
  (ROOT/'sources/native-launch-signal-race.json').write_text(json.dumps(report,indent=2)+'\n')
  print('Pre-exec stop: default SIGTERM terminated child; parent reaped and returned without launching app.')
