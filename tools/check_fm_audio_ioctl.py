"""Replay the pinned kernel mixer dispatcher. Codec helpers are replacements."""
from pathlib import Path
import hashlib,io,json,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];raw=(ROOT/'work/upg-jp/verified-1.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
elf=ELFFile(io.BytesIO((ROOT/'work/isolation-audit/x1000-kernel-analysis.elf').read_bytes()))
assert elf.get_section_by_name('.kernel').data()[:len(raw)]==raw
symbols={s.name:s['st_value']for s in elf.get_section_by_name('.symtab').iter_symbols()}
assert symbols['MixerIoctl']==0xc016fda8
settings=0xc027a7cc;seed=[9,0,1,0x1212,0,0,0x3232,0x2020,0,0,0,1]
def machine():
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0xc0008000,0x400000);u.mem_write(0xc0008000,raw);u.mem_map(0x60000000,0x20000);u.mem_write(settings,struct.pack('<12I',*seed));return u

def call(u,command,value=0,helper_failure=False):
 pointer=0x60001000;sentinel=0x6001f000;events=[]
 u.mem_write(pointer,struct.pack('<I',value));helpers={symbols[n]:n for n in ['__get_user_4','__put_user_4','DoMute','SetPlaybackSrc','SetOutputDevice']}
 def hook(uc,pc,size,data):
  if pc==sentinel:uc.emu_stop();return
  if pc not in helpers:return
  name=helpers[pc];a=[uc.reg_read(r)for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2]];result=0
  if name=='__get_user_4':assert a[0]==pointer;uc.reg_write(UC_ARM_REG_R2,struct.unpack('<I',uc.mem_read(pointer,4))[0])
  elif name=='__put_user_4':assert a[0]==pointer;uc.mem_write(pointer,struct.pack('<I',a[2]))
  else:
   events.append({'helper':name,'arguments':a[:2]if name=='DoMute'else a[:1]});result=0xfffffffb if helper_failure else 0
   if not helper_failure:
    offset=0 if name=='DoMute'else 4 if name=='SetPlaybackSrc'else 8
    uc.mem_write(settings+offset,struct.pack('<I',a[1]if name=='DoMute'else a[0]))
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 token=u.hook_add(UC_HOOK_CODE,hook)
 for reg,value in [(UC_ARM_REG_R0,0),(UC_ARM_REG_R1,0),(UC_ARM_REG_R2,command),(UC_ARM_REG_R3,pointer),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,sentinel)]:u.reg_write(reg,value)
 u.emu_start(symbols['MixerIoctl'],0,count=3000);u.hook_del(token);assert u.reg_read(UC_ARM_REG_PC)==sentinel
 return u.reg_read(UC_ARM_REG_R0),struct.unpack('<I',u.mem_read(pointer,4))[0],events
rows=[]
for command,index in [(0x80046102,0),(0x80046104,1),(0x80046106,2),(0x80044d04,6),(0x80044d0a,7),(0x8004610e,11)]:
 result,value,events=call(machine(),command);assert result==0 and value==seed[index]and not events
 rows.append({'get':hex(command),'value':value,'settings_offset':index*4})
for command,value,helper in [(0x40046101,31,'DoMute'),(0x40046103,2,'SetPlaybackSrc'),(0x40046105,0,'SetOutputDevice')]:
 for failure in [False,True]:
  result,_,events=call(machine(),command,value,failure);assert events[0]['helper']==helper
  assert events[0]['arguments']==([31,31]if helper=='DoMute'else[value])
  expected=0xfffffffb if failure and helper=='SetOutputDevice'else 0
  assert result==expected
  rows.append({'set':hex(command),'argument':value,'simulated_codec_failure':failure,'ioctl_return':result,'events':events})
u=machine();result,_,events=call(u,0x40046103,2,True);assert result==0
result_read,source,_=call(u,0x80046104);assert result_read==0 and source==0

result,_,events=call(machine(),0x40046103,7);assert result==0xffffffea and not events
# The radio's internal mute helper owns bit0x100, outside AUDIO_SET_MUTE's
# low-five-bit mask. Execute its original dispatch with only DoMute replaced.
u=machine();u.mem_write(settings,struct.pack('<I',31));inner_rows=[]
for argument,expected_return,expected_mute in [(1,1,287),(0,1,287),(2,0,31),(0,2,31)]:
    events=[];sentinel=0x6001f000
    def inner_hook(uc,pc,size,data):
        if pc==sentinel:uc.emu_stop();return
        if pc!=symbols['DoMute']:return
        mask=uc.reg_read(UC_ARM_REG_R0);value=uc.reg_read(UC_ARM_REG_R1)
        assert mask==256
        old=struct.unpack('<I',uc.mem_read(settings,4))[0]
        uc.mem_write(settings,struct.pack('<I',(old&~mask)|(value&mask)))
        events.append({'mask':mask,'value':value})
        uc.reg_write(UC_ARM_REG_R0,old);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    token=u.hook_add(UC_HOOK_CODE,inner_hook)
    for reg,value in [(UC_ARM_REG_R0,argument),(UC_ARM_REG_SP,0x60018000),(UC_ARM_REG_LR,sentinel)]:u.reg_write(reg,value)
    u.emu_start(symbols['icx1087_AdcMixMute'],0,count=100);u.hook_del(token)
    assert u.reg_read(UC_ARM_REG_PC)==sentinel and u.reg_read(UC_ARM_REG_R0)==expected_return
    mute=struct.unpack('<I',u.mem_read(settings,4))[0];assert mute==expected_mute and mute&31==31
    inner_rows.append({'argument':argument,'return':expected_return,'mute':mute,'codec_helper_replaced':events})
report={'passed':True,'kernel_sha256':hashlib.sha256(raw).hexdigest(),'cases':rows,'internal_adc_mute_cases':inner_rows,'silent_source_failure_detectable_by_readback':True,'scope':'Original MixerIoctl dispatcher; virtual user-copy and codec/mute/source/output helpers','hardware_tested':False,'limits':['No codec operations, mixer open/release, clocks, DSP or actual audio route execute.','SetPlaybackSrc and DoMute helper failures are not propagated by the original dispatcher.','Matching readback proves software state only; no headphone sound or ownership handoff.']}
out=ROOT/'work/fm-radio-research/audio-ioctl.json';out.write_text(json.dumps(report,indent=2)+'\n');print('Original mixer ioctl: six getters, mute/source/output setters, silent source failure and invalid source checked.')
