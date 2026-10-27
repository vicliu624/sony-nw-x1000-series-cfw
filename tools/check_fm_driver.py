"""Read-only range-guard replay from the pinned Japanese 1.11 Si470x module."""
from pathlib import Path
import hashlib, io, json, tarfile, struct, subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_R5, UC_ARM_REG_R2, UC_ARM_REG_CPSR
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/fm-radio-research';work.mkdir(parents=True,exist_ok=True)
upg=ROOT/'work/updater-jp/NW_WM_FW.UPG'
assert hashlib.sha256(upg.read_bytes()).hexdigest()=='002b6720b59f093a84440f554ffabe29f5879646839a5a28d43487b5cb41914b'
# Verify component source against the existing independent extraction/roundtrip evidence
# by decrypting the pinned original UPG, without executing an installer.
import sys
sys.path.insert(0,str(ROOT))
from scripts import upg as upg_module

_,components=upg_module.unpack(upg.read_bytes())
with tarfile.open(fileobj=io.BytesIO(components[3]),mode='r:gz') as archive:
    matches=[m for m in archive.getmembers() if m.name.lstrip('./')=='lib/modules/icx_si470x_radio_tuner.ko']
    assert len(matches)==1
    module=archive.extractfile(matches[0]).read()
(work/'si470x.ko').write_bytes(module)
elf=ELFFile(io.BytesIO(module));text=elf.get_section_by_name('.text').data()
start=0x132c;code=text[start:0x1340]
assert struct.unpack('<5I',code)==(0xe5952000,0xe242394a,0xe2433c0e,0xe3530a7d,0x83e02000)
# Execute load, subtract lower bound, compare width; stop before conditional error write.
checks=[]
for khz in [0,75900,76000,76050,90000,90100,107900,108000,108100,200000]:
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x10000,0x1000);u.mem_map(0x20000,0x1000)
    u.mem_write(0x10000,code[:16]);u.mem_write(0x20000,struct.pack('<I',khz*16))
    u.reg_write(UC_ARM_REG_R5,0x20000);u.emu_start(0x10000,0x10010,count=4)
    flags=u.reg_read(UC_ARM_REG_CPSR);hi=bool(flags&(1<<29)) and not bool(flags&(1<<30))
    accepted=not hi;assert accepted==(76000<=khz<=108000)
    checks.append({'khz':khz,'guard_accepts':accepted})
disassembly=subprocess.check_output(['arm-linux-gnueabi-objdump','-dr','--disassemble=fm_do_ioctl',str(work/'si470x.ko')],text=True)
(work/'fm-do-ioctl.txt').write_text(disassembly)
report={'upg_sha256':hashlib.sha256(upg.read_bytes()).hexdigest(),'module_sha256':hashlib.sha256(module).hexdigest(),'module_source':'pinned original Japanese 1.11 rootfs','scope':'fm_do_ioctl .text+0x132c range guard only, original ARM arithmetic in Unicorn','input_units':'kHz times 16 in this branch; downstream code shifts right by 4','guard_low_khz':76000,'guard_high_khz':108000,'checks':checks,'physical_device_execution_performed':False,'limits':['Range guard alone does not validate tune command encoding, completion or RF reception.','Actual model driver selection, chip configuration and audio route remain unverified.','No evidence yet that changing region or Sony UI is necessary or sufficient.','No module loading, driver execution on hardware, NVP write or firmware creation.']}
(work/'driver-range.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
