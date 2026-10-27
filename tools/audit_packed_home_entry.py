"""Reconstruct the menu patch from source and compare to actual review UPG."""
from pathlib import Path
import argparse,hashlib,io,json,subprocess,sys,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.upg import unpack
from scripts.home_candidate import make_candidate,PAYLOAD_ADDRESS
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',default='dist/0.1.0-dev.16/diagnostic-review-2');parser.add_argument('--output',default='work/packed-home-source-audit');args=parser.parse_args()
candidate=(ROOT/args.candidate).resolve();assert candidate.is_relative_to(ROOT/'dist')
work=(ROOT/args.output).resolve();assert work.is_relative_to(ROOT/'work');work.mkdir(exist_ok=False)
upg=candidate/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG'
_,parts=unpack(upg.read_bytes(),require_stock=False)
with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as archive:actual=archive.extractfile('./usr/local/bin/SpiderApp').read()
with tarfile.open(ROOT/'work/upg-jp/verified-3.bin','r:gz') as archive:stock=archive.extractfile('./usr/local/bin/SpiderApp').read()
linker=work/'hook.ld'
linker.write_text('ENTRY(hb_home_select)\nSECTIONS { . = '+hex(PAYLOAD_ADDRESS)+'; .text : { *(.text*) *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } /DISCARD/ : { *(.comment*) *(.note*) *(.ARM.exidx*) *(.ARM.extab*) *(.eh_frame*) } ASSERT(SIZEOF(.data)==0,"no data") ASSERT(SIZEOF(.bss)==0,"no bss") }\n')
elf_path=work/'hook.elf';binary=work/'hook.bin'
subprocess.run(['arm-linux-gnueabi-gcc','-march=armv5te','-marm','-nostdlib','-static','-Wl,--build-id=none','-Wl,-T,'+str(linker),'runtime/native/home_entry.S','-o',str(elf_path)],cwd=ROOT,check=True)
subprocess.run(['arm-linux-gnueabi-objcopy','-O','binary',str(elf_path),str(binary)],check=True)
elf=ELFFile(io.BytesIO(elf_path.read_bytes()));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name}
payload=binary.read_bytes();rebuilt,detail=make_candidate(stock,payload,symbols)
assert rebuilt==actual,'Packed menu ELF differs from the source-defined patch'
code=payload[:symbols['hb_code_end']-PAYLOAD_ADDRESS]
for i in range(0,len(code),4):
 word=int.from_bytes(code[i:i+4],'little');assert word&0x0f000000!=0x0b000000 and word&0x0ffffff0!=0x012fff30 and word&0xfe000000!=0xfa000000
tracked=[Path(__file__),ROOT/'runtime/native/home_entry.S',ROOT/'scripts/home_candidate.py',ROOT/'scripts/upg.py',upg,ROOT/'work/upg-jp/verified-3.bin',linker,elf_path,binary]
report={'scope':'Actual UPG menu ELF equals a fresh source reconstruction; not UI execution or hardware qualification','passed':True,'upg_sha256':hashlib.sha256(upg.read_bytes()).hexdigest(),'packed_SpiderApp_sha256':hashlib.sha256(actual).hexdigest(),'source_reconstruction_exact':True,'original_virtual_addresses_preserved':True,'original_notes_unwind_tables_preserved':True,'new_leaf_has_bl_blx':False,'payload_bytes':len(payload),'file_growth_bytes':detail['growth_bytes'],'edits':detail['edits'],'hardware_tested':False,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('passed','source_reconstruction_exact','payload_bytes','file_growth_bytes','new_leaf_has_bl_blx')},indent=2))
