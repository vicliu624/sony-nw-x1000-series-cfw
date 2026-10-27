"""Static register/argument chain for a separate internal database open.

Does not run Responder, SQLite or any hardware. Arguments alone do not prove
the final VFS destinations, actual writes or use by the stock music scanner.
"""
from pathlib import Path
import hashlib,io,json,struct,subprocess
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'work/targets-jp/Responder';raw=path.read_bytes()
digest=hashlib.sha256(raw).hexdigest();assert digest=='71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261'
segments=[s for s in ELFFile(io.BytesIO(raw)).iter_segments() if s['p_type']=='PT_LOAD']
def at(address,size):
 for segment in segments:
  if segment['p_vaddr']<=address and address+size<=segment['p_vaddr']+segment['p_filesz']:
   start=segment['p_offset']+address-segment['p_vaddr'];return raw[start:start+size]
 raise ValueError('Address outside file-backed segment')
def word(address):return struct.unpack('<I',at(address,4))[0]
def cstring(address):return at(address,96).split(b'\0',1)[0].decode('ascii')
def branch(address,destination):
 ins=word(address);assert ins&0x0f000000==0x0b000000
 delta=(ins&0xffffff)<<2
 if delta&0x2000000:delta-=0x4000000
 assert (address+8+delta)&0xffffffff==destination
branch(0x1334c,0x17f764);branch(0x17f7b4,0x1af788);branch(0x17f7c8,0x1b6dec)
assert cstring(word(0x17f8e4))=='/db/MTPDB.dat'
assert cstring(word(0x17f8e8))=='/contents'
assert word(0x1af78c)==0xe5801000 and word(0x1af790)==0xe5802004
assert word(0x1af7b0)==0xe5801008 and word(0x1af7c0)==0xe5801010
branch(0x1b6e2c,0x1acfe8);assert word(0x1acff0)==0xe1a02003
branch(0x1acffc,0x1aff38);assert word(0x1aff3c)==0xe1a06002
assert word(0x1affa4)==0xe5961000
branch(0x1affbc,0x1accdc);assert word(0x1acce4)==0xe1a05001 and word(0x1acd14)==0xe1a00005
branch(0x1acd24,0xb8c4)
assert word(0x17f7e8)==0xe5903038
windows=[(0x13320,0x13364),(0x17f764,0x17f814),(0x1af788,0x1af7cc),(0x1b6dec,0x1b6e74),
 (0x1acfe8,0x1ad008),(0x1aff38,0x1affc8),(0x1accdc,0x1acd2c)]
work=ROOT/'work/qqmusic-stock-db-flow';work.mkdir(exist_ok=True)
disassembly='\n'.join(subprocess.run(['arm-linux-gnueabi-objdump','-d',f'--start-address={a}',f'--stop-address={b}',str(path)],capture_output=True,text=True,check=True).stdout for a,b in windows)
output=work/'internal-open-disassembly.txt';output.write_text(disassembly)
report={'scope':'separate local open descriptor to sqlite filename argument','stock_process_started':False,'device_accessed':False,'sqlite_opened':False,
 'responder_sha256':digest,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'caller':'0x1334c','routine':'0x17f764','descriptor':{'kind':'local open descriptor with six initialized words, not the earlier 40-byte global configuration','constructor':'0x1af788','first_field':'/db/MTPDB.dat','second_field':'/contents','other_fields':'callback/context slots initialized to zero; helpers fill offsets 8/12 and 16/20'},
 'argument_chain':[
  {'call':'0x17f7c8','callee':'0x1b6dec','value':'r3 points to local open descriptor'},
  {'call':'0x1b6e2c','callee':'0x1acfe8','value':'descriptor passed in r3 after default callbacks are installed'},
  {'call':'0x1acffc','callee':'0x1aff38','value':'incoming r3 moved into r2'},
  {'call':'0x1affbc','callee':'0x1accdc','value':'r1 loaded from descriptor first field'},
  {'call':'0x1acd24','callee':'sqlite3_open@plt 0xb8c4','value':'r0 is the incoming filename saved in r5'}],
 'selector_order':{'open_dispatch':'0x17f7c8','later_selector_load':'0x17f7e8','meaning':'this dispatch precedes the later +0x38 check in this routine'},
 'auxiliary_path':{'field':'second field /contents','consumer':'0x1b5e40 from 0x1aff78','meaning':'separate auxiliary argument, not the filename loaded at 0x1affa4'},
 'disassembly':str(output.relative_to(ROOT)),'disassembly_sha256':hashlib.sha256(disassembly.encode()).hexdigest(),
 'limits':['Register-flow connection is conditional on preceding allocation/auxiliary calls succeeding; no complete runtime executed.',
 'Physical SQLite VFS destinations and actual writes are not proven by the filename argument.',
 'The trigger and relationship to normal stock music scanning/QQ imports remain unqualified.',
 'This local open descriptor is distinct from the global 40-byte configuration; that entire consumer graph remains incomplete.',
 'No refresh API or installation policy was enabled.']}
(ROOT/'sources/native-stock-internal-db-open.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('argument_chain','limits')},indent=2))
