"""Data-only JP Settings descriptor edit; never generates or installs firmware."""
import hashlib,io,json,struct
from pathlib import Path
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from build_player_met_anchor import branch

TABLE=0x4e692c
JP_SETTINGS=0x61
RECORD_BYTES=132
FIELDS=(21,32)

def offset(raw,address,size):
 segments=[s for s in ELFFile(io.BytesIO(raw)).iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+size<=s['p_vaddr']+s['p_filesz']]
 if len(segments)!=1:raise ValueError('Descriptor span needs one mapping')
 s=segments[0];return int(s['p_offset']+address-s['p_vaddr'])

def compose(raw,out):
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 # Refuse the superseded media-list prototype rather than silently stacking it.
 for site,target in ((0x590a0,0x12ae8),(0x5b948,0x12ae8),(0xa8b90,0x12ae8),(0x5af4c,0x12c64)):
  if struct.unpack_from('<I',raw,offset(raw,site,4))[0]!=branch(site,target,True):raise ValueError('Superseded media-list hook or unexpected call present')
 if raw[offset(raw,0x4d8e00,256):offset(raw,0x4d8e00,256)+256]!=bytes(256):raise ValueError('Superseded counter slot is not empty')
 if struct.unpack_from('<I',raw,offset(raw,0x73954,4))[0]!=0xe3a02061:raise ValueError('Original Settings request changed')
 rows=[struct.unpack_from('<5I',raw,offset(raw,0x3f611c+i*20,20)) for i in range(95)]
 row=next(row for row in rows if row[0]==2);count=row[2]
 if count not in (11,12):raise ValueError('Completed native-language list required')
 record=struct.unpack_from('<33I',raw,offset(raw,TABLE+JP_SETTINGS*RECORD_BYTES,RECORD_BYTES))
 if (record[21],record[22],record[26],record[32])!=(10,49,5000,10):raise ValueError('Pinned JP Settings display descriptor mismatch')
 result=bytearray(raw);edits=[]
 for field in FIELDS:
  address=TABLE+JP_SETTINGS*RECORD_BYTES+field*4;at=offset(raw,address,4)
  struct.pack_into('<I',result,at,count);edits.append(dict(address=address,before=10,after=count,field=field))
 report=dict(kind='native-settings-descriptor-count',descriptor=JP_SETTINGS,resource_id=5000,
  target_count=count,capacity_preserved=49,code_bytes=0,rewritten_data_bytes=8,differing_bytes=sum(a!=b for a,b in zip(raw,result)),elf_growth_bytes=0,edits=edits,
  media_list_hooks_present=False,base_sha256=hashlib.sha256(raw).hexdigest(),candidate_sha256=hashlib.sha256(result).hexdigest(),
  source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('tools/native_settings_count.py','tools/build_player_met_anchor.py')})
 assert revert(bytes(result),report)==raw
 (out/'composition.json').write_text(json.dumps(report,indent=2)+'\n')
 return bytes(result),report

def revert(raw,report):
 if report.get('kind')!='native-settings-descriptor-count' or hashlib.sha256(raw).hexdigest()!=report['candidate_sha256']:raise ValueError('Settings descriptor candidate mismatch')
 restored=bytearray(raw)
 for edit in report['edits']:
  at=offset(raw,edit['address'],4)
  if struct.unpack_from('<I',raw,at)[0]!=edit['after']:raise ValueError('Settings descriptor edit changed')
  struct.pack_into('<I',restored,at,edit['before'])
 if hashlib.sha256(restored).hexdigest()!=report['base_sha256']:raise ValueError('Undeclared descriptor edit')
 return bytes(restored)
