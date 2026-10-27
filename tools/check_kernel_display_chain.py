"""Original kernel ioctl -> validation -> state -> LCD descriptor; stops before driver submit."""
from pathlib import Path
import argparse,hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC,UC_ARM_REG_CPSR
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--virtual-driver-roundtrip',action='store_true',help='Simulate LCD driver success, then replay native return and state readback.')
parser.add_argument('--virtual-completion-callback',action='store_true',help='After virtual submit, inject qfb_callback(page,0) before native readback; no real completion implied.')
parser.add_argument('--queued-work-after-submit',action='store_true',help='After virtual driver roundtrip, execute original queued worker to LCD boundary.')
parser.add_argument('--irq-completion',action='store_true',help='Use original IRQ handler on supplied registers instead of directly calling qfb_callback.')
parser.add_argument('--native-driver-prefix',action='store_true',help='Continue original LCD driver only through page-global assignment, before update/trigger branch.')
parser.add_argument('--native-mix-prefix',action='store_true',help='After staged driver prefix, manually invoke mix_image only through callback-page transfer.')
parser.add_argument('--native-driver-to-mix',action='store_true',help='Follow native driver update1 branch directly into mix_image prefix; no manual mix call.')
parser.add_argument('--native-deferred-submit',action='store_true',help='Video state1/timeout0: follow native submit return without triggering mix.')
parser.add_argument('--native-timeout-followup',action='store_true',help='After deferred submit, manually invoke original LCD timeout and queued work to mix prefix.')
parser.add_argument('--native-mode-prefix',action='store_true',help='Replay stock command6 display-mode request only through validated mode configuration.')
parser.add_argument('--native-brightness-boundary',action='store_true',help='Continue mode request to the actual qfb_set_brightness boundary.')
parser.add_argument('--native-video-stop',action='store_true',help='After deferred submit, invoke native V4L2 image stop branch to mix prefix.')
parser.add_argument('--native-v4l2-stop-caller',action='store_true',help='Reach video stop through original V4L2 lcd_call_func with operation0.')
parser.add_argument('--native-v4l2-stop-work',action='store_true',help='Use original stop_do worker to select operation0 and global context.')
parser.add_argument('--native-release-queue',action='store_true',help='Run original active-owner V4L2 release through streamoff/stop-work enqueue before manual work scheduling.')
parser.add_argument('--native-streamoff-queue',action='store_true',help='Use original V4L2 do_ioctl STREAMOFF dispatch rather than device release.')
parser.add_argument('--streamoff-type',type=int,choices=(1,2),default=2,help='Decoded buffer-type fixture; SpiderApp observed payload is1.')
args=parser.parse_args()
assert not args.virtual_completion_callback or args.virtual_driver_roundtrip
assert not args.queued_work_after_submit or args.virtual_driver_roundtrip
assert not args.irq_completion or args.virtual_completion_callback
assert not args.native_driver_prefix or not args.virtual_driver_roundtrip
assert not args.native_mix_prefix or args.native_driver_prefix
assert not args.native_driver_to_mix or (args.native_driver_prefix and args.native_mix_prefix)
assert not args.native_deferred_submit or (args.native_driver_prefix and not args.native_mix_prefix)
assert not args.native_timeout_followup or args.native_deferred_submit
assert not args.native_brightness_boundary or args.native_mode_prefix
assert not args.native_video_stop or (args.native_deferred_submit and not args.native_timeout_followup)
assert not args.native_v4l2_stop_caller or args.native_video_stop
assert not args.native_v4l2_stop_work or args.native_v4l2_stop_caller
assert not args.native_release_queue or args.native_v4l2_stop_work
assert not args.native_streamoff_queue or args.native_release_queue
raw=(ROOT/'work/upg-jp/verified-1.bin').read_bytes();digest=hashlib.sha256(raw).hexdigest()
assert digest=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
a=(ROOT/'work/isolation-audit/x1000-kernel-analysis.elf').read_bytes();elf=ELFFile(io.BytesIO(a));assert elf.get_section_by_name('.kernel').data()==raw
source=json.loads((ROOT/'sources/native-display-submit-prefix.json').read_text());rows=[]
assert source['input_sha256']=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
for case in source['cases']:
 page=case['page_fixture'];payload=case['calls'][0]['payload_words']
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
 for s in elf.iter_segments():
  if s['p_type']=='PT_LOAD':
   low=s['p_vaddr']&~4095;high=(s['p_vaddr']+s['p_memsz']+4095)&~4095
   u.mem_map(low,high-low);u.mem_write(s['p_vaddr'],s.data())
 u.mem_map(0x50000000,4096);u.mem_map(0x60000000,0x20000)
 def put(p,v):u.mem_write(p,struct.pack('<I',v))
 def word(p):return struct.unpack('<I',u.mem_read(p,4))[0]
 put(0x60001234,0x60002000)
 for offset in (4,0x14,0x24):put(0x60002000+offset,1)
 target=0xc02c2250 if page==0 else 0xc02c2268
 u.mem_write(0x60003000,struct.pack('<6I',*payload))
 put(0x60018000,0x60001000)
 put(0x60016008,0xffffffff)  # Virtual current-thread address limit.
 copies=[];driver_calls=[];readbacks=[];callback_services=[];resume_driver=False;worker_boundary=False;contended_worker=False;trylock_wakes=[];mix_entries=[];timeout_work=[];lcd_timer_requests=[];release_requests=[]
 def hook(uc,pc,size,data):
  if args.native_release_queue and pc==(0xc0159b18 if args.native_streamoff_queue else 0xc0159cd0):
   uc.emu_stop();return
  if args.native_release_queue and pc==0xc01569f4:
   assert uc.reg_read(UC_ARM_REG_R0)==0x6000c008
   release_requests.append({'service':'videobuf_streamoff','virtual_result':0})
   uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if args.native_release_queue and pc==0xc0058398:
   assert uc.reg_read(UC_ARM_REG_R0)==0x6000d000 and uc.reg_read(UC_ARM_REG_R1)==0x600091c0
   release_requests.append({'service':'queue_work','queue':'0x6000d000','work':'0x600091c0','virtual_result':1})
   uc.reg_write(UC_ARM_REG_R0,1);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if args.native_mode_prefix and not args.native_brightness_boundary and pc==0xc0102984:
   uc.emu_stop();return
  if args.native_brightness_boundary and pc==0xc0100bac:
   assert [uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]==[101,1,10]
   uc.emu_stop();return
  if args.native_timeout_followup and pc==0xc010413c:
   uc.emu_stop();return
  if args.native_timeout_followup and pc==0xc005012c:
   assert uc.reg_read(UC_ARM_REG_R0)==word(0xc0104168)
   assert uc.reg_read(UC_ARM_REG_R1)==1010
   lcd_timer_requests.append({'timer':hex(word(0xc0104168)),'expires_fixture':1010})
   uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc==0xc010376c:mix_entries.append(pc)
  if args.native_driver_prefix and not args.native_driver_to_mix and not args.native_deferred_submit and pc==0xc0103e24:
   uc.emu_stop();return
  if (args.native_mix_prefix or args.native_timeout_followup or args.native_video_stop) and pc==0xc0103808:
   uc.emu_stop();return
  if args.native_timeout_followup and pc==0xc0058398:
   assert uc.reg_read(UC_ARM_REG_R0)==0x60006000 and uc.reg_read(UC_ARM_REG_R1)==0xc02c2d98
   timeout_work.append({'queue':'0x60006000','work':'0xc02c2d98'})
   uc.reg_write(UC_ARM_REG_R0,1);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc==0xc0102608 and not resume_driver:
   uc.emu_stop();return
  if pc==0xc0103d44:
   if args.native_driver_prefix:return
   if worker_boundary:
    uc.emu_stop();return
   assert resume_driver and uc.reg_read(UC_ARM_REG_R0)==0xc02c21e0
   driver_calls.append('virtual LCD driver success')
   uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc in (0xc01056a4,0xc004ffa8,0xc0042f90):
   if args.native_video_stop and pc==0xc004ffa8:
    assert uc.reg_read(UC_ARM_REG_R0)==word(0xc0104168)
    callback_services.append(hex(pc));uc.reg_write(UC_ARM_REG_R0,0)
    uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
   if pc==0xc0042f90 and contended_worker:
    assert uc.reg_read(UC_ARM_REG_R0)==0x6000200c
    trylock_wakes.append(hex(pc))
    uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
   assert args.virtual_completion_callback
   callback_services.append(hex(pc))
   uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc==0xc00f58b0:
   dst,src,n=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
   assert (dst,n) in ((0x60004000,24),(0x60003000,12))
   uc.mem_write(dst,bytes(uc.mem_read(src,n)));readbacks.append([dst,n])
   uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc==0xc00f5ce4:
   dst,src,n=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
   assert src==0x60003000 and n in ((8,12,24) if args.native_mode_prefix else (12,24))
   uc.mem_write(dst,bytes(uc.mem_read(src,n)));copies.append([src,n])
   uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc in (0xc0218680,0xc02186e0):raise AssertionError('Unexpected contended lock helper')
 def intr(uc,n,data):raise AssertionError(f'Unexpected syscall {n}')
 u.hook_add(UC_HOOK_CODE,hook);u.hook_add(UC_HOOK_INTR,intr)
 u.reg_write(UC_ARM_REG_CPSR,0x13);u.reg_write(UC_ARM_REG_R2,0x40044e01);u.reg_write(UC_ARM_REG_R3,0x60003000)
 u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 u.emu_start(0xc0101f80,0x50000000,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==0xc0102608 and copies==[[0x60003000,24]]
 assert list(struct.unpack('<6I',u.mem_read(target,24)))==[payload[0],payload[1],payload[2],payload[4],page,0]
 address=word(0xc02c21e4)
 assert address==(0x33000000 if page==0 else 0x33060000)
 observed=[word(0xc02c21e0+x) for x in (0x1c,0x20,0x24,0x28,0x2c)]
 assert observed==[payload[1],payload[0],payload[2],payload[4],page]
 assert word(0x60002014)==word(0x60002024)==1
 assert word(0x60002004)==0
 readback=None;ready_record=None;next_page=None
 if args.virtual_driver_roundtrip:
  resume_driver=True
  u.emu_start(0xc0102608,0x50000000,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R0)==0
  assert driver_calls==['virtual LCD driver success'] and word(0x60002004)==1
  assert word(0xc02c28e0)==0
  if args.virtual_completion_callback:
   if args.irq_completion:
    for p,v in ((0xc02c2d64,0x60005000),(0x60005060,1),(0x60005044,4),(0xc02c2f24,0),(0xc02c2e80,page),(0xc02c2d84,0)):put(p,v)
   else:
    u.reg_write(UC_ARM_REG_R0,page);u.reg_write(UC_ARM_REG_R1,0)
   u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
   u.emu_start(0xc01042c8 if args.irq_completion else 0xc0101680,0x50000000,count=10000)
   assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and word(0xc02c28e0)==page
   assert callback_services and callback_services[0]==('0xc01056a4' if args.irq_completion else '0xc004ffa8')
  u.reg_write(UC_ARM_REG_R2,0x80044e03);u.reg_write(UC_ARM_REG_R3,0x60004000)
  u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
  u.emu_start(0xc0101f80,0x50000000,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R0)==0
  assert readbacks==[[0x60004000,24]]
  readback=list(struct.unpack('<6I',u.mem_read(0x60004000,24)))
  # Getter selects a global state bank; virtual LCD success does not change it.
  # Do not inject a bank switch to make page1 appear to roundtrip.
  assert word(0xc02c28e0)==(page if args.virtual_completion_callback else 0)
  assert readback==(payload[:5]+[0] if page==0 or args.virtual_completion_callback else [0]*6), (page,payload,readback)
  assert all(word(0x60002000+offset)==1 for offset in (4,0x14,0x24))
  if args.virtual_completion_callback:
   # Native application's wait count is100. With a free bank this must not schedule.
   u.mem_write(0x60003000,struct.pack('<3I',100,0,0))
   u.reg_write(UC_ARM_REG_R2,0x80044e00);u.reg_write(UC_ARM_REG_R3,0x60003000)
   u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
   u.emu_start(0xc0101f80,0x50000000,count=10000)
   assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and u.reg_read(UC_ARM_REG_R0)==0
   ready_record=list(struct.unpack('<3I',u.mem_read(0x60003000,12)))
   assert ready_record==([100,1,0] if page==0 else [100,0,1])
   next_page=0 if ready_record[1]==0 else 1
   assert next_page==1-page
 worker_result=None
 if args.native_mode_prefix:
  config_global=word(0xc0102f7c);config=0x60007000;table=0x60008000
  put(config_global,config);put(config+40,table)
  if args.native_brightness_boundary:put(word(0xc0102f84),0)
  for i in range(6):put(table+4*i,100+i)
  put(0xc02c2ec0,1)
  u.mem_write(0x60003000,struct.pack('<2I',1,0))
  put(0x60018000,0x60001000)
  u.reg_write(UC_ARM_REG_R2,0x40044e0c);u.reg_write(UC_ARM_REG_R3,0x60003000)
  u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
  u.emu_start(0xc0101f80,0x50000000,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==(0xc0100bac if args.native_brightness_boundary else 0xc0102984)
  mode_record=word(0xc0102f88)
  assert list(struct.unpack('<3I',u.mem_read(mode_record,12)))==[101,1,10]
  assert word(0xc02c2ec0)==1
  worker_result={'request':'0x40044e0c','payload':[1,0],'mode_record_words':[101,1,10],
                 'mode_table_fixture':[100,101,102,103,104,105],'video_flag_unchanged_before_apply':True,
                 'stopped_before':'0xc0102984'}
 if args.native_driver_prefix:
  driver_lock=word(0xc0103ebc)
  put(driver_lock,1);resume_driver=True
  if args.native_driver_to_mix:put(word(0xc0103c88),1)
  if args.native_deferred_submit:
   put(0xc02c2ec0,1);put(0xc02c2ec8,0)
  u.emu_start(0xc0102608,0x50000000,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==(0x50000000 if args.native_deferred_submit else 0xc0103808 if args.native_driver_to_mix else 0xc0103e24)
  assert word(0xc02c2e7c)==page and word(0xc02c2e80)==(page if args.native_driver_to_mix else 0)
  assert word(driver_lock)==int(args.native_deferred_submit) and word(0x60002004)==int(args.native_deferred_submit)
  if args.native_deferred_submit:assert u.reg_read(UC_ARM_REG_R0)==0 and not mix_entries
  worker_result={'native_driver_range':['0xc0103d44','0xc0103e24 exclusive'],
                 'staged_page_global':'0xc02c2e7c','staged_page_written_by_driver':word(0xc02c2e7c),
                 'irq_callback_page_global':'0xc02c2e80','irq_callback_page_still_initial':word(0xc02c2e80),
                 'driver_lock_fixture':hex(driver_lock),'driver_lock_held':not args.native_deferred_submit,'ioctl_outer_lock_held':not args.native_deferred_submit,'native_mix_entries':len(mix_entries)}
  if args.native_video_stop:
   put(word(0xc0103c88),1)
   if args.native_release_queue:
    assert word(0xc015a0c8)==0xc0158880 and word(0xc015a078)==0xe58a31cc
    put(0x6000b080,0x6000c000);put(0x6000c000,0x60009000)
    put(0x6000920c,0x6000c000);put(0x600090dc,0x6000d000)
    u.reg_write(UC_ARM_REG_R1,0x6000b000)
    if args.native_streamoff_queue:
     put(0x6000c004,args.streamoff_type);put(0x6000e000,args.streamoff_type)
     u.reg_write(UC_ARM_REG_R2,0x40045613);u.reg_write(UC_ARM_REG_R3,0x6000e000)
    u.reg_write(UC_ARM_REG_SP,0x60017000);u.reg_write(UC_ARM_REG_LR,0x50000000)
    u.emu_start(0xc01592f4 if args.native_streamoff_queue else 0xc0159c38,0x50000000,count=10000)
    assert u.reg_read(UC_ARM_REG_PC)==(0xc0159b18 if args.native_streamoff_queue else 0xc0159cd0) and len(release_requests)==2
   for reg in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3):u.reg_write(reg,0)
   if args.native_v4l2_stop_caller:
    put(0x60009000+0x1f8,1)
    u.reg_write(UC_ARM_REG_R0,0x60009000)
    if args.native_v4l2_stop_work:put(0xc02c6694,0x60009000)
   u.reg_write(UC_ARM_REG_SP,0x60017000);u.reg_write(UC_ARM_REG_LR,0x50000000)
   u.emu_start(0xc0158880 if args.native_v4l2_stop_work else 0xc015851c if args.native_v4l2_stop_caller else 0xc0103ef8,0x50000000,count=10000)
   assert u.reg_read(UC_ARM_REG_PC)==0xc0103808 and len(mix_entries)==1
   assert word(0xc02c2ec0)==0 and word(0xc02c2ec8)==0 and word(0xc02c2e80)==page
   assert word(driver_lock)==0 and callback_services==['0xc004ffa8']
   worker_result['native_video_stop']={'entry':'0xc0103ef8','args_fixture':[0,0,0,0],
                                     'video_flag_after':0,'timeout_flag_after':0,'callback_page':word(0xc02c2e80),
                                     'virtual_timer_deletions':1,'mix_called_by_native_branch':True,'stopped_before':'0xc0103808'}
   if args.native_v4l2_stop_caller:
    assert word(0x60009000+0x1f8)==0
    worker_result['native_video_stop']['caller']={'entry':'0xc015851c','operation':0,'context_fixture':'0x60009000',
                                               'caller_lock_held':True,'native_call_to_lcd':'0xc0158804'}
    if args.native_v4l2_stop_work:worker_result['native_video_stop']['caller']['native_stop_worker_entry']='0xc0158880'
    if args.native_release_queue:worker_result['native_video_stop']['release_prefix']={'entry':'0xc0159c38','active_owner_fixture':True,'virtual_services':release_requests,'stopped_after_queue':'0xc0159cd0'}
    if args.native_streamoff_queue:
     worker_result['native_video_stop']['streamoff_prefix']={'entry':'0xc01592f4','request':'0x40045613','decoded_type_fixture':args.streamoff_type,'active_owner_fixture':True,'virtual_services':release_requests,'stopped_after_queue':'0xc0159b18'}
     del worker_result['native_video_stop']['release_prefix']
  if args.native_timeout_followup:
   put(0xc02c2d94,0x60006000)
   u.reg_write(UC_ARM_REG_SP,0x60017000);u.reg_write(UC_ARM_REG_LR,0x50000000)
   u.emu_start(0xc01043d0,0x50000000,count=10000)
   assert u.reg_read(UC_ARM_REG_PC)==0x50000000 and len(timeout_work)==1 and word(0xc02c2ec8)==1
   put(word(0xc0103c88),1)
   u.reg_write(UC_ARM_REG_SP,0x60017000);u.reg_write(UC_ARM_REG_LR,0x50000000)
   u.emu_start(0xc0104408,0x50000000,count=10000)
   assert u.reg_read(UC_ARM_REG_PC)==0xc0103808 and len(mix_entries)==1
   assert word(0xc02c2e80)==page and word(driver_lock)==0 and word(0x60002004)==1
   worker_result['lcd_timeout_followup']={'timer_entry':'0xc01043d0','work_entry':'0xc0104408',
                                        'virtual_queue_requests':timeout_work,'callback_page':word(0xc02c2e80),
                                        'stopped_before':'0xc0103808','driver_lock_held':True,'ioctl_outer_lock_held':False}
   # Independently replay the memory/timer scheduling fragment in video submit.
   # Prior mix remains stopped; this is not a claimed continuous hardware cycle.
   timer_active=word(0xc010416c);put(timer_active,0);put(0xc02532a8,1000)
   u.emu_start(0xc0104104,0x50000000,count=1000)
   assert u.reg_read(UC_ARM_REG_PC)==0xc010413c and len(lcd_timer_requests)==1 and word(timer_active)==1
   assert word(word(0xc0104168)+8)==1010
   u.emu_start(0xc0104104,0x50000000,count=1000)
   assert u.reg_read(UC_ARM_REG_PC)==0xc010413c and len(lcd_timer_requests)==1
   worker_result['isolated_video_timer_schedule']={'range':['0xc0104104','0xc010413c exclusive'],
                                                  'virtual_timer_requests':lcd_timer_requests,'jiffies_fixture':1000,
                                                  'expiry_delta_ticks':10,'already_active_second_run_did_not_rearm':True}
  if args.native_mix_prefix:
   mix_lock=word(0xc0103c88)
   if not args.native_driver_to_mix:
    put(mix_lock,1)
    u.reg_write(UC_ARM_REG_R0,0);u.reg_write(UC_ARM_REG_R1,0)
    u.reg_write(UC_ARM_REG_SP,0x60017000);u.reg_write(UC_ARM_REG_LR,0x50000000)
    u.emu_start(0xc010376c,0x50000000,count=10000)
   assert u.reg_read(UC_ARM_REG_PC)==0xc0103808
   assert word(0xc02c2e80)==page and word(mix_lock)==0
   worker_result['manual_mix_prefix']={'range':['0xc010376c','0xc0103808 exclusive'],
                                      'callback_page_after_native_transfer':word(0xc02c2e80),
                                      'mix_lock_fixture':hex(mix_lock),'mix_lock_held':True,
                                      'automatic_driver_to_mix_call_proven':args.native_driver_to_mix}
 if args.queued_work_after_submit:
  assert word(0xc02c28e4)==page
  worker_boundary=True
  # Other-owner fixture: original down_trylock failure path must skip LCD.
  # Execute both native failure helpers, replacing only waitqueue wakeup.
  saved_descriptor=bytes(u.mem_read(0xc02c21e0,52))
  put(0x60002004,0);put(0x60002008,0);contended_worker=True
  u.reg_write(UC_ARM_REG_R0,0x60001000);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
  u.emu_start(0xc01019f0,0x50000000,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==0x50000000
  assert word(0x60002004)==0 and word(0x60016004)==0
  assert bytes(u.mem_read(0xc02c21e0,52))==saved_descriptor and len(trylock_wakes)==1
  contended_worker=False;put(0x60002004,1) # Release other-owner fixture.
  u.reg_write(UC_ARM_REG_R0,0x60001000);u.reg_write(UC_ARM_REG_SP,0x60018000);u.reg_write(UC_ARM_REG_LR,0x50000000)
  u.emu_start(0xc01019f0,0x50000000,count=10000)
  assert u.reg_read(UC_ARM_REG_PC)==0xc0103d44
  assert word(0xc02c21e4)==address and word(0xc02c220c)==page and word(0xc02c2210)==1
  assert word(0x60002004)==0 and word(0x60002014)==word(0x60002024)==1
  worker_result={'page':page,'descriptor_base':hex(word(0xc02c21e4)),'update':1,'same_outer_lock_held':True,'stopped_before':'0xc0103d44','contended_first_attempt_skipped_lcd':True,'native_trylock_helpers_executed':True,'virtual_trylock_wakes':trylock_wakes}
 rows.append({'page':page,'input_request':payload,'lcd_descriptor_address_value':hex(address),'lcd_fields_at_1c_20_24_28_2c':observed,'page_locks_restored':True,'submit_lock_held_at_driver_boundary':True,'virtual_driver_calls':driver_calls,'native_readback_after_virtual_submit':readback,'native_ready_record':ready_record,'next_free_page_from_record':next_page,'injected_callback_page':page if args.virtual_completion_callback else None,'virtual_callback_services':callback_services,'readback_selector_0xc02c28e0':word(0xc02c28e0) if args.virtual_driver_roundtrip else None,'queued_worker_after_submit':worker_result})
report={'kernel_sha256':digest,'procedure':'0xc0101f80 qfb_ioctl ->0xc0102608 before LCD driver','cases':rows,'limits':['Original ioctl dispatcher, internal validation, global state writes and set_image_info_to_LCD execute continuously. User copy, info pointer, thread address limit and uncontended lock counters are virtual.','Physical base constants come from the original kernel image, but no physical addresses are dereferenced.','Stopped with outer submit lock held before mp200_lcd_set_fb_image_data; driver call, completion/unlock, MMIO, interrupts and actual concurrency remain unqualified.']}
if args.virtual_driver_roundtrip:
 report['limits'][-1]='LCD driver returns virtual success; native return/unlock/state-readback execute. No actual LCD/MMIO/interrupts, completion timing or concurrency.'
 report['limits'].append('Getter80044e03 selects state using globalc02c28e0, which remains0 here. Page1 submission is not immediately reflected in readback; writer/timing of that selector remain unresolved.')
 report['procedure']+='; virtual driver -> native return -> ioctl80044e03 readback'
if args.virtual_completion_callback:
 report['limits'][-1]='qfb_callback(page,0) is explicitly injected, and timer deletion/wakeup are virtual; original callback updates selector, state getter and readiness query execute. Free-bank path only; blocking wait, actual LCD completion source, timing and timer rearm remain unqualified.'
report_name='native-kernel-display-callback-readback.json' if args.virtual_completion_callback else 'native-kernel-display-roundtrip.json' if args.virtual_driver_roundtrip else 'native-kernel-display-chain.json'
if args.queued_work_after_submit:
 report_name='native-kernel-display-queued-after-submit.json'
 report['limits'].append('Worker is manually scheduled after virtual driver return, with original shared outer lock available. Stops before second LCD call; no actual concurrency, outstanding LCD completion or IRQ scheduling.')
if args.irq_completion:
 report_name='native-kernel-submit-irq-ready.json'
 report['procedure']+='; original IRQ/callback on register fixtures -> native readiness query'
 report['limits'][-1]='Original IRQ handler calls qfb_callback on supplied registers, then original getter/readiness execute. Interrupt disable, timer deletion and wakeup virtual; free-bank path only.'
 report['limits'].append('IRQ manually invoked with supplied pending/status/mode/page globals. Hardware interrupt-disable, timer deletion and wakeup virtual; no physical IRQ or proof that driver selected these registers/page.')
if args.native_driver_prefix:
 report_name='native-kernel-lcd-driver-prefix.json'
 report['procedure']+='; original LCD driver prefix through staged page assignment'
 report['limits'].append('Driver lock supplied available; actual driver stores page into staged global2e7c, not IRQ callback global2e80. Stops before update mode/trigger branch; no LCD MMIO, completion, unlock or hardware IRQ qualification.')
if args.native_mix_prefix:
 report_name='native-kernel-lcd-mix-page-transfer.json'
 report['limits'].append('After stopped driver prefix, mix_image is manually called with args0/0 and supplied available lock on separate simulated stack. Native code transfers staged page2e7c to callback page2e80. Stops before remaining mix/register operations; no automatic trigger or completion qualification.')
if args.native_driver_to_mix:
 report_name='native-kernel-driver-to-mix.json'
 report['procedure']='Original qfb_ioctl -> LCD driver update1 branch -> mix_image prefix, stopping at c0103808'
 report['limits']=['Original ioctl -> LCD driver update1 -> mix_image runs continuously with supplied available locks and default video globals0. Native branch transfers callback page; stops before remaining mix/register operations.',
                   'User copy and fd info are fixtures. No manual mix invocation or virtual LCD success is used in this mode.',
                   'At stop ioctl/driver/mix locks remain held; no physical trigger, IRQ, unlock or completion qualification.']
if args.native_deferred_submit:
 report_name='native-kernel-deferred-submit.json'
 report['procedure']='Original qfb_ioctl -> LCD driver with video1/timeout0 -> native return/unlock'
 report['limits']=['Video-related state1/timeout0 and available driver lock supplied. Original ioctl/driver return0, release locks and stage page without mix call or callback-page update.',
                   'User copy and fd info are fixtures. No LCD-success replacement in this mode; no subsequent video/timer trigger, MMIO, IRQ or frame completion qualification.']
if args.native_timeout_followup:
 report_name='native-kernel-deferred-timeout-mix.json'
 report['procedure']='Native deferred submit return -> manually scheduled original LCD timeout -> original queued work -> mix prefix'
 report['limits']=['Original submit, timeout callback, timeout flag update and queued work execute; queue_work service is simulated and work manually scheduled, available mix lock supplied.',
                   'Same native staged page reaches callback-page global. Stops before remaining mix/MMIO; no actual timer arrival, scheduler, hardware start or completion qualification.']
if args.native_mode_prefix:
 report_name='native-kernel-mode-request-prefix.json'
 report['procedure']='Original ioctl40044e0c validation and mode record setup, stopping before apply branch'
 report['limits']=['Mode config pointer/table are fixtures; user copy simulated. Payload1/0 selects table index1, sets record101/1/10.',
                   'Video flag remains supplied1 before apply; later configuration application is not executed. This does not prove the full request leaves video unchanged or disables it. No MMIO or hardware handoff.']
if args.native_brightness_boundary:
 report_name='native-kernel-brightness-request.json'
 report['procedure']='Original ioctl40044e0c -> original level-table lookup -> qfb_set_brightness boundary'
 report['limits']=['Level table100..105 and config pointer are fixtures; user copy simulated. Native original branch reaches qfb_set_brightness(101,1,10) when apply gate0.',
                   'Stopped before brightness implementation, backlight timer or hardware access. This corrects earlier generic display-mode naming; request is not shown to disable video.']
if args.native_video_stop:
 report_name='native-kernel-video-stop-mix.json'
 report['procedure']='Native deferred submit -> manually invoked original V4L2 image stop branch -> native mix prefix'
 report['limits']=['Video driver entry manually invoked with args0/0/0/0 after native deferred submit; timer deletion virtual, available mix lock supplied.',
                   'Original branch clears video/timeout state and calls mix on latest staged page. No userland-to-video-stop call origin, MMIO, lock release or display completion qualification.']
if args.native_v4l2_stop_caller:
 report_name='native-kernel-v4l2-stop-caller.json'
 report['procedure']='Native deferred submit -> manually invoked V4L2 lcd_call_func(operation0) -> original LCD stop -> mix prefix'
 report['limits']=['Original V4L2 wrapper zeroes image arguments and calls LCD stop; context/available wrapper and mix locks supplied, timer deletion virtual.',
                   'No userland stream-off/close origin proven; execution stops before mix hardware operations and before wrapper lock release. No physical frame completion qualification.']
if args.native_v4l2_stop_work:
 report_name='native-kernel-v4l2-stop-work.json'
 report['procedure']='Native deferred submit -> manually scheduled original V4L2 stop worker -> native operation0 wrapper -> LCD stop -> mix prefix'
 report['limits']=['Global V4L2 context/available locks supplied, stop worker manually scheduled, timer deletion virtual. Original worker selects operation0 itself.',
                   'No actual workqueue scheduling, userland stream-off/close origin, MMIO, lock release or physical completion qualification.']
if args.native_release_queue:
 report_name='native-kernel-v4l2-release-stop.json'
 report['procedure']='Original active-owner release -> virtual streamoff -> stop-work enqueue; manually pump original stop work -> LCD stop -> mix prefix'
 report['limits']=['File/private/context/current-owner pointers and available locks supplied. videobuf_streamoff returns virtual0 and queue_work virtual1; release stops after enqueue before remaining cleanup.',
                   'Queued work then manually scheduled. Original open registration binds stop worker at context+1cc (static instruction evidence); no actual workqueue or VFS/userland/APF close scheduling, MMIO or hardware completion qualification.']
if args.native_streamoff_queue:
 report_name='native-kernel-v4l2-streamoff-type1-stop.json' if args.streamoff_type==1 else 'native-kernel-v4l2-streamoff-stop.json'
 report['procedure']='Original V4L2 do_ioctl STREAMOFF40045613 -> virtual videobuf_streamoff -> stop-work enqueue; manually pump native stop work -> LCD stop -> mix prefix'
 report['limits']=[f'Decoded V4L2 request pointer, buffer type{args.streamoff_type}, active owner context and available locks supplied. videobuf_streamoff and queue acceptance simulated; ioctl stops after enqueue before remaining bookkeeping.',
                   'This is internal do_ioctl dispatch, not original user-copy wrapper or actual userspace/OpenMAX/APF request. Queued work manually scheduled; no MMIO or physical completion qualification.']
(ROOT/'sources'/report_name).write_text(json.dumps(report,indent=2)+'\n')
print('Two native submit/descriptor chains verified' + ('; original IRQ/callback on register fixtures releases opposite page in native ready query' if args.irq_completion else '; queued worker uses latest submitted page under shared outer lock, stopped before LCD' if args.queued_work_after_submit else '; injected original callback updates selector and native readback matches' if args.virtual_completion_callback else '; virtual driver return leaves getter on bank0' if args.virtual_driver_roundtrip else '; stopped before driver'))
