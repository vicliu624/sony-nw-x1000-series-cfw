"""Bounded original ARM client API replay; IPC/mutex imports are RAM models.
Does not initialize a real client, write FIFOs or contact a device/network.
"""
from pathlib import Path
import hashlib,io,json,re,struct,subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'work/qqmusic-wifi/libcnmgr.so.1';raw=path.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='688e09dded18c621dba0bf6f0c2bd9088cd495988a3e3e7dadb0a928efd1aac1'
elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
asm=subprocess.check_output(['arm-linux-gnueabi-objdump','-d',str(path)],text=True)
imports={int(address,16):name for address,name in re.findall(r'^([0-9a-f]+) <([^>]+)@plt>:',asm,re.M)}
rows=[]
for name,kind,expected in [('cnmgr_get_state',18,2),('cnmgr_power_on',3,0),('cnmgr_prepare_connect',16,0),('cnmgr_connect',12,0)]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0,0x20000)
 for segment in elf.iter_segments():
  if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
 u.mem_map(0x300000,0x20000);end=0x300100;requests=[]
 # Fixed observed PIC global flag. The init/daemon lifecycle is not replayed.
 u.mem_write(0x12cf0+0x238,struct.pack('<I',1))
 def hook(uc,pc,size,unused):
  if pc==end:uc.emu_stop();return
  if pc not in imports:return
  function=imports[pc];a,b,c=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
  if function=='memset':assert c<=8192;uc.mem_write(a,bytes([b&255])*c);result=a
  elif function=='memcpy':assert c<=8192;uc.mem_write(a,bytes(uc.mem_read(b,c)));result=a
  elif function=='write':assert c==1020;requests.append(struct.unpack('<I',uc.mem_read(b,4))[0]);result=c
  elif function=='read':assert c==1012;uc.mem_write(b,struct.pack('<II',0,2 if kind==18 else 0)+bytes(c-8));result=c
  elif function in ('lockf','pthread_mutex_lock','pthread_mutex_unlock'):pass
  else:raise AssertionError('Unexpected original import: '+function)
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_SP,0x31f000);u.reg_write(UC_ARM_REG_LR,end)
 u.emu_start(symbols[name],end,count=20000)
 assert u.reg_read(UC_ARM_REG_PC)==end and requests==[kind] and u.reg_read(UC_ARM_REG_R0)==expected
 rows.append({'api':name,'null_argument':name=='cnmgr_connect','captured_request_kind':kind,'request_bytes':1020,'response_bytes':1012,'return':expected})
report={'passed':True,'stock_library_sha256':hashlib.sha256(raw).hexdigest(),'actual_arm_api_bodies':True,'ipc_and_mutexes_simulated':True,'real_device_or_network_accessed':False,'cases':rows,'limits':['Client initialized flag supplied in RAM; actual cnmgr_init and daemon lifecycle not executed.','No radio, saved access point, DHCP, DNS or physical connection qualification.']}
(ROOT/'sources/qqmusic-cnmgr-api.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
