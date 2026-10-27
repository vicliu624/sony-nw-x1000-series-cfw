"""Compare actual rebuild ELF sections/segments; no device/native execution."""
from pathlib import Path
import subprocess,sys,hashlib,json,shutil,io
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/network-store-rebuild-tests';work.mkdir(exist_ok=True)
def capture(path):
 data=path.read_bytes();elf=ELFFile(io.BytesIO(data))
 return {'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'entry':int(elf.header['e_entry']),'flags':int(elf.header['e_flags']),'sections':{s.name:{'bytes':s['sh_size'],'flags':s['sh_flags'],'sha256':hashlib.sha256(s.data()).hexdigest()} for s in elf.iter_sections()},'segments':[{'type':s['p_type'],'vaddr':s['p_vaddr'],'filesz':s['p_filesz'],'memsz':s['p_memsz'],'flags':s['p_flags'],'sha256':hashlib.sha256(s.data()).hexdigest()} for s in elf.iter_segments()]}
records=[]
for index in range(2):
 subprocess.run([sys.executable,str(ROOT/'tools/build_network_store_app.py')],cwd=ROOT,check=True)
 build=json.loads((ROOT/'sources/native-network-store-app-build.json').read_text());source=ROOT/build['artifact'];target=work/f'rebuild-{index}.elf';shutil.copyfile(source,target);records.append(capture(target))
a,b=records;changed=[name for name in sorted(set(a['sections'])|set(b['sections'])) if a['sections'].get(name)!=b['sections'].get(name)]
report={'all_bounded_checks_passed':a['sha256']==b['sha256'],'same_toolchain_rebuild_identical':a['sha256']==b['sha256'],'source_hashes':{'tools/build_network_store_app.py':hashlib.sha256((ROOT/'tools/build_network_store_app.py').read_bytes()).hexdigest(),'tools/check_network_store_rebuild.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'physical_device_access':False,'changed_sections':changed,'entry_flags_equal':(a['entry'],a['flags'])==(b['entry'],b['flags']),'segments_equal':a['segments']==b['segments'],'builds':records,'limits':['Two builds in the same checkout/toolchain, not cross-machine or cross-toolchain reproducibility.','No native or physical device execution.']}
if report['same_toolchain_rebuild_identical']:(ROOT/'sources/native-network-store-rebuild-tests.json').write_text(json.dumps(report,indent=2)+'\n')
(work/'comparison.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('same_toolchain_rebuild_identical','changed_sections','entry_flags_equal','segments_equal')},indent=2))
if '--require-identical' in sys.argv:assert report['same_toolchain_rebuild_identical'],'Whole ELF rebuild differs; see comparison.json'
