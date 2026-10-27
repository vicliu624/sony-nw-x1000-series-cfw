"""Execute original JP kernel remount routines against virtual superblock callbacks."""
from pathlib import Path
import struct,json,hashlib
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
ROOT=Path(__file__).resolve().parents[1];b=(ROOT/'work/upg-jp/verified-1.bin').read_bytes();base=0xc0008000
assert hashlib.sha256(b).hexdigest()=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
assert b.find(b'Linux version 2.6.10_dev-mp201-20090310A for ICX1134-1135')>=0
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0xc0000000,0x800000);u.mem_write(base,b);u.mem_map(0xc1000000,0x200000)
def put(p,n):u.mem_write(p,struct.pack('<I',n))
def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
sb=0xc1100000;sops=0xc1100800;node=0xc1101000;callback=0xc1102000;stop=0xc1103000;sp=0xc101f000
head=0xc02570fc;pending=0xc02c0000
put(head,sb);put(sb,head);put(sb+36,sops);put(sb+60,1);put(sb+144,1);put(sb+52,0);put(sb+92,1);put(sb+76,1);put(sops+56,callback)
events=[];fault=False
def hook(uc,pc,size,data):
 a=[uc.reg_read(r)for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2]];ret=0
 if fault and pc==0xc0063660:events.append(['injected-freeze-failure']);ret=1
 elif fault and pc in [0xc0063954,0xc0063830,0xc0063a10]:events.append(['failure-path-boundary',hex(pc)])
 elif pc==callback:assert a[0]==sb;events.append(['remount_fs',word(a[1])]);ret=0
 elif pc==0xc006d590:events.append(['allocate-remount-record']);ret=node
 elif pc==0xc006dd18:assert a[0]==node;events.append(['free-remount-record'])
 elif pc==0xc0082e20:events.append(['may-remount-readonly']);ret=1
 elif pc in [0xc009b67c,0xc00831d4,0xc021a384,0xc0088e90,0xc015e190]:events.append(['kernel-boundary',hex(pc)])
 elif pc in [0xc0218680,0xc02186e0,0xc0219030]:raise AssertionError(('unexpected scheduling boundary',hex(pc)))
 else:return
 uc.reg_write(UC_ARM_REG_R0,ret);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def call(pc):
 u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,stop);u.emu_start(pc,stop,count=50000);assert u.reg_read(UC_ARM_REG_PC)==stop
call(0xc0062ff0);assert word(pending)==node and word(node)==sb and ['remount_fs',1]in events
call(0xc00631cc);assert word(pending)==0 and [x for x in events if x[0]=='remount_fs']==[['remount_fs',1],['remount_fs',0]]
def target(va):
 w=word(va);assert w&0x0f000000==0x0b000000
 d=(w&0xffffff)<<2
 if d&0x2000000:d-=0x4000000
 return va+8+d
assert target(0xc00632d4)==0xc0062ff0 and target(0xc00633b0)==0xc00631cc
normal_events=events.copy()
events.clear();fault=True
put(0xc02565a4,1);put(0xc02bfffc,0xc1104000);put(0xc1104000+8,0xc1105000)
u.reg_write(UC_ARM_REG_R0,3)
call(0xc0063254)
assert u.reg_read(UC_ARM_REG_R0)==0xfffffff5
assert [x for x in events if x[0]=='remount_fs']==[['remount_fs',1]]
assert word(pending)==node
failure_events=events.copy()
events=normal_events
r={'passed':True,'kernel_sha256':hashlib.sha256(b).hexdigest(),'load_base':hex(base),'native_prepare_remount':'0xc0062ff0','native_resume_remount':'0xc00631cc','native_suspend_calls':{'0xc00632d4':'0xc0062ff0','0xc00633b0':'0xc00631cc'},'events':events,'freeze_failure':{'injected':True,'return':'-EAGAIN','events':failure_events,'resume_remount_called':False},'scope':'Actual shipped JP kernel instructions, supplied superblock/list/stack and virtual allocation, lock, sync, filesystem callbacks; not actual driver suspend or physical filesystem. Confirms remount_fs flags1 then0, not unmount. Does not prove every failure branch or application callback.','physical_device_access':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(ROOT/'work/external-language-bridge-8-ram-snapshot/kernel-remount-replay.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
