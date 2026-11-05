"""Local diagnostic capsules at current Home boundaries; no observer/deployment/UPG."""
import argparse,io,json,struct,subprocess,time
from elftools.elf.elffile import ELFFile
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
from app_registry import ROOT
from review_managed_remote_profile import receipt,digest
from native_settings_count import offset
from build_player_met_anchor import branch

def compose(host_review):
 rp,host=receipt(host_review);source=rp.parent/'SpiderApp.player-prepare.analysis-only.elf'
 assert digest(source)==host['candidate_sha256'];raw=source.read_bytes()
 out=ROOT/'work/parent-entry-trace'/str(time.time_ns());out.mkdir(parents=True)
 start=0x4d8e00
 ld=out/'trace.ld';ld.write_text('SECTIONS { . = 0x4d8e00; .text : { *(.text*) *(.rodata*) } /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }\nparent_trace_getpid = 0xda84; parent_trace_original_switch = 0x2681e8;\nASSERT(. < 0x4d9400,"Trace capsule slot exceeded")\n')
 asm='runtime/platform/player/parent_entry_trace.S';elfpath=out/'trace.elf';binary=out/'trace.bin'
 subprocess.run(['arm-linux-gnueabi-gcc','-march=armv5te','-marm','-nostdlib','-static','-Wl,--build-id=none,-e,parent_trace_launch,-T,'+str(ld),asm,'-o',str(elfpath)],cwd=ROOT,check=True)
 subprocess.run(['arm-linux-gnueabi-objcopy','-O','binary',str(elfpath),str(binary)],check=True)
 elf=ELFFile(io.BytesIO(elfpath.read_bytes()));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()};code=binary.read_bytes()
 at=offset(raw,start,len(code));assert raw[at:at+len(code)]==bytes(len(code))
 aliases=[]
 for s in ELFFile(io.BytesIO(raw)).iter_segments():
  if s['p_type']!='PT_LOAD':continue
  low,high=max(at,s['p_offset']),min(at+len(code),s['p_offset']+s['p_filesz'])
  if low<high:aliases.append((s['p_vaddr']+low-s['p_offset'],s['p_flags']))
 assert aliases==[(start,5)], 'Diagnostic slot must be uniquely mapped read/execute, never writable'
 selection=struct.unpack_from('<I',raw,offset(raw,0x737ec,4))[0];assert selection>>24==0xea
 displacement=selection&0xffffff
 if displacement&0x800000:displacement-=0x1000000
 select_start=0x737ec+8+displacement*4;launches=[]
 for address in range(select_start,select_start+96,4):
  word,next_word=struct.unpack_from('<2I',raw,offset(raw,address,8))
  if word==0xe3a00004 and next_word&0xfffff000==0xe59ff000:
   literal=address+12+(next_word&0xfff)
   if struct.unpack_from('<I',raw,offset(raw,literal,4))[0]==0xb0464:launches.append(address)
 assert len(launches)==1
 edits=[];result=bytearray(raw);result[at:at+len(code)]=code
 for address,expected,name,link in ((launches[0],0xe3a00004,'parent_trace_launch',False),(0xb04f8,0xe1a00006,'parent_trace_lookup',False),(0xb0504,0xe3500000,'parent_trace_lookup_return',False),(0xb0554,branch(0xb0554,0x2681e8,True),'parent_trace_switch',True)):
  location=offset(raw,address,4);assert struct.unpack_from('<I',raw,location)[0]==expected
  replacement=branch(address,symbols[name],link);struct.pack_into('<I',result,location,replacement)
  edits.append(dict(address=address,before=expected,after=replacement,target=symbols[name]))
 restored=bytearray(result);restored[at:at+len(code)]=bytes(len(code))
 for edit in edits:struct.pack_into('<I',restored,offset(raw,edit['address'],4),edit['before'])
 assert bytes(restored)==raw
 callers=[i.address+4 for i in Cs(CS_ARCH_ARM,CS_MODE_ARM).disasm(code,start) if i.mnemonic=='bl' and i.op_str=='#0xda84'];assert len(callers)==5
 artifact=out/'SpiderApp.parent-entry-trace.analysis-only.elf';artifact.write_bytes(result)
 report=dict(prepared=True,analysis_only=True,artifact=artifact.relative_to(ROOT).as_posix(),sha256=digest(artifact),base_artifact=source.relative_to(ROOT).as_posix(),base_sha256=digest(source),slot=start,code_bytes=len(code),elf_growth_bytes=0,observer_callers=callers,edits=edits,symbols={k:v for k,v in symbols.items() if k.startswith('parent_trace_')},observer_backend_implemented=False,storage_writes_implemented=False,firmware_created=False,device_accessed=False,ready_to_run_on_device=False,source_hashes={p:digest(ROOT/p) for p in [asm,'tools/compose_parent_entry_trace.py','tools/native_settings_count.py','tools/build_player_met_anchor.py']},limits=['Local capsules only; ordinary getpid without a paired observer captures nothing.','No device execution, complete GUI/manager or hardware qualification.'])
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return out,report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host-review',required=True);a=p.parse_args();out,r=compose(a.host_review);print(json.dumps(r,indent=2))
