"""Replay Sony libc space-field conversion; kernel/mount flag helpers are virtual."""
from pathlib import Path
import gzip, hashlib, io, json, struct, tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_PC, UC_ARM_REG_LR, UC_ARM_REG_SP

ROOT=Path(__file__).resolve().parents[1]
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
    binary=tar.extractfile('./lib/libc-2.3.3.so').read()
elf=ELFFile(io.BytesIO(binary))
symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
segments=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
low=min(s['p_vaddr'] for s in segments)&~4095
high=(max(s['p_vaddr']+s['p_memsz'] for s in segments)+4095)&~4095
base=0x1000000
rows=[]
for function,query,stat in [('statvfs64','statfs64','__xstat64'),('fstatvfs64','fstatfs64','__fxstat64')]:
    for case,frsize,error in [('large',2048,0),('zero-frsize',0,0),('EIO',2048,5)]:
        u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(base+low,high-low)
        for segment in segments:u.mem_write(base+segment['p_vaddr'],segment.data())
        u.mem_map(0x60000000,0x20000)
        end,errno,output,path=0x60000100,0x60001000,0x60002000,0x60003000
        u.mem_write(output,b'\xa5'*128);u.mem_write(path,b'/fixture/apps\0')
        argument=42 if function.startswith('f') else path
        raw=bytearray(88)
        struct.pack_into('<IIQQQQQ',raw,0,0x4d44,4096,0x400000123,0x300000122,0x200000121,0x100000120,0x100000119)
        struct.pack_into('<I',raw,56,255);struct.pack_into('<I',raw,60,frsize)
        calls=[]
        def code(uc,pc,size,unused):
            result=None
            if pc==base+symbols[query]:
                assert uc.reg_read(UC_ARM_REG_R0)==argument
                calls.append(query)
                if error:
                    uc.mem_write(errno,struct.pack('<I',error));result=0xffffffff
                else:
                    uc.mem_write(uc.reg_read(UC_ARM_REG_R1),bytes(raw));result=0
            elif pc==base+symbols[stat]:
                # Metadata unavailable: exercise the stock null-stat conversion.
                calls.append(stat);result=0xffffffff
            elif pc==base+symbols['__errno_location']:result=errno
            elif pc==base+0xa586c:
                # Mount flag discovery is unrelated to the space fields tested.
                calls.append('virtual-mount-flags');result=0
            if result is not None:
                uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
        u.hook_add(UC_HOOK_CODE,code)
        for reg,value in ((UC_ARM_REG_R0,argument),(UC_ARM_REG_R1,output),(UC_ARM_REG_SP,0x6001f000),(UC_ARM_REG_LR,end)):
            u.reg_write(reg,value)
        u.emu_start(base+symbols[function],end,count=10000)
        assert u.reg_read(UC_ARM_REG_PC)==end
        actual=bytes(u.mem_read(output,128))
        assert actual[96:]==b'\xa5'*32
        if error:
            assert u.reg_read(UC_ARM_REG_R0)==0xffffffff and actual==b'\xa5'*128
            assert calls==[query]
        else:
            assert u.reg_read(UC_ARM_REG_R0)==0
            assert struct.unpack_from('<II',actual,0)==(4096,frsize or 4096)
            assert struct.unpack_from('<QQQ',actual,8)==(0x400000123,0x300000122,0x200000121)
            assert calls==[query,stat,'virtual-mount-flags']
        rows.append({'function':function,'case':case,'passed':True,'calls':calls,'guard_intact':True})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'libc_sha256':hashlib.sha256(binary).hexdigest(),'cases':rows,'observed_output_bytes':96,'f_frsize_offset':4,'f_bavail_offset':24,'limits':['Original wrapper/converter instructions with synthetic statfs64 result, failed metadata query and stubbed mount flag helper.','No real statfs64 syscall, ENOSYS fallback, mount discovery, loader or device filesystem qualification.','Large counts test conversion only; no claim of actual device capacity.']}
(ROOT/'sources/native-stock-statvfs64.json').write_text(json.dumps(report,indent=2)+'\n')
print('Stock statvfs64/fstatvfs64: six bounded conversion checks passed.')
