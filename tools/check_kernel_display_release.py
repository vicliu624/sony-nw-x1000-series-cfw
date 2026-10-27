"""Stock QFB release callback with virtual timer services, not physical close."""
from pathlib import Path
import hashlib, io, json, struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT/'work/upg-jp/verified-1.bin').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
elf = ELFFile(io.BytesIO((ROOT/'work/isolation-audit/x1000-kernel-analysis.elf').read_bytes()))
assert elf.get_section_by_name('.kernel').data() == raw
rows = []
for opens in (0, 1, 2, 3):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    for s in elf.iter_segments():
        if s['p_type'] == 'PT_LOAD':
            low=s['p_vaddr']&~4095; high=(s['p_vaddr']+s['p_memsz']+4095)&~4095
            u.mem_map(low, high-low); u.mem_write(s['p_vaddr'], s.data())
    u.mem_map(0x60000000, 0x20000)
    def put(p,v): u.mem_write(p,struct.pack('<I',v))
    def word(p): return struct.unpack('<I',u.mem_read(p,4))[0]
    # Verify fb_ops really routes its release slot to the function under test.
    assert word(0xc0270ea4+8) == 0xc0101218
    put(0x60001234,0x60002000); put(0x60002000,opens)
    put(0xc02532a8,1000)  # Simulated jiffies, no real timer scheduling.
    flags=(0xc02c28ec,0xc02c28e8,0xc02c28d8,0xc02c28dc,0xc02c28e0,0xc02c28e4)
    for p in flags: put(p,7)
    calls=[]; work_requests=[]; lcd_requests=[]; sentinel=0x6001f000
    def hook(uc,pc,size,data):
        if pc==sentinel: uc.emu_stop(); return
        if pc==0xc0103d44:
            assert uc.reg_read(UC_ARM_REG_R0)==0xc02c21e0
            lcd_requests.append({'descriptor_base':hex(word(0xc02c21e4)),
                                 'page':word(0xc02c220c),'update':word(0xc02c2210)})
            uc.emu_stop(); return
        if pc==0xc00f5ce4:
            dst=uc.reg_read(UC_ARM_REG_R0); src=uc.reg_read(UC_ARM_REG_R1)
            assert src==0x60003000 and uc.reg_read(UC_ARM_REG_R2)==8
            uc.mem_write(dst,bytes(uc.mem_read(src,8)))
            uc.reg_write(UC_ARM_REG_R0,0)
            uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR)); return
        if pc==0xc004ffa8:
            assert uc.reg_read(UC_ARM_REG_R0)==0xc02c2444
            calls.append('del_timer'); result=0
        elif pc==0xc005012c:
            assert uc.reg_read(UC_ARM_REG_R0)==0xc02c2444
            assert uc.reg_read(UC_ARM_REG_R1)==1006
            calls.append('__mod_timer'); result=0
        elif pc==0xc0058398:
            assert uc.reg_read(UC_ARM_REG_R0)==0x60004000
            assert uc.reg_read(UC_ARM_REG_R1)==0x60002038
            work_requests.append({'queue':hex(0x60004000),'work':hex(0x60002038)})
            result=1
        else: return
        uc.reg_write(UC_ARM_REG_R0,result)
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    u.reg_write(UC_ARM_REG_R0,0x60001000); u.reg_write(UC_ARM_REG_SP,0x60018000)
    u.reg_write(UC_ARM_REG_LR,sentinel)
    u.emu_start(0xc0101218,0,count=2000)
    assert u.reg_read(UC_ARM_REG_PC)==sentinel
    assert word(0x60002000)==max(0,opens-1)
    assert u.reg_read(UC_ARM_REG_R0)==(0xffffffea if opens==0 else 0)
    assert calls==(['del_timer','__mod_timer'] if opens==1 else [])
    assert [word(p) for p in flags]==([1,0,0,0,0,0] if opens==1 else [7]*6)
    if opens==1:
        assert word(0xc02c2464)==60 and word(0xc02c244c)==1006 and word(0xc02c28f0)==1
    row={'open_count_fixture':opens,'remaining':word(0x60002000),'timer_calls':calls[:],
         'flags_after':[word(p) for p in flags]}
    if opens==1:
        # Probe writes timeout_update into this timer's function slot: native
        # literal-load/store pair, not the separately named backlight timer.
        assert word(0xc0018274)==0xc02c2444
        assert word(0xc0018278)==0xc01018cc
        assert word(0xc00180d4)==0xe59f319c and word(0xc00180dc)==0xe5813010
        # Reopening the native fb_ops callback does not cancel the timer or
        # initialize page state. Verify that before manually pumping timeout.
        assert word(0xc0270ea4+4)==0xc0101184
        state_before=bytes(u.mem_read(0xc02c28d8,28))
        calls.clear()
        u.reg_write(UC_ARM_REG_R0,0x60001000)
        u.reg_write(UC_ARM_REG_SP,0x60018000); u.reg_write(UC_ARM_REG_LR,sentinel)
        u.emu_start(0xc0101184,0,count=200)
        assert u.reg_read(UC_ARM_REG_PC)==sentinel and u.reg_read(UC_ARM_REG_R0)==0
        assert word(0x60002000)==1 and calls==[]
        assert bytes(u.mem_read(0xc02c28d8,28))==state_before
        assert word(0xc02c28f0)==1 and word(0xc02c244c)==1006
        row['reopen_before_timeout']={'entry':'0xc0101184','remaining':1,
                                     'timer_calls':[],'page_flags_unchanged':True,
                                     'timer_active':1,'expires_fixture':1006}
        put(0x60002034,0x60004000)
        calls.clear()
        u.reg_write(UC_ARM_REG_R0,0x60001000)
        u.reg_write(UC_ARM_REG_SP,0x60018000); u.reg_write(UC_ARM_REG_LR,sentinel)
        u.emu_start(0xc01018cc,0,count=3000)
        assert u.reg_read(UC_ARM_REG_PC)==sentinel
        assert calls==['del_timer','__mod_timer'] and len(work_requests)==1
        assert word(0x60016004)==0 and word(0xc02c28f0)==1
        row['timeout_after_close_and_reopen']={'entry':'0xc01018cc','timer_calls':calls[:],
                                       'work_requests':work_requests,'timer_active_after':word(0xc02c28f0)}
        # Manually pump the queued work only to the LCD driver boundary.
        # Semaphore is a supplied available-state fixture; no hardware call.
        put(0x60002004,1)
        put(0x60002014,1); put(0x60002024,1)
        u.reg_write(UC_ARM_REG_R0,0x60001000)
        u.reg_write(UC_ARM_REG_SP,0x60018000); u.reg_write(UC_ARM_REG_LR,sentinel)
        u.emu_start(0xc01019f0,0,count=3000)
        assert u.reg_read(UC_ARM_REG_PC)==0xc0103d44
        assert lcd_requests==[{'descriptor_base':'0x33000000','page':0,'update':1}]
        row['background_work_before_lcd']={'entry':'0xc01019f0','stopped_before':'0xc0103d44',
                                          'requests':lcd_requests}
        # Stock userspace init explicitly sends this request after open/mmap.
        # Unlike open alone, [0,33] cancels the timeout and disables rearming.
        u.mem_write(0x60003000,struct.pack('<2I',0,33))
        put(0x60016008,0xffffffff); put(0x60018000,0x60001000)
        calls.clear()
        u.reg_write(UC_ARM_REG_R2,0x80044e04); u.reg_write(UC_ARM_REG_R3,0x60003000)
        u.reg_write(UC_ARM_REG_SP,0x60018000); u.reg_write(UC_ARM_REG_LR,sentinel)
        u.emu_start(0xc0101f80,0,count=3000)
        assert u.reg_read(UC_ARM_REG_PC)==sentinel
        assert u.reg_read(UC_ARM_REG_R0)==0 and calls==['del_timer']
        assert word(0xc02c28f0)==0 and word(0xc02c28ec)==0 and word(0xc02c2464)==33
        row['stock_init_timeout_request']={'request':'0x80044e04','payload':[0,33],
                                          'timer_calls':calls[:],'timer_active_after':0,
                                          'periodic_mode_after':0,'period_after':33}
        # A queued worker can still run after the timer has been disabled.
        # Prior worker stopped before driver; restore uncontended semaphore
        # fixture instead of pretending that driver completed.
        for off in (4,0x14,0x24): put(0x60002000+off,1)
        lcd_requests.clear(); calls.clear()
        u.reg_write(UC_ARM_REG_R0,0x60001000)
        u.reg_write(UC_ARM_REG_SP,0x60018000); u.reg_write(UC_ARM_REG_LR,sentinel)
        u.emu_start(0xc01019f0,0,count=3000)
        assert u.reg_read(UC_ARM_REG_PC)==0xc0103d44
        assert lcd_requests==[{'descriptor_base':'0x33000000','page':0,'update':1}]
        assert word(0xc02c28ec)==0 and word(0xc02c28f0)==0
        row['queued_worker_after_timer_disable']={
            'entry':'0xc01019f0','stopped_before':'0xc0103d44','periodic_mode':0,
            'timer_active':0,'requests':lcd_requests[:],
            'fixture':'Available semaphores restored; earlier stopped LCD call is not treated as completed.'}
    rows.append(row)
report={'kernel_sha256':digest,'callback':'0xc0101218','cases':rows,
        'finding':'Last close resets QFB flags and rearms timeout_update; non-last close only decrements count. Native open increments count without cancelling timer or clearing flags. Replayed timeout after reopen still queues work and rearms. No completion-wait service is called in release.',
        'limits':['Open count and jiffies are fixtures; timer and workqueue services are virtual. timeout_update and its queued work are manually invoked; work stops before LCD driver with an available semaphore fixture. No VFS close, IRQ, MMIO or panel execution.',
                  'This does not prove a submitted frame completed or that last close is the normal inter-application handoff case.']}
(ROOT/'sources/native-kernel-display-release.json').write_text(json.dumps(report,indent=2)+'\n')
print('Four stock QFB release cases passed: last-close flag reset/timer rearm differs from shared-open close')
