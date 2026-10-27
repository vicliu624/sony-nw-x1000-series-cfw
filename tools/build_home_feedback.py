"""Build the isolated JP1.11 feedback ELF; no UPG or device access."""
from pathlib import Path
import argparse,hashlib,io,json,struct,subprocess,sys
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.home_candidate import make_candidate,PAYLOAD_ADDRESS

def build(output):
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT/'work'):
        raise ValueError('Output must be inside project work/')
    output.mkdir(exist_ok=False)
    linker=output/'hook.ld'
    linker.write_text('SECTIONS { . = '+hex(PAYLOAD_ADDRESS)+''';
.text : { *(.text*) *(.rodata*) }
.data : { *(.data*) } .bss : { *(.bss*) *(COMMON) }
/DISCARD/ : { *(.note*) *(.comment*) *(.ARM.exidx*) *(.ARM.extab*) }
ASSERT(SIZEOF(.data)==0,"No writable payload data")
ASSERT(SIZEOF(.bss)==0,"No payload BSS") }
''')
    exe=output/'hook.elf';binary=output/'hook.bin'
    subprocess.run(['arm-linux-gnueabi-gcc','-march=armv5te','-marm','-nostdlib','-static','-Wl,--build-id=none,-e,hb_home_select','-Wl,-T,'+str(linker),'runtime/native/home_feedback.S','-o',str(exe)],cwd=ROOT,check=True)
    subprocess.run(['arm-linux-gnueabi-objcopy','-O','binary',str(exe),str(binary)],check=True)
    elf=ELFFile(io.BytesIO(exe.read_bytes()))
    symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name}
    stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
    candidate,report=make_candidate(stock,binary.read_bytes(),symbols)
    data=bytearray(candidate);elf=ELFFile(io.BytesIO(candidate));loads=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
    for address,before,symbol in [(0x281e0,0xe59f4028,'hb_message_descriptor'),(0x28110,0xe35000b5,'hb_message_index')]:
        target=symbols[symbol]
        if not PAYLOAD_ADDRESS<=target<PAYLOAD_ADDRESS+len(binary.read_bytes()):raise ValueError('Adapter outside payload')
        delta=target-address-8
        if delta%4 or not -(1<<25)<=delta<(1<<25):raise ValueError('Branch outside ARM range')
        offset=next(s['p_offset']+address-s['p_vaddr'] for s in loads if s['p_vaddr']<=address and address+4<=s['p_vaddr']+s['p_filesz'])
        if struct.unpack_from('<I',data,offset)[0]!=before:raise ValueError('Unexpected original instruction')
        after=0xea000000|((delta>>2)&0xffffff)
        struct.pack_into('<I',data,offset,after)
        report['edits'].append({'address':hex(address),'before':hex(before),'after':hex(after)})
    artifact=output/'SpiderApp.feedback.analysis-only.elf';artifact.write_bytes(data)
    report.update({'candidate_sha256':hashlib.sha256(data).hexdigest(),'symbols':symbols,'profile':'home-feedback','ready_to_flash':False,'hardware_tested':False,'firmware_package_created':False,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'scripts/home_candidate.py',ROOT/'runtime/native/home_feedback.S']}})
    (output/'build.json').write_text(json.dumps(report,indent=2)+'\n')
    return bytes(data),symbols,report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();_,_,r=build(ROOT/args.output)
    print(json.dumps({k:r[k] for k in ('candidate_sha256','payload_bytes','growth_bytes','ready_to_flash')},indent=2))
