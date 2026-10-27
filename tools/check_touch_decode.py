"""Compare original SpiderApp touch conversion with our C core, mocking ioctl only."""
from pathlib import Path
import io,hashlib,struct,json,ctypes,subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R2,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_SP
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();e=ELFFile(io.BytesIO(raw));segments=[s for s in e.iter_segments()if s['p_type']=='PT_LOAD']
low=min(s['p_vaddr']for s in segments)&~4095;high=(max(s['p_vaddr']+s['p_memsz']for s in segments)+4095)&~4095
syms={s.name:s['st_value']for s in e.get_section_by_name('.dynsym').iter_symbols()}
subprocess.run(['gcc','-shared','-fPIC','-std=c99','-O2',str(ROOT/'runtime/native/frontend.c'),'-o',str(ROOT/'work/frontend-core.so')],check=True)
class Touch(ctypes.Structure):_fields_=[('raw_x',ctypes.c_uint),('raw_y',ctypes.c_uint),('x',ctypes.c_uint),('y',ctypes.c_uint),('down',ctypes.c_int),('in_bounds',ctypes.c_int)]
lib=ctypes.CDLL(str(ROOT/'work/frontend-core.so'));cases=[]
for rx,ry in [(0,0),(1,1),(1464,2640),(2928,5280),(2929,5281),(8191,8191)]:
    p=bytearray(11);p[1]=1;struct.pack_into('>HH',p,2,rx,ry)
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(low,high-low)
    for s in segments:u.mem_write(s['p_vaddr'],s.data())
    u.mem_map(0x50000000,0x1000);u.mem_map(0x60000000,0x20000)
    u.mem_write(0x60010000,bytes(0x240));u.reg_write(UC_ARM_REG_R0,0x60010000);u.reg_write(UC_ARM_REG_SP,0x60008000);u.reg_write(UC_ARM_REG_LR,0x50000000)
    def hook(uc,pc,size,data):
        if pc==syms['ioctl']:
            dest=uc.reg_read(UC_ARM_REG_R2);uc.mem_write(dest,bytes(p));uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook);u.emu_start(0x14b0a4,0x50000000,count=100000)
    native=struct.unpack('<HH',u.mem_read(0x6001020a,4))
    t=Touch();buffer=(ctypes.c_ubyte*11).from_buffer_copy(p);lib.hb_touch_decode(buffer,ctypes.byref(t))
    assert native==(t.x,t.y),(rx,ry,native,(t.x,t.y))
    cases.append({'raw':[rx,ry],'stock':[native[0],native[1]],'ours':[t.x,t.y],'in_bounds':bool(t.in_bounds)})
result={'scope':'Original default-mode coordinate conversion with ioctl payload mocked; no touch hardware/gesture validation','SpiderApp_sha256':hashlib.sha256(raw).hexdigest(),'procedure':'0x14b0a4','cases':cases}
(ROOT/'sources/native-touch-replay.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
