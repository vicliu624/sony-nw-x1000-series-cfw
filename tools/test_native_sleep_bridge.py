"""Patched Main actions -> sleep anchor; request shim remains modeled."""
import hashlib,io,json,struct,time
from app_registry import ROOT
from native_sleep_bridge import compose,ENTRY
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
folder=ROOT/'work/player-host-managed-prepare-builtin-language-native-settings-wireless-settings-rf-gate'
base=(folder/'SpiderApp.player-prepare.analysis-only.elf').read_bytes()
review=json.loads((folder/'build.json').read_text());assert review['analysis_only'] and not review['ready_to_flash']
assert hashlib.sha256(base).hexdigest()==review['candidate_sha256']
out=ROOT/'work/native-sleep-bridge'/str(time.time_ns())
patched,report=compose(base,out)
(out/'SpiderApp.sleep.analysis-only.elf').write_bytes(patched)
rows=[]
for entry,callsite,expected in ((0x614e4,0x614f0,2),(0x6163c,0x61648,0),(0x61928,0x61940,4),(0x61c44,0x61c5c,0)):
 for handled in (False,True):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
  segments=[s for s in ELFFile(io.BytesIO(patched)).iter_segments() if s['p_type']=='PT_LOAD'];merged=[]
  for lo,hi in sorted((s['p_vaddr']&~4095,(s['p_vaddr']+s['p_memsz']+4095)&~4095) for s in segments):
   if merged and lo<=merged[-1][1]:merged[-1]=(merged[-1][0],max(hi,merged[-1][1]))
   else:merged.append((lo,hi))
  for lo,hi in merged:u.mem_map(lo,hi-lo)
  for segment in segments:u.mem_write(segment['p_vaddr'],segment.data())
  u.mem_map(0x71000000,65536);done=0x7100ff00;requests=[];acks=[]
  def hook(cpu,pc,size,unused):
   value=0
   if pc==0xda84:
    assert cpu.reg_read(UC_ARM_REG_R0)==callsite and cpu.reg_read(UC_ARM_REG_LR)==ENTRY+12
    requests.append(callsite);value=0x58575052 if handled else 123
   elif pc==0xb03e8:acks.append(pc)
   elif pc==0xe5f4:value=0x613e2c
   elif pc not in (0xe600,0xb174c):return
   cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  u.hook_add(UC_HOOK_CODE,hook)
  preserved=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)
  for index,reg in enumerate(preserved):u.reg_write(reg,0x900+index)
  u.reg_write(UC_ARM_REG_SP,0x7100f000);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(entry,done,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==expected and u.reg_read(UC_ARM_REG_SP)==0x7100f000
  assert [u.reg_read(reg) for reg in preserved]==list(range(0x900,0x908))
  assert requests==[callsite] and len(acks)==int(not handled)
  rows.append(dict(action=hex(entry),callsite=hex(callsite),handled=handled,original_ack_calls=len(acks)))
report.update(passed=True,cases=rows,device_accessed=False,native_host_handler_installed=False,source_hashes={**report['source_hashes'],'tools/test_native_sleep_bridge.py':hashlib.sha256((ROOT/'tools/test_native_sleep_bridge.py').read_bytes()).hexdigest()},limits=['Original Main actions and composed anchor execute; shim return/native media helpers are fixtures.','No C host dispatch installation, deferred owner-loop pump, actual sleep, wake/rearm or RF qualification.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');(ROOT/'work/native-sleep-bridge-latest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
