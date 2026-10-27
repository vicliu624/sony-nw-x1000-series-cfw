"""Actual ARM helper + unchanged Sony cnmgr/libpthread over real local FIFOs.
The daemon is a protocol fixture. No radio, account, physical device or network.
"""
from pathlib import Path
import argparse,fcntl,hashlib,json,os,selectors,shutil,signal,struct,subprocess,tempfile,time
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stock-daemon',action='store_true');args=parser.parse_args()
if args.stock_daemon:from stock_wifi_daemon_fixture import StockWifiDaemon
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work'/('qqmusic-stock-daemon-transport' if args.stock_daemon else 'qqmusic-stock-transport');work.mkdir(exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib';stock=ROOT/'work/qqmusic-wifi';resolver=ROOT/'work/stock-resolver-probe'
assert hashlib.sha256((stock/'libcnmgr.so.1').read_bytes()).hexdigest()=='688e09dded18c621dba0bf6f0c2bd9088cd495988a3e3e7dadb0a928efd1aac1'
sources=['runtime/apps/qqmusic/qqmusic_wifi_helper.c','tools/fixtures/qqmusic_wifi_stock_transport.c','runtime/native/linux_signals.c','runtime/native/syscalls.S','runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S']
app=work/'stock-helper.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=gnu99','-O2','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,-E','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(stock/'libcnmgr.so.1'),'-Wl,--no-as-needed',str(resolver/'libpthread.so.0'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
reports=[]
for case in ('ready','borrowed','cancel','late_cancel'):
 # WSL's Windows-mounted project cannot host FIFOs. Only transient account-free
 # protocol pipes use the PC's native temporary filesystem; reports stay here.
 with tempfile.TemporaryDirectory(prefix='qqmusic-stock-transport-'+case+'-') as directory:
  folder=Path(directory);fds={};selector=selectors.DefaultSelector();buffers={'main':bytearray(),'sub':bytearray()};requests=[];phases=[];pending=None;due=None;cancel_at=None;release_at=None;state=4 if case=='borrowed' else 2;count=0;ctrl_open=True;status=None
  daemon=StockWifiDaemon(ROOT,8 if case=='borrowed' else 0) if args.stock_daemon else None
  held=[]
  for channel in ('main','sub'):
   for suffix in ('req','res'):
    name=f'cnmgr_{channel}_{suffix}';os.mkfifo(folder/name);fd=os.open(folder/name,os.O_RDWR|os.O_NONBLOCK);fds[name]=fd
   selector.register(fds[f'cnmgr_{channel}_req'],selectors.EVENT_READ,channel)
  os.mkfifo(folder/'cnmgr_event_res')
  read_result,write_result=os.pipe();read_control,write_control=os.pipe()
  # Keep source descriptors above3/4 so spawn DUP2 actions never alias them.
  child_result=fcntl.fcntl(write_result,fcntl.F_DUPFD_CLOEXEC,20);child_control=fcntl.fcntl(read_control,fcntl.F_DUPFD_CLOEXEC,20)
  os.close(write_result);os.close(read_control);os.set_blocking(read_result,False);selector.register(read_result,selectors.EVENT_READ,'result');output=bytearray()
  trace=os.open(work/(case+'-qemu.log'),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
  lease=os.open(folder/'lease.lock',os.O_RDWR|os.O_CREAT,0o600);fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
  child_lease=fcntl.fcntl(lease,fcntl.F_DUPFD_CLOEXEC,20);contender=os.open(folder/'lease.lock',os.O_RDWR)
  command=[shutil.which('qemu-arm'),'-strace','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',f'{lib}:{resolver}:{stock}',str(app),'--session']
  pid=os.posix_spawn(command[0],command,{'LANG':'C','QQ_TEST_FIFO_ROOT':directory},file_actions=[(os.POSIX_SPAWN_DUP2,trace,2),(os.POSIX_SPAWN_DUP2,child_result,3),(os.POSIX_SPAWN_DUP2,child_control,4),(os.POSIX_SPAWN_DUP2,child_lease,5)],setpgroup=0)
  os.close(child_lease);os.close(lease)
  os.close(trace)
  os.close(child_result);os.close(child_control);started=time.monotonic()
  def respond(channel,result=0,payload=0):
   message=struct.pack('<ii',result,payload)+bytes(1004)
   assert os.write(fds[f'cnmgr_{channel}_res'],message)==1012
  def deliver(replies):
   for channel,message in replies:assert len(message)==1012 and os.write(fds[f'cnmgr_{channel}_res'],message)==1012
  try:
   try:fcntl.flock(contender,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:pass
   else:raise AssertionError('Controller did not retain inherited lease')
   while time.monotonic()-started<15:
    now=time.monotonic()
    if due is not None and now>=due:
     assert pending is not None
     if daemon is not None:deliver(held if case=='late_cancel' else daemon.wlan('SUCCESS cancel'))
     else:respond('main',0 if case=='late_cancel' else 4)
     pending=None;due=None
     if case!='late_cancel':state=3
     release_at=now
    for key,_ in selector.select(.01):
     channel=key.data;data=os.read(key.fd,4096)
     if channel=='result':
      if not data:selector.unregister(key.fd);continue
      output.extend(data)
      while len(output)>=12:
       magic,phase,result=struct.unpack('<IIi',output[:12]);del output[:12];assert magic==0x514e4554;phases.append([phase,result])
       if phase==6 and case in ('ready','borrowed') and ctrl_open:os.close(write_control);ctrl_open=False
      continue
     buffers[channel].extend(data)
     while len(buffers[channel])>=1020:
      packet=bytes(buffers[channel][:1020]);del buffers[channel][:1020];kind=struct.unpack_from('<I',packet)[0];requests.append([channel,kind])
      if daemon is not None:
       assert kind in (29,30,18,3,16,12,27,8),kind
       if kind==30:assert pending is None
       replies=daemon.command(channel,packet)
       if kind==3:
        assert daemon.state==1 and not replies
        replies+=daemon.wlan('SUCCESS get');assert daemon.state==2
       elif kind==12:
        assert daemon.state==4 and not replies and pending is None
        replies+=daemon.wlan('SUCCESS set');replies+=daemon.wlan('SUCCESS set');assert daemon.state==6 and not replies
        if case in ('ready','late_cancel'):
         replies+=daemon.wlan('CONNECTED');assert daemon.state==7
         replies+=daemon.ip(0);assert daemon.state==8
        if case!='ready':
         pending=12;held=replies;replies=[]
         assert ctrl_open;os.close(write_control);ctrl_open=False
       elif kind==27:
        assert pending==12 and channel=='sub'
        cancel_at=time.monotonic();due=cancel_at+.4
        assert daemon.state==(8 if case=='late_cancel' else 12)
       elif kind==8:
        assert case=='late_cancel' and pending is None and daemon.state==9 and not replies
        replies+=daemon.ip(2);assert daemon.state==10
        replies+=daemon.wlan('DISCONNECTED');assert daemon.state==2
       deliver(replies);count=daemon.reference_count
       continue
      if kind==29:count+=1;respond(channel)
      elif kind==30:assert pending is None;count-=1;respond(channel)
      elif kind==18:respond(channel,payload=state)
      elif kind==3:assert case!='borrowed';state=3;respond(channel)
      elif kind==16:assert case!='borrowed';respond(channel)
      elif kind==12:
       assert channel=='main' and pending is None and case!='borrowed'
       if case=='ready':state=4;respond(channel)
       else:
        pending=12
        if case=='late_cancel':state=4
        assert ctrl_open;os.close(write_control);ctrl_open=False
      elif kind==27:
       assert channel=='sub' and pending==12
       cancel_at=time.monotonic();respond(channel);due=cancel_at+.4
      elif kind==8:assert case=='late_cancel' and pending is None;state=3;respond(channel)
      else:raise AssertionError(('Unexpected command',case,channel,kind))
    reaped,result=os.waitpid(pid,os.WNOHANG)
    if reaped==pid:status=result;break
   assert status is not None,('Timed out',case,requests,phases)
   assert os.WIFEXITED(status) and os.WEXITSTATUS(status)==(2 if case in ('cancel','late_cancel') else 0),(case,status,requests,phases)
   assert count==0 and requests[-1]==['sub',30] and not pending
   fcntl.flock(contender,fcntl.LOCK_EX|fcntl.LOCK_NB)
   if case=='borrowed':assert all(k not in (3,16,12,8,27) for _,k in requests)
   if case in ('cancel','late_cancel'):
    assert cancel_at is not None and release_at-cancel_at>=.39
    assert [7,-5] in phases and all(p!=6 for p,_ in phases)
    assert (['main',8] in requests)==(case=='late_cancel')
   row={'case':case,'requests':requests,'phases':phases,'native_wait_status':status,'cancel_ack_before_connect_reply':cancel_at is not None,'no_fin_while_connect_pending':True,'lease_held_through_stock_library_and_released_after_exit':True}
   if daemon is not None:row.update(daemon_sha256=daemon.sha256,original_daemon_state_writes=daemon.state_writes,modeled_driver_calls=daemon.driver_calls,final_daemon_state=daemon.state)
   reports.append(row)
  finally:
   if status is None:
    # Only this PC fixture's explicitly spawned process group is addressed.
    if os.getpgid(pid)==pid:os.killpg(pid,signal.SIGKILL)
    os.waitpid(pid,0)
   if ctrl_open:os.close(write_control)
   selector.close();os.close(read_result)
   os.close(contender)
   for fd in fds.values():os.close(fd)
report={'passed':True,'cases':reports,'original_daemon_handlers':args.stock_daemon,'unchanged_stock_cnmgr_sha256':hashlib.sha256((stock/'libcnmgr.so.1').read_bytes()).hexdigest(),'helper_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'physical_device_or_account_access':False,'limits':['FIFO path redirect and route/IPC guard boundaries are PC fixtures.','Original daemon handlers generate replies/state if enabled; driver/AP validation/initial context and events remain modeled.' if args.stock_daemon else 'Daemon replies are synthetic; original daemon/driver are not running.','Does not prove physical radio ownership or complete application deployment.']}
report['source_hashes']['tools/test_qqmusic_stock_transport.py']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
if args.stock_daemon:report['source_hashes']['tools/stock_wifi_daemon_fixture.py']=hashlib.sha256((ROOT/'tools/stock_wifi_daemon_fixture.py').read_bytes()).hexdigest()
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
