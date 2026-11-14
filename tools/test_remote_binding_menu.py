"""Exact native word bridge, bound cache, confirmation and fault-page ARM checks."""
import argparse,hashlib,io,json,re,struct,subprocess,tempfile,time
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
from review_managed_remote_profile import receipt,digest
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host-review',required=True);args=p.parse_args()
hp,review=receipt(args.host_review);library=hp.parent/'libx1000-player-analysis.so';assert digest(library)==review['library_sha256']
elf=ELFFile(io.BytesIO(library.read_bytes()));syms={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s['st_info']['type']!='STT_FILE'}
origin=''
for s in elf.get_section_by_name('.symtab').iter_symbols():
 if s['st_info']['type']=='STT_FILE':origin=s.name
 elif (origin=='remote_auto.c' and s.name=='factory') or (origin=='remote_page_adapter.c' and s.name in ('page','view')):syms[s.name]=s['st_value']
page_review=json.loads((hp.parent/'remote-page/report.json').read_text());native=ROOT/page_review['artifact'];assert digest(native)==page_review['sha256'];main=ELFFile(io.BytesIO(native.read_bytes()))
dis=subprocess.check_output(['arm-linux-gnueabi-objdump','-d',str(library)],text=True);plt={name:int(at,16) for at,name in re.findall(r'^([0-9a-f]+) <(\w+)@plt>:',dis,re.M)}
fields={
 'fi':('wr_settings_factory','initialized'),'fo':('wr_settings_factory','owner_pid'),'fs':('wr_settings_factory','shared_wifi'),'ff':('wr_settings_factory','fault_latched'),
 'fk':('wr_settings_factory','pairing_store_known'),'fr':('wr_settings_factory','pairing_store_result'),'fq':('wr_settings_factory','pairing_store_request'),'fm':('wr_settings_factory','paired_peer'),
 'bo':('wr_settings_factory','backend.owner'),'bg':('wr_settings_factory','backend.generation'),'bp':('wr_settings_factory','backend.phase'),'bc':('wr_settings_factory','backend.process.child'),
 'pb':('wr_native_page_bridge','backend'),'po':('wr_native_page_bridge','owner'),'pg':('wr_native_page_bridge','generation'),'pop':('wr_native_page_bridge','open'),'pp':('wr_native_page_bridge','preview'),
 'pc':('wr_native_page_bridge','view_context'),'pbegin':('wr_native_page_bridge','view_begin'),'pend':('wr_native_page_bridge','view_end'),
 'vh':('wr_native_choice_view','held'),'vc':('wr_native_choice_view','closing'),'vo':('wr_native_choice_view','owner'),'vs':('wr_native_choice_view','borrowed_sid')}
with tempfile.TemporaryDirectory(dir=ROOT/'work',prefix='binding-layout-') as d:
 c=ROOT/d/'layout.c';o=c.with_suffix('.o');c.write_text(
     ('#define WR_PAIRING_TRACE\n' if 'wr_start_failure_capture' in syms else '') +
     '#define WR_PAIRING_PROCESS\n#include <stddef.h>\n#include "runtime/apps/wireless-remote/settings_factory.h"\n'
     '#include "runtime/apps/wireless-remote/native_page_bridge.h"\n#include "runtime/platform/sony-settings/native_choice_view.h"\n'
     +''.join(f'char {n}[offsetof(struct {s},{f})+1];\n' for n,(s,f) in fields.items()))
 subprocess.run(['arm-linux-gnueabi-gcc','-c','-I',str(ROOT),str(c),'-o',str(o)],check=True)
 off={s.name:s['st_size']-1 for s in ELFFile(io.BytesIO(o.read_bytes())).get_section_by_name('.symtab').iter_symbols() if s.name in fields}
rows=[]
for case in ('bound','native-list-render','absent','pending','lookup-error','lookup-uncertain','fault-bound','wrong-row','foreign-sid','closing','passive-read','fault-passive-read','delete-no','delete-yes','delete-completed'):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);base=0x50000000;area=0x70000000;stop=area+0xff00;u.mem_map(0x8000,0x1000000);u.mem_map(base,0x400000);u.mem_map(area,0x10000)
 for image,reloc in ((main,0),(elf,base)):
  for seg in image.iter_segments():
   if seg['p_type']=='PT_LOAD':u.mem_write(reloc+seg['p_vaddr'],seg.data())
 for section in elf.iter_sections():
  if section['sh_type']=='SHT_REL':
   for r in section.iter_relocations():
    if r['r_info_type']==23:
     at=base+r['r_offset'];v=struct.unpack('<I',u.mem_read(at,4))[0];u.mem_write(at,struct.pack('<I',base+v))
 put=lambda a,v:u.mem_write(a,struct.pack('<I',v&0xffffffff));get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
 f=base+syms['factory'];page=base+syms['page'];view=base+syms['view'];peer=bytes.fromhex('021122334455');posts=[];deletes=[];requests=[];rendered=[]
 def setf(n,v):put(f+off[n],v)
 for n,v in (('fi',1),('fo',1234),('fs',1),('fk',case!='pending'),('fr',1 if case in ('absent','delete-completed') else 2 if case=='lookup-error' else 3 if case=='lookup-uncertain' else 0),('bo',17),('bp',5 if case.startswith('fault-') else 1)):
  setf(n,v)
 if case.startswith('fault-'):setf('ff',1)
 u.mem_write(f+off['fm'],peer)
 u.mem_write(f+off['bg'],struct.pack('<Q',41))
 for n,v in (('pb',f),('po',17),('pop',1),('pp',2),('pc',view),('pbegin',base+syms['begin_view']),('pend',base+syms['end_view'])):put(page+off[n],v)
 u.mem_write(page+off['pg'],struct.pack('<Q',41))
 for n,v in (('vh',1),('vc',case=='closing'),('vo',17),('vs',13901)):put(view+off[n],v)
 for n,v in (('host_ready',1),('host_busy',0),('host_owner',17)):put(base+syms[n],v)
 u.mem_write(0x683400,bytes((194,2)));sid=0x4eb99c+43*48+4;put(sid,14400)
 original=area+0x600;u.mem_write(original,'Start pairing\0'.encode('utf-16le'))
 models={base+syms['xw_player_host_original_exiting']:0,base+syms['xw_player_host_wireless_player_active']:1,
  base+syms['xw_player_remote_page_image_valid']:1,base+syms['xw_player_remote_view_image_valid']:1,base+syms['wr_view_confirm_resource_ready']:1,
  base+syms['wr_view_menu_context']:0x683400}
 def hook(cpu,pc,size,unused):
  if pc==stop:cpu.emu_stop();return
  a=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
  def finish(v=0):cpu.reg_write(UC_ARM_REG_R0,v&0xffffffff);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
  if pc==0xda84:requests.append(a[:2]);cpu.reg_write(UC_ARM_REG_PC,base+syms['getpid']);return
  if pc==base+syms['xw_host_getpid_oabi']:finish(1234);return
  if pc==base+plt['pthread_self']:finish(17);return
  if pc==base+plt['getpid']:finish(1234);return
  if pc==base+plt['__errno_location']:finish(area+0x300);return
  if pc==base+plt['memcpy']:cpu.mem_write(a[0],bytes(cpu.mem_read(a[1],a[2])));finish(a[0]);return
  if pc==base+plt['memcmp']:
   left,right=bytes(cpu.mem_read(a[0],a[2])),bytes(cpu.mem_read(a[1],a[2]));finish((left>right)-(left<right));return
  if pc==base+plt['memset']:cpu.mem_write(a[0],bytes([a[1]&255])*a[2]);finish(a[0]);return
  if pc in models:finish(models[pc]);return
  if pc==0xec244:
   cpu.mem_write(a[0]+24,b'/usr/local/share/gemini/res/swd/ucs2-dev-sid-139-01.swd\0');finish(a[0]+24);return
  if pc==0xec340:finish();return
  if pc==0xf3694:rendered.append(a[1]);finish();return
  if pc==0xc6598:
   sp=cpu.reg_read(UC_ARM_REG_SP);values=struct.unpack('<4I',cpu.mem_read(sp+752,16))
   for reg,v in zip((UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6),values):cpu.reg_write(reg,v)
   cpu.reg_write(UC_ARM_REG_SP,sp+768);cpu.reg_write(UC_ARM_REG_PC,values[3]);return
  if pc==0xec51c:
   sp=cpu.reg_read(UC_ARM_REG_SP);values=struct.unpack('<5I',cpu.mem_read(sp,20))
   for reg,v in zip((UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7),values):cpu.reg_write(reg,v)
   cpu.reg_write(UC_ARM_REG_SP,sp+20);cpu.reg_write(UC_ARM_REG_R0,original);cpu.reg_write(UC_ARM_REG_PC,values[4]);return
  if pc==base+syms['xw_player_host_remote_pairing_forget']:
   assert bytes(cpu.mem_read(a[0],6))==peer
   if a[1]:deletes.append(True)
   finish(1 if a[1] else 0);return
  if pc==base+syms['hb_monotonic_millis']:cpu.mem_write(a[0],struct.pack('<Q',1000));finish();return
  if pc==0xa57f0:posts.append(a);finish(1);return
  if pc==base+syms['wr_native_choice_view_observe']:finish(-4);return
 u.hook_add(UC_HOOK_CODE,hook)
 def call(address,*args):
  for reg,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),list(args)+[0]*4):u.reg_write(reg,v)
  u.reg_write(UC_ARM_REG_SP,area+0xf000);u.reg_write(UC_ARM_REG_LR,stop);u.emu_start(address,stop+4,count=1000000)
  assert u.reg_read(UC_ARM_REG_PC)==stop and u.reg_read(UC_ARM_REG_SP)==area+0xf000
  return u.reg_read(UC_ARM_REG_R0)
 def text(pointer):
  raw=bytearray()
  for i in range(64):
   c=bytes(u.mem_read(pointer+i*2,2))
   if c==b'\0\0':return raw.decode('utf-16le')
   raw.extend(c)
  raise AssertionError('Unterminated label')
 if case.endswith('passive-read'):
  assert call(base+syms['xw_player_host_remote_binding_refresh'])==1 and get(f+off['fq'])==1 and not get(f+off['bc']);assert not requests and not deletes
 else:
  resource=area+0x1000
  resource_path='/usr/local/share/gemini/res/swd/ucs2-dev-sid-139-'+('00' if case=='foreign-sid' else '01')+'.swd'
  u.mem_write(resource+24,resource_path.encode()+b'\0')
  # The original choice-list renderer calls ec518 directly, bypassing the
  # dialog-only 10a544 convenience function. Exercise the actual shared entry.
  if case=='native-list-render':
   widget,descriptor=area+0x3000,area+0x3500;put(widget+24,0x1234);put(descriptor+20,13901);put(descriptor+24,2)
   call(0xc6538,widget,descriptor);assert len(rendered)==1;label=rendered[0]
  else:label=call(0xec518,resource,0 if case=='wrong-row' else 2)
  expected='Start pairing' if case in ('absent','delete-completed','wrong-row','foreign-sid','closing') else '...' if case=='pending' else '--' if case.startswith('lookup-') else '02:11:22:33:44:55'
  assert text(label)==expected,(case,text(label),expected,requests)
  if case in ('wrong-row','foreign-sid'):assert not requests
  if case.startswith('delete-') and case!='delete-completed':
   result=call(base+syms['xw_player_host_remote_page_request'],4,0);assert result==0x575a0000 and get(sid)==13903 and not deletes
   u.mem_write(0x683400,bytes((194,3)))
   result=call(base+syms['xw_player_host_remote_page_request'],11,1 if case=='delete-yes' else 2)
   assert result==(0x57520001 if case=='delete-yes' else 0x57520000) and bool(deletes)==(case=='delete-yes') and get(sid)==14400
  if case=='bound':assert call(base+syms['xw_player_host_remote_pairing_progress'])==24
 rows.append(dict(case=case,native_word_bridge=True,destructive_requests=len(deletes)))
folder=ROOT/'work/remote-binding-menu-tests'/str(time.time_ns());folder.mkdir(parents=True)
report=dict(passed=True,device_accessed=False,cases=rows,library_sha256=digest(library),native_elf_sha256=digest(native),
 source_hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in ['tools/test_remote_binding_menu.py','runtime/platform/player/remote_page_adapter.c','runtime/platform/player/remote_auto.c','runtime/platform/sony-settings/native_page_entry.c']},
 limits=['Original renderer c6538, patched shared word entry, native PID bridge, C adapter, real cache lookup and confirmation logic execute.','Source ownership, resource loading, stock wording fallback, font submission and destructive store request effects are fixtures; no device writes or RF actions.'])
(folder/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
