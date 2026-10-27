"""Original Spider cancellation action, virtual cnmgr imports and event queue.
Do not apply this action to an unowned connection in an external application.
"""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
rows=[]
for cancel_result,state in ((0,3),(0,4),(1,3),(1,4)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x900000)
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x2000000,0x20000);end=0x2000100;ctx=0x2001000;calls=[];events=[];queued=[]
 data=bytearray(32);data[0:2]=bytes([2,1]);data[13]=14;struct.pack_into('<I',data,4,0x3efb3c);u.mem_write(ctx,bytes(data))
 def hook(uc,pc,size,unused):
  result=0
  if pc==end:uc.emu_stop();return
  elif pc==0xd8bc:calls.append('cancel_connect');result=cancel_result
  elif pc==0xda18:calls.append('get_state');result=state
  elif pc==0xd958:calls.append('disconnect')
  elif pc==0xa57f0:events.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)])
  elif pc==0x336abc:
   pointer=uc.reg_read(UC_ARM_REG_R1);assert uc.reg_read(UC_ARM_REG_R2)==16
   queued.append(list(struct.unpack('<4I',uc.mem_read(pointer,16))))
  elif pc in (0xb3248,0x33b918,0x33b83c,0x17c42c):pass
  else:return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 def reject(*args):raise AssertionError('Unexpected system instruction')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,reject)
 for reg,value in ((UC_ARM_REG_R0,ctx),(UC_ARM_REG_R1,0x4c000d),(UC_ARM_REG_R2,0),(UC_ARM_REG_R3,0),(UC_ARM_REG_SP,0x201f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
 u.emu_start(0x17c608,end,count=20000)
 assert u.reg_read(UC_ARM_REG_PC)==end
 expected=['cancel_connect']+(['disconnect'] if cancel_result else [])+['get_state']+(['disconnect'] if state==4 else [])
 assert calls==expected
 assert events==([[0x420012,0,1,0]] if state==4 else [])+[[0x4c800e,0,0,0]]
 rows.append({'supplied_radio_context':[2,1],'event':'0x4c000d','supplied_cancel_result':cancel_result,'supplied_state_after_cancel':state,'imported_call_order':calls,'event_headers':events})
calls=[];events=[];queued=[]
u.mem_write(ctx,bytes([3,1]));u.mem_write(0x682cfc,struct.pack('<I',ctx))
parent=0x2003000;packet=0x2003100
u.mem_write(parent+16,struct.pack('<I',51))
def route(code):
 u.mem_write(packet,struct.pack('<4I',0,code,0,0))
 for reg,value in ((UC_ARM_REG_R0,parent),(UC_ARM_REG_R1,packet),(UC_ARM_REG_R2,0),(UC_ARM_REG_R3,0),(UC_ARM_REG_SP,0x201f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
 u.emu_start(0x3b994,end,count=10000);assert u.reg_read(UC_ARM_REG_PC)==end
route(0x4c0001)
assert queued==[[0,0x4c0001,0,0]] and not calls
assert struct.unpack('<I',u.mem_read(0x65e8f8+24,4))[0]==1
route(0x4c000d)
assert queued==[[0,0x4c0001,0,0]] and not calls and not events
assert struct.unpack('<2I',u.mem_read(0x65e8f8+24,8))==(0,1)
queue_case={'entry':'0x3b994','supplied_initial_radio_context':[3,1],'input_events':['0x4c0001','0x4c000d'],'queued_headers':queued,'field18_after':0,'field1c_after':1,'imported_calls':calls,'worker_not_executed':True}
report={'passed':True,'SpiderApp_sha256':digest,'action':'0x62c94','cases':rows,'cancel_before_worker':queue_case,'physical_device_or_ipc':False,
 'limits':['Initial original radio context and imported results supplied; dispatch/action/wrappers execute.',
           'No actual cnmgr cancellation, driver, IPC or application ownership proof.',
           'Additional original front-door route sets cancellation fields before worker delivery; queue transport modeled and worker not executed.',
           'The action belongs to stock radio control; not permission to disconnect arbitrary existing connections.']}
(ROOT/'sources/stock-wifi-cancel-policy.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':True,'cases':len(rows),'original_action':'0x62c94'}))
