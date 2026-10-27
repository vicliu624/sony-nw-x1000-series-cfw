"""Replay only the stock DLL CopyFile failure-to-HRESULT tail on the PC."""
from pathlib import Path
import hashlib,json,struct
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX,UC_X86_REG_ESP,UC_X86_REG_EIP
p=Path(__file__).resolve().parents[1]/'work/updater-static-review-1/extracted/FWUpdaterCom.dll'
b=p.read_bytes()
if hashlib.sha256(b).hexdigest()!='2b7550cd945a8d71d139063fce0ce006bfa6b59ee940f17e5151bdb6e35ebe2f':
 raise SystemExit('Unexpected DLL')
results=[]
for error,expected in [(112,0x80047008),(5,0x80047007),(2,0x80047006),(0,0x80047006)]:
 u=Uc(UC_ARCH_X86,UC_MODE_32)
 u.mem_map(0x10000000,0x50000);u.mem_write(0x10000000,b)
 u.mem_map(0x20000000,0x2000);u.reg_write(UC_X86_REG_ESP,0x20001000)
 stub=0x10048000;u.mem_write(0x1002e060,struct.pack('<I',stub));calls=[]
 def hook(uc,address,size,data):
  if address==stub:
   calls.append('GetLastError fixture');uc.reg_write(UC_X86_REG_EAX,error)
   sp=uc.reg_read(UC_X86_REG_ESP);ret=struct.unpack('<I',uc.mem_read(sp,4))[0]
   uc.reg_write(UC_X86_REG_ESP,sp+4);uc.reg_write(UC_X86_REG_EIP,ret)
 u.hook_add(UC_HOOK_CODE,hook)
 u.emu_start(0x10007da7,0x10007c68,count=100)
 actual=u.reg_read(UC_X86_REG_EAX)
 if actual!=expected or len(calls)!=1 or u.reg_read(UC_X86_REG_EIP)!=0x10007c68:
  raise SystemExit('Error propagation replay failed')
 results.append({'win32_error':error,'hresult':hex(actual)})
print(json.dumps({'passed':True,'scope':'Original instruction tail only; GetLastError mocked; no copying, device or DLL execution by Windows','cases':results},indent=2))
