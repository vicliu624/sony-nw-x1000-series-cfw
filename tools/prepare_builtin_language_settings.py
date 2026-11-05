"""Enable only stock language entry on restored JP base; no firmware/device write."""
import hashlib,io,json,struct,time
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_SP,UC_ARM_REG_LR
base_path=max((ROOT/'work/builtin-player-base').glob('*/SpiderApp.builtin-language.analysis-only.elf'),key=lambda p:p.parent.name)
raw=base_path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='ea106d7d362793fe39450673b79e3cf77dbdd00bc1ba573b7e8f854d56dc53e0'
elf=ELFFile(io.BytesIO(raw));segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
def off(a,n):return next(s['p_offset']+a-s['p_vaddr'] for s in segments if s['p_vaddr']<=a and a+n<=s['p_vaddr']+s['p_filesz'])
table=0x3f611c;records=[struct.unpack_from('<5I',raw,off(table+i*20,20)) for i in range(95)]
index=next(i for i,r in enumerate(records) if r[0]==2);row=records[index]
assert row[1:3]==(0x3f6fc4,10)
original=list(struct.unpack_from('<10I',raw,off(row[1],40)));assert 0xf80000 not in original and 0xfa0000 in original
extra=original+[0xf80000];address=0x4d8000;payload=struct.pack('<11I',*extra);at=off(address,len(payload));assert raw[at:at+len(payload)]==bytes(len(payload))
aliases=[]
for s in segments:
 lo=max(at,s['p_offset']);hi=min(at+len(payload),s['p_offset']+s['p_filesz'])
 if lo<hi:aliases.append((s['p_vaddr']+lo-s['p_offset'],s['p_flags']))
assert aliases==[(address,5)]
patched=bytearray(raw);patched[at:at+len(payload)]=payload
struct.pack_into('<II',patched,off(table+index*20+4,8),address,11)
from builtin_language import enable_settings
assert bytes(patched)==enable_settings(raw)
market=[1]
def emulator(image):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
 for s in ELFFile(io.BytesIO(image)).iter_segments():
  if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x10000)
 def hook(uc,pc,size,unused):
  if pc not in (0xe5f4,0xf6c0):return
  uc.reg_write(UC_ARM_REG_R0,market[0] if pc==0xf6c0 else 0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);return u
before,after=emulator(raw),emulator(bytes(patched))
def query(u,item):
 u.mem_write(0x60000000,bytes(8));u.reg_write(UC_ARM_REG_R0,item);u.reg_write(UC_ARM_REG_R1,0x60000000);u.reg_write(UC_ARM_REG_R2,0x60000004);u.reg_write(UC_ARM_REG_SP,0x6000f000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 u.emu_start(0x751ec,0x50000000,count=10000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
 pointer,count=struct.unpack('<II',u.mem_read(0x60000000,8));assert count<=100
 return list(struct.unpack('<'+str(count)+'I',u.mem_read(pointer,count*4))) if count else []
checks=0
for country in (1,2):
 market[0]=country
 for item in sorted({r[0] for r in records}):
  a,b=query(before,item),query(after,item)
  assert b==(a+[0xf80000] if country==1 and item==2 else a),(country,item)
  checks+=1
out=ROOT/'work/builtin-language-settings-patch'/str(time.time_ns());out.mkdir(parents=True)
artifact=out/'SpiderApp.language-settings.analysis-only.elf';artifact.write_bytes(patched)
report=dict(prepared=True,artifact=artifact.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(patched).hexdigest(),
            native_settings_language_entry_enabled=True,external_language_hooks=False,original_jp_items_preserved=True,
            other_lists_unchanged=True,arm_list_replay_cases=checks,read_only_data_added_bytes=44,elf_growth_bytes=0,
            original_language_picker_preserved=True,four_completed_language_resources_separate=True,
            hardware_verified=False,remote_sdk_recomposition_pending=True,firmware_generated=False,device_accessed=False,
            source_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest())
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
