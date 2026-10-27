"""Build and execute the isolated JP1.11 feedback adapter, PC only."""
from pathlib import Path
import hashlib,io,json,struct,subprocess,sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.home_candidate import make_candidate,PAYLOAD_ADDRESS
from build_home_feedback import build
import argparse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args()
out=(ROOT/args.output).resolve()
b,symbols,detail=build(out)
e=ELFFile(io.BytesIO(b));loads=[s for s in e.iter_segments() if s['p_type']=='PT_LOAD']
stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
rows=[]
def machine():
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x700000)
 for s in loads:u.mem_write(s['p_vaddr'],bytes(b[s['p_offset']:s['p_offset']+s['p_filesz']]))
 u.mem_map(0x50000000,0x10000);return u
# Execute actual adapter plus original descriptor arithmetic. Stop before factory.
for mid in list(range(182))+list(range(700,746)):
 u=machine();index=22 if mid==745 else (mid if mid<182 else mid-518)
 u.reg_write(UC_ARM_REG_R0,index);u.reg_write(UC_ARM_REG_R5,mid)
 u.emu_start(0x281e0,0x281ec,count=20)
 expected=symbols['hb_error_descriptor'] if mid==745 else 0x4eb99c+index*48
 assert u.reg_read(UC_ARM_REG_R4)==expected
 rows.append({'id':mid,'descriptor_preserved_or_added':True})
# Run the actual index routine used by both description and action tables.
for mid in list(range(746))+[0xffffffff]:
 u=machine();u.reg_write(UC_ARM_REG_R0,mid);u.reg_write(UC_ARM_REG_LR,0x50008000)
 u.emu_start(0x28110,0x50008000,count=40)
 expected=22 if mid==745 else (mid if mid<=181 else ((mid-518)&0xffffffff if mid>=700 else 0))
 assert u.reg_read(UC_ARM_REG_R0)==expected
u=machine();desc=symbols['hb_error_descriptor'];words=struct.unpack('<12I',u.mem_read(desc,48));assert words[:5]==(745,0,1,0,0) and words[-1]==2
raw=bytes(u.mem_read(words[5],94));assert raw.decode('utf-16le').rstrip('\0')=='Homebrew unavailable.\nCheck HOMEBREW folder.'
# Run original-frame epilogue for stock selectors, successful new selector,
# and failed new selector. Only the queue service is mocked.
for selector,result in [(0,7),(1,0),(2,9),(3,0),(4,0),(4,1),(4,0xffffffff)]:
 u=machine();sp=0x50001000;u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_R4,selector);u.reg_write(UC_ARM_REG_R5,result);u.reg_write(UC_ARM_REG_R0,0x1234)
 saved=(0x44,0x55,0x66,0x50008000);u.mem_write(sp+16,struct.pack('<4I',*saved));calls=[]
 def hook(uc,pc,size,data):
  if pc==0xa57f0:
   args=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
   assert args==[0x2010e,0,745,0] and struct.unpack('<I',uc.mem_read(sp,4))[0]==0
   calls.append(args);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(symbols['hb_switch_return'],0x50008000,count=100)
 assert len(calls)==int(selector==4 and result!=0)
 assert u.reg_read(UC_ARM_REG_SP)==sp+32
 assert [u.reg_read(r) for r in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6)]==list(saved[:3])
 assert u.reg_read(UC_ARM_REG_R0)==(0 if selector==4 else 0x1234)
# Exercise file preflight in the original switcher's frame. libc services
# are controlled fault fixtures, not physical I/O or a complete loader test.
header=bytearray(52);header[:7]=b'\x7fELF\x01\x01\x01'
struct.pack_into('<HHI',header,16,2,40,1)
struct.pack_into('<HHH',header,40,52,32,1)
fixtures=[('valid',bytes(header),None,0),('missing',bytes(header),'open',0),('read-error',bytes(header),'read',0),('close-error',bytes(header),None,-1)]
for length in (0,15,16,31,32,47,48,51):fixtures.append(('truncated-'+str(length),bytes(header[:length]),None,0))
for offset in (0,4,5,6,16,18,20,40,42,44):
 bad=bytearray(header);bad[offset]=0;fixtures.append(('bad-'+str(offset),bytes(bad),None,0))
for case,data,fault,close_result in fixtures:
 u=machine();sp=0x50001000;u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_R4,4);u.reg_write(UC_ARM_REG_R6,0x6000)
 u.mem_write(sp+16,struct.pack('<4I',0x44,0x55,0x66,0x50008000));calls=[];position=[0];success=[]
 def preflight(uc,pc,size,_):
  if pc==0xb04f8:
   assert bytes(uc.mem_read(sp,16))==struct.pack('<4I',0,0,0,1)
   success.append(True);uc.emu_stop();return
  if pc not in (0xe09c,0xe48c,0xd6f4,0xa57f0):return
  calls.append(pc)
  if pc==0xe09c:
   ptr=uc.reg_read(UC_ARM_REG_R0);assert bytes(uc.mem_read(ptr,len(b'/contents/HOMEBREW/launcher/app\0')))==b'/contents/HOMEBREW/launcher/app\0'
   assert uc.reg_read(UC_ARM_REG_R1)==0;result=-1 if fault=='open' else 7
  elif pc==0xe48c:
   assert uc.reg_read(UC_ARM_REG_R0)==7
   n=uc.reg_read(UC_ARM_REG_R2);chunk=data[position[0]:position[0]+n];position[0]+=len(chunk)
   if fault=='read':result=-1
   else:
    if chunk:uc.mem_write(uc.reg_read(UC_ARM_REG_R1),chunk)
    result=len(chunk)
  elif pc==0xd6f4:
   assert uc.reg_read(UC_ARM_REG_R0)==7;result=close_result
  else:
   assert uc.reg_read(UC_ARM_REG_R2)==745;result=0
  uc.reg_write(UC_ARM_REG_R0,result&0xffffffff);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,preflight);u.emu_start(symbols['hb_switch_name'],0x50008000,count=500)
 assert bool(success)==(case=='valid'),case
 assert calls.count(0xd6f4)==int(fault!='open'),case
 assert calls.count(0xa57f0)==int(case!='valid'),case
 if not success:
  assert u.reg_read(UC_ARM_REG_SP)==sp+32
  assert [u.reg_read(r) for r in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6)]==[0x44,0x55,0x66]
report={'passed':True,'descriptor_cases':len(rows),'index_cases':747,'interaction_index':22,'return_cases':7,'payload_bytes':detail['payload_bytes'],'system_file_growth_bytes':len(b)-len(stock),'new_descriptor_id':745,'queue_service_mocked':True,'visible_gui_verified':False,'preflight_implemented':True,'preflight_fixture_cases':len(fixtures),'hardware_tested':False,'firmware_package_created':False,'sha256':hashlib.sha256(b).hexdigest(),'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'runtime/native/home_feedback.S',ROOT/'scripts/home_candidate.py',ROOT/'tools/build_home_feedback.py']}}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
