"""Replay bounded slices of the pinned X1000 kernel. No hardware calls execute."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_LR,UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_CPSR
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/"work/upg-jp/verified-1.bin").read_bytes()
assert hashlib.sha256(raw).hexdigest()=="6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645"
elfdata=(ROOT/"work/isolation-audit/x1000-kernel-analysis.elf").read_bytes()
elf=ELFFile(io.BytesIO(elfdata));symbols={s.name:s['st_value']for s in elf.get_section_by_name('.symtab').iter_symbols()}
base=0xc0008000
assert symbols['vector_swi']==0xc0024ae0 and symbols['sys_call_table']==0xc0024ba4
assert next(s for s in elf.iter_sections()if s.name=='.kernel').data()[:len(raw)]==raw

def machine():
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(base,0x400000);u.mem_write(base,raw);u.mem_map(0x50000000,0x1000);u.mem_map(0x60000000,0x20000);return u

def decode(instruction,r7):
    u=machine();u.mem_write(0x50000000,struct.pack('<I',instruction));u.reg_write(UC_ARM_REG_CPSR,0x13);u.reg_write(UC_ARM_REG_R8,0x10);u.reg_write(UC_ARM_REG_R7,r7);u.reg_write(UC_ARM_REG_LR,0x50000004);u.reg_write(UC_ARM_REG_SP,0x60001f80)
    table={struct.unpack_from('<I',raw,symbols['sys_call_table']-base+i*4)[0]for i in range(288)};reached=[]
    def hook(uc,pc,size,data):
        if pc==0xc0024b18:uc.reg_write(UC_ARM_REG_PC,pc+4)
        elif pc in table or pc==symbols['arm_syscall']:reached.append(pc);uc.emu_stop()
    u.hook_add(UC_HOOK_CODE,hook);u.emu_start(0xc0024b04,0,count=100)
    assert reached;return reached[0]

routes=[]
for nr in [1,2,3,4,5,6,11,12,19,21,23,37,46,54,57,61,75,80,81,85,91,114,120,141,162,164,168,170,173,174,192,206,208,210,213,214,215,216]:
    expected=struct.unpack_from('<I',raw,symbols['sys_call_table']-base+nr*4)[0]
    assert decode(0xef900000+nr,999)==expected
    assert decode(0xef000000,nr)==symbols['arm_syscall']
    routes.append({'number':nr,'entry':hex(expected),'OABI_dispatch':True,'ARM_svc0_r7_dispatches_normally':False})
capchecks=[]
for cap in [6,7,12,17,18,21,27]:
    for granted in [False,True]:
        u=machine();u.mem_write(0x60010198,struct.pack('<I',(1<<cap)if granted else 0));u.reg_write(UC_ARM_REG_R0,0x60010000);u.reg_write(UC_ARM_REG_R1,cap);u.reg_write(UC_ARM_REG_SP,0x60008000);u.reg_write(UC_ARM_REG_LR,0x50000000)
        u.emu_start(symbols['cap_capable'],0x50000000,count=50);result=u.reg_read(UC_ARM_REG_R0)
        assert result==(0 if granted else 0xffffffff)
        capchecks.append({'capability':cap,'synthetic_task_bit_set':granted,'return':hex(result)})
required=['sys_chroot','sys_setuid','sys_setresuid','sys_setgroups','copy_namespace','shmem_fill_super','sys_mount','cap_capable']
report={'scope':'original kernel instruction slices in Unicorn; no device or real kernel services','kernel_sha256':hashlib.sha256(raw).hexdigest(),'analysis_elf_is_not_flash_image':True,'required_symbols':{n:hex(symbols[n])for n in required},'syscall_decoder':routes,'capability_checker':capchecks,'limitations':['CP15 control write skipped in decoder','Stop at handler entry: syscall implementations not executed','Capability checker receives synthetic task memory, not an actual launched app','No live mounts/devfs/USB/display or persistence validation'],'physical_device_execution_performed':False}
(ROOT/'sources/kernel-isolation-replay.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(f'{len(routes)} original-kernel syscall route comparisons and {len(capchecks)} capability-bit checks passed; no physical-device execution performed')
