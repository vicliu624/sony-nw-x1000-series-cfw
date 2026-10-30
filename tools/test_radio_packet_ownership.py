"""Execute original packet factories/header/TX/free; ROM queue/IRQ are modeled.

No player/network access. The original large pool is tested at counts4 and3.
This validates packet bounds/lifetime, not DMA completion or task concurrency.
"""
from pathlib import Path
import hashlib,json,struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
from marvell_firmware import parse
blob=(ROOT/'work/targets-jp/sd8686.bin').read_bytes()
assert hashlib.sha256(blob).hexdigest()=='08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a'
records=parse(blob);reports=[]
for blocks in (4,3):
    cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    for base,size in ((0,0x20000),(0xc0000000,0x20000),(0x04000000,0x4000),(0x200000,0x10000),(0xffff0000,0x10000)):
        cpu.mem_map(base,size)
    for record in records:
        if record.command==1:cpu.mem_write(record.address,record.data)
    if blocks==3:cpu.mem_write(0x163ee,bytes.fromhex('0322'))
    reserved=0xc000a190;sentinel=bytes([0xa5])*1900;cpu.mem_write(reserved,sentinel)
    copies=[];queued=[];notified=[];queue_result=[0];trace=[]
    def word(address):return struct.unpack('<I',cpu.mem_read(address,4))[0]
    def put(address,value):cpu.mem_write(address,struct.pack('<I',value))
    def ret(value=0):cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def hook(u,pc,size,unused):
        trace.append(pc)
        if pc==0x1f000:u.emu_stop()
        elif pc in (0xfa94,0xfaa0):ret()
        elif pc==0x758:
            address,length=u.reg_read(UC_ARM_REG_R0),u.reg_read(UC_ARM_REG_R1)
            assert address==0xc0014770 and length==24;u.mem_write(address,bytes(length));ret(address)
        elif pc==0x65c4:ret() # post-factory feature setup, unrelated to pool objects
        elif pc==0x7b4:
            dest,source,n=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
            assert 0<=n<=1700;u.mem_write(dest,bytes(u.mem_read(source,n)));copies.append(n);ret(dest)
        elif pc==0x5710:ret(0) # no synthetic association/key entry for plaintext peer
        elif pc==0xffff1d2c:
            handle,slot,timeout=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
            assert handle==0x12340003 and timeout==0
            queued.append(word(slot));ret(queue_result[0])
        elif pc==0xffff1518:
            target,event,option=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
            assert target==0x04001970 and event==2 and option==0;notified.append((target,event));ret()
    cpu.hook_add(UC_HOOK_CODE,hook)
    def call(entry,*args):
        cpu.reg_write(UC_ARM_REG_SP,0x208000);cpu.reg_write(UC_ARM_REG_LR,0x1f001)
        for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):cpu.reg_write(reg,value)
        cpu.emu_start(entry if entry==0x1360 else entry|1,0x1f002,count=20000)
        assert cpu.reg_read(UC_ARM_REG_PC)==0x1f000,hex(cpu.reg_read(UC_ARM_REG_PC))
        return cpu.reg_read(UC_ARM_REG_R0)
    call(0xc0004b6c)
    manager=0xc000d5a4;descriptor=word(0xc000ee50)
    assert descriptor==0xc0014728 and word(descriptor+20)==manager
    assert bytes(cpu.mem_read(descriptor,4))==bytes.fromhex('20004400')
    assert word(descriptor+12)==0x102dd and word(descriptor+16)==0x1031d
    def free_count():return struct.unpack('<H',cpu.mem_read(manager+8,2))[0]
    assert free_count()==blocks
    put(0x04001bc8,0x200400);put(0x04001bc4,0x200420)
    cpu.mem_write(0x200400,bytes(32));cpu.mem_write(0x200420,bytes.fromhex('021122334455'))
    cpu.mem_write(0x200440,bytes.fromhex('0266778899aa'));cpu.mem_write(0x200460,b'\xff'*6)
    put(0x040015e0+3*4,0x12340003)
    entries=[]
    for logical_body in (15,265,1520,1536):
        pointer=call(0xd458,1900);assert pointer
        node=word((pointer&~3)-4);base=node-4
        assert base>=0xc0008b4c and (base-0xc0008b4c)%1900==0
        assert word(node+24)==descriptor and pointer-node==136
        capacity=base+1900-pointer;assert capacity==1760 and 32+logical_body<=capacity
        cpu.mem_write(pointer,bytes(capacity))
        call(0xda00,pointer,0x200440,13,0x200460)
        assert bytes(cpu.mem_read(pointer+6,6))==bytes.fromhex('0266778899aa')
        assert bytes(cpu.mem_read(pointer+12,6))==bytes.fromhex('021122334455')
        assert bytes(cpu.mem_read(pointer+18,6))==b'\xff'*6
        assert bytes(cpu.mem_read(pointer+2,2))==b'\xd0\0'
        cpu.mem_write(pointer,struct.pack('<H',logical_body))
        payload=bytes((i*17)&255 for i in range(logical_body));cpu.mem_write(pointer+32,payload)
        queue_result[0]=0;before=free_count();assert call(0xd800,pointer)==0
        assert queued[-1]==pointer and free_count()==before and notified
        # Only model completion after proving accepted submission did not free.
        assert call(0x1360,pointer)==0 and free_count()==blocks
        pointer=call(0xd458,1900);before=free_count();queue_result[0]=1;notifications=len(notified)
        assert call(0xd800,pointer)==0xffffffff
        assert free_count()==blocks and len(notified)==notifications
        entries.append({'logical_body':logical_body,'packet_capacity':capacity,'submitted_block_retained':True,'explicit_completion_release_restored_pool':True,'queue_failure_freed_by_original_submit':True})
        if blocks==3:assert bytes(cpu.mem_read(reserved,1900))==sentinel
    reports.append({'pool_blocks':blocks,'descriptor':hex(descriptor),'data_headroom_from_pool_payload':136,'cases':entries})
report={'passed':True,'reports':reports,'original_factory_allocator_header_submit_and_free_executed':True,
    'small_pool_not_used_for_large_packets':True,'rom_queue_irq_memzero_and_peer_lookup_modeled':True,
    'hardware_completion_modeled':True,'mac_ack_qualified':False,'device_accessed':False,
    'stock_image_sha256':hashlib.sha256(blob).hexdigest(),
    'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
OUT=ROOT/'work/espnow-packet-ownership';OUT.mkdir(parents=True,exist_ok=True)
(OUT/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
