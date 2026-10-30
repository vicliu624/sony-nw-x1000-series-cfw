"""Real managed owner/gate, modeled radio: EOF, duplicate exclusion and IO stop."""
from pathlib import Path
import hashlib,json,os,select,signal,struct,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/glass-marble-owner-tests';OUT.mkdir(exist_ok=True)
sources=['runtime/apps/glass-marble/owner.c','runtime/apps/glass-marble/marble.c','tools/fixtures/glass_marble_owner.c','runtime/apps/glass-marble/handoff.c','runtime/platform/espnow/xnow_managed_process.c','runtime/platform/espnow/xnow_owner_gate.c']
binary=OUT/'owner'
subprocess.run(['gcc','-std=c99','-D_DEFAULT_SOURCE','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-I'+str(ROOT/'sdk/include'),*sources,'-lm','-o',str(binary)],cwd=ROOT,check=True)
reserved=[]
while not reserved or reserved[-1]<5:reserved.append(os.open('/dev/null',os.O_RDONLY))
cookie=bytes(range(1,17));record=struct.Struct('<II120s');active=[]
def start(io=False):
 cr,cw=os.pipe();er,ew=os.pipe();rr,rw=os.pipe()
 def remap():os.dup2(cr,3);os.dup2(ew,4);os.dup2(rw,5)
 env=dict(os.environ,XNOW_HANDOFF_FD='5',XNOW_HANDOFF_COOKIE=cookie.hex())
 if io:env['GM_TEST_IO_FAILURE']='1'
 p=subprocess.Popen([str(binary),'--ipc'],env=env,pass_fds=(3,4,5,cr,ew,rw),preexec_fn=remap,start_new_session=True)
 os.close(cr);os.close(ew);os.close(rw);row=[p,cw,er,rr];active.append(row);return row
def until(row,kind):
 data=bytearray();deadline=time.monotonic()+5
 while time.monotonic()<deadline:
  assert select.select([row[2]],[],[],max(0,deadline-time.monotonic()))[0],'event timeout'
  part=os.read(row[2],record.size-len(data));assert part,'unexpected EOF';data.extend(part)
  if len(data)==record.size:
   found=record.unpack(data);data.clear()
   if found[0]==kind:return found
 raise AssertionError('missing event')
def done(row,failure=0):
 assert row[0].wait(timeout=5)==(69 if failure else 0)
 data=os.read(row[3],33);assert data==b'XRFDONE1'+cookie+struct.pack('<II',1,failure),data
 assert not os.read(row[3],1)
 for fd in row[1:]:
  if fd>=0:os.close(fd)
 active.remove(row)
try:
 first=start();until(first,2);frame=until(first,6);assert frame[1]==120 and frame[2][:4]==b'AQF3'
 duplicate=start();done(duplicate,1)
 os.close(first[1]);first[1]=-1;until(first,5);done(first)
 io=start(True);until(io,2);until(io,5);done(io)
 report={'passed':True,'production_owner_loop':True,'pipe_eof_restores':True,'duplicate_owner_refused':True,'negative_io_requests_recovery':True,'cookie_record_and_eof':True,'radio_manager_modeled':True,'device_accessed':False,'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources}}
 (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
finally:
 for row in active:
  if row[0].poll() is None:os.kill(row[0].pid,signal.SIGKILL);row[0].wait(timeout=3)
  for fd in row[1:]:
   if fd>=0:os.close(fd)
 for fd in reserved:os.close(fd)
