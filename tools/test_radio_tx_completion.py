"""Replay original e760 completion-ring decoding; hardware results are inputs."""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
with contextlib.redirect_stdout(io.StringIO()):
    env=runpy.run_path(str(ROOT/'tools/test_radio_packet_ownership.py'))
cpu=env['cpu'];call=env['call'];put=env['put'];word=env['word']
cpu.mem_map(0x8000a000,0x1000)
bookkeeping=[]
def helper(u,pc,size,unused):
    if pc in (0xc10,0x73a8):
        if pc==0x73a8:bookkeeping.append(u.reg_read(UC_ARM_REG_R0))
        u.reg_write(UC_ARM_REG_R0,0x200a00 if pc==0xc10 else 0)
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
cpu.hook_add(UC_HOOK_CODE,helper)
put(0x8000a000,0x200000)
put(0x8000a8b0,0x1680000) # avoids the hardware-stall recovery branch
out=0x200b00;descriptor=0xc0000900;cases=[]
for failed in (0,1):
    for retries,extra in ((0,0),(3,1),(15,7)):
        cpu.mem_write(descriptor,bytes(64));cpu.mem_write(descriptor+2,struct.pack('<H',failed));cpu.mem_write(descriptor+10,b'\x09');cpu.mem_write(descriptor+28,struct.pack('<H',0x1234))
        encoded=0x00000900|(retries<<24)|((extra>>1)<<29)|((extra&1)<<1)
        put(0x200d00,encoded);put(0x8000a010,4);put(0x8000a014,0)
        cpu.mem_write(out,b'\xa5'*16)
        assert call(0xe760,out)==1
        assert word(out)==0x200a00 and word(out+4)==failed
        assert bytes(cpu.mem_read(out+8,3))==bytes((retries,9,extra))
        assert bytes(cpu.mem_read(out+12,2))==bytes.fromhex('3412')
        assert word(0x8000a014)==4 and bookkeeping[-1]==(0 if failed else 1)
        cases.append({'descriptor_failure_bit':failed,'completion_status':word(out+4),'retry_field':retries,'extra_status_bits':extra})
# Empty completion queue produces no descriptor and does not consume an entry.
put(0x8000a010,4);put(0x8000a014,4);before=len(bookkeeping)
assert call(0xe760,out)==0 and word(out)==0 and word(out+4)==1
assert word(0x8000a014)==4 and len(bookkeeping)==before
report={'passed':True,'original_e760_instructions_executed':True,'cases':cases,'empty_queue_checked':True,'mmio_completion_words_synthetic':True,'frame_view_and_bookkeeping_helpers_modeled':True,'mac_ack_semantics_physically_verified':False,'device_accessed':False,'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'stock_image_sha256':hashlib.sha256(env['blob']).hexdigest()}
area=ROOT/'work/espnow-tx-completion';area.mkdir(exist_ok=True);(area/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

