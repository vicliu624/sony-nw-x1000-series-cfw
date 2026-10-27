"""Original AppList parser -> command builder -> proxy exec argument contract.

Only libc/stdio/account/allocation services are virtual. No executable is run.
"""
from pathlib import Path
import hashlib
import io
import json
import struct
import argparse,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                              UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT / 'work/targets-jp/sysmgrd').read_bytes()
digest = hashlib.sha256(raw).hexdigest()
assert digest == '131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
elf = ELFFile(io.BytesIO(raw))
syms = {s.name: s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
frontend = '/contents/HOMEBREW/launcher/app'
proxy_raw = (ROOT / 'work/targets-jp/appproxy').read_bytes()
proxy_digest = hashlib.sha256(proxy_raw).hexdigest()
assert proxy_digest == '57fae7071cbeed2421ea8ac12f432e8605f475de86f04da3a4abd2f197a76479'
proxy_elf = ELFFile(io.BytesIO(proxy_raw))
proxy_syms = {s.name: s['st_value'] for s in proxy_elf.get_section_by_name('.dynsym').iter_symbols()}
fragment = (ROOT / 'work/home-entry-candidate/AppList.fragment.NOT_INSTALLED').read_text()
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--full-config',action='store_true');options=parser.parse_args()
scenarios=[('duplicate-executable-control',f'0x00030001 * {frontend} {frontend} --native\n'),('generated',fragment)]
if options.full_config:
    archive=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
    assert hashlib.sha256(archive).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
    with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
        stock=tar.extractfile('./etc/AppList.conf').read().decode('ascii')
        passwd=tar.extractfile('./etc/passwd').read().decode('ascii')
    assert 'app:x:100:100:' in passwd
    scenarios += [('full-stock',stock),('full-merged',stock+('' if stock.endswith('\n') else '\n')+fragment)]
    merged_path=ROOT/'work/home-entry-candidate/overlay/etc/AppList.conf'
    if merged_path.exists():assert merged_path.read_text()==scenarios[-1][1]
rows = []
for name,line in scenarios:
    expected=[text.split() for text in line.splitlines() if text.strip() and not text.lstrip().startswith('#')]
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.mem_map(0x8000, 0x40000)
    for segment in elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            u.mem_write(segment['p_vaddr'], segment.data())
    u.mem_map(0x50000000, 4096)
    u.mem_map(0x60000000, 0x20000)
    position = 0
    def put(address, value):
        u.mem_write(address, struct.pack('<I', value))
    def word(address):
        return struct.unpack('<I', u.mem_read(address, 4))[0]
    def cstr(address):
        result = bytearray()
        while True:
            c = bytes(u.mem_read(address, 1))
            if c == b'\0':
                return bytes(result)
            result.extend(c)
            address += 1
    data_bytes = line.encode('ascii')
    def hook(uc, pc, size, data):
        global position
        a = [uc.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        result = 0
        if pc == syms['fopen']:
            result = 77
        elif pc == syms['fgetpos']:
            put(a[1], position)
        elif pc == syms['fsetpos']:
            position = word(a[1])
        elif pc == syms['fseek']:
            assert a[1:3] == [0, 0]
            position = 0
        elif pc == syms['fgets']:
            if position < len(data_bytes):
                end = data_bytes.find(b'\n', position)
                end = len(data_bytes) if end < 0 else end + 1
                piece = data_bytes[position:min(end, position + a[1] - 1)]
                uc.mem_write(a[0], piece + b'\0')
                position += len(piece)
                result = a[0]
        elif pc == syms['malloc']:
            assert a[0] == 0x510*len(expected)
            result = 0x60004000
        elif pc==syms['getpwnam']:
            assert cstr(a[0])==b'app';put(0x60016008,100);put(0x6001600c,100);result=0x60016000
        elif pc == syms['memcpy']:
            uc.mem_write(a[0], bytes(uc.mem_read(a[1], a[2])))
            result = a[0]
        elif pc == syms['__strtok_r']:
            cursor = a[0] or word(a[2])
            separators = cstr(a[1])
            while bytes(uc.mem_read(cursor, 1))[0] in separators:
                cursor += 1
            start = cursor
            while bytes(uc.mem_read(cursor, 1)) != b'\0' and bytes(uc.mem_read(cursor, 1))[0] not in separators:
                cursor += 1
            if bytes(uc.mem_read(cursor, 1)) != b'\0':
                uc.mem_write(cursor, b'\0')
                cursor += 1
            put(a[2], cursor)
            result = start if cstr(start) else 0
        elif pc == syms['__strtol_internal']:
            result = int(cstr(a[0]), 0)
        elif pc == syms['strlen']:
            result = len(cstr(a[0]))
        elif pc == syms['strcmp']:
            result = 0 if cstr(a[0]) == cstr(a[1]) else 1
        elif pc in (0x1c888, 0x1c8c8):
            raise AssertionError('Original parser rejected fixture')
        elif pc not in (syms['getuid'], syms['getgid'], syms['fclose']):
            return
        uc.reg_write(UC_ARM_REG_R0, result)
        uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE, hook)
    def call(pc, a, b, c=0):
        for reg, value in [(UC_ARM_REG_R0, a), (UC_ARM_REG_R1, b), (UC_ARM_REG_R2, c),
                           (UC_ARM_REG_SP, 0x60018000), (UC_ARM_REG_LR, 0x50000000)]:
            u.reg_write(reg, value)
        u.emu_start(pc, 0x50000000, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == 0x50000000
        return u.reg_read(UC_ARM_REG_R0)
    u.mem_write(0x60001000, b'/fixture/AppList.conf\0')
    assert call(0x1574c, 0x60002000, 0x60001000) == 0
    if name.startswith('full-'):
        assert word(0x60002000)==len(expected)
        records=[]
        for index,tokens in enumerate(expected):
            record=0x60004000+index*0x510
            app_id=int(tokens[0],0);assert word(record)==app_id and cstr(record+4).decode()==tokens[2]
            uid=100 if tokens[1]=='app' else 0
            assert word(record+0x508)==uid and word(record+0x50c)==uid
            vector=call(0x10f64,0,record);command=[]
            for i in range(8):
                pointer=word(vector+4*i)
                if not pointer:break
                command.append(cstr(pointer).decode())
            assert command==(['appproxy'] if app_id>>16==3 else [])+tokens[2:]
            records.append({'id':hex(app_id),'name':tokens[2],'uid':uid,'gid':uid,'command':command})
        rows.append({'case':name,'records':records});continue
    assert word(0x60002000) == 1 and word(0x60004000) == 0x30001
    assert cstr(0x60004004).decode() == frontend
    argv, at = [], 0x60004108
    for _ in range(word(0x60004104)):
        token = cstr(at)
        argv.append(token.decode())
        at += len(token) + 1
    u.mem_write(0x60001000, frontend.encode() + b'\0')
    assert call(0x117d8, 0x60002000, 0x60001000, 0x60003000) == 0
    assert word(0x60003000) == 0x30001
    assert argv == ([frontend, '--native'] if name.startswith('duplicate') else ['--native']), argv
    vector = call(0x10f64, 0, 0x60004000)
    command = []
    for i in range(8):
        pointer = word(vector + i * 4)
        if not pointer:
            break
        command.append(cstr(pointer).decode())
    assert command == ['appproxy', frontend] + argv
    p = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    p.mem_map(0x8000, 0x20000)
    for segment in proxy_elf.iter_segments():
        if segment['p_type'] == 'PT_LOAD':
            p.mem_write(segment['p_vaddr'], segment.data())
    p.mem_map(0x60000000, 0x10000)
    cursor, pointers = 0x60002000, []
    for token in command:
        pointers.append(cursor)
        encoded = token.encode() + b'\0'
        p.mem_write(cursor, encoded)
        cursor += len(encoded)
    p.mem_write(0x60001000, struct.pack('<' + 'I' * (len(pointers) + 1), *pointers, 0))
    p.mem_write(0x1ca4c, struct.pack('<I', pointers[1]))
    p.mem_write(0x1ca50, struct.pack('<I', 0x60001004))
    child_argv = []
    def proxy_string(address):
        token = bytearray()
        while (value := bytes(p.mem_read(address, 1))) != b'\0':
            token.extend(value)
            address += 1
        return token.decode()
    def proxy_hook(uc, pc, size, data):
        if pc == proxy_syms['execvp']:
            assert proxy_string(uc.reg_read(UC_ARM_REG_R0)) == frontend
            vector = uc.reg_read(UC_ARM_REG_R1)
            for i in range(8):
                pointer = struct.unpack('<I', uc.mem_read(vector + i * 4, 4))[0]
                if not pointer:
                    break
                child_argv.append(proxy_string(pointer))
            uc.emu_stop()  # Capture only; never execute a program.
        elif pc in (0xc6cc, proxy_syms['fork']):
            uc.reg_write(UC_ARM_REG_R0, 0)
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR))
    p.hook_add(UC_HOOK_CODE, proxy_hook)
    p.reg_write(UC_ARM_REG_SP, 0x60008000)
    p.emu_start(0x95c4, 0, count=10000)
    assert child_argv == [frontend] + argv
    assert (child_argv == [frontend, '--native']) == (name == 'generated')
    rows.append({'case': name, 'lookup_name': frontend, 'app_id': '0x30001',
                 'parsed_arguments': argv, 'manager_command': command, 'proxy_child_argv': child_argv})
report = {'scope': 'Original parser/name lookup/command builder/proxy child exec arguments; libc/stdio/fork virtual',
          'sysmgrd_sha256': digest, 'cases': rows,
          'appproxy_sha256': proxy_digest,
          'limits': ['No actual AppList install, fork/exec, UID change, APF service or physical player ran.']}
if options.full_config:
    before=next(row['records'] for row in rows if row['case']=='full-stock')
    after=next(row['records'] for row in rows if row['case']=='full-merged')
    assert after[:-1]==before and after[-1]['id']=='0x30001'
    report['original_registrations_preserved']=True
(ROOT / ('sources/native-applist-full-config.json' if options.full_config else 'sources/native-applist-fragment.json')).write_text(json.dumps(report, indent=2) + '\n')
print('Original full command chain verifies single executable token; duplicate-path control misplaces --native')
