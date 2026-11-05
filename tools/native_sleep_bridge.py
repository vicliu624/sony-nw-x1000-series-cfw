"""Analysis-only Main ack callsites; never makes a firmware/install package."""
import hashlib,io,struct,subprocess
from app_registry import ROOT
from wireless_callback_bridge import offset
from elftools.elf.elffile import ELFFile
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM

ENTRY=0x4d8900
CALLS=(0x614f0,0x61648,0x61940,0x61c5c)
def branch(address,target):
 delta=target-address-8
 if delta%4 or not -(1<<25)<=delta<(1<<25):raise ValueError('ARM BL out of range')
 return 0xeb000000|((delta//4)&0xffffff)
def compose(base,out,*,restore_observers=False):
 text=ELFFile(io.BytesIO(base)).get_section_by_name('.text')
 decoder=Cs(CS_ARCH_ARM,CS_MODE_ARM);decoder.skipdata=True
 calls=tuple(i.address for i in decoder.disasm(text.data(),text['sh_addr']) if i.mnemonic=='bl' and i.op_str=='#0xb03e8')
 if calls!=CALLS:raise ValueError('Original acknowledgement call inventory changed')
 out.mkdir(parents=True,exist_ok=True)
 ld=out/'sleep.ld';elf=out/'sleep.elf';binary=out/'sleep.bin'
 end='0x4d8960' if restore_observers else '0x4d892c'
 ld.write_text('ENTRY(xw_native_sleep_ack)\nSECTIONS { . = 0x4d8900; .text : { *(.text*) } /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }\nASSERT(. == '+end+', "Sleep anchor layout changed")\nxw_native_sleep_request = 0xda84;\nxw_native_stock_restore = 0x61a1c;\n')
 subprocess.run(['arm-linux-gnueabi-gcc',*(['-DXW_SLEEP_RESTORE_ANCHOR'] if restore_observers else []),'-march=armv5te','-marm','-nostdlib','-no-pie','-Wl,--build-id=none,-T,'+str(ld),'runtime/platform/player/sleep_anchor.S','-o',str(elf)],cwd=ROOT,check=True)
 subprocess.run(['arm-linux-gnueabi-objcopy','-O','binary',str(elf),str(binary)],check=True)
 code=binary.read_bytes();slot=offset(base,ENTRY,len(code))
 if base[slot:slot+len(code)]!=bytes(len(code)):raise ValueError('Sleep anchor slot occupied')
 mappings=[s for s in ELFFile(io.BytesIO(base)).iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=ENTRY and ENTRY+len(code)<=s['p_vaddr']+s['p_filesz']]
 if len(mappings)!=1 or mappings[0]['p_flags']!=5:raise ValueError('Expected unique RX slot')
 patched=bytearray(base);patched[slot:slot+len(code)]=code;edits=[]
 for address in CALLS:
  at=offset(base,address,4);before=struct.unpack_from('<I',base,at)[0]
  if before!=branch(address,0xb03e8):raise ValueError('Unexpected original acknowledgement call')
  after=branch(address,ENTRY);struct.pack_into('<I',patched,at,after)
  edits.append(dict(address=hex(address),before=hex(before),after=hex(after)))
 if restore_observers:
  at=offset(base,0x4d7fc0,44)
  if hashlib.sha256(base[at:at+44]).hexdigest()!='074c73e0f56be6592f3554bead6f00a0aef0d815dff410eb3b858b2470f16325':raise ValueError('Paired preparation bridge required')
  address=0x71e6c;at=offset(base,address,4);before=struct.unpack_from('<I',base,at)[0]
  if before!=branch(address,0x112fc):raise ValueError('Unexpected command15 entry call')
  after=branch(address,0x4d7fc0);struct.pack_into('<I',patched,at,after)
  edits.append(dict(address=hex(address),before=hex(before),after=hex(after)))
  descriptor=offset(base,0x3ef8d4,16);count=struct.unpack_from('<H',base,descriptor+4)[0];table=struct.unpack_from('<I',base,descriptor+12)[0]
  matches=[table+4*i for i in range(count) if struct.unpack_from('<I',base,offset(base,table+4*i,4))[0]==0x61a1c]
  if len(matches)!=1:raise ValueError('Expected unique Main restore action')
  address=matches[0];struct.pack_into('<I',patched,offset(base,address,4),0x4d8940)
  edits.append(dict(address=hex(address),before=hex(0x61a1c),after=hex(0x4d8940)))
 reverted=bytearray(patched);reverted[slot:slot+len(code)]=bytes(len(code))
 for edit in edits:struct.pack_into('<I',reverted,offset(base,int(edit['address'],16),4),int(edit['before'],16))
 if reverted!=base:raise ValueError('Changes escaped reviewed spans')
 guards=[dict(address=hex(ENTRY),bytes=len(code),sha256=hashlib.sha256(code).hexdigest())]
 for address in [int(edit['address'],16) for edit in edits]:
  at=offset(patched,address,4);guards.append(dict(address=hex(address),bytes=4,sha256=hashlib.sha256(patched[at:at+4]).hexdigest()))
 report=dict(analysis_only=True,ready_to_flash=False,firmware_package_created=False,entry=hex(ENTRY),request_caller=hex(ENTRY+12),ack_call_inventory=[hex(address) for address in calls],restore_observers=restore_observers,restore_entry='0x4d8940' if restore_observers else None,restore_caller='0x4d8958' if restore_observers else None,code_bytes=len(code),elf_growth_bytes=0,edits=edits,guards=guards,
  base_sha256=hashlib.sha256(base).hexdigest(),candidate_sha256=hashlib.sha256(patched).hexdigest(),anchor_sha256=hashlib.sha256(code).hexdigest(),
  source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/native_sleep_bridge.py','runtime/platform/player/sleep_anchor.S']})
 return bytes(patched),report
