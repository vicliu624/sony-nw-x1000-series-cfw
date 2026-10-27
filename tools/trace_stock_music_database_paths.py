"""Read-only JP Responder path-flow evidence; never executes stock code."""
from pathlib import Path
import hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'work/targets-jp/Responder';data=path.read_bytes()
digest=hashlib.sha256(data).hexdigest();assert digest=='71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261'
elf=ELFFile(io.BytesIO(data));segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
def at(address,count):
 for s in segments:
  if s['p_vaddr']<=address and address+count<=s['p_vaddr']+s['p_filesz']:
   offset=s['p_offset']+address-s['p_vaddr'];return data[offset:offset+count]
 raise ValueError('Address outside file-backed load segment')
def word(address):return struct.unpack('<I',at(address,4))[0]
def text(address):return at(address,96).split(b'\0',1)[0].decode('ascii')
assert word(0x17dc18)==0xe5913038  # config object's +0x38 selector
assert word(0x17dc28)==0x0a00001d  # zero skips the path setter
assert word(0x17dc2c)==0xeb002880  # setter 0x187e34
assert word(0x187e34)==0xe1a02000 and word(0x187e38)==0xe59f0004
global_base=word(0x187d80);default_path=word(0x187d84);setter_destination=word(0x187e44)
assert global_base+0x28c0+0x20==setter_destination==0x6b8058
assert text(default_path)=='/contents/MTPDB.dat'
override_path=word(0x17dcdc);assert text(override_path)=='/db/MTPDB.dat'
assert word(0x17e8b0)==override_path and word(0x17e850)==0xeb006d2d
assert word(0x199d44)==0x6ca294
assert word(0x185b8c)==0xe1a00001 and word(0x185b98)==0xebfa1749
assert word(0x1acd14)==0xe1a00005 and word(0x1acd24)==0xebf97ae6
# One open wrapper also serves a different SQLite database; do not classify
# every sqlite3_open instruction as a music-database operation.
other_database=text(word(0x183e28));assert other_database=='/var/apfconf.dat'
targets={0x185b84:'sqlite_wrapper_A',0x1accdc:'sqlite_wrapper_B',0x187e34:'path_setter',0x199d0c:'descriptor_copy'}
calls=[]
for s in segments:
 if not s['p_flags']&1:continue
 raw=s.data();base=int(s['p_vaddr'])
 for offset in range(0,len(raw)-3,4):
  ins=struct.unpack_from('<I',raw,offset)[0]
  if ins&0x0f000000!=0x0b000000:continue
  delta=(ins&0xffffff)<<2
  if delta&0x2000000:delta-=0x4000000
  destination=(base+offset+8+delta)&0xffffffff
  if destination in targets:calls.append({'at':hex(base+offset),'target':hex(destination),'role':targets[destination]})
windows=[(0x17dc04,0x17dc34),(0x187c6c,0x187ce4),(0x187e34,0x187e48),(0x17e7cc,0x17e854),(0x199d0c,0x199d4c),(0x185b84,0x185ba0),(0x1accdc,0x1acd2c),(0x183db0,0x183e2c),(0x1f1a5c,0x1f1abc)]
work=ROOT/'work/qqmusic-stock-db-flow';work.mkdir(exist_ok=True)
disassembly='\n'.join(subprocess.run(['arm-linux-gnueabi-objdump','-d',f'--start-address={a}',f'--stop-address={b}',str(path)],capture_output=True,text=True,check=True).stdout for a,b in windows)
(work/'disassembly.txt').write_text(disassembly)
report={'scope':'static_path_initialization_override_and_sqlite_wrapper_flow','stock_executed':False,'device_accessed':False,'database_modified':False,
 'responder_sha256':digest,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'default_path_buffer':{'address':hex(setter_destination),'initialized_from':text(default_path),'initializer':'0x187c6c','copy_call':'0x187ce0'},
 'conditional_override':{'caller':'0x17dc04','config_getter':'0x17d690','selector_offset':'0x38','when_nonzero':'copy /db/MTPDB.dat into the same 4096-byte path buffer','setter':'0x187e34','zero_branch':'0x17dca4'},
 'separate_descriptor_initialization':{'caller':'0x17e7cc','first_word':text(override_path),'copier':'0x199d0c','destination':'0x6ca294','bytes':40},
 'sqlite_wrappers':{'A':{'entry':'0x185b84','filename_from':'incoming r1','open_call':'0x185b98'},'B':{'entry':'0x1accdc','filename_from':'incoming r1 saved as r5','open_call':'0x1acd24'}},
 'non_music_sqlite_example':{'caller':'0x183dd0','filename':other_database,'path_to_wrapper':['0x183cb4','0x185b84']},
 'direct_calls':calls,'disassembly':str((work/'disassembly.txt').relative_to(ROOT)),'disassembly_sha256':hashlib.sha256(disassembly.encode()).hexdigest(),
 'limits':['No runtime selector value or initialization order qualified.','The descriptor-to-actual-music-open connection and indirect calls remain unproven.','A user-volume default string is not proof that stock refresh writes only to user storage.','No SQLite database was opened; no scan/refresh API or physical storage policy enabled.']}
(ROOT/'sources/native-stock-music-database-path-flow.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('sqlite_wrappers','direct_calls')},indent=2))
