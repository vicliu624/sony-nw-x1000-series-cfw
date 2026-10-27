"""Bounded original FM wrapper -> audio source mapping, plus kernel proc inventory."""
from pathlib import Path
import io,json,hashlib,struct,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/stock-manager-runtime-probe/root/usr/local/bin/SpiderApp').read_bytes()
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(packed),mode='r:gz') as t:assert t.extractfile('./usr/local/bin/SpiderApp').read()==raw
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value']for s in elf.get_section_by_name('.dynsym').iter_symbols()}
def word(address):
 for p in elf.iter_segments():
  if p['p_type']=='PT_LOAD'and p['p_vaddr']<=address<p['p_vaddr']+p['p_filesz']:return struct.unpack_from('<I',p.data(),address-p['p_vaddr'])[0]
 raise AssertionError(hex(address))
rows=[]
for action,entry,selection in [('initialize',0xb44c8,0),('initialize',0xb44c8,1),('finalize',0xb4520,0)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for p in elf.iter_segments():
  if p['p_type']!='PT_LOAD':continue
  base=p['p_vaddr']&~4095;end=(p['p_vaddr']+p['p_memsz']+4095)&~4095;u.mem_map(base,end-base);u.mem_write(p['p_vaddr'],p.data())
 u.mem_map(0x60000000,0x20000);obj=0x60001000;sentinel=0x6001f000
 u.mem_write(obj+8,struct.pack('<I',82500));u.mem_write(word(0x329278),struct.pack('<I',1));u.mem_write(word(0x329284),struct.pack('<I',17))
 events=[];executed=[]
 helper={0xb6888:'wrapper preparation',0xb6b38:'MFM object',0x26e424:'MFM initialize',0x26e548:'MFM finalize',0x3e620:'mode query preparation',0x3ef10:'mode query',0x326ea0:'audio active query',0x327384:'audio subordinate update',0x328020:'audio subordinate output update',0x327ba8:'audio subordinate settings',0x327b3c:'audio subordinate mode',symbols['pthread_mutex_lock']:'mutex lock',symbols['pthread_mutex_unlock']:'mutex unlock',symbols['ioctl']:'ioctl'}
 def hook(uc,pc,size,data):
  if pc==sentinel:uc.emu_stop();return
  if pc in [0x3c2d4,0xb23f8,0x329110]:executed.append(hex(pc))
  if pc not in helper:return
  name=helper[pc];a=[uc.reg_read(r)for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]]
  if name=='ioctl':
   assert a[0]==17 and a[1]==0x40046103
   value=struct.unpack('<I',uc.mem_read(a[2],4))[0];assert value==(0 if action=='finalize'else 2)
   events.append({'ioctl':hex(a[1]),'source':value});result=0
  else:
   events.append({'replacement':name});result=obj if name=='MFM object'else selection if name=='mode query'else 1 if name=='audio active query'else 0
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook)
 for reg,value in [(UC_ARM_REG_R0,obj),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,sentinel)]:u.reg_write(reg,value)
 u.emu_start(entry,0,count=5000);assert u.reg_read(UC_ARM_REG_PC)==sentinel and u.reg_read(UC_ARM_REG_R0)==0
 assert executed==['0x3c2d4','0xb23f8','0x329110']
 rows.append({'action':action,'mode_query_fixture':selection,'original_functions':executed,'events':events})
kernel=(ROOT/'work/upg-jp/verified-1.bin').read_bytes();assert hashlib.sha256(kernel).hexdigest()=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
def kw(address):return struct.unpack_from('<I',kernel,address-0xc0008000)[0]
def ks(address):return kernel[address-0xc0008000:].split(b'\0',1)[0].decode('ascii')
assert kw(0xc0171214)==0xc027a844
# GetEntryIndex walks inode field at +16 with a 20-byte stride for 13 entries.
proc=[]
for i in range(13):
 address=0xc027a834+i*20;proc.append({'name':ks(kw(address)),'mode':oct(kw(address+4)),'id':kw(address+8)})
assert [p['name']for p in proc]==['reset','playsrc','outputdev','mute','vol','beep','restart','freqchg','mclk','nc','fadein','se','se_sync']
report={'passed':True,'spider_sha256':hashlib.sha256(raw).hexdigest(),'kernel_sha256':hashlib.sha256(kernel).hexdigest(),'fm_audio_source_cases':rows,'registered_audio_proc_entries':proc,'power_proc_registered_in_this_table':False,'hardware_tested':False,'limits':['Audio initialized/active flags, queries, MFM service, mutexes and subordinate audio helpers are virtual.','Original source-mapping and ioctl-construction instructions execute; no actual mixer ioctl.','The audio proc table lacks power. Its pathname in SpiderApp is not proof of a working power-control API.','No initialization of the entire audio-control library, codec or hardware lifecycle.']}
out=ROOT/'work/fm-radio-research/stock-audio-path.json';out.write_text(json.dumps(report,indent=2)+'\n');print('Stock FM initializes tuner source 2 and finalizes to PCM 0; registered audio proc table has no power entry.')
