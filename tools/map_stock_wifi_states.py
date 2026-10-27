"""Execute stock daemon's state projection/labels, with logging intercepted.
No daemon loop, command, radio, IPC, profile or actual application is run.
"""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'work/qqmusic-wifi/cnmgr_daemon';raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()=='351eb99a05ae9a6baf00c8d8fd6e5e16129cc58dc6f300cf5f43d0fc5ad4eb35'
elf=ELFFile(io.BytesIO(raw));u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x100000)
for s in elf.iter_segments():
 if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],s.data())
u.mem_map(0x2000000,0x40000);obj=0x2001000;end=0x2000100;captured=[]
def cstr(address):return bytes(u.mem_read(address,180)).split(b'\0')[0].decode()
def hook(uc,pc,size,unused):
 if pc==end:uc.emu_stop()
 elif pc==0xa14c:captured.append(cstr(uc.reg_read(UC_ARM_REG_R1)));uc.emu_stop()
def no_syscall(uc,number,unused):raise AssertionError('Unexpected system instruction')
u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,no_syscall)
rows=[]
for state in range(46):
 u.mem_write(obj+0xa09c,struct.pack('<I',state));u.reg_write(UC_ARM_REG_R0,obj);u.reg_write(UC_ARM_REG_SP,0x203f000);u.reg_write(UC_ARM_REG_LR,end);u.emu_start(0xa9dc,end,count=100)
 assert u.reg_read(UC_ARM_REG_PC)==end;api=u.reg_read(UC_ARM_REG_R0);captured.clear()
 u.reg_write(UC_ARM_REG_R0,obj);u.reg_write(UC_ARM_REG_SP,0x203f000);u.reg_write(UC_ARM_REG_LR,end);u.emu_start(0xaacc,end,count=500)
 assert len(captured)==1;rows.append({'internal':state,'api':api,'stock_label':captured[0]})
report={'passed':True,'daemon_sha256':hashlib.sha256(raw).hexdigest(),'state_function':'0xa9dc','label_function':'0xaacc','state_field':'object+0xa09c','rows':rows,'physical_device_or_ipc_access':False,'limits':['Internal state values supplied; transitions and reachability are not established by this projection.','Labels are original firmware strings; semantic interpretation must follow event producers.']}
(ROOT/'sources/stock-wifi-state-map.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'api_groups':{str(k):[r for r in rows if r['api']==k] for k in (2,3,4)}},indent=2))
