"""Exact current payload APF request mode; no manager, GUI startup or hardware."""
import argparse,io,json,struct,time,sys,tarfile,gzip
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R6,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
from review_managed_remote_profile import receipt,digest
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host-review',required=True);p.add_argument('--failed-firmware',help='Read exact failed package AppList for original name lookup');p.add_argument('--parent-trace-review',help='Explicit passive parent capsules; observer modeled, no storage backend');a=p.parse_args()
rp,build=receipt(a.host_review);image=rp.parent/'SpiderApp.player-prepare.analysis-only.elf';assert digest(image)==build['candidate_sha256']
trace=None
if a.parent_trace_review:
 _,trace=receipt(a.parent_trace_review);assert trace['base_sha256']==digest(image)
 image=ROOT/trace['artifact'];assert digest(image)==trace['sha256']
raw=image.read_bytes();out=ROOT/'work/current-home-switch-mode'/str(time.time_ns());out.mkdir(parents=True);rows=[]
config=None
if a.failed_firmware:
 from review_managed_remote_profile import private
 from native_lookup_fixture import lookup
 sys.path.insert(0,str(ROOT/'scripts'));from upg import unpack
 failed=private(a.failed_firmware);assert digest(failed)=='de4a233023e4855cf4d94cd5a048f8c3aefaa40f86928724c718de4e32a3f1b1'
 _,parts=unpack(failed.read_bytes(),require_stock=False)
 decoded=gzip.decompress(parts[3]) # Validate the complete stream before tar seeking.
 with tarfile.open(fileobj=io.BytesIO(decoded),mode='r:') as archive:config=archive.extractfile('./etc/AppList.conf').read()
 launcher=ROOT/'work/sdk-app-refresh/1793710385092748300/managed-launcher/launcher.elf'
 assert digest(launcher)=='0be950324a42eed4c5976d50bca6b7eca4bf057557a8898aa188afb12e9c0d6b'
routes=[(0,'direct-client'),(1,'direct-client'),(1,'current-home-adapter')]
if config:routes.append((1,'preflight-and-original-name-lookup'))
for mode,route in routes:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000);u.mem_map(0x70000000,0x20000)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 put=lambda at,v:u.mem_write(at,struct.pack('<I',v))
 context=0x820f68;stack=0x70018000;done=0x7001ff00;packets=[];lookups=[];replies=[];position=0;boundaries=[];after_header=[];observations=[]
 for offset,value in ((0,1),(4,2),(12,55),(16,500),(20,0),(40,88)):put(context+offset,value)
 def hook(cpu,pc,size,unused):
  global position
  args=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];value=0
  if position>=52 and len(after_header)<60:after_header.append((hex(pc),args[0],cpu.reg_read(UC_ARM_REG_R6)))
  if pc in (0xb04f8,0xb0500,0x2664d0,0x2664ec,0xb0518,0xb04ec):boundaries.append((hex(pc),args,cpu.reg_read(UC_ARM_REG_R6)))
  if trace and pc==0xda84:
   assert args[0]&0xffffff00==0x48425000 and cpu.reg_read(UC_ARM_REG_LR) in trace['observer_callers']
   observations.append(args[0]&255);value=0x58575052 # Must not consume a native switch.
  elif pc==0xd574:u.mem_write(args[0],bytes([args[1]&255])*args[2]);value=args[0]
  elif pc==0x268c9c:
   assert args[:2]==[500,55] and args[3] in (276,1060)
   packet=bytes(u.mem_read(args[2],args[3]))
   if args[3]==276:
    assert config is not None
    details={};reply,comparisons=lookup(ROOT,packet,config_bytes=config,core_state=2,details=details)
    assert details['native_parser_executed'] and struct.unpack('<5I',reply)[4]==0x30001
    lookups.append(dict(words=list(struct.unpack('<5I',packet[:20])),parser=details,comparisons=comparisons));replies.append(reply)
   else:
    packets.append(list(struct.unpack('<8I',packet[:32])));replies.append(struct.pack('<4I',16,packets[-1][1],6,0))
  elif pc==0x268d48:
   reply=replies[-1];assert args[0]==500 and args[2]==len(reply)
   u.mem_write(args[1],reply);put(args[3],len(reply))
  elif route=='preflight-and-original-name-lookup' and pc==0xe09c:
   assert bytes(u.mem_read(args[0],64)).split(b'\0')[0]==b'/contents/HOMEBREW/launcher/app';value=77
  elif route=='preflight-and-original-name-lookup' and pc==0xe48c:
   assert args[0]==77;part=launcher.read_bytes()[position:position+args[2]];position+=len(part);u.mem_write(args[1],part);value=len(part)
  elif route=='preflight-and-original-name-lookup' and pc in (0xd6f4,0xb00bc,0x33b83c):pass
  elif pc in (0x337a80,0x337ae8,0x265298,0x17c42c):pass
  else:return
  cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 for r,v in ((UC_ARM_REG_R0,context),(UC_ARM_REG_R1,0x30001),(UC_ARM_REG_R2,0),(UC_ARM_REG_R3,mode),(UC_ARM_REG_SP,stack),(UC_ARM_REG_LR,done)):u.reg_write(r,v)
 entry=0x2681e8
 if route=='current-home-adapter':
  elf=ELFFile(io.BytesIO(raw));segment=next(s for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=0xb0518<s['p_vaddr']+s['p_filesz'])
  instruction=struct.unpack_from('<I',raw,segment['p_offset']+0xb0518-segment['p_vaddr'])[0]
  assert instruction>>24==0xea,hex(instruction)
  displacement=instruction&0xffffff
  if displacement&0x800000:displacement-=0x1000000
  adapter=0xb0518+8+displacement*4;assert 0x4d0000<=adapter<0x4e0000
  entry=0xb0510 # Run the original selector bounds/default branch as well.
  u.reg_write(UC_ARM_REG_R4,4);u.reg_write(UC_ARM_REG_R6,context)
  for offset,value in ((12,0x30001),(16,4),(20,0),(24,context),(28,done)):put(stack+offset,value)
 if route=='preflight-and-original-name-lookup':entry=0xb0464;u.reg_write(UC_ARM_REG_R0,4)
 if trace and route=='preflight-and-original-name-lookup':
  entry=0x737ec;put(0x613e4c,1);u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_R1,0);u.reg_write(UC_ARM_REG_R2,10)
 u.emu_start(entry,done,count=100000);assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==0
 assert packets==[[1060,len(lookups),1,6,55,0x30001,mode,0]],(route,position,lookups,packets,boundaries,after_header)
 if route=='preflight-and-original-name-lookup':assert len(lookups)==1 and position==52
 if trace:assert observations==({'current-home-adapter':[4,5],'preflight-and-original-name-lookup':[1,2,3,4,5]}.get(route,[]))
 rows.append(dict(mode=mode,route=route,entry=hex(entry),request_words=packets[0],original_client_executed=True,name_queries=lookups,passive_observer_stages=observations))
report=dict(passed=True,candidate_sha256=digest(image),cases=rows,physical_device_accessed=False,
 limits=['APF active-client state, IPC locks/transport and switch acceptance reply are fixtures.','Adapter-only case supplies completed name lookup; full-preflight case executes original name-query/client/parser and bounded string-copy body. No live manager retirement, GUI startup or physical order executes.'],source_sha256=digest(ROOT/'tools/test_current_home_switch_mode.py'))
if config:
 import hashlib
 report['failed_applist_sha256']=hashlib.sha256(config).hexdigest()
 report['limits'].append('Full preflight case reads exact launcher header through modeled read/close, then original client and manager parser/name lookup; switch acceptance remains supplied, not a live manager.')
report['parent_capsules_executed']=bool(trace)
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
