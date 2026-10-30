"""Replay original controller message copy/enqueue code; no player/device execution.

The message allocator, mutex/ticket/wakeup primitives are modeled. Request
validation, payload copies and controller enqueue execute pinned Sony code.
This is not playback completion or a public external-process endpoint.
"""
from pathlib import Path
import hashlib, io, json, struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
work = ROOT / 'work/stock-audio-requests'
work.mkdir(exist_ok=True)
stock = (ROOT / 'work/targets-jp/SpiderApp').read_bytes()
identity = hashlib.sha256(stock).hexdigest()
assert identity == '80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
elf = ELFFile(io.BytesIO(stock))
def original(address, count):
 for segment in elf.iter_segments():
  if segment['p_type'] == 'PT_LOAD' and segment['p_vaddr'] <= address and address + count <= segment['p_vaddr'] + segment['p_filesz']:
   offset = int(segment['p_offset'] + address - segment['p_vaddr'])
   return stock[offset:offset + count]
 raise AssertionError(hex(address))
def word(address): return struct.unpack('<I', original(address, 4))[0]
# Software requests use the exact same stable-state handlers as the native UI.
# They are NOT hardware evdev codes. Keep direction qualification separate from
# successful enqueue: the GUI handler itself discards the controller result.
request_map = []
for mode, descriptor, stable, expected in ((1, 0x3f1604, 5, (0x68a80, 0x68a48)),
                                           (2, 0x3f11e0, 2, (0x68040, 0x68078))):
 states = original(descriptor, 1)[0]
 count = struct.unpack('<H', original(descriptor + 6, 2))[0]
 transitions, handlers, pairs = (word(descriptor + off) for off in (8, 12, 16))
 for request, expected_handler in zip((0x440028, 0x440029), expected):
  matches = [word(pairs + row * 8 + 4) for row in range(count) if word(pairs + row * 8) == request]
  assert len(matches) == 1
  index = matches[0]
  resolved = [word(handlers + 4 * original(transitions + index * states + state, 1)[0]) for state in range(states)]
  assert resolved[stable - 1] == expected_handler
  assert all(handler == 0x67fc8 for state, handler in enumerate(resolved, 1) if state != stable)
  request_map.append(dict(mode=mode, stable_state=stable, request=hex(request), handler=hex(expected_handler)))
symbols = {symbol.name: symbol['st_value'] for section in elf.iter_sections()
           if section['sh_type'] in ('SHT_SYMTAB', 'SHT_DYNSYM')
           for symbol in section.iter_symbols()}
ticket_cancel = symbols['PltTicket_cancel']
stack, area, done = 0x70000000, 0x71000000, 0x72000000
controller, message, options, output = area, area + 0x1000, area + 0x2000, area + 0x2100
cases = []
for name, entry, operation, payload, request_type in [
    ('state-one', 0x27c890, 1, [0, 1], 0x12),
    ('state-two', 0x27c890, 2, [1, 1], 0x12),
    ('next', 0x27cbdc, -1, [1, 1], 0x15),
    ('previous', 0x27ccd0, -1, [1, 1000, 1, 1], 0x16),
]:
 for failure in ('none', 'invalid-options', 'allocation'):
  u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
  for segment in elf.iter_segments():
   if segment['p_type'] != 'PT_LOAD': continue
   start = int(segment['p_vaddr']); base = start & ~4095
   u.mem_map(base, (start - base + int(segment['p_memsz']) + 4095) & ~4095)
   u.mem_write(start, segment.data())
  u.mem_map(stack, 65536); u.mem_map(area, 16384); u.mem_map(done, 4096)
  def put(address, value): u.mem_write(address, struct.pack('<I', value & 0xffffffff))
  def get(address): return struct.unpack('<I', u.mem_read(address, 4))[0]
  put(controller + 0x10, 6); put(controller + 0x2c, controller + 0x28)
  values = payload.copy()
  if failure == 'invalid-options': values[-1] = 0
  u.mem_write(options, struct.pack('<' + 'I' * len(values), *values)); put(output, 0xa5a5a5a5)
  allocated = []; wakes = []
  def finish(value=0):
   u.reg_write(UC_ARM_REG_R0, value); u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
  def hook(uc, pc, size, data):
   if pc == done: uc.emu_stop(); return
   if pc == 0x27c378:
    assert uc.reg_read(UC_ARM_REG_R0) == controller
    assert uc.reg_read(UC_ARM_REG_R2) == request_type
    allocated.append(request_type)
    if failure == 'allocation': finish(0x2604); return
    put(message + 0xc, request_type); put(uc.reg_read(UC_ARM_REG_R3), message)
    finish(); return
   if pc in (0x335788, 0x3357e4, ticket_cancel): finish(); return
   if pc == 0x3354f4: wakes.append(pc); finish(); return
  u.hook_add(UC_HOOK_CODE, hook)
  sp = stack + 65520
  u.reg_write(UC_ARM_REG_SP, sp); u.reg_write(UC_ARM_REG_LR, done)
  for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3),
                        (controller, 0x1234, operation, options)):
   u.reg_write(reg, value & 0xffffffff)
  put(sp, output)
  u.emu_start(entry, done + 4, count=200000)
  assert u.reg_read(UC_ARM_REG_PC) == done
  rc = u.reg_read(UC_ARM_REG_R0)
  expected = {'none': 0, 'invalid-options': 0x102, 'allocation': 0x2604}[failure]
  assert rc == expected, (name, failure, hex(rc))
  if failure != 'none':
   assert get(output) == 0xa5a5a5a5 and get(controller + 0x28) == 0 and not wakes
   assert len(allocated) == int(failure == 'allocation')
  else:
   assert get(output) == 7 and get(controller + 0x10) == 7
   assert get(controller + 0x28) == message and get(controller + 0x2c) == message
   assert get(message) == 0 and get(message + 4) == 7 and len(wakes) == 1
   assert get(message + 0x10) == message + 0x14
   assert get(message + 0x14) == operation & 0xffffffff
   copied = bytes(u.mem_read(message + 0x28, len(payload) * 4))
   assert copied == struct.pack('<' + 'I' * len(payload), *payload)
   assert get(message + 0x24) == message + 0x28
   pair = payload[-2:]
   assert bytes(u.mem_read(message + 0x1c, 8)) == struct.pack('<II', *pair)
   assert get(message + 0x18) == message + 0x1c
   u.mem_write(options, b'\xa5' * (len(payload) * 4))
   assert bytes(u.mem_read(message + 0x28, len(payload) * 4)) == copied
  cases.append(dict(case=name, failure=failure, result=rc, allocations=len(allocated), wakes=len(wakes)))
report = dict(passed=True, stock_sha256=identity, device_accessed=False,
              original_validation_copy_enqueue=True, playback_completed=False,
              software_request_map=request_map,
              modeled=['allocator', 'mutex', 'ticket cancellation', 'worker wakeup'], cases=cases,
              source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(work / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
