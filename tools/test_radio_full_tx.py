"""Original packet path + compiled host-command full TX, no RX/poll callback.

Reuses the complete allocator/header/ownership experiment as an initialized
fixture. ROM queue/completion remain simulated; no radio image is produced.
"""
import ctypes,hashlib,json,runpy,struct,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R6,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
OUT=ROOT/'work/espnow-full-tx';OUT.mkdir(parents=True,exist_ok=True)
sources=['runtime/platform/espnow/radio_packet.c','runtime/platform/espnow/radio_full_tx.c','runtime/platform/espnow/radio_word_command.c','runtime/platform/espnow/radio_command_hook.S']
link=OUT/'tx.ld';link.write_text('ENTRY(xnow_radio_word_command_entry)\nSECTIONS { . = 0xc000a190; .text : { *(.text*) *(.rodata*) } .state : { *(.state) } /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } ASSERT(.<=0xc000a8fc,"reserved block exceeded") }')
elf=OUT/'tx.elf'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-mthumb','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-static','-Wl,--build-id=none','-Wl,-T,'+str(link),*sources,'-o',str(elf)],cwd=ROOT,check=True)
with elf.open('rb') as f:
    image=ELFFile(f);sections=[(s['sh_addr'],s.data()) for s in image.iter_sections() if s['sh_flags']&2 and s['sh_size']]
    symbols={s.name:s['st_value'] for s in image.get_section_by_name('.symtab').iter_symbols() if s.name}
env=runpy.run_path(str(ROOT/'tools/test_radio_packet_ownership.py'))
cpu,put,word,call,free_count=[env[x] for x in ('cpu','put','word','call','free_count')]
for address,data in sections:cpu.mem_write(address,data)
cpu.mem_write(0x88d6,struct.pack('<HHHI',0x4b01,0x4718,0x46c0,symbols['xnow_radio_word_command_entry']|1))
state=symbols['xnow_full_tx'];request=0xc00155b8;seq=0
def responses(u,pc,size,unused):
    if pc==0x9a46:u.emu_stop()
    elif pc==0x9c90:
        dest,source,n=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
        u.mem_write(dest,bytes(u.mem_read(source,n)));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
cpu.hook_add(UC_HOOK_CODE,responses)
def command(address,value):
    cpu.mem_write(request,struct.pack('<4H',0x86,20,0x55aa,0)+struct.pack('<HHII',1,0,address,value))
    cpu.mem_write(0xc000edf4,b'\0') # model drained response bookkeeping between commands
    cpu.reg_write(UC_ARM_REG_SP,0x208000);cpu.reg_write(UC_ARM_REG_LR,0x1f001)
    cpu.emu_start(0x8079,0x9b40,count=30000)
    assert cpu.reg_read(UC_ARM_REG_PC)==0x9a46 and cpu.reg_read(UC_ARM_REG_R6)==0
def operation(kind):
    global seq
    command(state+16,kind);seq+=1;command(state+4,seq)
    assert word(state+8)==seq
    return ctypes.c_int32(word(state+12)).value
shared=OUT/'wire.so';subprocess.run(['gcc','-std=c99','-shared','-fPIC','runtime/platform/espnow/xnow_wire.c','-o',str(shared)],cwd=ROOT,check=True)
codec=ctypes.CDLL(str(shared));codec.xnow_espnow_encode_body.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
nonce=ctypes.create_string_buffer(b'\x11\x22\x33\x44');cases=[];env['queue_result'][0]=0
for version,length in ((1,0),(1,250),(2,251),(2,1470)):
    data=bytes((i*17)&255 for i in range(length));payload=ctypes.create_string_buffer(data);body=ctypes.create_string_buffer(1520);used=ctypes.c_size_t()
    assert codec.xnow_espnow_encode_body(body,1520,version,nonce,payload,length,ctypes.byref(used))==0
    assert operation(1)==0;packet=word(state+24);assert word(state+28)==1760 and free_count()==2
    assert operation(1)==-2 and free_count()==2
    raw=body.raw[:used.value];padded=raw+bytes((-len(raw))%4)
    for at in range(0,len(padded),4):command(packet+32+at,struct.unpack_from('<I',padded,at)[0])
    command(state+20,len(raw));command(state+32,0x88776602);command(state+36,0x0000aa99)
    accepted=len(env['queued']);assert operation(2)==0 and len(env['queued'])==accepted+1
    assert word(state+24)==0 and free_count()==2
    assert bytes(cpu.mem_read(packet+32,len(raw)))==raw
    assert struct.unpack('<H',cpu.mem_read(packet,2))[0]==len(raw)
    assert bytes(cpu.mem_read(packet+6,6))==bytes.fromhex('0266778899aa')
    assert call(0x1360,packet)==0 and free_count()==3
    cases.append({'version':version,'application_bytes':length,'body_bytes':len(raw),'native_word_command_upload':True,'original_header_and_queue':True,'rx_trigger_used':False})
assert operation(1)==0;packet=word(state+24);command(state+20,1521)
assert operation(2)==-5 and word(state+24)==packet and free_count()==2
assert operation(3)==0 and free_count()==3 and not word(state+24)
assert operation(3)==0 and free_count()==3
# Refuse an unreserved pool before touching its allocator.
cpu.mem_write(0xc000d5a4+6,struct.pack('<H',4))
assert operation(1)==-4 and free_count()==3 and not word(state+24)
cpu.mem_write(0xc000d5a4+6,struct.pack('<H',3))
held_all=[call(0xd458,1900) for _ in range(3)];assert all(held_all) and free_count()==0
assert operation(1)==-3 and free_count()==0 and not word(state+24)
for p in held_all:assert call(0x1360,p)==0
assert free_count()==3
# A reused node may contain a stale next pointer into another live allocation.
# Clearing that link is essential: original free walks entire packet chains.
held=call(0xd458,1900);held_node=word(held-4);assert free_count()==2
next_node=word(0xc000d5a4)+4;put(next_node+12,held_node)
assert operation(1)==0;packet=word(state+24);assert word(word(packet-4)+12)==0
cpu.mem_write(packet+32,b'\x7f\x18\xfe\x34'+bytes(11));command(state+20,15)
env['queue_result'][0]=1
assert operation(2)==-1 and free_count()==2 and word(held_node+8)==held
assert call(0x1360,held)==0 and free_count()==3
# Queue rejection must free exactly once inside the original submit routine.
assert operation(1)==0;packet=word(state+24);cpu.mem_write(packet+32,b'\x7f\x18\xfe\x34'+bytes(11));command(state+20,15)
env['queue_result'][0]=1;assert operation(2)==-1 and free_count()==3 and not word(state+24)
assert operation(3)==0 and free_count()==3
for address,data in sections:
    if address!=state:assert bytes(cpu.mem_read(address,len(data)))==data,'packet writes damaged reserved code'
tracked=[*sources,'runtime/platform/espnow/radio_full_tx.h','runtime/platform/espnow/radio_packet.h','runtime/platform/espnow/xnow_wire.c','runtime/platform/espnow/xnow_wire.h','tools/test_radio_packet_ownership.py','tools/test_radio_full_tx.py']
report={'passed':True,'cases':cases,'explicit_destination':True,'duplicate_allocate_and_abort_safe':True,'oversized_submit_keeps_buffer_for_abort':True,'queue_rejection_no_double_free':True,'stale_chain_cleared_without_freeing_live_neighbor':True,'unreserved_pool_refused_before_allocation':True,'exhausted_pool_returns_error_without_allocation':True,'rx_dependency_removed_in_instruction_replay':True,'reserved_code_survived':True,'elf_bytes_in_reserved_region':sum(len(data) for _,data in sections),'rom_queue_and_completion_modeled':True,'physical_radio_tested':False,'download_image_created':False,'device_accessed':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in tracked}}
(OUT/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
