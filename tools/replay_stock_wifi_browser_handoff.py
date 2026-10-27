"""Replay command-21 completion through browser relay to stock connection entry.

Coordinator drain completion and browser mode2/state1 are supplied preconditions.
Manager queries, event delivery and diagnostics are virtual. No real IPC/radio.
"""
from pathlib import Path
import hashlib, io, json, struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
u.mem_map(0x8000, 0x900000)
for s in ELFFile(io.BytesIO(raw)).iter_segments():
    if s['p_type'] == 'PT_LOAD': u.mem_write(s['p_vaddr'], s.data())
u.mem_map(0x2000000, 0x20000)
end, coordinator, browser, config = 0x2000100, 0x2001000, 0x2002000, 0x2003000
def get(a): return struct.unpack('<I', u.mem_read(a, 4))[0]
def put(a, n): u.mem_write(a, struct.pack('<I', n))
put(coordinator + 4, 21)
context = bytearray(32); context[0:2] = bytes([2, 1]); context[13] = 6
struct.pack_into('<I', context, 4, 0x3ef680)
u.mem_write(browser, bytes(context))
events, manager_calls, entered, switches = [], [], [], []
def cstr(a): return bytes(u.mem_read(a, 256)).split(b'\0')[0].decode('ascii')
def hook(uc, pc, size, unused):
    regs = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
    result = 0
    if pc == end: uc.emu_stop(); return
    if pc == 0xa57f0: events.append(regs)
    elif pc == 0x265510: result = 0x2008000
    elif pc == 0x2680a8: manager_calls.append({'operation': 'manager mode request', 'mode': regs[1]})
    elif pc == 0x267b94: put(regs[1], 0)  # modeled manager query output
    elif pc == 0x26534c: pass  # manager callback registration boundary
    elif pc == 0x2664d0:
        assert cstr(regs[1]) == 'netfront'
        put(regs[2], 20001)  # modeled name lookup result
    elif pc == 0x2681e8:
        assert regs[2] and get(regs[2]+4) == 0
        switches.append({'target': regs[1], 'mode': regs[3], 'argv': [cstr(get(regs[2]))]})
    elif pc == 0xd85c:
        uc.mem_write(regs[0], bytes(uc.mem_read(regs[1], regs[2]))); result = regs[0]
    elif pc == 0x7fb48: result = config
    elif pc in (0xff5c, 0xb00bc, 0x33b83c, 0x33b918, 0x17c42c, 0x140b4): pass
    elif pc == 0x615d8: entered.append(hex(pc)); return
    else: return
    uc.reg_write(UC_ARM_REG_R0, result)
    uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
def reject(*args): raise AssertionError('Unexpected system instruction')
u.hook_add(UC_HOOK_CODE, hook); u.hook_add(UC_HOOK_INTR, reject)
def call(pc, r0, r1=0, r2=0, r3=0):
    for reg, value in ((UC_ARM_REG_R0,r0),(UC_ARM_REG_R1,r1),(UC_ARM_REG_R2,r2),(UC_ARM_REG_R3,r3),(UC_ARM_REG_SP,0x201f000),(UC_ARM_REG_LR,end)):
        u.reg_write(reg,value)
    u.emu_start(pc, end, count=20000)
    assert u.reg_read(UC_ARM_REG_PC) == end
call(0x10ee4, coordinator)
assert events == [[0x410201, 0, 0, 0]]
header = events.pop()
call(0x17c608, browser, *header[:3])
assert entered == ['0x615d8']
assert list(u.mem_read(browser,2)) == [3,1]
assert events == [[0x4c9002,0,0,0]]
assert get(0x65fe30+60) == 2
parameters = [get(config+0x1764+i*4) for i in range(4)]
assert parameters == [51,2,0x4a012c,6]
handoff_events = list(events)
call(0xb0108, 0)  # original argument-vector initialization
returns = []
for outcome in (0,5):
    events.clear(); switches.clear()
    call(0x73ec8, 0, 0x4a012c, outcome)
    assert events == [[0x410304,0,0,0]]
    before = bytes(u.mem_read(browser,32))
    call(0x17c608, browser, *events.pop()[:3])
    assert switches == [{'target':20001,'mode':0,'argv':['--restart']}]
    assert list(u.mem_read(browser,2)) == [3,3]
    returns.append({'supplied_connection_result':outcome,'relay_event':'0x410304','switch':list(switches),'relay_state_after':[3,3]})
    u.mem_write(browser,before)
report = {'passed':True,'SpiderApp_sha256':digest,'coordinator_completion':'0x10ee4',
          'supplied_command':21,'completion_event':hex(header[0]),'original_relay_action':entered,
          'browser_state_before':[2,1],'browser_state_after':[3,1],
          'manager_calls':manager_calls,'stock_connection_event':hex(handoff_events[0][0]),'return_cases':returns,
          'stored_connection_context':{'field_1764':51,'field_1768':2,'return_event':'0x4a012c','field_1770':6},
          'physical_device_or_ipc':False,'limits':[
              'Coordinator prerequisites/drain completion and initial browser state supplied; full startup reachability not proven.',
              'Manager mode/query results modeled; event posts captured and one relay event delivered explicitly.',
              'Connection event consumer and AP selection not executed; result supplied directly to callback 0x73ec8.',
              'Return callback and restart argument construction execute; manager lookup/switch intercepted.',
              'Result-code meanings and NetFront restart handling are not proven by this replay alone.']}
(ROOT/'sources/stock-wifi-browser-handoff.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
