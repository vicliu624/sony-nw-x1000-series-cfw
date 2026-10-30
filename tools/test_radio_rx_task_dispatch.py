"""Actual stock MAC task clause -> e164 ->4b9c -> veneer -> compiled full RX.

Starts after work-node acquisition. DMA producer/MMIO and IRQ are synthetic.
No physical MAC admission or unknown-key decryption claim; no device access.
"""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R4,UC_ARM_REG_R6,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/espnow-rx-task-dispatch';OUT.mkdir(parents=True,exist_ok=True)
with contextlib.redirect_stdout(io.StringIO()):env=runpy.run_path(str(ROOT/'tools/test_radio_completion_hook.py'))
cpu,put,word,call,free_count,command=[env[n] for n in ('cpu','put','word','call','free_count','command')]
entry=env['symbols']['xnow_radio_full_receive'];rx=env['symbols']['xnow_full_rx'];put(0xc00026b0,entry)
cpu.ctl_remove_cache(0xc00026a8,0xc00026b4)
if not any(a<=0x8000a000<=b for a,b,_ in cpu.mem_regions()):cpu.mem_map(0x8000a000,0x1000)
ring=0x201000;config=0xc000dc8c+4*32
for offset,value in [(0,ring),(8,4096),(16,0x8000a440),(20,0x8000a454),(24,0x7b4)]:put(config+offset,value)
trace=[];fallback=[]
def hook(u,pc,size,unused):
    trace.append(pc)
    if pc==0xc0003288:u.emu_stop()
    if pc==0xa314:
        fallback.append(u.reg_read(UC_ARM_REG_R0));u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
cpu.hook_add(UC_HOOK_CODE,hook)
def plain(n):
    p=bytes(i%256 for i in range(n));body=b'\x7f\x18\xfe\x34\x11\x22\x33\x44'
    chunks=[p[i:i+250] for i in range(0,n,250)] or [b'']
    for i,c in enumerate(chunks):body+=bytes([221,len(c)+5])+b'\x18\xfe\x34\x04'+bytes([0x12 if i+1<len(chunks) else 2])+c
    return body
rows=[]
for protected,length,kind,enabled in [(0,0,0xd0,1),(0,250,0xd0,1),(0,1470,0xd0,1),(1,31,0xd0,1),(1,281,0xd0,1),(1,1536,0xd0,1),(1,31,0x08,1),(1,31,0xd0,0)]:
    body=bytes([1,0,0,0x20,0,0,0,0])+bytes([0x55])*(length-8) if protected else plain(length)
    node=call(0xc000465c,word(0xc000ee4c));assert node==0xc000cdb0
    context=word(node+20);frame=word(node+8);before=word(rx+4);old_fallback=len(fallback);put(rx+56,enabled)
    raw=bytearray(32+len(body));struct.pack_into('<H',raw,0,len(body)+48);raw[2]=kind;raw[3]=0x40 if protected else 0;raw[6:12]=bytes.fromhex('021122334455');raw[12:18]=bytes.fromhex('0266778899aa');raw[18:24]=b'\xff'*6;raw[32:]=body
    record=bytearray(16)+raw;struct.pack_into('<H',record,2,0xbeef);cpu.mem_write(ring,bytes(record));put(0x8000a440,0);put(0x8000a454,(len(record)+3)&~3)
    trace.clear();cpu.reg_write(UC_ARM_REG_SP,0x208000);cpu.reg_write(UC_ARM_REG_LR,0x1f001);cpu.reg_write(UC_ARM_REG_R6,node);cpu.reg_write(UC_ARM_REG_R4,1)
    cpu.emu_start(0xc000323b,0xc000328a,count=60000)
    assert cpu.reg_read(UC_ARM_REG_PC)==0xc0003288,hex(cpu.reg_read(UC_ARM_REG_PC))
    assert 0xe164 in trace and 0x4b9c in trace and 0xc00046c0 in trace
    dispatched=kind==0xd0;accepted=dispatched and enabled
    assert (0xc00026a8 in trace)==dispatched and ((entry&~1) in trace)==dispatched
    assert word(rx+4)==before+int(accepted)
    assert len(fallback)==old_fallback+int(dispatched and not enabled)
    # No original software peer/key lookup is traversed in this task clause.
    assert 0x5710 not in trace
    if accepted:
        slot=rx+24+(before&1)*16;p,n=word(slot),word(slot+4)
        assert n==len(body) and bytes(cpu.mem_read(p,n))==body and bool(word(slot+12)&0x10000)==bool(protected)
        command(rx+12,before+1);assert word(rx+20)==0
    assert free_count()==3 and call(0xc000465c,word(0xc000ee4c))==node
    call(0xc00046c0,node) # Original release has no specified scalar result.
    rows.append({'protected':bool(protected),'payload_or_protected_body_bytes':length,'frame_type_byte':hex(kind),'bridge_enabled':bool(enabled),'original_task_dispatched':dispatched,'full_rx_queued':bool(accepted),'original_ring_copy_executed':True,'body_preserved':bool(accepted),'rx_work_released':True,'peer_lookup_5710_executed':False})
report={'passed':True,'cases':rows,'stock_sha256':hashlib.sha256(env['env']['env']['blob']).hexdigest(),'original_task_clause':'0xc000323a..0xc0003288','original_ring_poll':'0xe164','original_copy':'0x4b9c','original_veneer':'0xc00026a8 -> [0xc00026b0]','synthetic_dma_mmio_irq':True,'hardware_unknown_key_admission_verified':False,'device_accessed':False,'radio_loaded':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/test_radio_rx_task_dispatch.py','tools/test_radio_completion_hook.py','runtime/platform/espnow/radio_full_rx.c','runtime/platform/espnow/radio_full_rx.h']}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
