"""Borrow/restore prototype with actual Sony Pcs setters and active-layer query.

Root layer IDs/flags/draw counts and owner/resource/code qualification are
fixtures. This is not qualification of asynchronous device restore timing.
"""
import hashlib,io,json,struct,subprocess,time,argparse
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--ports-review');args=parser.parse_args()
ports=None
if args.ports_review:
 from review_managed_remote_profile import receipt,private,digest
 from player_arm_guest import stock_libraries
 rp,ports=receipt(args.ports_review);header=private(ports['guard_profile']);assert digest(header)==ports['guard_profile_sha256']
out=ROOT/'work/native-choice-view'/str(time.time_ns());out.mkdir(parents=True)
fixture=out/'ports.c';fixture.write_text('''unsigned long test_owner=17; int test_code=1,test_resource=1;
unsigned long pthread_self(void){return test_owner;}
int wr_view_code_valid(void){return test_code;} int wr_view_resource_ready(void){return test_resource;}
unsigned wr_view_sid_get(void){return *(volatile unsigned *)(0x4e692c+29*132+26*4);}
void wr_view_sid_set(unsigned v){*(volatile unsigned *)(0x4e692c+29*132+26*4)=v;}
void wr_view_counts_get(unsigned v[3]){volatile unsigned *p=(volatile unsigned *)(0x4e692c+29*132);v[0]=p[21];v[1]=p[22];v[2]=p[32];}
void wr_view_counts_set(const unsigned v[2]){volatile unsigned *p=(volatile unsigned *)(0x4e692c+29*132);p[21]=v[0];p[32]=v[1];}
void _start(void){}
''')
if ports:
 fixture.write_text('''#include <stdint.h>
unsigned long test_owner=17; int test_code=1,test_resource=1;
unsigned long pthread_self(void){return test_owner;}
struct image_info {const char *name;void *base;const char *symbol;void *address;};
int dladdr(const void *p,struct image_info *out){uintptr_t a=(uintptr_t)p;if(a<0x8000||a>0x4de000)return 0;out->name="SpiderApp";out->base=(void *)0x8000;out->symbol=0;out->address=0;return 1;}
void _start(void){}
''')
linker=out/'view.ld';linker.write_text('''ENTRY(_start)
SECTIONS { . = 0x50000000; .text : { *(.text*) *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) }
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }
wr_view_root = 0x2a984; wr_view_pool = 0x1094f0;
wr_view_active = 0x2a824; wr_view_params_get = 0x10a118;
wr_view_menu_context = 0x736c0; wr_view_menu_state = 0x17ca18;
wr_view_params_set = 0x10a0d4;
wr_view_sid_word = 0x4e692c + 29 * 132 + 26 * 4;
''')
if ports:
 linker.write_text('''ENTRY(_start)
SECTIONS { . = 0x50000000; .text : { *(.text*) *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) }
 /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } }
wr_view_sid_word = 0x4e692c + 29 * 132 + 26 * 4;
''')
source='runtime/apps/wireless-remote/native_choice_view.c';binary=out/'view.arm'
sources=[source];extra=[]
if ports:
 sources+=['runtime/platform/player/remote_page_ports.c','runtime/platform/player/remote_page_guard.c','runtime/platform/player/stock_image.c','runtime/native/sha256.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
 libs=stock_libraries();extra=['-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-Wno-misleading-indentation','-I'+str(header.parent),str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-pie','-nostdlib','-no-pie','-Wl,--build-id=none,-T,'+str(linker),*sources,str(fixture),*extra,'-o',str(binary)],cwd=ROOT,check=True)
helper=ELFFile(io.BytesIO(binary.read_bytes()));symbols={s.name:s['st_value'] for s in helper.get_section_by_name('.symtab').iter_symbols()}
path=ROOT/'work/player-mode-refresh-fix-20261105-1/SpiderApp.player-prepare.analysis-only.elf';raw=path.read_bytes()
if ports:
 path=private(ports['artifact']);assert digest(path)==ports['sha256'];raw=path.read_bytes()
u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
segments=[s for image in (ELFFile(io.BytesIO(raw)),helper) for s in image.iter_segments() if s['p_type']=='PT_LOAD']
merged=[]
for start,end in sorted((int(s['p_vaddr'])&~4095,(int(s['p_vaddr'])+int(s['p_memsz'])+4095)&~4095) for s in segments):
 if merged and start<=merged[-1][1]:merged[-1]=(merged[-1][0],max(end,merged[-1][1]))
 else:merged.append((start,end))
for start,end in merged:u.mem_map(start,end-start)
u.mem_map(0x70000000,0x10000)
for s in segments:u.mem_write(s['p_vaddr'],s.data())
put=lambda a,v:u.mem_write(a,struct.pack('<I',v&0xffffffff))
word=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
area=0x70000000;done=area+0xff00;scope=area+0x5000
def hook(cpu,pc,size,unused):
 a=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
 if ports and pc==symbols['wr_view_resource_ready']:value=word(symbols['test_resource'])
 elif ports and pc==symbols['wr_view_code_valid'] and not word(symbols['test_code']):value=0
 elif pc==0xd85c:u.mem_write(a[0],bytes(u.mem_read(a[1],a[2])));value=a[0]
 elif pc==0xd574:u.mem_write(a[0],bytes([a[1]&255])*a[2]);value=a[0]
 elif pc in (0x17c42c,0x33b918):value=0
 else:return
 cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def call(target,args=(),extra=0):
 for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),[*args,0,0,0,0][:4]):u.reg_write(r,v)
 put(area+0xe000,extra);u.reg_write(UC_ARM_REG_SP,area+0xe000);u.reg_write(UC_ARM_REG_LR,done)
 u.emu_start(symbols[target] if isinstance(target,str) else target,done,count=3000000)
 assert u.reg_read(UC_ARM_REG_PC)==done
 value=u.reg_read(UC_ARM_REG_R0);return value if value<0x80000000 else value-0x100000000
call(0x10e754,[0x4e692c,156]);manager=call(0x1094f0);call(0x109524,[manager])
assert call(0x10e558,[29,area])==0;view=word(area);root=call(0x2a984)
slot=root+0x2b18+29*8;put(slot,view);put(slot+4,0);put(root+8,0)
layers=[root+0x2ff8+i*0x2e94 for i in range(4)]
for layer in layers:put(layer,-1)
put(layers[0],97);put(root+0xea48,1)
# Construct/read the actual menu context; its initial/destination state is a fixture.
master=area+0x6000;u.mem_write(master,bytes(u.mem_read(0x3f55d8,193*4))+bytes(u.mem_read(0x3f55d8+153*4,4)))
menu_context=0x683400
assert call(0x17c494,[menu_context,194,master,2],2)==0
put(0x6833fc,menu_context)
def menu(group,state):assert call(0x17ca34,[menu_context,group,state])==((group<<8)|state)
menu(2,2)
sid=symbols['wr_view_sid_word'];before=bytes(u.mem_read(view,0xac));root_before=bytes(u.mem_read(root,0xea50))
template=sid-26*4;template_before=bytes(u.mem_read(template,132))
for layer in layers:
 previous=word(layer)
 put(layer,29);assert call('wr_native_choice_view_begin',[scope,17])==-4
 assert word(view+0x4c)==3 and word(sid)==13900
 put(layer,previous)
put(root+8,1);assert call('wr_native_choice_view_begin',[scope,17])==-4;put(root+8,0)
put(symbols['test_resource'],0);assert call('wr_native_choice_view_begin',[scope,17])==-2;put(symbols['test_resource'],1)
assert call('wr_native_choice_view_begin',[scope,17])==0
assert word(view+0x4c)==2 and word(sid)==13901
assert [word(template+i*4) for i in (21,22,32)]==[2,3,2]
put(symbols['test_owner'],18);assert call('wr_native_choice_view_end',[scope])==-4;put(symbols['test_owner'],17)
assert call('wr_native_choice_view_end',[scope])==-4 # Not an exit from Remote yet.
menu(194,2)
assert call('wr_native_choice_view_end',[scope])==0
put(layers[0],29);assert call('wr_native_choice_view_poll',[scope])==-4;put(layers[0],97)
put(root+8,1);assert call('wr_native_choice_view_poll',[scope])==-4;put(root+8,0)
put(slot+4,1);assert call('wr_native_choice_view_poll',[scope])==-4;put(slot+4,0)
assert call('wr_native_choice_view_poll',[scope])==-4 # Absence alone is no completion.
epoch=word(scope+28) # Explicit ARM32 private struct layout.
assert call('wr_native_choice_view_acknowledge',[scope,epoch+1])==-5
assert call('wr_native_choice_view_acknowledge',[scope,epoch])==-4
menu(2,1)
assert call('wr_native_choice_view_acknowledge',[scope,epoch])==-4
assert call(0x17c608,[menu_context,0x4a0116,0,0])==0
assert call(0x17ca18,[menu_context])==0x0202
put(layers[0],-1);assert call('wr_native_choice_view_acknowledge',[scope,epoch])==-4;put(layers[0],97)
put(layers[0]+0x2e2c,1);assert call('wr_native_choice_view_acknowledge',[scope,epoch])==-4;put(layers[0]+0x2e2c,0)
assert call('wr_native_choice_view_acknowledge',[scope,epoch])==0
put(sid,13902);assert call('wr_native_choice_view_poll',[scope])==-5;put(sid,13901)
put(template+21*4,4);assert call('wr_native_choice_view_poll',[scope])==-5;put(template+21*4,2)
put(slot,view+4);assert call('wr_native_choice_view_poll',[scope])==-2;put(slot,view)
put(symbols['test_code'],0);assert call('wr_native_choice_view_poll',[scope])==-2;put(symbols['test_code'],1)
assert call('wr_native_choice_view_poll',[scope])==0
for i in range(20):
 assert call('wr_native_choice_view_begin',[scope,17])==0
 menu(194,2)
 assert call('wr_native_choice_view_end',[scope])==0
 menu(2,1)
 assert call('wr_native_choice_view_observe',[scope])==-4
 assert call(0x17c608,[menu_context,0x4a0116,0,0])==0
 assert call('wr_native_choice_view_observe',[scope])==0
assert call('wr_native_choice_view_begin',[scope,17])==0
menu(194,2)
assert call('wr_native_choice_view_end',[scope])==0
put(layers[0],123);menu(90,1)
assert call('wr_native_choice_view_observe',[scope])==-4
menu(90,2);put(layers[1],29)
assert call('wr_native_choice_view_observe',[scope])==-4
assert word(sid)==13901
put(layers[1],-1)
assert call('wr_native_choice_view_observe',[scope])==0
put(layers[0],97)
assert bytes(u.mem_read(view,0xac))==before and bytes(u.mem_read(root,0xea50))==root_before and word(sid)==13900
assert bytes(u.mem_read(template,132))==template_before
report=dict(passed=True,input_player_sha256=hashlib.sha256(raw).hexdigest(),native_active_lookup_and_pcs_setters=True,
 native_port_wrappers_executed=bool(ports),resource_ready_hooked=bool(ports),loader_identity_is_fixture=bool(ports),
 template_and_view_counts_consistent=True,template_exactly_restored=True,
 wireless_parent_restores_only_when_interactive_and_inactive=True,
 active_layer_refusals=4,draw_pending_refused=True,foreign_owner_refused=True,unknown_replacement_refused=True,
 unknown_sid_preserved=True,repeat_cycles=20,view_and_root_exactly_restored=True,
 completion_required=True,stale_completion_refused=True,native_menu_ready_transition_executed=True,
 scene_layer_and_event_order_are_fixtures=True,
 device_accessed=False,firmware_created=False,
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/apps/wireless-remote/native_choice_view.h','tools/test_native_choice_view.py']},
 limits=['Active IDs/flags/draw counts and code/resource/owner ports are supplied fixtures.',
         'Original active-layer query, Pcs constructor and property helpers execute; asynchronous renderer/close ordering remains unqualified.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
