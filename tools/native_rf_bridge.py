"""Pinned stock RF callsite composition, no firmware or hardware operation."""
import hashlib,io,struct,subprocess
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
from wireless_callback_bridge import offset
ENTRY=0x4d8700
# wrapper ranges, imported target and operation. Prepare-WPS has three callers.
OPERATIONS=[(0xb3458,0xb34c8,0xda9c,1),(0xb3784,0xb37f4,0xe108,2),
 (0xb3538,0xb35b4,0xda3c,3),(0xb3538,0xb35b4,0xe2ac,4),
 (0xb3ee4,0xb3f70,0xe030,5),(0xb3f70,0xb3ffc,0xe030,5),(0xb3ffc,0xb4078,0xe030,5),
 (0xb3ee4,0xb3f70,0xd640,6),(0xb3f70,0xb3ffc,0xd880,7),(0xb3ffc,0xb4078,0xdf4c,8)]
def compose(base,out,*,native_handoff=False):
 out.mkdir(parents=True,exist_ok=True);ld=out/'anchor.ld';image=out/'anchor.elf';binary=out/'anchor.bin'
 ld.write_text('''ENTRY(xw_native_rf_power_on)
SECTIONS { . = 0x4d8700; .text : { *(.text*) }
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }
ASSERT(. == 0x4d88f4, "Unexpected RF anchor layout")
xw_native_rf_request = 0xda84;
xw_native_stock_worker = 0x3b9a8;
xw_native_stock_router = 0x3b994;
xw_native_stock_dispatch = 0x61db4;
xw_native_stock_activation = 0x2680a8;
''')
 source='runtime/platform/wireless/native_rf_anchor.S'
 subprocess.run(['arm-linux-gnueabi-gcc','-march=armv5te','-marm','-ffreestanding','-nostdlib','-no-pie','-Wl,--build-id=none,-T,'+str(ld),source,'-o',str(image)],cwd=ROOT,check=True)
 subprocess.run(['arm-linux-gnueabi-objcopy','-O','binary',str(image),str(binary)],check=True)
 code=binary.read_bytes();slot=offset(base,ENTRY,len(code));assert base[slot:slot+len(code)]==bytes(len(code))
 aliases=[]
 for segment in ELFFile(io.BytesIO(base)).iter_segments():
  if segment['p_type']!='PT_LOAD':continue
  lo=max(slot,segment['p_offset']);hi=min(slot+len(code),segment['p_offset']+segment['p_filesz'])
  if lo<hi:aliases.append((segment['p_vaddr']+lo-segment['p_offset'],segment['p_flags']))
 assert aliases==[(ENTRY,5)]
 patched=bytearray(base);patched[slot:slot+len(code)]=code;edits=[]
 for start,end,target,operation in OPERATIONS:
  at=offset(base,start,end-start)
  matches=[i for i in Cs(CS_ARCH_ARM,CS_MODE_ARM).disasm(base[at:at+end-start],start) if i.mnemonic=='bl' and i.op_str==hex(target).replace('0x','#0x')]
  assert len(matches)==1,(hex(start),hex(target),matches)
  address=matches[0].address;at=offset(base,address,4);before=struct.unpack_from('<I',base,at)[0]
  assert before==0xeb000000|(((target-address-8)//4)&0xffffff)
  destination=ENTRY+(operation-1)*28;after=0xeb000000|(((destination-address-8)//4)&0xffffff)
  struct.pack_into('<I',patched,at,after)
  edits.append(dict(address=hex(address),before=hex(before),after=hex(after),operation=operation,target=hex(target)))
 factory=offset(base,0x3c138,4);assert struct.unpack_from('<I',base,factory)[0]==0x3b9a8
 struct.pack_into('<I',patched,factory,0x4d87e0)
 edits.append(dict(address='0x3c138',before='0x3b9a8',after='0x4d87e0',operation=9,target='0x3b9a8',kind='worker-entry-pointer'))
 queue=offset(base,0x10958,4);before=struct.unpack_from('<I',base,queue)[0]
 assert before==0xeb000000|(((0x3b994-0x10958-8)//4)&0xffffff)
 after=0xeb000000|(((0x4d87fc-0x10958-8)//4)&0xffffff)
 struct.pack_into('<I',patched,queue,after)
 edits.append(dict(address='0x10958',before=hex(before),after=hex(after),operation=10,target='0x3b994',kind='gui-router-call'))
 for start,end,target,operation in ((0xb34c8,0xb3538,0xd4fc,13),(0xb3624,0xb3694,0xd958,14),(0xb35b4,0xb3624,0xd8bc,15),(0xb4078,0xb40e8,0xddfc,16)):
  at=offset(base,start,end-start)
  matches=[i for i in Cs(CS_ARCH_ARM,CS_MODE_ARM).disasm(base[at:at+end-start],start) if i.mnemonic=='bl' and i.op_str==hex(target).replace('0x','#0x')]
  assert len(matches)==1,(hex(start),hex(target));address=matches[0].address;at=offset(base,address,4)
  before=struct.unpack_from('<I',base,at)[0];destination=0x4d8834+(operation-13)*28
  after=0xeb000000|(((destination-address-8)//4)&0xffffff);struct.pack_into('<I',patched,at,after)
  edits.append(dict(address=hex(address),before=hex(before),after=hex(after),operation=operation,target=hex(target),kind='owned-cleanup-call'))
 dispatch=offset(base,0x3b9e4,4);before=struct.unpack_from('<I',base,dispatch)[0]
 assert before==0xeb000000|(((0x61db4-0x3b9e4-8)//4)&0xffffff)
 after=0xeb000000|(((0x4d88a4-0x3b9e4-8)//4)&0xffffff);struct.pack_into('<I',patched,dispatch,after)
 edits.append(dict(address='0x3b9e4',before=hex(before),after=hex(after),operation=12,target='0x61db4',kind='worker-dispatch-checkpoint'))
 if native_handoff:
  from player_prepare_bridge import prepare_bridge
  anchor=offset(base,0x4d7fc0,44)
  if base[anchor:anchor+44]!=prepare_bridge():raise ValueError("Paired native prepare anchor required")
  handoff=offset(base,0x71f5c,4);before=struct.unpack_from('<I',base,handoff)[0]
  assert before==0xeb000000|(((0x112fc-0x71f5c-8)//4)&0xffffff)
  after=0xeb000000|(((0x4d7fc0-0x71f5c-8)//4)&0xffffff);struct.pack_into('<I',patched,handoff,after)
  edits.append(dict(address='0x71f5c',before=hex(before),after=hex(after),operation=17,target='0x112fc',kind='command6-prepare-call'))
  for address,target,destination,kind in ((0x71cd8,0x112fc,0x4d7fc0,'command7-prepare-call'),(0xb0624,0x2680a8,0x4d88cc,'activation-result-call')):
   at=offset(base,address,4);before=struct.unpack_from('<I',base,at)[0]
   assert before==0xeb000000|(((target-address-8)//4)&0xffffff)
   after=0xeb000000|(((destination-address-8)//4)&0xffffff);struct.pack_into('<I',patched,at,after)
   edits.append(dict(address=hex(address),before=hex(before),after=hex(after),operation=18,target=hex(target),kind=kind))
 restored=bytearray(patched);restored[slot:slot+len(code)]=base[slot:slot+len(code)]
 for edit in edits:
  at=offset(base,int(edit['address'],16),4);struct.pack_into('<I',restored,at,int(edit['before'],16))
 assert restored==base and len(patched)==len(base)
 guards=[dict(address=hex(ENTRY),bytes=len(code),sha256=hashlib.sha256(code).hexdigest())]
 for edit in edits:
  at=offset(base,int(edit['address'],16),4);guards.append(dict(address=edit['address'],bytes=4,sha256=hashlib.sha256(patched[at:at+4]).hexdigest()))
 # Qualify the original read-only cached-setting getter used by boot policy.
 at=offset(base,0x37f5c,0x4ac);guards.append(dict(address='0x37f5c',bytes=0x4ac,sha256=hashlib.sha256(base[at:at+0x4ac]).hexdigest()))
 at=offset(base,0xa57f0,0x128);guards.append(dict(address='0xa57f0',bytes=0x128,sha256=hashlib.sha256(base[at:at+0x128]).hexdigest()))
 if native_handoff:
  for address,count in ((0x265510,12),(0xe5f4,12),(0x2680a8,0xe0),(0xb05e8,0x7c)):
   at=offset(base,address,count);guards.append(dict(address=hex(address),bytes=count,sha256=hashlib.sha256(patched[at:at+count]).hexdigest()))
 report=dict(entry=hex(ENTRY),code_bytes=len(code),elf_growth_bytes=0,edits=edits,guards=guards,native_handoff=native_handoff,
  request_callers=[hex(ENTRY+i*28+24) for i in range(8)],
  worker_entry='0x4d87e0',worker_request_caller='0x4d87f0',worker_factory_pointer='0x3c138',
  queue_entry='0x4d87fc',queue_request_caller='0x4d8820',queue_callsite='0x10958',
  poweroff_entry='0x4d8834',poweroff_request_caller='0x4d884c',poweroff_callsite='0xb34f4',
  cleanup_request_callers=[hex(0x4d884c+i*28) for i in range(4)],
  dispatch_entry='0x4d88a4',dispatch_request_caller='0x4d88c4',dispatch_callsite='0x3b9e4',
  original_targets=[hex(n) for n in (0xda9c,0xe108,0xda3c,0xe2ac,0xe030,0xd640,0xd880,0xdf4c)],
  base_sha256=hashlib.sha256(base).hexdigest(),candidate_sha256=hashlib.sha256(patched).hexdigest(),
  source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [source,'tools/native_rf_bridge.py']})
 return bytes(patched),report
