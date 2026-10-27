"""Build an analysis-only Sony ELF/overlay candidate, never a firmware package."""
from pathlib import Path
import hashlib
import io
import json
import re
import subprocess
import sys
import tarfile
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.home_candidate import make_candidate, PAYLOAD_ADDRESS
from scripts.resources import parse_stx, append_stx


def main():
    work = ROOT / 'work/home-entry-candidate'
    work.mkdir(parents=True, exist_ok=True)
    linker = work / 'payload.ld'
    linker.write_text('ENTRY(hb_home_select)\nSECTIONS { . = ' + hex(PAYLOAD_ADDRESS) + ''';
 .text : { *(.text*) *(.rodata*) }
 .data : { *(.data*) }
 .bss : { *(.bss*) *(COMMON) }
 /DISCARD/ : { *(.comment*) *(.note*) *(.ARM.exidx*) *(.ARM.extab*) *(.eh_frame*) }
 ASSERT(SIZEOF(.data) == 0, "No writable payload data allowed")
 ASSERT(SIZEOF(.bss) == 0, "No payload BSS allowed")
}
''')
    payload_elf = work / 'home-hook.elf'
    subprocess.run(['arm-linux-gnueabi-gcc', '-march=armv5te', '-marm',
                    '-nostdlib', '-static',
                    '-Wl,--build-id=none', '-Wl,-T,' + str(linker),
                    'runtime/native/home_entry.S', '-o', str(payload_elf)], cwd=ROOT, check=True)
    payload_bin = work / 'home-hook.bin'
    subprocess.run(['arm-linux-gnueabi-objcopy', '-O', 'binary', str(payload_elf), str(payload_bin)], check=True)
    pelf = ELFFile(io.BytesIO(payload_elf.read_bytes()))
    symbols = {s.name: s['st_value'] for s in pelf.get_section_by_name('.symtab').iter_symbols() if s.name}
    payload = payload_bin.read_bytes()
    code_bytes = payload[:symbols['hb_code_end'] - PAYLOAD_ADDRESS]
    for offset in range(0, len(code_bytes), 4):
        instruction = int.from_bytes(code_bytes[offset:offset + 4], 'little')
        assert instruction & 0x0f000000 != 0x0b000000, 'Payload must not use BL'
        assert instruction & 0x0ffffff0 != 0x012fff30, 'Payload must not use BLX register'
        assert instruction & 0xfe000000 != 0xfa000000, 'Payload must not use BLX immediate'
    candidate, report = make_candidate((ROOT / 'work/targets-jp/SpiderApp').read_bytes(),
                                       payload, symbols)
    output = work / 'SpiderApp.analysis-only.elf'
    output.write_bytes(candidate)
    archive = (ROOT / 'work/upg-jp/verified-3.bin').read_bytes()
    assert hashlib.sha256(archive).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
    overlays = []
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        stock_applist=tar.extractfile('./etc/AppList.conf').read()
        label_ids=[]
        for member in tar.getmembers():
            if member.name.startswith('./usr/local/share/gemini/res/stx/') and member.name.endswith('.stx'):
                data=tar.extractfile(member).read()
                modified,label_id=append_stx(data,'Homebrew');label_ids.append(label_id)
                assert parse_stx(modified)[:-1]==parse_stx(data)
                path=member.name[2:];target=work/'overlay'/path
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(modified)
                overlays.append({'path':path,'before_sha256':hashlib.sha256(data).hexdigest(),'after_sha256':hashlib.sha256(modified).hexdigest(),'growth_bytes':len(modified)-len(data),'added_index':label_id,'label':'Homebrew'})
        assert len(label_ids)==11 and len(set(label_ids))==1
        label_id=label_ids[0]
        for collection, count in ((10, 10), (11, 9)):
            path = 'usr/local/share/gemini/res/swd/ucs2-dev-sid-000-' + str(collection) + '.swd'
            data = tar.extractfile('./' + path).read()
            indices = [int(x) for x in re.findall(rb'^tid\.(\d+):', data, re.M)]
            assert indices == list(range(count))
            modified = data.rstrip() + ('\n\ntid.' + str(count) + ':\t"tid-'+str(label_id)+'"\t; homebrew candidate\n').encode()
            target = work / 'overlay' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(modified)
            overlays.append({'path': path, 'before_sha256': hashlib.sha256(data).hexdigest(),
                             'after_sha256': hashlib.sha256(modified).hexdigest(),
                             'added_index': count, 'label_tid': label_id})
    frontend = '/contents/HOMEBREW/launcher/app'
    # Sony's third token is both lookup name and executable. Remaining tokens
    # are arguments; makeExecCommand prepends appproxy for class 3.
    (work / 'AppList.fragment.NOT_INSTALLED').write_text(
        f'0x00030001 * {frontend} --native\n')
    fragment=(work/'AppList.fragment.NOT_INSTALLED').read_bytes()
    assert all(line.split()[0]!=b'0x00030001' for line in stock_applist.splitlines() if line.strip() and not line.lstrip().startswith(b'#'))
    merged=stock_applist+(b'' if stock_applist.endswith(b'\n') else b'\n')+fragment
    config=work/'overlay/etc/AppList.conf';config.parent.mkdir(parents=True,exist_ok=True);config.write_bytes(merged)
    overlays.append({'path':'etc/AppList.conf','before_sha256':hashlib.sha256(stock_applist).hexdigest(),'after_sha256':hashlib.sha256(merged).hexdigest(),'growth_bytes':len(merged)-len(stock_applist),'original_registrations_preserved':True})
    subprocess.run([sys.executable,'tools/check_applist_fragment.py','--full-config'],cwd=ROOT,check=True)
    report.update({'version': (ROOT / 'VERSION').read_text().strip(),
                   'scope': 'analysis-only ELF and uninstalled resource overlays; not a flashable package',
                   'artifact': str(output.relative_to(ROOT)), 'symbols': symbols,
                   'leaf_adapter_no_bl_blx': True, 'native_switcher_selector': 4,
                   'applist_native_parser_contract_verified': True,'applist_merged_in_local_overlay':True,
                   'service_return_pcs': {'instance': '0xb047c', 'lookup': '0xb0504', 'change': '0xb0558'},
                   'overlays': overlays, 'caption':'Homebrew','caption_tid':label_id,'original_texts_preserved':True,
                   'placeholder_icon': 'Existing Settings texture 63',
                   'limits': ['Native UI event producer and complete APF lifecycle remain unqualified.',
                              'Hook launch failures currently stay on Home without a popup.',
                              'Leaf payload has no BL/BLX; service return PCs use the original switcher frame. Asynchronous unwind from leaf PCs is unqualified.',
                              'Original device loader, mount execution permissions and system capacity remain unqualified.',
                              'AppList fragment, ELF and overlays are not installed or packed.']})
    (work / 'candidate.json').write_text(json.dumps(report, indent=2) + '\n')
    # Generate the hash-bound constructor metadata companion used by cell checks.
    subprocess.run([sys.executable,'tools/check_stx_append.py'],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'tools/check_home_labels.py','--candidate'],cwd=ROOT,check=True)
    subprocess.run([sys.executable, 'tools/check_home_action_to_launch.py'], cwd=ROOT, check=True)
    subprocess.run([sys.executable, 'tools/check_home_parent.py'], cwd=ROOT, check=True)
    subprocess.run([sys.executable, 'tools/check_home_geometry.py', '--candidate'],
                   cwd=ROOT, check=True, stdout=subprocess.PIPE, text=True)
    report['action_to_request_fixture_verified'] = True
    report['native_cell_factory_fixture_verified'] = True
    (work / 'candidate.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('scope', 'growth_bytes', 'payload_bytes', 'candidate_sha256')}, indent=2))


if __name__ == '__main__':
    main()
