"""Pinned JP Responder DB paths and sqlite open callers; static, never run stock."""
from pathlib import Path
import hashlib,io,json,struct,subprocess,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];path=ROOT/'work/targets-jp/Responder';data=path.read_bytes()
assert hashlib.sha256(data).hexdigest()=='71f9869eeda472e508e74adea04c95155599585a4f7e7ef218bbff251b8af261'
archive=ROOT/'work/upg-jp/verified-3.bin';assert hashlib.sha256(archive.read_bytes()).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
elf=ELFFile(io.BytesIO(data));segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD'];symbols=elf.get_section_by_name('.dynsym')
sqlite=[s for s in symbols.iter_symbols() if s.name=='sqlite3_open'];assert len(sqlite)==1;sqlite_address=int(sqlite[0]['st_value'])
def at(address,count):
 for s in segments:
  if s['p_vaddr']<=address and address+count<=s['p_vaddr']+s['p_filesz']:
   offset=s['p_offset']+address-s['p_vaddr'];return data[offset:offset+count]
 return None
targets={}
for text in ['/db/MTPDB.dat','/contents/MTPDB.dat','/contents/SONYWM/PROP_REP','/contents/SONYWM/TEMPMETA']:
 needle=text.encode()+b'\0';start=0;found=[]
 while True:
  offset=data.find(needle,start)
  if offset<0:break
  for s in segments:
   if s['p_offset']<=offset<s['p_offset']+s['p_filesz']:found.append(int(s['p_vaddr']+offset-s['p_offset']));break
  start=offset+len(needle)
 assert found,text
 for address in found:targets[address]=text
references=[];calls=[]
def window(address):
 output=subprocess.run(['arm-linux-gnueabi-objdump','-d','--start-address='+str(address-64),'--stop-address='+str(address+100),str(path)],cwd=ROOT,capture_output=True,text=True,check=True).stdout
 return output.splitlines()[-44:]
for s in segments:
 if not s['p_flags']&1:continue
 raw=s.data();base=int(s['p_vaddr'])
 for offset in range(0,len(raw)-3,4):
  ins=struct.unpack_from('<I',raw,offset)[0];pc=base+offset
  if ins&0x0f7f0000==0x051f0000:
   pool=pc+8+(1 if ins&0x800000 else -1)*(ins&4095);word=at(pool,4)
   if word is not None and struct.unpack('<I',word)[0] in targets:
    target=struct.unpack('<I',word)[0];references.append({'path':targets[target],'address':hex(pc),'target':hex(target),'window':window(pc)})
  if ins&0x0f000000==0x0b000000:
   displacement=(ins&0xffffff)<<2
   if displacement&0x2000000:displacement-=0x4000000
   if (pc+8+displacement)&0xffffffff==sqlite_address:calls.append({'address':hex(pc),'window':window(pc)})
configs=[];db_entries=[]
with tarfile.open(archive,'r|gz') as tar:
 for entry in tar:
  name=entry.name.removeprefix('./')
  if name=='db' or name.startswith('db/'):
   row={'path':entry.name,'bytes':entry.size,'type':entry.type.decode('ascii'),'link':entry.linkname}
   if entry.isfile():
    raw=tar.extractfile(entry).read();row['sha256']=hashlib.sha256(raw).hexdigest();row['sqlite_header']=raw.startswith(b'SQLite format 3\0')
   db_entries.append(row)
  if entry.isfile() and (name=='etc/fstab' or name.startswith('etc/init.d/') or name=='usr/local/bin/sysmgr.sh') and entry.size<131072:
   raw=tar.extractfile(entry).read()
   lines=[line for line in raw.decode('utf-8','replace').splitlines() if any(p in line for p in ('/db','MTPDB','_DEV_DB=','ramfs','tmpfs'))]
   if lines:configs.append({'path':entry.name,'sha256':hashlib.sha256(raw).hexdigest(),'matching_lines':lines})
report={'scope':'static_responder_sqlite_path_and_boot_config_audit','device_access':False,'stock_program_executed':False,'responder_sha256':hashlib.sha256(data).hexdigest(),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'sqlite3_open_plt':hex(sqlite_address),'path_addresses':{hex(k):v for k,v in targets.items()},'literal_references':references,'sqlite_open_calls':calls,'archive_db_entries':db_entries,'boot_config_lines':configs,'limits':['Literal references and call windows do not prove which runtime path is selected or where every write goes.','No stock refresh API, physical mount or safe USB ownership inferred.','No database creation, edits, updater or device execution.']}
(ROOT/'sources/native-stock-music-database-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'path_references':len(references),'sqlite_open_calls':len(calls),'db_entries':db_entries,'boot_config_lines':configs},indent=2))
