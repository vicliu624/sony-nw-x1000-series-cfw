"""Analysis-only Met trampoline. No firmware package or device execution."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from build_player_host import ROOT,STOCK_SHA

def branch(source,target,link):
 delta=target-source-8
 if delta%4 or not -(1<<25)<=delta<(1<<25):raise ValueError('ARM branch out of range')
 return (0xeb000000 if link else 0xea000000)|((delta//4)&0xffffff)

def patch_met_anchor(raw):
 elf=ELFFile(io.BytesIO(raw));segments=list(elf.iter_segments())
 if elf.elfclass!=32 or not elf.little_endian or elf['e_machine']!='EM_ARM' or elf['e_type']!='ET_EXEC':raise ValueError('Expected ARM32 executable')
 symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
 if symbols.get('getpid')!=0xda84:raise ValueError('Unexpected original getpid PLT')
 loads=[(i,s) for i,s in enumerate(segments) if s['p_type']=='PT_LOAD']
 if len(loads)!=2:raise ValueError('Expected two original load segments')
 index,code=loads[0];_,data=loads[1]
 insert=int(code['p_offset']+code['p_filesz']);stub=int(code['p_vaddr']+code['p_filesz']);growth=0x8000
 if code['p_offset']!=0 or code['p_filesz']!=code['p_memsz'] or code['p_flags']!=5 or data['p_offset']!=insert or stub+16>data['p_vaddr']:raise ValueError('Unexpected load boundary')
 if any(s['p_align']>growth for s in segments):raise ValueError('Insertion would break alignment')
 def offset(address):
  return next(int(s['p_offset'])+address-int(s['p_vaddr']) for s in segments if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address< s['p_vaddr']+s['p_filesz'])
 at=offset(0x27c610)
 if struct.unpack_from('<II',raw,at)!=(0xebfffdac,0xe3a03f41):raise ValueError('Unexpected Met maintenance callsite')
 if elf['e_phoff']+elf['e_phnum']*elf['e_phentsize']>insert or elf['e_shentsize']!=40 or elf['e_phentsize']!=32:raise ValueError('Unexpected ELF tables')
 # Save all incoming argument/scratch registers and LR around the optional
 # argument-free PID anchor; tail-call the original session maintenance.
 trampoline=struct.pack('<4I',0xe92d500f,branch(stub+4,0xda84,True),0xe8bd500f,branch(stub+12,0x27bcc8,False))
 result=bytearray(raw[:insert]+trampoline+bytes(growth-len(trampoline))+raw[insert:])
 struct.pack_into('<I',result,at,branch(0x27c610,stub,True))
 for i,s in enumerate(segments):
  h=int(elf['e_phoff'])+i*32
  if i==index:struct.pack_into('<II',result,h+16,int(s['p_filesz'])+16,int(s['p_memsz'])+16)
  elif s['p_offset']>=insert:struct.pack_into('<I',result,h+4,int(s['p_offset'])+growth)
 old_sh=int(elf['e_shoff']);new_sh=old_sh+growth if old_sh>=insert else old_sh
 struct.pack_into('<I',result,32,new_sh)
 for i,section in enumerate(elf.iter_sections()):
  if section['sh_offset']>=insert:struct.pack_into('<I',result,new_sh+i*40+16,int(section['sh_offset'])+growth)
 check=ELFFile(io.BytesIO(result))
 for old,new in zip(segments,check.iter_segments()):
  assert old['p_vaddr']==new['p_vaddr'] and old['p_flags']==new['p_flags']
  if old['p_type']=='PT_LOAD' and old is not code:assert old.data()==new.data()
 assert check['e_entry']==elf['e_entry'] and check['e_phoff']==elf['e_phoff'] and check['e_phnum']==elf['e_phnum']
 return bytes(result),dict(callsite=hex(0x27c610),stub=hex(stub),stub_return=hex(stub+8),original_target=hex(0x27bcc8),growth_bytes=growth,added_executable_bytes=16,original_virtual_addresses_preserved=True)

def build():
 raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes()
 if hashlib.sha256(raw).hexdigest()!=STOCK_SHA:raise ValueError('Pinned original Japanese image required')
 result,edit=patch_met_anchor(raw);w=ROOT/'work/player-met-anchor';w.mkdir(exist_ok=True)
 (w/'SpiderApp.met-anchor.analysis-only.elf').write_bytes(result)
 report=dict(analysis_only=True,ready_to_flash=False,device_accessed=False,firmware_package_created=False,edit=edit,stock_sha256=STOCK_SHA,candidate_sha256=hashlib.sha256(result).hexdigest(),limits=['No DSO callback dispatch or altered-image compatibility profile is enabled.','ELF mapping and trampoline fixtures do not qualify original loader boot, sleep, audio or physical runtime.'])
 (w/'build.json').write_text(json.dumps(report,indent=2)+'\n');return result,report
if __name__=='__main__':print(json.dumps(build()[1],indent=2))
