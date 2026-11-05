"""Replay Sony WLAN power-module exit with RAM-only GPIO and import models."""
import hashlib
import io
import json
import tarfile
from app_registry import ROOT
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_MEM_WRITE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

root=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(root).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(root),mode='r:gz') as archive:
    raw=archive.extractfile('./lib/modules/wlan_pwr_ctrl.ko').read()
    script=archive.extractfile('./usr/local/bin/wlanapi.sh').read()
    assert './usr/local/bin/wlanapi.inc' not in archive.getnames(), 'Review board-specific script overrides'
unload=script.split(b'w8_proc_unload()',1)[1].split(b'\n}',1)[0]
assert [unload.index(b'rmmod ${'+name+b'}') for name in (
    b'w8_wlan_driver',b'w8_sdio_driver',b'w8_wlan_pm_driver',b'w8_wlan_pwr_driver')]==sorted(
    unload.index(b'rmmod ${'+name+b'}') for name in (
    b'w8_wlan_driver',b'w8_sdio_driver',b'w8_wlan_pm_driver',b'w8_wlan_pwr_driver'))
assert raw==(ROOT/'work/targets-jp/wlan_pwr_ctrl.ko').read_bytes()
elf=ELFFile(io.BytesIO(raw));section=elf.get_section_by_name('.exit.text')
assert section is not None
relocations=elf.get_section_by_name('.rel.exit.text')
symbols=elf.get_section(relocations['sh_link'])
imports={r['r_offset']:symbols.get_symbol(r['r_info_sym']).name for r in relocations.iter_relocations() if r['r_info_type']==1}
assert imports=={0x10:'pwc_regulator_off',0x58:'mp200_pmu_write_reg',0x68:'mp200_pmu_write_reg',0x78:'mp200_pmu_write_reg',0x84:'printk'}
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);code=0x100000;end=0x200000
u.mem_map(code,4096);u.mem_write(code,section.data());u.mem_map(end,4096)
u.mem_map(0x300000,0x10000);u.mem_map(0xec050000,4096)
calls=[];writes=[]
def hook(uc,pc,size,unused):
    if pc==end:uc.emu_stop();return
    offset=pc-code
    if offset not in imports:return
    name=imports[offset]
    args=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
    calls.append(dict(import_name=name,arguments=args if name!='printk' else []))
    # The original relocation call instruction remains in the input. Model its
    # external return; a tail-call printk returns through the restored LR.
    uc.reg_write(UC_ARM_REG_R0,0)
    uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR) if offset==0x84 else pc+4)
def store(uc,access,address,size,value,unused):
    if 0xec050000<=address<0xec051000:writes.append(dict(address=hex(address),bytes=size,value=value))
def reject(*args):raise AssertionError('Unexpected actual system instruction')
u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_MEM_WRITE,store);u.hook_add(UC_HOOK_INTR,reject)
u.reg_write(UC_ARM_REG_SP,0x30f000);u.reg_write(UC_ARM_REG_LR,end)
u.emu_start(code,end,count=1000)
assert u.reg_read(UC_ARM_REG_PC)==end
assert calls[0]==dict(import_name='pwc_regulator_off',arguments=[0x50806,0,0])
assert [c['arguments'] for c in calls[1:4]]==[[0xec81022c,4,4],[0xec81022c,1,1],[0xec81022c,32,32]]
assert [(w['address'],w['value']) for w in writes]==[
    ('0xec050200',0x2000),('0xec050208',0x20000000),
    ('0xec050200',0x100),('0xec050208',0x1000000),
    ('0xec050200',0x400),('0xec050208',0x4000000)]
report=dict(passed=True,original_exit_instructions_executed=True,device_accessed=False,
            module_sha256=hashlib.sha256(raw).hexdigest(),calls=calls,gpio_writes_to_ram=writes,
            stock_unload_script_sha256=hashlib.sha256(script).hexdigest(),
            stock_unload_order=['sd8xxx','mp200_sdio','wlan_pm_register','wlan_pwr_ctrl'],
            source_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
            limits=['Kernel imports return modeled success; PMU/GPIO hardware are never accessed.',
                    'Shows regulator-off intent in the original unload path, not measured rail voltage or standby current.'])
out=ROOT/'work/remote-settings-native';out.mkdir(exist_ok=True)
(out/'power-module-exit-replay.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
