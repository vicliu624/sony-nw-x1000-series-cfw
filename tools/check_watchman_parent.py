"""Replay original watchman parent startup check; virtual fork/sleep/wait only."""
from pathlib import Path
import hashlib,io,json,struct,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:binary=tar.extractfile('./usr/local/bin/watchman').read()
digest=hashlib.sha256(binary).hexdigest()
assert digest=='5079500da11cd60d687adfbd0ea48a691367dbfa706c37c59a06df350a49b863'
elf=ELFFile(io.BytesIO(binary));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows=[]
for name,wait_result,expected in [('supervisor-still-running',0,0),('supervisor-exited-early',321,0xffffffff)]:
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x20000)
    for segment in elf.iter_segments():
        if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
    u.mem_map(0x200000,0x10000);end=0x200100;argv=0x200200
    u.mem_write(0x200300,b'/usr/local/bin/sysmgr.sh\0');u.mem_write(argv,struct.pack('<II',0x200300,0))
    events=[]
    def hook(uc,pc,size,unused):
        if pc==end:uc.emu_stop();return
        if pc not in (symbols['fork'],symbols['sleep'],symbols['waitpid']):return
        a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
        if pc==symbols['fork']:events.append('virtual-fork-parent');result=321
        elif pc==symbols['sleep']:assert a[0]==20;events.append('virtual-sleep20')
        else:
            assert a[0]==321 and a[2]==1
            uc.mem_write(a[1],struct.pack('<I',0));events.append('virtual-waitpid-WNOHANG');result=wait_result
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    for reg,value in ((UC_ARM_REG_R0,1),(UC_ARM_REG_R1,argv),(UC_ARM_REG_R2,20),(UC_ARM_REG_SP,0x20f000),(UC_ARM_REG_LR,end)):u.reg_write(reg,value)
    u.emu_start(0x8bf8,end,count=3000)
    assert u.reg_read(UC_ARM_REG_PC)==end and u.reg_read(UC_ARM_REG_R0)==expected
    assert events==['virtual-fork-parent','virtual-sleep20','virtual-waitpid-WNOHANG']
    rows.append({'case':name,'events':events,'supplied_wait_result':wait_result,'return':hex(expected)})
report={'watchman_sha256':digest,'entry':'0x8bf8','cases':rows,'all_passed':True,'physical_device_access':False,
        'limits':['Original parent branch only; fork returns321 and child supervisor is not executed.',
                  'Seconds20 is supplied to internal function, matching original gemini command; getopt/main not replayed.',
                  'sleep is virtual, no real wait/process/firmware execution occurs.',
                  'This removes permanent foreground-wait as a blocker; actual eth0 availability and boot completion remain unknown.']}
(ROOT/'sources/native-watchman-parent.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
