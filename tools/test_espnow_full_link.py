"""Shared C chat+mailbox -> actual compiled radio Thumb -> shared C peer.

Computer-only integration: RF delivery/loss, radio helpers and word IO are
modeled. It is neither a physical link test nor an old-driver timing benchmark.
"""
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/espnow-full-link';OUT.mkdir(parents=True,exist_ok=True)
sources=['tools/fixtures/xnow_full_link.c','runtime/platform/espnow/xnow_chat.c','runtime/platform/espnow/xnow_mailbox.c']
library=OUT/'protocol.so'
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-fPIC','-shared','-g',*sources,'-o',str(library)],cwd=ROOT,check=True)
lib=C.CDLL(str(library));READ=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint32,C.POINTER(C.c_uint32));WRITE=C.CFUNCTYPE(C.c_int,C.c_void_p,C.c_uint32,C.c_uint32)
Packet=C.c_uint8*32
lib.sim_init.argtypes=[READ,WRITE];lib.sim_submit.argtypes=[C.c_uint,C.c_char_p,C.c_uint,C.c_uint32,C.c_uint32]
lib.sim_step.argtypes=[C.c_uint32];lib.sim_peer_receive.argtypes=[C.POINTER(C.c_uint8),C.c_uint32]
lib.sim_peer_take.argtypes=[C.POINTER(C.c_uint8)];lib.sim_count.argtypes=[C.c_uint,C.c_uint]
lib.sim_message.argtypes=[C.c_uint];lib.sim_message.restype=C.c_char_p;lib.sim_active.argtypes=[C.c_uint]
ELF=ROOT/'work/espnow-radio-bridge/bridge.elf'


def simulation(name,loss=False,absent=False,start=0):
    cpu=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    for base,size in ((0,0x20000),(0xc0000000,0x20000),(0x200000,0x10000)):cpu.mem_map(base,size)
    with ELF.open('rb') as f:
        elf=ELFFile(f)
        for section_name in ('.text','.state'):
            section=elf.get_section_by_name(section_name);cpu.mem_write(section['sh_addr'],section.data())
        symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
    state=symbols['xnow_radio_state'];transmitted=[];io_errors=[];words=0
    @READ
    def read_word(context,offset,out):
        nonlocal words
        words+=1
        if offset&3 or offset>88:io_errors.append(offset);return -1
        out[0]=struct.unpack('<I',cpu.mem_read(state+offset,4))[0];return 0
    @WRITE
    def write_word(context,offset,value):
        nonlocal words
        words+=1
        if offset&3 or (offset!=4 and not 20<=offset<52):io_errors.append(offset);return -1
        cpu.mem_write(state+offset,struct.pack('<I',value));return 0
    def hook(u,address,size,data):
        if address==0x1f000:u.emu_stop();return
        if address not in (0x7b4,0xd458,0xda00,0xd800,0xa314):return
        r0,r1,r2=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)]
        if address==0x7b4:
            assert r2<=32;u.mem_write(r0,bytes(u.mem_read(r1,r2)))
        elif address==0xd458:
            assert r0==348;u.reg_write(UC_ARM_REG_R0,0x202000)
        elif address==0xda00:u.mem_write(r0,bytes(128))
        elif address==0xd800:
            transmitted.append(bytes(u.mem_read(r0+47,32)));u.reg_write(UC_ARM_REG_R0,0)
        else:raise AssertionError('valid test frame reached original fallback')
        u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
    cpu.hook_add(UC_HOOK_CODE,hook)
    def radio_receive(packet):
        frame=bytearray(79);frame[0]=95;frame[2]=0xd0
        frame[12:18]=bytes.fromhex('020000000001');frame[18:24]=bytes([255])*6
        frame[32:47]=bytes.fromhex('7f18fe3401020304dd2518fe340401');frame[47:]=packet
        cpu.mem_write(0x200100,bytes(frame));cpu.reg_write(UC_ARM_REG_SP,0x208000)
        cpu.reg_write(UC_ARM_REG_R0,0x200100);cpu.reg_write(UC_ARM_REG_R1,0x200500)
        cpu.reg_write(UC_ARM_REG_LR,0x1f001)
        cpu.emu_start(symbols['xnow_radio_receive'],0x1f002,count=3000)
        assert cpu.reg_read(UC_ARM_REG_PC)==0x1f000
    assert lib.sim_init(read_word,write_word)==0
    text0=(b'X1060 '+b'abcdefghij'*9)[:96]
    text1=('Cardputer '+'\u4f60\u597d'*14+'!!').encode() # valid UTF-8 crosses fragment boundaries
    assert len(text0)==len(text1)==96
    assert lib.sim_submit(0,text0,len(text0),0x12345678,start)==0
    if not absent:assert lib.sim_submit(1,text1,len(text1),0x87654321,start)==0
    last_peer=start;air=0;dropped=0;duplicates=0;heartbeats=0
    def deliver_to_peer(packet,now):
        nonlocal air,dropped,duplicates
        air+=1
        if loss and air%5==0:dropped+=1;return
        lib.sim_peer_receive(Packet.from_buffer_copy(packet),now)
        if loss and air%7==0:lib.sim_peer_receive(Packet.from_buffer_copy(packet),now);duplicates+=1
    for elapsed in range(0,30001,20):
        now=(start+elapsed)&0xffffffff
        assert lib.sim_step(now)==0
        outgoing=Packet()
        while lib.sim_peer_take(outgoing):
            if absent:continue
            packet=bytes(outgoing);last_peer=now;air+=1
            if loss and air%5==0:dropped+=1;continue
            radio_receive(packet)
            if loss and air%7==0:radio_receive(packet);duplicates+=1
            while transmitted:deliver_to_peer(transmitted.pop(0),now)
        if not absent and ((now-last_peer)&0xffffffff)>=250:
            radio_receive(b'XNOW'+bytes([1,1,0,0])+bytes(24));last_peer=now;heartbeats+=1
            while transmitted:deliver_to_peer(transmitted.pop(0),now)
    counts=[[lib.sim_count(side,event) for event in (1,2,3)] for side in (0,1)]
    if absent:assert counts[0]==[0,0,1] and not lib.sim_active(0)
    else:
        assert counts==[[1,1,0],[1,1,0]],(name,counts)
        assert lib.sim_message(0)==text1 and lib.sim_message(1)==text0
    assert not io_errors
    return {'case':name,'message_delivered_failed_counts':counts,'modeled_air_frames':air,
            'modeled_drops':dropped,'modeled_duplicates':duplicates,'heartbeat_calls':heartbeats,
            'word_io_calls':words,'native_request_still_pending':struct.unpack('<II',cpu.mem_read(state+4,8))[0]!=struct.unpack('<II',cpu.mem_read(state+4,8))[1]}


cases=[simulation('bidirectional96'),simulation('loss-and-duplicates',loss=True),
       simulation('clock-wrap',loss=True,start=0xffffffff-500),simulation('absent-peer',absent=True)]
report={'passed':True,'cases':cases,'shared_c_chat_and_mailbox_executed':True,
        'compiled_radio_thumb_executed':True,'radio_sha256':hashlib.sha256(ELF.read_bytes()).hexdigest(),
        'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},
        'rf_rtos_and_word_io_timing_modeled':True,'native_c_built_for_host':True,
        'old_driver_or_hardware_qualified':False,'over_air_tested':False,'device_accessed':False}
(OUT/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
