"""Read-only stock ELF display path inventory; not runtime fd ownership."""
from pathlib import Path
import gzip,io,tarfile,hashlib,json
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();digest=hashlib.sha256(packed).hexdigest()
assert digest=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
rows=[];selected={};elf_count=0
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as archive:
 for entry in archive:
  if not entry.isfile():continue
  data=archive.extractfile(entry).read()
  if not data.startswith(b'\x7fELF'):continue
  elf_count+=1;matches=[]
  for needle in (b'/dev/fb/0',b'/dev/fb/1',b'/dev/fb0',b'/dev/fb1'):
   offset=0
   while (offset:=data.find(needle,offset))>=0:
    matches.append({'literal':needle.decode(),'file_offset':offset});offset+=len(needle)
  basename=Path(entry.name).name
  if not matches and basename not in ('appproxy','sysmgrd','SpiderApp','Responder','netfront'):continue
  elf=ELFFile(io.BytesIO(data));section=elf.get_section_by_name('.dynsym');imports=[]
  if section:
   imports=sorted({symbol.name for symbol in section.iter_symbols() if symbol['st_shndx']=='SHN_UNDEF' and symbol.name})
  dynamic=elf.get_section_by_name('.dynamic');needed=[]
  if dynamic:needed=[tag.needed for tag in dynamic.iter_tags() if tag.entry.d_tag=='DT_NEEDED']
  row={'path':entry.name,'sha256':hashlib.sha256(data).hexdigest(),'display_path_literals':matches,'needed':needed,'relevant_imports':[name for name in imports if name in ('open','open64','close','ioctl','mmap','mmap64','munmap','dup','dup2','fork','execvp','execve')],'runtime_ownership_established':False}
  rows.append(row)
  if basename in ('appproxy','sysmgrd','SpiderApp','Responder','netfront'):selected[basename]=row
assert set(selected)=={'appproxy','sysmgrd','SpiderApp','Responder','netfront'}
report={'input_sha256':digest,'physical_device_access':False,'ELF_files_scanned':elf_count,'literal_candidates':rows,'application_manager_and_proxy':{name:selected[name] for name in ('appproxy','sysmgrd')},'ownership_conclusion':'Not established: literals/imports do not prove opening, live descriptors, inheritance or last-close state.','limits':['Pinned stock rootfs ELF bytes only; no device access or execution.','Constructed paths, inherited descriptors, library paths and alternate interfaces may evade literal search.','Neither absence nor presence proves runtime framebuffer ownership.']}
(ROOT/'sources/stock-display-owner-inventory.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'ELF_files_scanned':elf_count,'literal_candidate_count':sum(bool(r['display_path_literals']) for r in rows),'manager_proxy_literals':{k:len(selected[k]['display_path_literals']) for k in ('appproxy','sysmgrd')},'runtime_ownership_established':False}))
