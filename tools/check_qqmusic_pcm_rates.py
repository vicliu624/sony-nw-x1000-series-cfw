"""Execute pinned X1000 DspIoctl on virtual userspace/MMIO. PC only."""
from pathlib import Path
import struct,json,hashlib
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/upg-jp/verified-1.bin').read_bytes();assert hashlib.sha256(raw).hexdigest()=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
with (ROOT/'work/isolation-audit/x1000-kernel-analysis.elf').open('rb')as f:symbols={s.name:s['st_value']for s in ELFFile(f).get_section_by_name('.symtab').iter_symbols()}
assert symbols['DspIoctl']==0xc0170de8
rows=[]
for request,value,family in [(0xc0045006,n,0)for n in [1,2,6]]+[(0xc0045002,n,f)for n in [0,11025,22050,32000,44100,48000]for f in [0,1]]+[(0xc0045005,16,0)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0xc0008000,0x400000);u.mem_write(0xc0008000,raw);u.mem_map(0x60000000,0x20000);pointer=0x60001000;file=0x60002000;sentinel=0x6001f000
 u.mem_write(pointer,struct.pack('<I',value));u.mem_write(file+28,struct.pack('<I',2));mmio=struct.unpack('<I',u.mem_read(0xc01710d0,4))[0];u.mem_map(mmio&~4095,4096);events=[]
 helpers={symbols[n]:n for n in ['__get_user_4','__put_user_4','mp200_pmu_read_reg','local_bh_enable','audio_pcm_set_ctrl','audio_dsp_set_ctrl']}
 def hook(uc,pc,size,context):
  if pc==sentinel:uc.emu_stop();return
  name=helpers.get(pc)
  if not name:return
  a=[uc.reg_read(r)for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2]]
  if name=='__get_user_4':assert a[0]==pointer;uc.reg_write(UC_ARM_REG_R2,struct.unpack('<I',uc.mem_read(pointer,4))[0])
  elif name=='__put_user_4':assert a[0]==pointer;uc.mem_write(pointer,struct.pack('<I',a[2]))
  elif name=='mp200_pmu_read_reg':uc.mem_write(a[1],struct.pack('<I',family))
  else:events.append(name)
  uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 for r,v in [(UC_ARM_REG_R0,0),(UC_ARM_REG_R1,file),(UC_ARM_REG_R2,request),(UC_ARM_REG_R3,pointer),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,sentinel)]:u.reg_write(r,v)
 u.emu_start(symbols['DspIoctl'],0,count=5000);assert u.reg_read(UC_ARM_REG_PC)==sentinel and u.reg_read(UC_ARM_REG_R0)==0
 output=struct.unpack('<I',u.mem_read(pointer,4))[0];assert output==(2 if request==0xc0045006 else (11025 if value<=12000 else 22050 if value<=24000 else 44100) if request==0xc0045002 else value)
 divisor=struct.unpack('<I',u.mem_read(mmio+0x164,4))[0]
 if request==0xc0045002:assert divisor==([3,1,0]if family==0 else[91,45,22])[[11025,22050,44100].index(11025 if value<=12000 else 22050 if value<=24000 else 44100)]
 rows.append({'request':hex(request),'input':value,'output':output,'clock_family_fixture':family,'virtual_clock_divisor':divisor,'substituted_helpers':events})
report={'passed':True,'kernel_sha256':hashlib.sha256(raw).hexdigest(),'cases':rows,'scope':'Original DspIoctl scalar format/channels/rate branches. Userspace copies, clock read, codec and DMA helpers virtual; MMIO is emulator RAM, no device execution.','hardware_tested':False}
w=ROOT/'work/qqmusic-preview-audio';(w/'preview-rate-negotiation.json').write_text(json.dumps(report,indent=2)+'\n');print('Original rate negotiation: requested0/11025/22050/32000/44100/48000; outputs11025/22050/44100 and stereo confirmed offline.')
