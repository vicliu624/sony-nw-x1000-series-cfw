"""Replay original hardware-ring admission; no RF completion is simulated."""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
with contextlib.redirect_stdout(io.StringIO()):
    env=runpy.run_path(str(ROOT/'tools/test_radio_packet_ownership.py'))
cpu=env['cpu'];call=env['call'];put=env['put'];word=env['word']
cpu.mem_map(0x8000a000,0x1000)
# Only the frame-view accessor and an unrelated packet flag helper are modeled.
def helper(u,pc,size,unused):
    if pc in (0xc10,0x684c):
        u.reg_write(UC_ARM_REG_R0,0x200800 if pc==0xc10 else 0)
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
cpu.hook_add(UC_HOOK_CODE,helper)
queue=3;write_reg=0x8000a300;read_reg=0x8000a304
put(0xc0006d08+queue*4,write_reg);put(0xc0006cd0+queue*4,read_reg)
put(0x8000a000,0x200000);put(0xc000dc40,0)
descriptor=0x200900
cases=[]
for write,read,accepted,next_write in ((0,0,1,4),(0,8,0,0),(8,0,1,12),(248,0,0,248),(0x1fc,0xfc,1,0)):
    put(write_reg,write);put(read_reg,read)
    slot=0x200000|(queue<<8)|(write&255);put(slot,0xfeed1234)
    before=word(0xc00148b8)
    assert call(0xaf34,descriptor,queue)==accepted
    assert word(write_reg)==next_write
    assert word(slot)==(descriptor if accepted else 0xfeed1234)
    assert word(0xc00148b8)==(before+1)&0xffffffff
    cases.append({'write':write,'read':read,'accepted':bool(accepted),'next_write':next_write})
report={'passed':True,'original_af34_instructions_executed':True,'cases':cases,'mmio_registers_and_hardware_consumer_modeled':True,'irq_and_frame_helpers_modeled':True,'mac_ack_verified':False,'device_accessed':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'stock_image_sha256':hashlib.sha256(env['blob']).hexdigest()}
out=ROOT/'work/espnow-tx-ring';out.mkdir(exist_ok=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
