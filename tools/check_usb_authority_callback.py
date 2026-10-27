"""Bounded stock USB ioctl -> MSC callback replay; no kernel/device execution."""
from pathlib import Path
import hashlib, io, json, struct, tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tar:
    modules = [tar.extractfile('./lib/modules/' + n).read() for n in ('icx1087_usbconn.ko', 'g_nwm_msc.ko')]

def relocated_text(binary, base):
    elf = ELFFile(io.BytesIO(binary))
    text = bytearray(elf.get_section_by_name('.text').data())
    symbols = elf.get_section_by_name('.symtab')
    for relocation in elf.get_section_by_name('.rel.text').iter_relocations():
        symbol = symbols.get_symbol(relocation['r_info_sym'])
        if relocation['r_info_type'] != 1 or not isinstance(symbol['st_shndx'], int):
            continue
        if elf.get_section(symbol['st_shndx']).name != '.text':
            continue
        offset = relocation['r_offset']
        word = struct.unpack_from('<I', text, offset)[0]
        addend = (word & 0xffffff) << 2
        if addend & 0x2000000:
            addend -= 0x4000000
        displacement = symbol['st_value'] + addend - offset
        struct.pack_into('<I', text, offset, (word & 0xff000000) | ((displacement >> 2) & 0xffffff))
    return elf, text

conn_base, msc_base = 0x100000, 0x200000
conn_elf, conn = relocated_text(modules[0], conn_base)
msc_elf, msc = relocated_text(modules[1], msc_base)
assert struct.unpack_from('<I', conn, 0x800)[0] == 0x40046703
assert struct.unpack_from('<I', msc, 0x4b74)[0] == 0xe5c5403f
# Only this callback's global-pointer literal is needed. Binding/global state are fixtures.
struct.pack_into('<I', msc, 0x4b7c, 0x400000)
struct.pack_into('<I', conn, 0xa0c, 0x400100)
rows = []
for name, request, initial, final, change, old_status, expected_callbacks in [
        ('allow', 0x40046702, 0, 1, None, 1, [1]),
        ('prohibit-keeps-PC', 0x40046703, 1, 1, None, 1, [2]),
        ('prohibit-keeps-APL', 0x40046703, 0, 0, None, 1, [2]),
        ('disconnect-retains-authority', None, 1, 1, 0, 1, []),
        ('new-start-connect-resets-authority', None, 1, 0, 4, 0, [0]),
        ('connected-resets-authority', None, 1, 0, 1, 4, [0])]:
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    for base, code in ((conn_base, conn), (msc_base, msc)):
        u.mem_map(base, 0x20000)
        u.mem_write(base, bytes(code))
    u.mem_map(0x400000, 0x20000)
    write = lambda address, value: u.mem_write(address, struct.pack('<I', value))
    file, device, table, fsg, end = 0x401000, 0x402000, 0x403000, 0x404000, 0x405000
    write(file + 128, device)
    write(device + 104, table)
    write(table, msc_base + 0x4b40)
    write(0x400000, fsg)
    write(0x400100, device)
    write(device + 112, old_status)
    write(device + 116, 2)
    u.mem_write(fsg + 63, bytes([initial]))
    callbacks = []
    def hook(uc, pc, size, unused):
        if pc == end:
            uc.emu_stop()
        elif pc == msc_base + 0x4b40:
            callbacks.append(uc.reg_read(UC_ARM_REG_R0))
        elif pc in (msc_base + 0x4b60, conn_base + 0x964, conn_base + 0xa00):
            # Skip printk call only; preserve function's saved argument in r4.
            uc.reg_write(UC_ARM_REG_PC, pc + 4)
    u.hook_add(UC_HOOK_CODE, hook)
    for reg, value in ((UC_ARM_REG_R0, 0), (UC_ARM_REG_R1, file), (UC_ARM_REG_R2, request),
                       (UC_ARM_REG_R3, 0), (UC_ARM_REG_SP, 0x41f000), (UC_ARM_REG_LR, end)):
        u.reg_write(reg, value if value is not None else 0)
    if change is not None:
        u.reg_write(UC_ARM_REG_R0, change)
    u.emu_start(conn_base + (0x89c if change is not None else 0x688), end, count=1000)
    assert u.reg_read(UC_ARM_REG_PC) == end and u.reg_read(UC_ARM_REG_R0) == 0
    state = struct.unpack('<I', u.mem_read(device + 116, 4))[0]
    authority = bytes(u.mem_read(fsg + 63, 1))[0]
    assert callbacks == expected_callbacks
    assert state == (callbacks[0] if callbacks else 2) and authority == final
    rows.append({'case': name, 'request': hex(request) if request is not None else None,
                 'supplied_old_usb_status': old_status, 'usb_status_change': change, 'initial_authority': initial,
                 'connection_state': state, 'callback_arguments': callbacks, 'final_authority': authority})
report = {'module_sha256': [hashlib.sha256(m).hexdigest() for m in modules], 'cases': rows,
          'all_passed': True, 'physical_device_access': False,
          'limits': ['RAM supplies file/device objects, bound callback pointer and MSC singleton; no full module initialization.',
                     'Original ARM ioctl/status-change/callback bodies execute with local branch relocations; printk and wake-up delivery are skipped.',
                     'No physical USB, backing-volume I/O, unmount, or application-manager execution.']}
(ROOT / 'sources/native-usb-authority-callback.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
