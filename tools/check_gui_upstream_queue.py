"""Bounded original upstream GUI queue lifecycle, no OS threads or device access."""
import runpy,struct,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];queue=0x74e22c;message=0x60010000;payload=0x60011000
memory=[]
def put(p,v):u.mem_write(p,struct.pack('<I',v))
def hook(uc,pc,size,data):
 if pc not in (0xd574,0xd85c):return
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
 u.mem_write(a[0],bytes([a[1]&255])*a[2] if pc==0xd574 else bytes(u.mem_read(a[1],a[2])))
 memory.append({'pc':hex(pc),'bytes':a[2]});uc.reg_write(UC_ARM_REG_R0,a[0]);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
n['call'](0x106f98,(queue,0,0,0));assert n['word'](queue)==0
u.mem_write(payload,bytes(i%256 for i in range(272)))
raw=bytearray(84);struct.pack_into('<I',raw,64,payload);struct.pack_into('<I',raw,72,3);u.mem_write(message,bytes(raw))
assert n['call'](0x107034,(queue,message,0x1234,0))==5
put(queue+0x5e74,0x732d3c) # Supplied receiver binding, not a boolean enable flag.
assert n['call'](0x107034,(queue,message,0x1234,0))==0
assert n['word'](queue)==1
out=0x60012000;token=out+4
n['call'](0x107134,(queue,out,token,0));head=n['word'](out)
assert head==queue+556 and n['word'](token)==0x1234
assert n['word'](head+64)==queue+12
assert bytes(u.mem_read(n['word'](head+64),272))==bytes(u.mem_read(payload,272))
n['call'](0x1071ec,(queue,0,0,0));assert n['word'](queue)==0 and n['word'](queue+8)&1==0
n['call'](0x1071ec,(queue,0,0,0));assert n['word'](queue)==0
r={'SpiderApp_sha256':n['digest'],'scope':'Original upstream queue initialization/enqueue/peek/pop, supplied receiver binding','queue_capacity_from_init':38,'disabled_enqueue_return':5,'enabled_enqueue_return':0,'payload_copy_bytes':272,'token':0x1234,'count_roundtrip':[0,1,0],'duplicate_pop_no_underflow':True,'memory_services':memory,'limits':['Receiver pointer at+5e74 supplied here; original e8800 binding is exercised in the joint upstream-init check.','Message/payload supplied to native enqueue; no OS thread scheduling or receiver pump integrated.','Single record only; FIFO wrap and full queue not tested.']}
Path(n['ROOT'],'sources/native-gui-upstream-queue.json').write_text(json.dumps(r,indent=2)+'\n')
print('Original upstream enqueue/peek/pop and payload copy passed')
