"""Compare original inline device block and shared-include frontend builds."""
from pathlib import Path
import subprocess,hashlib,json,io
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/display-extraction';work.mkdir(exist_ok=True)
source=(ROOT/'runtime/native/platform_arm.c').read_text()
shared=(ROOT/'runtime/native/display_touch.inc').read_text()
original=source.replace('#include "display_touch.inc"',shared.rstrip('\n'))
assert original!=source
baseline=work/'platform_arm.c';baseline.write_text(original)
version=(ROOT/'VERSION').read_text().strip()
flags=['-DHB_BUILD_VERSION="'+version+'"','-I'+str(ROOT/'runtime/native'),'-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-Wall','-Wextra','-Werror','-nostdlib','-static','-Wl,-e,_start','-Wl,--build-id=none']
common=[str(ROOT/'runtime/native'/name) for name in ('frontend.c','sony_bridge.c','sha256.c','support.c','selftest.c','entry_start.S','syscalls.S')]
def build(path,name):
 out=work/name;subprocess.run(['arm-linux-gnueabi-gcc',*flags,*common,str(path),'-lgcc','-o',str(out)],check=True)
 return out.read_bytes()
before=build(baseline,'inline');after=build(ROOT/'runtime/native/platform_arm.c','shared')
def allocated(binary):
 elf=ELFFile(io.BytesIO(binary))
 return {s.name:(s['sh_addr'],s['sh_size'],s['sh_flags'],s['sh_type'],s.data()) for s in elf.iter_sections() if s['sh_flags']&2}
assert allocated(before)==allocated(after)
def execution_layout(binary):
 elf=ELFFile(io.BytesIO(binary))
 return (elf['e_entry'],elf['e_flags'],[dict(s.header) for s in elf.iter_segments()])
assert execution_layout(before)==execution_layout(after)
report={'all_allocated_sections_identical':True,'physical_device_access':False,'inline_sha256':hashlib.sha256(before).hexdigest(),'shared_sha256':hashlib.sha256(after).hexdigest(),'shared_source_sha256':hashlib.sha256(shared.encode()).hexdigest(),'sections':list(allocated(after)),'limits':['Compares reconstructed inline source against current shared include, not hardware execution.','Nonallocated symbol/file metadata may differ; whole-ELF byte identity is not claimed.','Does not create firmware or modify integration candidate.']}
(ROOT/'sources/native-display-extraction.json').write_text(json.dumps(report,indent=2)+'\n')
print('Inline/shared frontend allocated sections identical.')
