"""Source-built native Settings row/callback analysis; no installer or device."""
import contextlib,hashlib,io,json,struct,subprocess,time,tarfile
from app_registry import ROOT
from builtin_language import enable_settings,SETTINGS_SHA
from build_home_feedback import build
from elftools.elf.elffile import ELFFile
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from release_firmware import complete_wordings
from resources import append_stx
from wireless_resources import compose as compose_wireless_resources
out=ROOT/'work/remote-settings-row'/str(time.time_ns());out.mkdir(parents=True)
with contextlib.redirect_stdout(io.StringIO()):home,symbols,home_report=build(out/'home')
def offset(raw,address,count):
 matches=[s for s in ELFFile(io.BytesIO(raw)).iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+count<=s['p_vaddr']+s['p_filesz']]
 assert len(matches)==1
 s=matches[0];return int(s['p_offset']+address-s['p_vaddr'])
editable=bytearray(home);at=offset(home,symbols['hb_error_descriptor'],48)
struct.pack_into('<I',editable,at+4,99999);struct.pack_into('<I',editable,at+20,0)
base=enable_settings(bytes(editable));assert hashlib.sha256(base).hexdigest()==SETTINGS_SHA
source='runtime/apps/wireless-remote/native_settings.c';entry=0x4d8040
linker=out/'settings.ld'
linker.write_text('''ENTRY(wr_native_settings_select)
SECTIONS {
 . = 0x4d8040;
 .text : { *(.text*) *(.rodata*) }
 .data : { *(.data*) }
 .bss : { *(.bss*) *(COMMON) }
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) }
}
ASSERT(SIZEOF(.data) == 0, "No data")
ASSERT(SIZEOF(.bss) == 0, "No BSS")
ASSERT(. < 0x4d8240, "Callback exceeds reviewed slot")
wr_stock_row_id = 0x74634;
wr_stock_settings_select = 0x950f0;
wr_remote_settings_request = 0xda84;
''',encoding='utf-8')
helper=out/'settings.elf';binary=out/'settings.bin'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-ffreestanding','-nostdlib','-no-pie','-Wl,--build-id=none,-T,'+str(linker),source,'-o',str(helper)],cwd=ROOT,check=True)
subprocess.run(['arm-linux-gnueabi-objcopy','-O','binary',str(helper),str(binary)],check=True)
code=binary.read_bytes();patched=bytearray(base)
rows=offset(base,0x4d8000,48);old_rows=struct.unpack_from('<11I',base,rows)
assert base[rows+44:rows+48]==bytes(4) and 0xfd0000 not in old_rows
struct.pack_into('<I',patched,rows+44,0xfd0000)
table=0x3f611c
index=next(i for i in range(95) if struct.unpack_from('<I',base,offset(base,table+i*20,4))[0]==2)
assert struct.unpack_from('<II',base,offset(base,table+index*20+4,8))==(0x4d8000,11)
struct.pack_into('<I',patched,offset(base,table+index*20+8,4),12)
slot=offset(base,entry,len(code));assert base[slot:slot+len(code)]==bytes(len(code))
aliases=[]
for segment in ELFFile(io.BytesIO(base)).iter_segments():
 if segment['p_type']!='PT_LOAD':continue
 lo=max(slot,segment['p_offset']);hi=min(slot+len(code),segment['p_offset']+segment['p_filesz'])
 if lo<hi:aliases.append((segment['p_vaddr']+lo-segment['p_offset'],segment['p_flags']))
assert aliases==[(entry,5)]
patched[slot:slot+len(code)]=code
callback=offset(base,0x411350,4);assert struct.unpack_from('<I',base,callback)[0]==0x950f0
struct.pack_into('<I',patched,callback,entry)
elf=ELFFile(io.BytesIO(base));u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x1000000)
for s in elf.iter_segments():
 if s['p_type']=='PT_LOAD':u.mem_write(s['p_vaddr'],bytes(patched[s['p_offset']:s['p_offset']+s['p_filesz']]))
u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x10000)
selected=0;requests=0;delegated=[];market=1
def hook(uc,pc,size,unused):
 global requests
 if pc==0xe5f4:result=0
 elif pc==0xf6c0:result=market
 elif pc==0x74634:result=selected
 elif pc==0x950f0:
  delegated.append([uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]);result=0x1234
 elif pc==0xda84:requests+=1;result=4321
 else:return
 uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook);cases=[]
for selected in (*old_rows,0xfd0000,0xffffffff):
 requests=0;delegated.clear()
 for r,v in ((UC_ARM_REG_R0,0x1111),(UC_ARM_REG_R1,0x2222),(UC_ARM_REG_R2,7),(UC_ARM_REG_SP,0x6000f000),(UC_ARM_REG_LR,0x50000000)):u.reg_write(r,v)
 u.emu_start(entry,0x50000000,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0x50000000
 if selected==0xfd0000:assert requests==1 and not delegated and u.reg_read(UC_ARM_REG_R0)==0x202
 else:assert not requests and delegated==[[0x1111,0x2222,7]] and u.reg_read(UC_ARM_REG_R0)==0x1234
 cases.append(hex(selected))
before=Uc(UC_ARCH_ARM,UC_MODE_ARM);before.mem_map(0x8000,0x1000000)
for s in elf.iter_segments():
 if s['p_type']=='PT_LOAD':before.mem_write(s['p_vaddr'],s.data())
before.mem_map(0x50000000,4096);before.mem_map(0x60000000,0x10000);before.hook_add(UC_HOOK_CODE,hook)
def query(vm,item):
 vm.mem_write(0x60000000,bytes(8))
 for r,v in ((UC_ARM_REG_R0,item),(UC_ARM_REG_R1,0x60000000),(UC_ARM_REG_R2,0x60000004),(UC_ARM_REG_SP,0x6000f000),(UC_ARM_REG_LR,0x50000000)):vm.reg_write(r,v)
 vm.emu_start(0x751ec,0x50000000,count=10000);assert vm.reg_read(UC_ARM_REG_PC)==0x50000000
 pointer,count=struct.unpack('<II',vm.mem_read(0x60000000,8));assert count<=256
 return list(struct.unpack('<'+str(count)+'I',vm.mem_read(pointer,count*4))) if count else []
list_cases=0
for market in (1,2):
 for item in {struct.unpack_from('<I',base,offset(base,table+i*20,4))[0] for i in range(95)}:
  old,new=query(before,item),query(u,item)
  assert new==(old+[0xfd0000] if market==1 and item==2 else old),(market,item)
  list_cases+=1
restored=bytearray(patched)
for address,count in ((0x4d802c,4),(table+index*20+8,4),(entry,len(code)),(0x411350,4)):
 at=offset(base,address,count);restored[at:at+count]=base[at:at+count]
assert bytes(restored)==base and len(patched)==len(base)
anchors=[i.address+4 for i in Cs(CS_ARCH_ARM,CS_MODE_ARM).disasm(code,entry) if i.mnemonic=='bl' and i.op_str=='#0xda84']
assert len(anchors)==1
artifact=out/'SpiderApp.remote-settings-row.analysis-only.elf';artifact.write_bytes(patched)
root=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(root).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
prefix='usr/local/share/gemini/res/stx/'
with tarfile.open(fileobj=io.BytesIO(root),mode='r:gz') as archive:
 wordings={}
 for member in archive:
  if member.isfile() and member.name.startswith('./'+prefix) and member.name.endswith('.stx'):
   data,tid=append_stx(archive.extractfile(member).read(),'Homebrew');assert tid==7308
   data,tid=append_stx(data,'Homebrew unavailable.\nCheck HOMEBREW.');assert tid==7309
   wordings[member.name.rsplit('-',1)[1][:-4]]=data
 complete_wordings(wordings)
 labels={'jp':'ワイヤレスリモコン','en':'Wireless Remote','cs':'无线遥控','ct':'無線遙控'}
 resources={}
 for language_code,data in wordings.items():
  data,tid=append_stx(data,labels.get(language_code,'Wireless Remote'));assert tid==7310
  wordings[language_code]=data
 mode_name='usr/local/share/gemini/res/swd/ucs2-dev-sid-100-00.swd'
 choice_name='usr/local/share/gemini/res/swd/ucs2-dev-sid-139-00.swd'
 wordings,mode_swd,choice_swd,mode_ids=compose_wireless_resources(wordings,archive.extractfile('./'+mode_name).read(),archive.extractfile('./'+choice_name).read())
 for language_code,data in wordings.items():
  name=prefix+'ucs2-dev-'+language_code+'.stx';target=out/'root-overlay'/name
  target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
  resources[name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
 name='usr/local/share/gemini/res/swd/ucs2-dev-sid-050-00.swd'
 swd=archive.extractfile('./'+name).read();assert b'tid.11:' not in swd
 swd=swd.rstrip()+b'\n\ntid.11:\t"tid-7310"\t; Wireless Remote\n'
 target=out/'root-overlay'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(swd)
 resources[name]=dict(bytes=len(swd),sha256=hashlib.sha256(swd).hexdigest())
 target=out/'root-overlay'/mode_name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(mode_swd)
 resources[mode_name]=dict(bytes=len(mode_swd),sha256=hashlib.sha256(mode_swd).hexdigest())
 target=out/'root-overlay'/choice_name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(choice_swd)
 resources[choice_name]=dict(bytes=len(choice_swd),sha256=hashlib.sha256(choice_swd).hexdigest())
report=dict(prepared=True,analysis_only=True,ready_to_flash=False,firmware_created=False,device_accessed=False,
            artifact=artifact.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(patched).hexdigest(),
            original_rows_preserved=True,settings_rows=12,remote_row_id='0xfd0000',remote_label_index=11,
            callback=hex(entry),request_anchor_lr=hex(anchors[0]),callback_bytes=len(code),arm_dispatch_cases=cases,
            request_guards=[dict(address=hex(address),bytes=count,sha256=hashlib.sha256(patched[offset(base,address,count):offset(base,address,count)+count]).hexdigest()) for address,count in ((entry,len(code)),(0x411350,4),(0x4d8000,48))],
            native_list_replay_cases=list_cases,
            elf_growth_bytes=0,undeclared_changes=False,remote_activation_implemented=False,wording_overlay_pending=False,
            resource_overlay=resources,resource_label_id=7310,localized_label_languages=list(labels),
            source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [source,'tools/prepare_remote_settings_row.py','tools/builtin_language.py','tools/release_firmware.py','scripts/wording.py','scripts/resources.py',*[p.relative_to(ROOT).as_posix() for p in (ROOT/'translations').glob('x1000-*.json')]]},
            home_source_hashes=home_report['source_hashes'],native_wireless_choice_resource='sid-139-00',
            limits=['Request boundary is modeled here; paired native-remote-settings host build supplies the guarded bridge separately.',
                    'No complete on/off UI, native RF admission or actual original GUI execution.'])
report['source_hashes']['tools/wireless_resources.py']=hashlib.sha256((ROOT/'tools/wireless_resources.py').read_bytes()).hexdigest()
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
