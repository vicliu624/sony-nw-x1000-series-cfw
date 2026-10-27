"""Replay original readdir64 with synthetic DIR state and virtual getdents64."""
from pathlib import Path
import gzip, hashlib, io, json, struct, tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_INTR
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_SP

ROOT = Path(__file__).resolve().parents[1]
packed = (ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(packed).hexdigest() == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
    binary = tar.extractfile('./lib/libc-2.3.3.so').read()
elf = ELFFile(io.BytesIO(binary))
symbols = {s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
base = 0x1000000
segments = [s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
low = min(s['p_vaddr'] for s in segments)&~4095
high = (max(s['p_vaddr']+s['p_memsz'] for s in segments)+4095)&~4095

def record(inode, name):
    text = name.encode()+b'\0'
    length = (19+len(text)+7)&~7
    return struct.pack('<QQHB', inode, 123, length, 8)+text+bytes(length-19-len(text))

rows = []
for case in ('buffered', 'skip-zero-inode', 'refill', 'eof', 'EIO', 'ENOENT'):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(base+low, high-low)
    for segment in segments:
        u.mem_write(base+segment['p_vaddr'], segment.data())
    u.mem_map(0x60000000, 0x20000)
    end, errno, directory, buffer = 0x60000100, 0x60001000, 0x60002000, 0x60003000
    # Literal-derived thread lock callback cells. Disable callbacks in this
    # single-thread fixture only; dynamic relocations/threads are not tested.
    callbacks = base+0x7d448+0x85bb8+0x3618
    u.mem_write(callbacks+108, bytes(4)); u.mem_write(callbacks+116, bytes(4))
    payload = record(0x100000011, 'app.ini')
    prefix = record(0, 'deleted') if case=='skip-zero-inode' else b''
    buffered = case in ('buffered', 'skip-zero-inode')
    u.mem_write(buffer, prefix+payload)
    u.mem_write(directory, struct.pack('<IIIIII', 42, buffer, 4096, len(prefix+payload) if buffered else 0, 0, 0))
    u.mem_write(errno, struct.pack('<I', 77))
    requests = []
    def code(uc, pc, size, unused):
        if pc == base+symbols['__errno_location']:
            uc.reg_write(UC_ARM_REG_R0, errno)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    def intr(uc, interrupt, unused):
        instruction = struct.unpack('<I', uc.mem_read(uc.reg_read(UC_ARM_REG_PC)-4, 4))[0]
        assert instruction == 0xef9000d9
        assert uc.reg_read(UC_ARM_REG_R0)==42 and uc.reg_read(UC_ARM_REG_R1)==buffer and uc.reg_read(UC_ARM_REG_R2)==4096
        requests.append(217)
        assert len(requests)==1
        if case=='refill':
            uc.mem_write(buffer, payload); result=len(payload)
        else:
            result={'eof':0, 'EIO':-5, 'ENOENT':-2}[case]
        uc.reg_write(UC_ARM_REG_R0, result&0xffffffff)
    u.hook_add(UC_HOOK_CODE, code); u.hook_add(UC_HOOK_INTR, intr)
    for reg, value in ((UC_ARM_REG_R0,directory),(UC_ARM_REG_SP,0x6001f000),(UC_ARM_REG_LR,end)):
        u.reg_write(reg,value)
    u.emu_start(base+symbols['readdir64'],end,count=10000)
    assert u.reg_read(UC_ARM_REG_PC)==end
    result = u.reg_read(UC_ARM_REG_R0)
    expected = buffer+len(prefix) if buffered else buffer if case=='refill' else 0
    assert result==expected
    if result:
        assert bytes(u.mem_read(result+19,8))==b'app.ini\0'
        assert struct.unpack('<Q',u.mem_read(result,8))[0]==0x100000011
    observed_errno=struct.unpack('<I',u.mem_read(errno,4))[0]
    assert observed_errno==(5 if case=='EIO' else 77)
    rows.append({'case':case,'returned_entry':bool(result),'errno':observed_errno,'virtual_OABI_calls':requests})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'libc_sha256':hashlib.sha256(binary).hexdigest(),'cases':rows,'record_name_offset':19,'record_reclen_offset':16,'limits':['Synthetic DIR and kernel records, not real opendir/getdents or filesystem behavior.','Single-thread lock callbacks disabled; dynamic loader and threading unqualified.','No device program execution or firmware changes.']}
(ROOT/'sources/native-stock-readdir64.json').write_text(json.dumps(report,indent=2)+'\n')
print('Original readdir64: six bounded replay cases passed.')
