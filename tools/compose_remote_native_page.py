"""Compose native Remote UI state into a private ELF; no UPG or deployment.

The new request callers are deliberately unpaired until a qualified DSO/view
adapter is supplied. Existing Root/Pcs arrays remain156 entries.
"""
import argparse,hashlib,io,json,struct,subprocess,time,tarfile
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from review_managed_remote_profile import receipt,digest
from remote_choice_resource import SOURCE as RESOURCE_SOURCE,TARGET as RESOURCE_TARGET,compose as compose_resource

CODE=0x4d7000
MASTER=0x4d8a00
DESCRIPTOR=MASTER+194*4
CALLBACKS=DESCRIPTOR+32
INITIALIZERS=CALLBACKS+24*4

def compose(raw,out):
 image=ELFFile(io.BytesIO(raw))
 def at(address,size,execute=False):
  matches=[s for s in image.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=address and address+size<=s['p_vaddr']+s['p_filesz']]
  if len(matches)!=1 or (execute and not matches[0]['p_flags']&1):raise ValueError('Invalid mapped span')
  s=matches[0];return s['p_offset']+address-s['p_vaddr']
 def read(address,size):
  off=at(address,size);return raw[off:off+size]
 def word(address):return struct.unpack('<I',read(address,4))[0]
 if [word(a) for a in (0x736bc,0x73714)]!=[0x3f55d8]*2:raise ValueError('Original menu registration changed')
 if word(0x411350)!=0x4d8040:raise ValueError('Expected the source-composed Remote entry')
 if word(0x2ac3c)!=0xe3a0109c or word(0x2aca4)!=0xe354009b:
  raise ValueError('Root must retain its original156-view capacity')
 sources=['runtime/apps/wireless-remote/native_page.c','runtime/apps/wireless-remote/native_page_entry.c']
 out.mkdir(parents=True,exist_ok=False);ld=out/'page.ld';exe=out/'page.arm'
 ld.write_text('''ENTRY(wr_remote_page_entry)
SECTIONS { . = 0x4d7000; .text : { *(.text*) *(.rodata*) }
 .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) }
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }
ASSERT(. < 0x4d7800, "Page code exceeds reserved slot")
ASSERT(SIZEOF(.data)==0, "No mutable page data")
ASSERT(SIZEOF(.bss)==0, "No page BSS")
wr_remote_page_request = 0xda84;
wr_page_post = 0xa57f0; wr_page_parent = 0x7461c; wr_page_index = 0x74608;
wr_page_set_category = 0x74668; wr_page_stock_home = 0x7fb54;
wr_page_set_state = 0x17ca34;
wr_page_stock_playback = 0x73608;
wr_page_row_id = 0x74634; wr_page_stock_settings_select = 0x950f0;
wr_page_stock_wireless_select = 0x7c8cc;
''')
 subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-nostdlib','-no-pie','-Wl,--build-id=none,-T,'+str(ld),*sources,'-o',str(exe)],cwd=ROOT,check=True)
 helper=ELFFile(io.BytesIO(exe.read_bytes()));symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()}
 section=helper.get_section_by_name('.text');assert section['sh_addr']==CODE;code=section.data()
 master=read(0x3f55d8,193*4)+struct.pack('<I',DESCRIPTOR)
 desc=bytearray(read(0x4052e4,32));struct.pack_into('<I',desc,12,CALLBACKS);struct.pack_into('<I',desc,20,INITIALIZERS)
 callbacks=bytearray(read(0x40542c,24*4))
 for index,name in ((3,'confirm'),(4,'select'),(6,'playback'),(7,'home')):struct.pack_into('<I',callbacks,index*4,symbols['wr_remote_page_'+name])
 initializers=struct.pack('<4I',symbols['wr_remote_page_init'],0,0,0)
 metadata=master+desc+callbacks+initializers
 result=bytearray(raw);edits=[]
 def put(address,new,expected):
  offset=at(address,len(new));before=raw[offset:offset+len(new)]
  if before!=expected:raise ValueError('Unexpected source at '+hex(address))
  result[offset:offset+len(new)]=new
  edits.append(dict(address=hex(address),before=before.hex(),after=new.hex()))
 for address,data in ((CODE,code),(MASTER,metadata)):
  at(address,len(data),True);put(address,data,bytes(len(data)))
 def integer(address,before,after):put(address,struct.pack('<I',after),struct.pack('<I',before))
 integer(0x73698,0xe3a010c1,0xe3a010c2) # count194
 integer(0x736a4,0xe1a03001,0xe3a030c1) # initial group stays193
 integer(0x736e4,0xe1a0200c,0xe3a020c2) # constructor count194, stack initial remains193
 for address in (0x736bc,0x73714):integer(address,0x3f55d8,MASTER)
 integer(0x411350,0x4d8040,symbols['wr_remote_page_entry'])
 integer(0x3fd604,0x7c8cc,symbols['wr_remote_page_wireless_entry'])
 restored=bytearray(result)
 for row in edits:
  offset=at(int(row['address'],16),len(bytes.fromhex(row['before'])));restored[offset:offset+len(bytes.fromhex(row['before']))]=bytes.fromhex(row['before'])
 assert bytes(restored)==raw
 check=ELFFile(io.BytesIO(result));assert image.header==check.header and [dict(s.header) for s in image.iter_segments()]==[dict(s.header) for s in check.iter_segments()]
 # ARM literal pools can stop a linear disassembly before the next function.
 # Decode aligned words individually so later request sites are included.
 decoder=Cs(CS_ARCH_ARM,CS_MODE_ARM)
 callers=[i.address+4 for off in range(0,len(code),4)
          for i in decoder.disasm(code[off:off+4],CODE+off)
          if i.mnemonic=='bl' and i.op_str=='#0xda84']
 assert callers and len(set(callers))==len(callers)
 def guards(spans):
  return [dict(address=hex(a),bytes=n,sha256=hashlib.sha256(result[at(a,n):at(a,n)+n]).hexdigest()) for a,n in spans]
 page_guards=guards([(CODE,len(code)),(MASTER,len(metadata)),(0x411350,4),(0x73694,0x84),
                    (0x2ac38,0x9c),(0x17ca34,0x20),(0x3fd604,4)])
 view_guards=guards([(0x2a824,0x48),(0x2a984,12),(0x1094f0,12),(0x10a0d4,0x80),
                     (0x736c0,16),(0x17ca18,0x1c),(0x10e850,16)])
 def initializer(rows):
  return '{'+','.join('{'+r['address']+'u,'+str(r['bytes'])+'u,{'+','.join('0x'+r['sha256'][i:i+2] for i in range(0,64,2))+'}}' for r in rows)+'}'
 header=out/'remote_native_page_profile.h'
 stock_root=ROOT/'work/upg-jp/verified-3.bin'
 if digest(stock_root)!='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5':raise ValueError('Original resource root changed')
 with tarfile.open(stock_root,'r:gz') as archive:
  if './'+RESOURCE_TARGET in archive.getnames():raise ValueError('Resource ID already occupied')
  template=archive.getmember('./'+RESOURCE_SOURCE);resource_data=compose_resource(archive.extractfile(template).read())
 resource=out/'root-overlay'/RESOURCE_TARGET;resource.parent.mkdir(parents=True);resource.write_bytes(resource_data)
 header.write_text('#define XW_PLAYER_NATIVE_REMOTE_PAGE\n'+
  '#define XW_REMOTE_PAGE_CALLERS {'+','.join(hex(c)+'u' for c in callers)+'}\n'+
  '#define XW_REMOTE_PAGE_GUARDS '+initializer(page_guards)+'\n'+
  '#define XW_REMOTE_VIEW_GUARDS '+initializer(view_guards)+'\n'+
  '#define XW_REMOTE_RESOURCE_PATH "/'+RESOURCE_TARGET+'"\n'+
  '#define XW_REMOTE_RESOURCE_BYTES '+str(len(resource_data))+'u\n'+
  '#define XW_REMOTE_RESOURCE_DIGEST {'+','.join('0x'+digest(resource)[i:i+2] for i in range(0,64,2))+'}\n')
 target=out/'SpiderApp.remote-page.analysis-only.elf';target.write_bytes(result)
 report=dict(prepared=True,analysis_only=True,ready_to_flash=False,firmware_created=False,device_accessed=False,
  artifact=target.relative_to(ROOT).as_posix(),base_sha256=hashlib.sha256(raw).hexdigest(),sha256=digest(target),
  page_group=194,shared_control=29,original_state_descriptors_preserved=193,
  initial_group_preserved=193,root_view_array_extended=False,elf_growth_bytes=0,
  code_address=hex(CODE),code_bytes=len(code),metadata_address=hex(MASTER),metadata_bytes=len(metadata),
  request_callers=callers,symbols={k:v for k,v in symbols.items() if k.startswith('wr_remote_page_')},edits=edits,
  guard_profile=header.relative_to(ROOT).as_posix(),guard_profile_sha256=digest(header),page_guards=page_guards,view_guards=view_guards,
  resource_overlay={RESOURCE_TARGET:dict(artifact=resource.relative_to(ROOT).as_posix(),bytes=len(resource_data),sha256=digest(resource),mode=template.mode,uid=template.uid,gid=template.gid,template=RESOURCE_SOURCE)},
  request_bridge_paired=False,view_lifecycle_adapter_installed=False,
  source_hashes={p:digest(ROOT/p) for p in sources+['runtime/apps/wireless-remote/native_page.h','tools/compose_remote_native_page.py','tools/remote_choice_resource.py']},
  limits=['Standalone analysis ELF only; guarded DSO bridge/view observer/Wi-Fi entry guard are not installed.',
          'Compiled callback/context registration is not physical GUI, RF or startup qualification.'])
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');return target,report

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host-review',required=True);args=p.parse_args()
 hp,host=receipt(args.host_review);source=hp.parent/'SpiderApp.player-prepare.analysis-only.elf'
 if digest(source)!=host['candidate_sha256']:raise ValueError('Host payload changed')
 out=ROOT/'work/remote-native-page-composition'/str(time.time_ns())
 _,report=compose(source.read_bytes(),out)
 print(json.dumps(dict(report=(out/'report.json').relative_to(ROOT).as_posix(),code_bytes=report['code_bytes'],metadata_bytes=report['metadata_bytes'],firmware_created=False),indent=2))
if __name__=='__main__':main()
