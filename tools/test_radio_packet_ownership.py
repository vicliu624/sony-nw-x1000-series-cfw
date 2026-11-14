"""Execute original packet factories/header/TX/free; ROM queue/IRQ are modeled.

No player/network access. The original large pool is tested at counts4 and3.
This validates packet bounds/lifetime, not DMA completion or task concurrency.
"""
from pathlib import Path
import hashlib,json,struct
from app_registry import ROOT
from radio_test_profile import packet_fixture

reports = []
for blocks in (4, 3):
    fixture = packet_fixture(blocks)
    cpu, word, call, free_count = (fixture[key] for key in ('cpu', 'word', 'call', 'free_count'))
    queue_result, queued, notified = (fixture[key] for key in ('queue_result', 'queued', 'notified'))
    descriptor, reserved, sentinel = (fixture[key] for key in ('descriptor', 'reserved', 'sentinel'))
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
    'stock_image_sha256':hashlib.sha256(fixture['blob']).hexdigest(),
    'source_hashes':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('tools/radio_test_profile.py','tools/marvell_firmware.py')},
    'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
OUT=ROOT/'work/espnow-packet-ownership';OUT.mkdir(parents=True,exist_ok=True)
(OUT/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
