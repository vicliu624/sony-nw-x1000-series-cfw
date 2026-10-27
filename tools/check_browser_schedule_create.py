"""Capture stock manager notification10 producer; host-only virtual listener."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
b=(ROOT/'work/targets-jp/sysmgrd').read_bytes();sha=hashlib.sha256(b).hexdigest()
assert sha=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
e=ELFFile(io.BytesIO(b));rows=[]
for sender,state,allocation in ((1,1,True),(3,1,True),(0x30001,1,True),(3,4,True),(3,1,False)):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
 for s in e.iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x1000000,0x20000);core=0x1001000;service=0x1007000;packet=0x1008000;node=0x1009000;stop=0x1000100;insertions=[];persistence=[];results=[]
 def put(a,v):u.mem_write(a,struct.pack('<I',v))
 put(core+0x503c,state);put(core+0x4214+0x950,9);put(service,core)
 spec=struct.pack('<I',1)+bytes(104)
 u.mem_write(packet,struct.pack('<5I',128,55,sender,20,0)+spec)
 def hook(uc,pc,size,unused):
  if pc==0x100b0:results.append(uc.reg_read(UC_ARM_REG_R0))
  if pc not in (0x13930,0x1b858,0x99d8,0x16b7c,0x1633c,0x143ec,0xa188,0x1c5ac):return
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
  if pc==0x13930:result=100
  elif pc==0x1b858:result=node if allocation else 0
  elif pc==0x99d8:uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));result=a[0]
  elif pc==0x1633c:insertions.append(a[:2])
  elif pc==0x143ec:persistence.append(a[:2])
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 for reg,value in ((UC_ARM_REG_R0,service),(UC_ARM_REG_R1,packet),(UC_ARM_REG_SP,0x101e000),(UC_ARM_REG_LR,stop)):u.reg_write(reg,value)
 u.emu_start(0x10088,stop,count=2000);assert u.reg_read(UC_ARM_REG_PC)==stop
 expected=0x1d03 if state==4 else 0 if allocation else 0x1d01
 # Capture the operation result before handler epilogue restores callee-saved registers.
 from unicorn.arm_const import UC_ARM_REG_R6
 result=results[0];assert result==expected,(result,expected)
 words=list(struct.unpack('<4I',u.mem_read(node+4,16))) if insertions else None
 if expected==0:
  assert words==[9,sender,100,1] and len(insertions)==1 and len(persistence)==1
 else:assert not insertions and not persistence
 rows.append({'supplied_sender':sender,'core_state':state,'allocation_available':allocation,'operation_result':result,'inserted_node_words_id_owner_time_mode':words,'persistence_requests':len(persistence)})
report={'sysmgrd_sha256':sha,'service_entry':'0x10088','operation':20,'all_passed':True,'physical_device_access':False,'cases':rows,'limits':['Request packet is supplied directly; transport authentication/identity checks before handler are not replayed.','Mode1 schedule data is a structural test fixture, not a valid user appointment.','Clock, allocation, list insertion and persistence boundary are virtual; no file or device writes.','Owner/target comes from request sender field; accepting an unknown supplied sender here does not prove external sender impersonation is possible.','No external executable registration or launching is tested.']}
(ROOT/'sources/native-browser-schedule-create.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

