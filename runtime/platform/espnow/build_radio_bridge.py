"""PC-only radio prototype build. Does not create a download image or install."""
import hashlib
import json
import subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'work/espnow-radio-bridge'
OUT.mkdir(parents=True, exist_ok=True)
source = 'runtime/platform/espnow/radio_bridge.c'
script = 'runtime/platform/espnow/radio_bridge.ld'
obj, elf = OUT/'bridge.o', OUT/'bridge.elf'
subprocess.run(['arm-linux-gnueabi-gcc', '-Os', '-Wall', '-Wextra', '-Werror',
                '-Wno-missing-field-initializers', '-march=armv5te', '-mthumb',
                '-mfloat-abi=soft', '-ffreestanding', '-fno-builtin', '-fno-pie',
                '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
                '-c', source, '-o', str(obj)], cwd=ROOT, check=True)
subprocess.run(['arm-linux-gnueabi-ld', '-T', script, str(obj), '-o', str(elf)], cwd=ROOT, check=True)
with elf.open('rb') as f:
    e = ELFFile(f)
    sections = {name: {'address': e.get_section_by_name(name)['sh_addr'],
                       'bytes': e.get_section_by_name(name)['sh_size']}
                for name in ('.text', '.state')}
    symbols = {s.name: s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()
               if s.name in ('xnow_radio_receive', 'xnow_radio_state')}
    code = e.get_section_by_name('.text').data()
header = ('#ifndef XNOW_RADIO_BUILD_H\n#define XNOW_RADIO_BUILD_H\n'
          f'#define XNOW_RADIO_CODE_BASE 0x{sections[".text"]["address"]:08x}u\n'
          f'#define XNOW_RADIO_STATE_BASE 0x{symbols["xnow_radio_state"]:08x}u\n'
          'static const unsigned char xnow_radio_expected_code[]={' +
          ','.join(str(v) for v in code) + '};\n#endif\n')
(OUT/'xnow_radio_build.h').write_text(header)
report = {'sections': sections, 'symbols': symbols,
          'sha256': hashlib.sha256(elf.read_bytes()).hexdigest(),
          'candidate_memory_ownership_verified': False, 'device_written': False,
          'download_image_created': False, 'hardware_qualified': False}
(OUT/'build.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
