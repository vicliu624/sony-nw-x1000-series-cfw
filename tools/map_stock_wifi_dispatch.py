"""Stock root/radio/connection event routing matrix. Actions are intercepted.
This maps dispatch choices, NOT successful hardware transitions.
"""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf=ELFFile(io.BytesIO(raw));u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x900000)
for segment in elf.iter_segments():
 if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
u.mem_map(0x2000000,0x20000);ctx=0x2001000;end=0x2000100
def word(a):return struct.unpack('<I',u.mem_read(a,4))[0]
def half(a):return struct.unpack('<H',u.mem_read(a,2))[0]
groups=[('root',0x3f4f18,2,10),('browser_relay',0x3ef680,3,6),('radio',0x3efb3c,3,14),('connection',0x3efe6c,7,28)]
actions=set();descriptors=[]
for name,table,modes,number in groups:
 for mode in range(1,modes+1):
  descriptor=word(table+(mode-1)*4);states,events,count=half(descriptor),half(descriptor+2),half(descriptor+4)
  assert 0<states<=128 and 0<events<=512 and 0<count<=512
  callbacks=[word(word(descriptor+12)+i*4) for i in range(count)]
  # +8 is the byte action-index matrix; +16 is {event,column} rows, stride8.
  codes=[word(word(descriptor+16)+i*8) for i in range(events)]
  assert all(0x8000<=v<0x380000 for v in callbacks)
  actions.update(callbacks);descriptors.append((name,table,mode,number,descriptor,states,codes))
hits=[]
def hook(uc,pc,size,unused):
 if pc==end:uc.emu_stop()
 elif pc in actions:hits.append(pc);uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
def no_syscall(uc,number,unused):raise AssertionError('Unexpected system instruction')
u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,no_syscall)
rows=[];metadata=[]
for name,table,mode,number,descriptor,states,codes in descriptors:
 metadata.append({'group':name,'mode':mode,'descriptor':hex(descriptor),'states':states,'events':len(codes)})
 for state in range(1,states+1):
  for event in codes:
   context=bytearray(32);context[0]=mode;context[1]=state;context[13]=number;struct.pack_into('<I',context,4,table);u.mem_write(ctx,bytes(context));hits.clear()
   for reg,value in ((UC_ARM_REG_R0,ctx),(UC_ARM_REG_R1,event),(UC_ARM_REG_R2,0),(UC_ARM_REG_R3,0),(UC_ARM_REG_SP,0x201f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
   u.emu_start(0x17c608,end,count=2000);assert u.reg_read(UC_ARM_REG_PC)==end and len(hits)<=1
   if hits:rows.append({'group':name,'mode':mode,'state':state,'event':hex(event),'action':hex(hits[0])})
report={'passed':True,'SpiderApp_sha256':digest,'descriptors':metadata,'routes':rows,'action_bodies_executed':False,'physical_device_or_ipc':False,'limits':['Contexts supplied across valid table states; reachability and action-return transitions are not proven.','Callbacks intercepted with return0. This is routing evidence, not complete Wi-Fi operation.']}
(ROOT/'sources/stock-wifi-dispatch-map.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'descriptors':metadata,'root_wifi_actions':sorted(set(r['action'] for r in rows if r['group']=='root' and r['event']=='0x420036')),'route_count':len(rows)},indent=2))
