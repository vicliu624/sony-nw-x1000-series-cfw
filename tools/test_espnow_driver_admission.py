"""Execute relocated stock wlan_do_ioctl up to hostcmd entry/refusal.

Kernel adapter bytes/netdev/thread metadata are synthetic. No radio/USB access.
This tests original driver admission instructions, not command queue timing.
"""
import hashlib
import io
import json
from pathlib import Path
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_PC, UC_ARM_REG_LR
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
raw = (ROOT/'work/hardware-audit/sd8686.ko').read_bytes()
assert hashlib.sha256(raw).hexdigest() == '2cce84755878b1f697491d00f4c3e23829d3a1271b3bf8a634ceb88fe3928a69'
elf = ELFFile(io.BytesIO(raw));symbols = elf.get_section_by_name('.symtab')
sections, external, address = {}, {}, 0x100000
for index, section in enumerate(elf.iter_sections()):
    if section['sh_flags'] & 2 and section['sh_size']:
        size = (section['sh_size']+4095)&~4095
        sections[index] = (address, bytearray(section.data()), size)
        address += size+4096


def symbol_address(symbol):
    index = symbol['st_shndx']
    if isinstance(index, int):
        return sections[index][0]+symbol['st_value']
    if index == 'SHN_ABS':
        return symbol['st_value']
    assert index == 'SHN_UNDEF'
    if symbol.name not in external:
        external[symbol.name] = 0x900000+4*len(external)
    return external[symbol.name]


for section in elf.iter_sections():
    if section['sh_type'] != 'SHT_REL' or section['sh_info'] not in sections:
        continue
    base, data, _ = sections[section['sh_info']]
    for relocation in section.iter_relocations():
        offset, kind = relocation['r_offset'], relocation['r_info_type']
        target = symbol_address(symbols.get_symbol(relocation['r_info_sym']))
        value = struct.unpack_from('<I',data,offset)[0]
        if kind == 2:
            value = (target+value)&0xffffffff
        elif kind == 1:
            addend = (value&0xffffff)<<2
            if addend&0x2000000:addend-=0x4000000
            delta = target+addend-(base+offset)
            assert delta%4==0 and -0x2000000<=delta<0x2000000
            value = (value&0xff000000)|((delta>>2)&0xffffff)
        else:
            raise ValueError('unhandled relocation')
        struct.pack_into('<I',data,offset,value)
names = {s.name:symbol_address(s) for s in symbols.iter_symbols() if s.name and isinstance(s['st_shndx'],int) and s['st_shndx'] in sections}
text = elf.get_section_by_name('.text')
text_base = sections[next(i for i,s in enumerate(elf.iter_sections()) if s.name=='.text')][0]
# The following numeric adapter-field offsets are literals, not guessed labels.
literal = lambda offset:struct.unpack_from('<I',text.data(),offset)[0]
fields = {'initial':literal(0x8dd4),'first_gate':literal(0x8dd8),
          'second_gate':literal(0x8de4),'override_gate':literal(0x8df8)}


def replay(values,command=0x8be4,target='wlan_hostcmd_ioctl'):
    cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    for base,data,size in sections.values():
        cpu.mem_map(base,size);cpu.mem_write(base,bytes(data))
    cpu.mem_map(0x400000,0x20000);cpu.mem_map(0x900000,0x10000)
    write=lambda a,v:cpu.mem_write(a,struct.pack('<I',v))
    device,private,adapter,request,end=0x400100,0x401000,0x402000,0x404000,0x40f000
    write(device+104,private);write(private+4,adapter)
    write(request+16,0x405000);cpu.mem_write(request+20,struct.pack('<H',128))
    cpu.mem_write(0x405000,b'0')
    write(0x410008,0xffffffff) # kernel thread addr_limit fixture for any access_ok
    for key,value in values.items():cpu.mem_write(adapter+fields[key],bytes([value]))
    if 'drvdbg' in names:write(names['drvdbg'],0)
    trace=[]
    def hook(u,pc,size,data):
        trace.append(pc)
        if pc in (names[target],end):u.emu_stop()
        elif 0x900000<=pc<0x910000:raise AssertionError('unexpected kernel helper '+hex(pc))
    cpu.hook_add(UC_HOOK_CODE,hook)
    for reg,value in ((UC_ARM_REG_R0,device),(UC_ARM_REG_R1,request),(UC_ARM_REG_R2,command),
                      (UC_ARM_REG_SP,0x411f00),(UC_ARM_REG_LR,end)):
        cpu.reg_write(reg,value)
    cpu.emu_start(names['wlan_do_ioctl'],end+4,count=3000)
    admitted=trace[-1]==names[target]
    assert trace[-1] in (names[target],end)
    result=cpu.reg_read(UC_ARM_REG_R0)
    if result&0x80000000:result-=0x100000000
    return {'field_values':values,'ioctl':hex(command),'target':target,
            'target_reached':admitted,'result_if_returned':None if admitted else result}


cases=[]
for initial in (0,1):
    for first in (0,1):
        for second in (0,1):
            for override in (0,1):
                row=replay({'initial':initial,'first_gate':first,'second_gate':second,'override_gate':override})
                assert row['target_reached']==(not first and (not second or override))
                if not row['target_reached']:assert row['result_if_returned']==-16
                cases.append(row)
wake_cases=[]
for first in (0,1):
    for second in (0,1):
        row=replay({'initial':0,'first_gate':first,'second_gate':second,'override_gate':0},
                   0x8bfb,'wlan_deepsleep_ioctl')
        assert row['target_reached']
        wake_cases.append(row)
out=ROOT/'work/espnow-driver-admission';out.mkdir(parents=True,exist_ok=True)
report={'passed':True,'module_sha256':hashlib.sha256(raw).hexdigest(),'adapter_offsets':fields,
        'cases':cases,'wake_ioctl_cases':wake_cases,'original_relocated_instructions_executed':True,
        'kernel_calls_executed':False,'queue_or_radio_exercised':False,
        'field_meanings_hardware_qualified':False,'device_accessed':False}
(out/'report.json').write_text(json.dumps(report,indent=2))
print('Original Linux driver admission:',len(cases),'hostcmd cases and',len(wake_cases),'wake cases passed; no kernel IO')
