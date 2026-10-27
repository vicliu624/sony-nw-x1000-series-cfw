"""Inventory stock application-manager library candidates; no device access."""
from pathlib import Path
import hashlib,io,json,re,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];packed=ROOT/'work/upg-jp/verified-3.bin'
assert hashlib.sha256(packed.read_bytes()).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
pattern=re.compile(r'apf|app.*(change|switch|lookup)|change.*app',re.I)
targets={'./usr/local/bin/'+name for name in ('SpiderApp','Responder','appproxy','sysmgrd')}
libraries=[];programs=[]
with tarfile.open(packed,'r|gz') as archive:
 for member in archive:
  if not member.isfile() or not ('.so' in member.name or member.name in targets):continue
  data=archive.extractfile(member).read()
  if not data.startswith(b'\x7fELF'):continue
  elf=ELFFile(io.BytesIO(data));dynamic=elf.get_section_by_name('.dynamic');symbols=elf.get_section_by_name('.dynsym')
  row={'path':member.name,'sha256':hashlib.sha256(data).hexdigest(),'needed':[t.needed for t in dynamic.iter_tags() if t.entry.d_tag=='DT_NEEDED'] if dynamic else []}
  if member.name in targets:
   row['internal_branch_calls']=[]
   if member.name.endswith('/SpiderApp'):
    for address in (0xb0554,):
     segment=next(p for p in elf.iter_segments() if p['p_type']=='PT_LOAD' and p['p_vaddr']<=address<p['p_vaddr']+p['p_filesz'])
     instruction=int.from_bytes(segment.data()[address-segment['p_vaddr']:address-segment['p_vaddr']+4],'little')
     assert instruction&0x0f000000==0x0b000000
     immediate=instruction&0xffffff
     if immediate&0x800000:immediate-=1<<24
     destination=address+8+immediate*4
     plt=elf.get_section_by_name('.plt');in_plt=bool(plt and plt['sh_addr']<=destination<plt['sh_addr']+plt['sh_size'])
     row['internal_branch_calls'].append({'call_address':hex(address),'instruction':hex(instruction),'destination':hex(destination),'destination_in_PLT':in_plt})
   programs.append(row)
  else:
   definitions=[s.name for s in symbols.iter_symbols() if s['st_shndx']!='SHN_UNDEF'] if symbols else []
   row['defined_dynamic_symbols']=len(definitions);row['matching_defined_symbols']=[name for name in definitions if pattern.search(name)]
   libraries.append(row)
assert len(programs)==4 and len(libraries)==72
report={'passed':True,'libraries_scanned':len(libraries),'pattern':pattern.pattern,'matches':sum(len(r['matching_defined_symbols']) for r in libraries),'libraries':libraries,'programs':programs,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),packed]},'hardware_tested':False,'limits':['Name-based export inventory cannot prove absence of unnamed, differently named or private APIs.','Internal branch classification is static evidence, not a callable ABI or lifecycle qualification.','No runtime app-manager library was invented or added.']}
(ROOT/'sources/native-stock-app-api-inventory.json').write_text(json.dumps(report,indent=2)+'\n')
print('Stock library inventory:',len(libraries),'libraries;',report['matches'],'matching application-switch exports.')
print(next(p['internal_branch_calls'] for p in programs if p['path'].endswith('/SpiderApp')))
