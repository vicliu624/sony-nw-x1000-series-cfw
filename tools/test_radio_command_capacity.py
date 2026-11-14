"""Replay the original ingress boundary and its oversized-copy failure offline."""
from pathlib import Path
import struct,json,hashlib,time
from app_registry import ROOT
from marvell_firmware import parse
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR
OUT=ROOT/'work/radio-command-capacity'/str(time.time_ns());OUT.mkdir(parents=True)
raw=(ROOT/'work/targets-jp/sd8686.bin').read_bytes();assert hashlib.sha256(raw).hexdigest()=='08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a'
records=parse(raw)
rows=[]
for length in (20,1500,1552):
 cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
 for a,n in ((0,0x20000),(0xc0000000,0x20000),(0x04000000,0x2000),(0x80000000,0x10000),(0x200000,0x10000)):cpu.mem_map(a,n)
 for r in records:
  if r.command==1:cpu.mem_write(r.address,r.data)
 cpu.reg_write(UC_ARM_REG_SP,0x208000)
 cpu.emu_start(0xc029,0xc048,count=100)
 event,request,source=0xc0015b94,0xc00155b8,0xc0010000
 # The original initialization itself writes the event-buffer internal link.
 assert struct.unpack('<I',cpu.mem_read(event+12,4))[0]==event+24
 initial=bytes(cpu.mem_read(event,64))
 payload=bytes((i*17+3)&255 for i in range(length))
 cpu.mem_write(source,struct.pack('<HH',length+4,1)+payload)
 cpu.reg_write(UC_ARM_REG_R0,source);cpu.reg_write(UC_ARM_REG_R2,length+4)
 copies=[]
 def hook(u,pc,n,ctx):
  if pc==0x7b4:
   dest,origin,count=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];copies.append((dest,origin,count))
   u.mem_write(dest,bytes(u.mem_read(origin,count)));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 cpu.hook_add(UC_HOOK_CODE,hook);cpu.emu_start(0xc3cd,0xc3d6,count=100)
 assert copies==[(request,source+4,length)]
 after=bytes(cpu.mem_read(event,64));overlap=max(0,length-(event-request))
 assert after[:overlap]==payload[1500:1500+overlap] and after[overlap:]==initial[overlap:]
 rows.append(dict(command_bytes=length,adjacent_event_bytes_overwritten=overlap,
                  event_internal_link_before=hex(struct.unpack_from('<I',initial,12)[0]),
                  event_internal_link_after=hex(struct.unpack_from('<I',after,12)[0])))
report=dict(passed=True,stock_radio_sha256=hashlib.sha256(raw).hexdigest(),request='0xc00155b8',
            event='0xc0015b94',response='0xc0014e4c',request_to_event_bytes=1500,
            original_event_initialization_executed=True,original_ingress_copy_clause_executed=True,
            memcpy_effects_modeled=True,device_accessed=False,cases=rows,
            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            limits=['This proves overwrite at1552 bytes and non-overlap at1500 bytes in this original instruction path.',
                    'It does not prove the allocation size of either static object or physical SDIO timing.'])
(OUT/'capacity-overlap-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
