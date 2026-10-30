"""Original task5 preparation/e840 descriptor: plaintext vs Protected Action.

Unassociated feature-off fixture, modeled MMIO consumer/time/peer lookup/IRQ.
This does not prove MAC hardware encryption is disabled on a physical radio.
"""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,struct
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R4,UC_ARM_REG_R7,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
with contextlib.redirect_stdout(io.StringIO()):env=runpy.run_path(str(ROOT/'tools/test_radio_packet_ownership.py'))
cpu,call,word,put=[env[n] for n in ('cpu','call','word','put')]
cpu.mem_map(0x8000a000,0x1000);put(0xc000dc14,0x200a00);cpu.mem_write(0x200a00,bytes(1024))
put(0xc0006d08,0x8000a300);put(0xc0006cd0,0x8000a304);put(0x8000a000,0x200000)
def hook(u,pc,size,unused):
 if pc==0xf9cc:put(u.reg_read(UC_ARM_REG_R0),123);u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 if pc==0x9eaa:u.emu_stop()
cpu.hook_add(UC_HOOK_CODE,hook)
cases=[]
for threshold in (512,4096):
 cpu.mem_write(0x200426,struct.pack('<H',threshold))
 for length in (31,281,1536):
  desc=[]
  for protected in (0,1):
   pointer=call(0xd458,1900);node=word(pointer-4);metadata=word(node+20)
   put(node+12,0);cpu.mem_write(metadata,bytes(68));cpu.mem_write(pointer,bytes(1760))
   call(0xda00,pointer,0x200440,13,0x200460)
   cpu.mem_write(pointer,struct.pack('<H',length));cpu.mem_write(pointer+3,bytes([0x40 if protected else 0]));body=bytes((i*17+3)&255 for i in range(length));cpu.mem_write(pointer+32,body)
   before=bytes(cpu.mem_read(pointer,32+length))
   # Execute the actual task5 packet preparation before its68e8 call.
   cpu.reg_write(UC_ARM_REG_R4,pointer);cpu.reg_write(UC_ARM_REG_SP,0x208000);cpu.reg_write(UC_ARM_REG_LR,0x1f001)
   cpu.emu_start(0x9e69,0x9eac,count=20000)
   assert cpu.reg_read(UC_ARM_REG_PC)==0x9eaa and cpu.reg_read(UC_ARM_REG_R7)==metadata and word(metadata+60)==pointer
   put(0x8000a300,0);put(0x8000a304,0)
   assert call(0xe840,metadata)==1 and word(0x200000)==metadata+16
   after=bytes(cpu.mem_read(pointer,32+length));changed=[i for i,(a,b) in enumerate(zip(before,after)) if a!=b]
   assert set(changed)<={4,5},changed
   assert after[32:]==body and bool(after[3]&0x40)==bool(protected)
   # Pointers are allocation-dependent; compare only descriptor control bytes.
   control=bytes(cpu.mem_read(metadata+16,4))+bytes(cpu.mem_read(metadata+24,24))
   desc.append(control)
   assert call(0x65e0,pointer)==0
   assert call(0x1360,pointer)==0 and env['free_count']()==3
  assert desc[0]==desc[1],'Protected bit changed descriptor controls in this fixture'
  cases.append({'classification_threshold':threshold,'body_bytes':length,'descriptor_controls_identical':True,'frame_changes_only_mutable_duration':True,'body_unchanged':True})
report={'passed':True,'cases':cases,'original_task5_preparation_and_e840_executed':True,'original_hardware_ring_admission_executed':True,'peer_lookup_irq_time_and_hardware_consumer_modeled':True,'unassociated_feature_off_fixture_only':True,'physical_reencryption_excluded':False,'device_accessed':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/test_radio_protected_descriptor.py','tools/test_radio_packet_ownership.py']},'stock_image_sha256':hashlib.sha256(env['blob']).hexdigest()}
out=ROOT/'work/espnow-protected-descriptor';out.mkdir(exist_ok=True);(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
