"""Verify optimized language inputs and root overlay without writing a UPG or installer."""
from pathlib import Path
import copy,gzip,hashlib,io,json,sys,tarfile,struct
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack
from language_profile import audit_minimal_overlay

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verified(path,source=None):
 r=json.loads(path.read_text());assert r.get('passed') is True,path
 for name,h in r.get('source_hashes',{}).items():assert digest(ROOT/name)==h,(path,name)
 if source and 'source_sha256'in r:assert digest(ROOT/source)==r['source_sha256'],source
 return r

def review():
 w=ROOT/'work/external-language-bridge-10-process-cache-final'
 build=verified(w/'report.json');elf_path=ROOT/build['artifact'];elf_raw=elf_path.read_bytes();h=digest(elf_path);assert h==build['sha256']
 tests=verified(w/'native-cache-tests.json','tools/test_process_language_cache.py');layout=verified(w/'layout-probe.json','tools/test_language_cache_layout.py')
 assert tests['candidate_sha256']==layout['candidate_sha256']==h
 assert len(tests['cases'])==13 and sum(r['original_rebuild_cleanup_cycles']for r in tests['cases'])==384
 assert all(not r['external_io_during_recovery']and r['fds_after_cleanup']==0 for r in tests['cases'])
 for ident,files in tests['pack_inputs'].items():
  folder=ROOT/'dist/0.1.0-dev.16/language-packs-v1'/ident/'HOMEBREW/languages'/ident
  assert {p.name:digest(p)for p in folder.iterdir()if p.is_file()}==files,ident
 cap=verified(ROOT/'work/language-cache-capacity-review-1/report.json','tools/check_language_cache_capacity.py')
 assert cap['readback_files'][0]['sha256']==h and cap['extra_allocated_bytes']==0 and cap['new_inodes']==0
 shared=verified(ROOT/'work/external-language-pack-tests/report.json')
 base=ROOT/'dist/0.1.0-dev.16/diagnostic-review-9/firmware/DIAGNOSTIC-REVIEW-ONLY.UPG'
 assert digest(base)=='947acd961e019b79a07e006f21ce3751e2a555a23768f5ec21b769aa8bf093b4'
 _,parts=unpack(base.read_bytes(),require_stock=False)
 for i in range(3):assert parts[i]==(ROOT/f'work/upg-jp/verified-{i}.bin').read_bytes()
 # Root overlay exists in memory only. No firmware/archive package is emitted.
 buf=io.BytesIO();before_elf=None
 with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz')as a,tarfile.open(fileobj=buf,mode='w',format=tarfile.GNU_FORMAT)as b:
  for member in a:
   item=copy.copy(member)
   if not member.isfile():b.addfile(item);continue
   data=a.extractfile(member).read()
   if member.name.removeprefix('./')=='usr/local/bin/SpiderApp':before_elf=data;assert len(data)==len(elf_raw);data=elf_raw
   b.addfile(item,io.BytesIO(data))
 root=audit_minimal_overlay(parts[3],gzip.compress(buf.getvalue(),compresslevel=1,mtime=0));assert root['modified_system_files']==['usr/local/bin/SpiderApp']
 # Independent ELF comparison: only declared hooks, inserted code and BSS extents.
 original=ELFFile(io.BytesIO(before_elf));current=ELFFile(io.BytesIO(elf_raw));segments=[s for s in original.iter_segments()if s['p_type']=='PT_LOAD'];allowed=set()
 def offset(va,n):return next(s['p_offset']+va-s['p_vaddr']for s in segments if s['p_vaddr']<=va and va+n<=s['p_vaddr']+s['p_filesz'])
 for edit in build['callsite_edits']:
  p=offset(int(edit['address'],16),4);assert struct.unpack_from('<I',before_elf,p)[0]==int(edit['before'],16);assert struct.unpack_from('<I',elf_raw,p)[0]==int(edit['after'],16);allowed.update(range(p,p+4))
 p=offset(0x4d8000,build['payload_bytes']);assert before_elf[p:p+build['payload_bytes']]==bytes(build['payload_bytes']);allowed.update(range(p,p+build['payload_bytes']))
 for i,s in enumerate(original.iter_segments()):
  if s['p_type']=='PT_LOAD'and s['p_flags']&2:
   at=original['e_phoff']+i*original['e_phentsize']+20;allowed.update(range(at,at+4))
   t=list(current.iter_segments())[i];assert s.data()==t.data() and (s['p_vaddr']+s['p_memsz']+4095)//4096==(t['p_vaddr']+t['p_memsz']+4095)//4096
 for i,s in enumerate(original.iter_sections()):
  if s.name=='.bss':at=original['e_shoff']+i*original['e_shentsize']+20;allowed.update(range(at,at+4))
 assert not any(x!=y and i not in allowed for i,(x,y)in enumerate(zip(before_elf,elf_raw)))
 r={'passed':True,'profile':'process-owned-language-cache-local-review','elf_sha256':h,'source_and_artifact_hashes_verified':True,'language_pack_hashes_verified':True,'root_overlay':root,'extra_allocated_bytes':cap['extra_allocated_bytes'],'available_nonreserved_bytes':cap['available_nonreserved_bytes'],'native_cases':len(tests['cases']),'rebuild_cleanup_cycles':384,'additional_load_pages':0,'new_flashing_package_created':False,'device_written':False,'hardware_tested':False,'ready_to_flash':False}
 (w/'preflight-review.json').write_text(json.dumps(r,indent=2)+'\n')
 return r
def summary(r):
 return {k:v for k,v in r.items()if k!='root_overlay'}|{'root_overlay':{k:v for k,v in r['root_overlay'].items()if k!='unchanged_system_resource_files'},'unchanged_system_resource_files':len(r['root_overlay']['unchanged_system_resource_files'])}
if __name__=='__main__':print(json.dumps(summary(review()),indent=2))
