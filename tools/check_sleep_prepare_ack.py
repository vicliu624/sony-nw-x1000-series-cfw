"""Original manager sleep acknowledgments: two pending clients, no sleep until both ack."""
from pathlib import Path
import runpy,contextlib,io,struct,json,hashlib
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):m=runpy.run_path(str(ROOT/'tools/check_sleep_storage_paths.py'))
g=m['hook'].__globals__;g['kind']='sleep';g['parameter']=0;u=m['u'];core=m['core'];g['events'].clear();g['seen'].clear()
def put(p,n):u.mem_write(p,struct.pack('<I',n))
def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
put(core+0x503c,3);put(core+0x5164,0)
for i in range(16):put(core+0x5168+i*4,0)
put(core+0x5168,55);put(core+0x516c,77)
rows=[]
for client in [55,77]:
 before=len(g['events']);u.reg_write(UC_ARM_REG_R0,core);u.reg_write(UC_ARM_REG_R1,client);u.reg_write(UC_ARM_REG_SP,m['sp']);u.reg_write(UC_ARM_REG_LR,m['stop']);u.emu_start(0xb1f8,m['stop'],count=500000);assert u.reg_read(UC_ARM_REG_PC)==m['stop'] and u.reg_read(UC_ARM_REG_R0)==0
 events=g['events'][before:];pending=[word(core+0x5168+i*4)for i in range(16)];sleep=any(x[0]=='write'and x[2]=='S3'for x in events)
 assert sleep==(client==77)
 assert pending==([0,77]+[0]*14 if client==55 else[0]*16)
 rows.append({'client_ack':client,'pending_after':pending,'power_write':sleep,'core_state_after':word(core+0x503c),'events':events})
r={'passed':True,'sysmgrd_sha256':m['sha'],'cases':rows,'scope':'Original b1f8/aa40/aa74 clears two supplied pending clients in one manager instance; after final ack original aaac/129d0/17894 executes. Caller/client identities and initial state supplied; transport, policy, timer, physical power virtual. Not real scheduling or application completion.','physical_device_access':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(ROOT/'work/external-language-bridge-8-ram-snapshot/prepare-ack-flow.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
