"""Execute original host dispatcher plus compiled command hook, no RX needed.

This is a local instruction experiment, not a downloadable radio candidate.
Pool/RAM ownership of the combined future bridge is not established here.
"""
from pathlib import Path
import hashlib,json,struct,subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_THUMB,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_LR
from app_registry import ROOT
from marvell_firmware import parse

OUT=ROOT/'work/espnow-command-hook';OUT.mkdir(parents=True,exist_ok=True)
sources=['runtime/platform/espnow/radio_word_command.c','runtime/platform/espnow/radio_command_hook.S','tools/fixtures/radio_word_doorbell.c']
linker=OUT/'hook.ld';linker.write_text('ENTRY(xnow_radio_word_command_entry)\nSECTIONS { . = 0xc000a190; .text : { *(.text*) *(.rodata*) } .state : { *(.state) } /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } ASSERT(.<=0xc000a8fc,"probe budget") }')
elf=OUT/'hook.elf'
subprocess.run(['arm-linux-gnueabi-gcc','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-mthumb','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-static','-Wl,--build-id=none','-Wl,-T,'+str(linker),*sources,'-o',str(elf)],cwd=ROOT,check=True)
with elf.open('rb') as f:
    e=ELFFile(f);sections=[(s['sh_addr'],s.data()) for s in e.iter_sections() if s['sh_flags']&2 and s['sh_size']]
    symbols={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols() if s.name}
raw=(ROOT/'work/targets-jp/sd8686.bin').read_bytes();assert hashlib.sha256(raw).hexdigest()=='08f1a0ba5ce3895324899c88a2b0c05b7c1b843ac61e6a6eec530c2463395f3a'
records=parse(raw);cases=[]
for patched in (False,True):
    for action,address,value in ((0,0xc0017e00,0),(1,0xc0017e00,0x12345678),(1,0xc0017e04,0x87654321),(2,0xc0017e00,0)):
        cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
        for base,size in ((0,0x20000),(0xc0000000,0x20000),(0x04000000,0x2000),(0x200000,0x10000)):cpu.mem_map(base,size)
        for r in records:
            if r.command==1:cpu.mem_write(r.address,r.data)
        for base,data in sections:cpu.mem_write(base,data)
        if patched:
            # LDR at88d6 uses aligned(PC+4)=88d8, +4 -> literal88dc.
            assert bytes(cpu.mem_read(0x88d6,10))==bytes.fromhex('207863781b0218430128')
            cpu.mem_write(0x88d6,struct.pack('<HHHI',0x4b01,0x4718,0x46c0,symbols['xnow_radio_word_command_entry']|1))
        request=0xc00155b8;cpu.mem_write(request,struct.pack('<4H',0x86,20,0x55aa,0)+struct.pack('<HHII',action,0,address,value))
        cpu.mem_write(0xc0017e00,struct.pack('<II',0xaabbccdd,0x11223344))
        cpu.mem_write(0xc0007859,b'\x01');cpu.mem_write(0xc000edf4,b'\0');cpu.mem_write(0xc001452a,b'\x01')
        cpu.reg_write(UC_ARM_REG_SP,0x208000);trace=[];saved={}
        def hook(u,pc,size,context):
            trace.append(pc)
            if pc==0x88d6:
                for reg in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_SP):saved[reg]=u.reg_read(reg)
            if pc==0x9a46:
                assert saved and all(u.reg_read(reg)==v for reg,v in saved.items());u.emu_stop()
            elif pc==0x9c90:
                dest,source,n=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
                u.mem_write(dest,bytes(u.mem_read(source,n)));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
        cpu.hook_add(UC_HOOK_CODE,hook);cpu.emu_start(0x8079,0x9b40,count=4000)
        assert trace[-1]==0x9a46 and 0x88d6 in trace
        actual=struct.unpack('<I',cpu.mem_read(address,4))[0]
        if action==1:assert actual==value
        else:assert struct.unpack('<I',cpu.mem_read(request+16,4))[0]==actual
        count=struct.unpack('<I',cpu.mem_read(symbols['test_doorbell_count'],4))[0]
        assert count==int(patched and action==1 and address==0xc0017e00)
        assert 0xa314 not in trace and 0x136b0 not in trace
        cases.append({'hook':patched,'action':action,'address':hex(address),'doorbell_calls':count,'original_response_entry_reached':True,'rx_callback_executed':False})
report={'passed':True,'cases':cases,'original_get_set_semantics_preserved':True,'live_registers_and_stack_preserved':True,'trigger_from_host_command_without_rx':True,'real_radio_tx_tested':False,'combined_memory_ownership_qualified':False,'device_accessed':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}}
(OUT/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
