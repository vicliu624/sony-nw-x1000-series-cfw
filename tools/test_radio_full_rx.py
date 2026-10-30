"""Original RX ring-copy + compiled allocator-backed full RX/TX prototype.

ROM/IRQ and synthetic ring producer are fixture boundaries, not physical RX.
Uses the exact original singleton work factory, never invented RX frame bounds.
"""
import ctypes,hashlib,json,runpy,struct,subprocess
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_INVALID
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
from Crypto.Cipher import AES
from espnow_known_key_frame import PROFILES,analyze
OUT=ROOT/'work/espnow-full-rx';OUT.mkdir(parents=True,exist_ok=True)
sources=['runtime/platform/espnow/'+n for n in ('radio_packet.c','radio_full_rx.c','radio_full_tx.c','radio_word_command.c','radio_command_hook.S')]
link=OUT/'rx.ld';link.write_text('ENTRY(xnow_radio_full_receive)\nSECTIONS { . = 0xc000a190; .text : { *(.text*) *(.rodata*) } .state : { *(.state) } /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } ASSERT(.<=0xc000a8fc,"reserved block exceeded") }')
elf=OUT/'rx.elf'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-mthumb','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-static','-Wl,--build-id=none','-Wl,-T,'+str(link),*sources,'-o',str(elf)],cwd=ROOT,check=True)
with elf.open('rb') as f:
    image=ELFFile(f);sections=[(s['sh_addr'],s.data()) for s in image.iter_sections() if s['sh_flags']&2 and s['sh_size']]
    symbols={s.name:s['st_value'] for s in image.get_section_by_name('.symtab').iter_symbols() if s.name}
env=runpy.run_path(str(ROOT/'tools/test_radio_full_tx.py'))
cpu,put,word,call,free_count,command=[env[n] for n in ('cpu','put','word','call','free_count','command')]
cpu.mem_write(0xc000a190,bytes(1900))
for address,data in sections:cpu.mem_write(address,data)
cpu.ctl_remove_cache(0xc000a190,0xc000a8fc)
cpu.mem_write(0x88d6,struct.pack('<HHHI',0x4b01,0x4718,0x46c0,symbols['xnow_radio_word_command_entry']|1))
rx=symbols['xnow_full_rx'];fallback=[]
assert word(rx+56)==0 and word(rx+60)==0
put(rx+56,1) # explicit experimental activation after code/state initialization
def extra(u,pc,size,unused):
    if pc==0xa314:
        fallback.append((u.reg_read(UC_ARM_REG_R0),u.reg_read(UC_ARM_REG_R1)))
        u.reg_write(UC_ARM_REG_R0,7);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
cpu.hook_add(UC_HOOK_CODE,extra)
def invalid(u,access,address,size,value,unused):
    print('RX_INVALID_MEMORY',hex(address),'pc',hex(u.reg_read(UC_ARM_REG_PC)))
    return False
cpu.hook_add(UC_HOOK_MEM_INVALID,invalid)
node=call(0xc000465c,word(0xc000ee4c));ctx=word(node+20);frame=word(node+8)
assert node==0xc000cdb0 and ctx==0xc000cdd4 and frame==0xc000ce08
assert word(0xc0014710+20)==0xc000d5ec
put(ctx+16,frame) # Original task's c34 pointer store, before its ring read.
ring=0x201000;config=0xc000dc8c+4*32
put(config,ring);put(config+8,4096);put(config+16,0x200700);put(config+20,0x200704);put(config+24,0x7b4)
codec=env['codec'];nonce=env['nonce'];patterns=[]
def body(version,length,seed):
    data=bytes((i*17+seed)&255 for i in range(length));out=ctypes.create_string_buffer(1520);payload=ctypes.create_string_buffer(data);n=ctypes.c_size_t()
    assert codec.xnow_espnow_encode_body(out,1520,version,nonce,payload,length,ctypes.byref(n))==0
    return out.raw[:n.value]
def inject(raw,flags=0,declared=None,destination=bytes.fromhex('021122334455'),runner=call,fragment=0,a3=b'\xff'*6):
    length=len(raw)+48 if declared is None else declared
    packet=bytearray(32+len(raw));struct.pack_into('<H',packet,0,length);packet[2]=0xd0;packet[3]=flags
    packet[6:12]=destination;packet[12:18]=bytes.fromhex('0266778899aa');packet[18:24]=a3;packet[24]=fragment;packet[32:]=raw
    record=bytearray(16)+packet;struct.pack_into('<H',record,2,0xbeef)
    cpu.mem_write(ring,bytes(record));put(0x200704,(len(record)+3)&~3)
    copied=runner(0x4b9c,4,0,ctx);assert copied==length
    assert bytes(cpu.mem_read(frame,len(packet)))==packet
    return runner(symbols['xnow_radio_full_receive'],frame,ctx)
def slot(index):
    base=rx+24+(index&1)*16;return word(base),word(base+4)
def pop(ticket):
    command(rx+12,ticket&0xffffffff);return ctypes.c_int32(word(rx+20)).value
first=body(1,250,1);second=body(2,1470,2)
assert inject(first)==0 and word(rx+4)==1 and free_count()==2
p,n=slot(0);assert n==len(first) and bytes(cpu.mem_read(p,n))==first
assert inject(second)==0 and word(rx+4)==2 and free_count()==1
q,m=slot(1);assert m==len(second) and bytes(cpu.mem_read(q,m))==second
assert bytes(cpu.mem_read(p,n))==first,'old work buffer reuse changed queued payload'
assert inject(first)==0 and word(rx+4)==2 and word(rx+16)==1 and free_count()==1
assert pop(99)==-5 and word(rx+8)==0 and free_count()==1
assert pop(1)==0 and free_count()==2 and not slot(0)[0]
assert pop(1)==0 and free_count()==2 and slot(1)[0]==q
assert pop(2)==0 and free_count()==3
assert pop(3)==1 and free_count()==3
# Valid data is dropped, not overwritten, when original packet allocation fails.
held=[call(0xd458,1900) for _ in range(3)];assert free_count()==0
assert inject(first)==0 and word(rx+4)==2 and word(rx+16)==2
for pointer in held:assert call(0x1360,pointer)==0
assert free_count()==3
# Unsupported/protected/overlength input must not allocate a queue packet.
before=len(fallback);assert inject(first,0x40)==7 and len(fallback)==before+1 and free_count()==3
bad=bytearray(first);bad[0]=1;assert inject(bad)==7 and free_count()==3
assert call(symbols['xnow_radio_full_receive'],frame,0)==7 and free_count()==3
assert inject(second+b'\0')==7 and free_count()==3
assert inject(first,destination=bytes.fromhex('021111111111'))==7 and free_count()==3
assert inject(first,destination=b'\xff'*6)==0 and free_count()==2
assert pop(word(rx+8)+1)==0 and free_count()==3
# Wrap head/tail tickets without reusing an occupied slot or freeing twice.
put(rx+4,0xfffffffe);put(rx+8,0xfffffffe)
assert inject(first)==0 and inject(second)==0 and word(rx+4)==0
assert pop(0xffffffff)==0 and pop(0)==0 and word(rx+8)==0 and free_count()==3
# Switch to the producer after tail publication but before old-buffer free.
# It may reuse the ring slot, never the still-owned packet. Use a separate
# simulated task stack and actual compiled instructions for both contexts.
assert inject(first)==0 and inject(second)==0 and free_count()==1
old_packet=slot(0)[0];pause_free=[True]
def preempt(u,pc,size,unused):
    if pause_free[0] and pc==0x1360:u.emu_stop()
cpu.hook_add(UC_HOOK_CODE,preempt)
ticket=(word(rx+8)+1)&0xffffffff;put(rx+12,ticket)
cpu.reg_write(UC_ARM_REG_R0,rx+12);cpu.reg_write(UC_ARM_REG_R1,ticket)
cpu.reg_write(UC_ARM_REG_SP,0x208000);cpu.reg_write(UC_ARM_REG_LR,0x1f001)
cpu.emu_start(symbols['xnow_radio_rx_doorbell']|1,0x1f002,count=20000)
assert cpu.reg_read(UC_ARM_REG_PC)==0x1360 and word(rx+8)==ticket
consumer=cpu.context_save();pause_free[0]=False
def producer(entry,*args):
    cpu.reg_write(UC_ARM_REG_SP,0x206000);cpu.reg_write(UC_ARM_REG_LR,0x1f001)
    from unicorn.arm_const import UC_ARM_REG_R3
    for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):cpu.reg_write(reg,value)
    cpu.emu_start(entry|1,0x1f002,count=20000)
    assert cpu.reg_read(UC_ARM_REG_PC)==0x1f000
    return cpu.reg_read(UC_ARM_REG_R0)
assert inject(first,runner=producer)==0
new_packet=slot(0)[0];assert new_packet and new_packet!=old_packet and free_count()==0
cpu.context_restore(consumer);cpu.emu_start(0x1360,0x1f002,count=20000)
assert cpu.reg_read(UC_ARM_REG_PC)==0x1f000 and free_count()==1 and slot(0)[0]==new_packet
assert bytes(cpu.mem_read(new_packet,len(first)))==first
assert pop((ticket+1)&0xffffffff)==0 and pop((ticket+2)&0xffffffff)==0 and free_count()==3
# Stop with unread packets: disable closes admission, existing packets drain.
assert inject(first)==0 and inject(second)==0 and free_count()==1
put(rx+56,0);assert word(rx+60)==0
saved_head=word(rx+4);assert inject(first)==7 and word(rx+4)==saved_head
assert pop((word(rx+8)+1)&0xffffffff)==0
assert pop((word(rx+8)+1)&0xffffffff)==0 and free_count()==3
put(rx+56,1)
# Stop a producer after original allocation, before publication. It must keep
# active set until it frees its private packet and returns; host cannot unload.
stop_copy=[True]
def pause_producer(u,pc,size,unused):
    if stop_copy[0] and 0xc000a190<=pc<0xc000a8fc and word(rx+60)==1 and free_count()==2:
        stop_copy[0]=False;u.emu_stop()
cpu.hook_add(UC_HOOK_CODE,pause_producer)
def interrupted(entry,*args):
    if entry!=symbols['xnow_radio_full_receive']:return call(entry,*args)
    cpu.reg_write(UC_ARM_REG_SP,0x206000);cpu.reg_write(UC_ARM_REG_LR,0x1f001)
    for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1),args):cpu.reg_write(reg,value)
    cpu.emu_start(entry|1,0x1f002,count=30000)
    assert not stop_copy[0] and word(rx+60)==1 and free_count()==2
    assert word(rx+4)==saved_head
    put(rx+56,0) # modeled completed host word STORE while producer suspended
    assert word(rx+60)==1,'stop was reported complete before private free'
    resume=cpu.reg_read(UC_ARM_REG_PC);cpu.emu_start(resume|1,0x1f002,count=30000)
    assert cpu.reg_read(UC_ARM_REG_PC)==0x1f000
    return cpu.reg_read(UC_ARM_REG_R0)
assert inject(second,runner=interrupted)==0
assert word(rx+60)==0 and word(rx+4)==saved_head and free_count()==3
assert inject(first)==7 and free_count()==3
put(rx+56,1);assert inject(first)==0
assert pop((word(rx+8)+1)&0xffffffff)==0 and free_count()==3
# Canonical native headers are valid only after A3/fragment validation.
protected=bytearray(31);protected[3]=0x20
assert inject(protected,0x40,destination=b'\xff'*6)==7 and free_count()==3
assert inject(protected,0x40,a3=bytes(6))==7 and free_count()==3
assert inject(protected,0x40,fragment=1)==7 and free_count()==3
assert inject(first,a3=bytes(6))==7 and free_count()==3
head=word(rx+4);assert inject(protected,0x40)==0
base=rx+24+(head&1)*16
assert cpu.mem_read(base+14,2)==b'\x01\x00' and free_count()==2
assert pop((word(rx+8)+1)&0xffffffff)==0 and free_count()==3
# Two-device capture route: exercise the real compiled RX hook with independent
# encrypted bodies, then authenticate canonical headers reconstructed only from
# retained slot metadata and the verified fixture local MAC. No hardware key is
# provisioned here; upstream admission is still modeled, not established.
capture_cases=[];key=bytes(range(16));capture_pn=0x010203040506
capture_header=bytes.fromhex('d04000000211223344550266778899aaffffffffffff0000')
for profile,prefix,mask in PROFILES:
    for version,length in ((1,250),(2,1470)):
        plain=body(version,length,9)
        for key_id in (0,3):
            fc=int.from_bytes(capture_header[:2],'little');aad=(fc&~0x70 if mask else fc).to_bytes(2,'little')+capture_header[4:22]+bytes(2)
            cipher=AES.new(key,AES.MODE_CCM,nonce=bytes([prefix])+capture_header[10:16]+capture_pn.to_bytes(6,'big'),mac_len=8);cipher.update(aad)
            encrypted,mic=cipher.encrypt_and_digest(plain)
            iv=bytes([6,5,0,0x20|(key_id<<6),4,3,2,1]);protected_body=iv+encrypted+mic
            head=word(rx+4);assert inject(protected_body,0x40)==0
            base=rx+24+(head&1)*16;pointer,n=slot(head)
            assert n==len(protected_body) and bytes(cpu.mem_read(pointer,n))==protected_body
            retained_source=struct.pack('<IH',word(base+8),word(base+12)&0xffff)
            assert word(base+12)>>16==1
            canonical=capture_header[:10]+retained_source+b'\xff'*6+bytes(2)+bytes(cpu.mem_read(pointer,n))
            result,opened=analyze(canonical,key)
            assert result['matched_profiles']==[profile] and result['key_id']==key_id
            assert opened[profile]==bytes((i*17+9)&255 for i in range(length))
            assert pop((word(rx+8)+1)&0xffffffff)==0 and free_count()==3
            capture_cases.append({'profile':profile,'version':version,'payload_bytes':length,'key_id':key_id,'canonical_capture_authenticated':True})
assert call(0x1360,frame)==0 # original singleton RX work object is independently released
for address,data in sections:
    if address<rx and address<symbols['xnow_full_tx']:assert bytes(cpu.mem_read(address,len(data)))==data
tracked=[*sources,'runtime/platform/espnow/radio_packet.h','runtime/platform/espnow/radio_full_rx.h','runtime/platform/espnow/radio_full_tx.h','tools/test_radio_full_rx.py','tools/test_radio_full_tx.py','tools/test_radio_packet_ownership.py']
report={'passed':True,'original_rx_work_factory_and_4b9c_ring_copy_executed':True,'queue_depth':2,'v1_250_and_v2_1470_bodies_preserved':True,'borrowed_work_pointer_not_retained':True,'queue_full_and_pool_exhaustion_drop_without_overwrite':True,'stale_duplicate_and_empty_pop_handled':True,'protected_rx_flag_and_a3_fragment_unicast_filter':True,'tickets_wrap':True,'disabled_admission_and_queued_drain':True,'stop_during_private_allocation_releases_before_inactive':True,'unsupported_traffic_falls_back':True,'own_unicast_and_broadcast_only':True,'producer_preemption_between_tail_publish_and_free_safe':True,'task_preemption_manually_scheduled':True,'all_packet_buffers_released':free_count()==3,'combined_reserved_region_bytes':sum(len(data) for _,data in sections),'rom_irq_copy_and_dma_producer_modeled':True,'physical_rx_tested':False,'download_image_created':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in tracked}}
report.update(synthetic_encrypted_capture_cases=capture_cases,upstream_unknown_key_admission_proven=False)
report['source_hashes']['tools/espnow_known_key_frame.py']=hashlib.sha256((ROOT/'tools/espnow_known_key_frame.py').read_bytes()).hexdigest()
(OUT/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

