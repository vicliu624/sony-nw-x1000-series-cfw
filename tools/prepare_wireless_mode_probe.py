"""Prepare display-only native three-choice ELF/resources; no UPG or device."""
import contextlib,hashlib,io,json,re,struct,subprocess,tarfile,time
from app_registry import ROOT
from build_home_feedback import build
from builtin_language import enable_settings,SETTINGS_SHA
from release_firmware import complete_wordings
from resources import append_stx
from wireless_resources import compose as compose_wireless_resources
from wireless_init_bridge import patch_choice_descriptor
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
out=ROOT/'work/wireless-mode-probe'/str(time.time_ns());out.mkdir(parents=True)
with contextlib.redirect_stdout(io.StringIO()):home,symbols,home_report=build(out/'home')
def offset(raw,address,count):
 rows=[s for s in ELFFile(io.BytesIO(raw)).iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+count<=s['p_vaddr']+s['p_filesz']]
 assert len(rows)==1;s=rows[0];return int(s['p_offset']+address-s['p_vaddr'])
data=bytearray(home);at=offset(home,symbols['hb_error_descriptor'],48)
struct.pack_into('<I',data,at+4,99999);struct.pack_into('<I',data,at+20,0)
base=enable_settings(bytes(data));assert hashlib.sha256(base).hexdigest()==SETTINGS_SHA
source='runtime/platform/wireless/native_mode_probe.c';helper=out/'probe.elf';binary=out/'probe.bin';linker=out/'probe.ld'
linker.write_text('''ENTRY(xw_wireless_mode_probe_init)
SECTIONS {
 . = 0x4d8100;
 .text : { *(.text*) *(.rodata*) }
 .data : { *(.data*) }
 .bss : { *(.bss*) *(COMMON) }
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }
}
ASSERT(SIZEOF(.data) == 0, "No data")
ASSERT(SIZEOF(.bss) == 0, "No BSS")
ASSERT(. < 0x4d8400, "Probe exceeds reviewed slot")
xw_probe_ui_root = 0x2a984;
xw_probe_param_get = 0x10a118;
xw_probe_param_set = 0x10a0d4;
xw_probe_stock_init = 0x88400;
xw_probe_stock_confirm = 0x88494;
''',encoding='utf-8')
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-ffreestanding','-nostdlib','-no-pie','-Wl,--build-id=none,-T,'+str(linker),source,'-o',str(helper)],cwd=ROOT,check=True)
subprocess.run(['arm-linux-gnueabi-objcopy','-O','binary',str(helper),str(binary)],check=True)
compiled=ELFFile(io.BytesIO(helper.read_bytes()));names={s.name:s['st_value'] for s in compiled.get_section_by_name('.symtab').iter_symbols()}
code=binary.read_bytes();slot=offset(base,0x4d8100,len(code));assert base[slot:slot+len(code)]==bytes(len(code))
aliases=[]
for s in ELFFile(io.BytesIO(base)).iter_segments():
 if s['p_type']!='PT_LOAD':continue
 lo=max(slot,s['p_offset']);hi=min(slot+len(code),s['p_offset']+s['p_filesz'])
 if lo<hi:aliases.append((s['p_vaddr']+lo-s['p_offset'],s['p_flags']))
assert aliases==[(0x4d8100,5)]
patched=bytearray(base);patched[slot:slot+len(code)]=code;edits=[]
for address,expected,name in ((0x405304,0x88400,'xw_wireless_mode_probe_init'),(0x405438,0x88494,'xw_wireless_mode_probe_confirm')):
 at=offset(base,address,4);assert struct.unpack_from('<I',base,at)[0]==expected
 struct.pack_into('<I',patched,at,names[name]);edits.append(dict(address=hex(address),before=hex(expected),after=hex(names[name])))
edits+=[dict(edit,address=hex(edit['address'])) for edit in patch_choice_descriptor(base,patched)]
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
for s in ELFFile(io.BytesIO(base)).iter_segments():
 if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],bytes(patched[s['p_offset']:s['p_offset']+s['p_filesz']]))
u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x20000);stored=0;writes=[];events=[]
root=0x60001000;view=0x60008000
def hook(uc,pc,size,unused):
 if pc==0x2a984:answer=root
 elif pc==0x37f5c:
  assert uc.reg_read(UC_ARM_REG_R0)==6 and uc.reg_read(UC_ARM_REG_R1)==0x600
  uc.mem_write(uc.reg_read(UC_ARM_REG_R2),bytes([stored]));answer=0
 elif pc==0x38a18:writes.append(uc.reg_read(UC_ARM_REG_R2));answer=0
 elif pc in (0xda9c,0xd4fc,0xb3300):raise AssertionError('Display-only probe reached network/power API')
 elif pc==0xa57f0:events.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]);answer=0
 elif pc==0x7461c:answer=0x5a
 elif pc==0x74608:answer=17
 elif pc==0x74668:answer=0
 else:return
 uc.reg_write(UC_ARM_REG_R0,answer);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def call(address,event=0):
 for r,v in ((UC_ARM_REG_R0,0),(UC_ARM_REG_R1,0),(UC_ARM_REG_R2,event),(UC_ARM_REG_SP,0x6001f000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(r,v)
 u.emu_start(address,0x50000000,count=30000);assert u.reg_read(UC_ARM_REG_PC)==0x50000000
 return u.reg_read(UC_ARM_REG_R0)
cases=0
for stored in (0,1):
 for count in (0,1,2,3,4):
  for present in (False,True):
   original=[0x9000+i for i in range(15)];original[13]=count
   u.mem_write(view+0x18,struct.pack('<15I',*original));u.mem_write(root+0x2b18+0x1d*8,struct.pack('<I',view if present else 0))
   events.clear();writes.clear();call(names['xw_wireless_mode_probe_init'])
   expected=original[:]
   if present and count in (2,3):expected[13]=3
   assert struct.unpack('<15I',u.mem_read(view+0x18,60))==tuple(expected) and not writes
   assert events==[[0x20106,0,0x1d,stored]];cases+=1
for selection in (0,1,2):
 for event in (0xff0000,0xff0001):
  u.mem_write(0x4ee5d8,struct.pack('<I',selection));writes.clear();events.clear()
  assert call(names['xw_wireless_mode_probe_confirm'],event)==0x5a01 and not writes and not events;cases+=1
restored=bytearray(patched);restored[slot:slot+len(code)]=base[slot:slot+len(code)]
for edit in edits:
 at=offset(base,int(edit['address'],16),4);restored[at:at+4]=base[at:at+4]
assert bytes(restored)==base and len(patched)==len(base)
artifact=out/'SpiderApp.wireless-mode-display-probe.elf';artifact.write_bytes(patched)
rootfs=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(rootfs).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(rootfs),mode='r:gz') as archive:
 wordings={}
 prefix='usr/local/share/gemini/res/stx/'
 for m in archive:
  if m.isfile() and m.name.startswith('./'+prefix) and m.name.endswith('.stx'):
   data,tid=append_stx(archive.extractfile(m).read(),'Homebrew');assert tid==7308
   data,tid=append_stx(data,'Homebrew unavailable.\nCheck HOMEBREW.');assert tid==7309
   wordings[m.name.rsplit('-',1)[1][:-4]]=data
 complete_wordings(wordings);resources={}
 parent_name='usr/local/share/gemini/res/swd/ucs2-dev-sid-100-00.swd'
 choice_name='usr/local/share/gemini/res/swd/ucs2-dev-sid-139-00.swd'
 wordings,parent_swd,choice_swd,resource_ids=compose_wireless_resources(wordings,archive.extractfile('./'+parent_name).read(),archive.extractfile('./'+choice_name).read())
 assert resource_ids==dict(wifi=7310,espnow=7311,mode_title=7312)
 for language,data in wordings.items():
  name=prefix+'ucs2-dev-'+language+'.stx';target=out/'root-overlay'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
  resources[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
 for path,swd in ((parent_name,parent_swd),(choice_name,choice_swd)):
  target=out/'root-overlay'/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(swd);resources[path]=dict(bytes=len(swd),sha256=hashlib.sha256(swd).hexdigest())
report=dict(prepared=True,display_only=True,device_accessed=False,firmware_created=False,ready_to_flash=False,
            artifact=artifact.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(patched).hexdigest(),
            code_bytes=len(code),elf_growth_bytes=0,arm_cases=cases,edits=edits,resources=resources,
            standalone_base_sha256=SETTINGS_SHA,resource_ids=dict(wifi=7310,espnow=7311,mode_title=7312),
            composable_with_remote_row_overlay=False,
            persistence_writes=0,network_or_power_calls=0,stock_parameter_get_set_executed=True,
            source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [source,'tools/prepare_wireless_mode_probe.py','tools/builtin_language.py','tools/release_firmware.py','scripts/resources.py','scripts/wording.py',*[p.relative_to(ROOT).as_posix() for p in (ROOT/'translations').glob('x1000-*.json')]]},
            home_source_hashes=home_report['source_hashes'],
            limits=['UI root/object readiness is modeled; actual factory may rebuild/reset parameters and rendering remains unverified.',
                    'This standalone overlay allocates its own wording IDs; do not merge it with the separate remote-row overlay.',
                    'No authoritative system mode selection, persistence or RF handover; all valid confirmations are deliberately discarded.',
                    'No updater, device deployment or physical touch/font qualification.'])
report['source_hashes'].update({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('tools/wireless_resources.py','tools/wireless_init_bridge.py')})
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
