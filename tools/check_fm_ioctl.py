"""Replay the stock ioctl dispatcher; hardware helpers are explicit substitutes."""
import runpy, struct, json
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR, UC_ARM_REG_SP, UC_ARM_REG_PC
ctx=runpy.run_path(__file__.replace('check_fm_ioctl.py','check_fm_driver.py'))
elf=ctx['elf'];work=ctx['work'];module=ctx['module']
symtab=elf.get_section_by_name('.symtab')
sections={i:0x100000+i*0x10000 for i,s in enumerate(elf.iter_sections()) if s['sh_flags']&2}
external={};symbols={}
def symbol_address(sym):
    index=sym['st_shndx']
    if index=='SHN_UNDEF':
        if sym.name not in external:external[sym.name]=0x700000+16*len(external)
        return external[sym.name]
    assert index in sections,(sym.name,index)
    return sections[index]+sym['st_value']
for sym in symtab.iter_symbols():
    if sym.name and (sym['st_shndx'] in sections or sym['st_shndx']=='SHN_UNDEF'):
        symbols[sym.name]=symbol_address(sym)
images={i:bytearray(s.data()) for i,s in enumerate(elf.iter_sections()) if i in sections and s['sh_type']!='SHT_NOBITS'}
for relsec in elf.iter_sections():
    if relsec['sh_type']!='SHT_REL' or relsec['sh_info'] not in images:continue
    index=relsec['sh_info'];data=images[index]
    for rel in relsec.iter_relocations():
        off=rel['r_offset'];word=struct.unpack_from('<I',data,off)[0]
        target=symbol_address(symtab.get_symbol(rel['r_info_sym']));kind=rel['r_info_type']
        if kind==2:new=(target+word)&0xffffffff
        elif kind==1:
            addend=(word&0xffffff);addend=(addend-0x1000000 if addend&0x800000 else addend)*4
            delta=target+addend-(sections[index]+off)
            assert delta%4==0 and -(1<<25)<=delta<(1<<25)
            new=(word&0xff000000)|((delta>>2)&0xffffff)
        elif kind==40:continue
        else:raise AssertionError(kind)
        struct.pack_into('<I',data,off,new)

def replay(command,payload,station_valid=1,frequency=82500,register_value=0x4055,capture=None):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
    for i,base in sections.items():
        size=elf.get_section(i)['sh_size'];u.mem_map(base,max(0x1000,(size+0xfff)&~0xfff))
        if i in images:u.mem_write(base,bytes(images[i]))
    for base in [0x700000,0x800000,0x900000,0xa00000]:u.mem_map(base,0x10000)
    inode,file,dev,state,arg=0x800000,0x801000,0x802000,0x803000,0x804000
    u.mem_write(file+128,struct.pack('<I',0x805000));u.mem_write(dev+64,struct.pack('<I',state))
    u.mem_write(state,struct.pack('<5I',frequency,1,0,6,1));u.mem_write(arg,payload+b'\0'*max(0,128-len(payload)))
    calls=[]
    allowed={symbols[n]:n for n in ['video_devdata','__memzero','strncpy','fmGetSigStrength','fmSetFreq','si470x_read','si470x_write','icx1087_AdcMixMute','msleep']}
    def hook(uc,pc,size,data):
        if pc==0xa00000:uc.emu_stop();return
        if pc in external.values() and pc not in allowed:raise AssertionError(('unexpected external',hex(pc)))
        if pc not in allowed:return
        name=allowed[pc];r0=uc.reg_read(UC_ARM_REG_R0);r1=uc.reg_read(UC_ARM_REG_R1);r2=uc.reg_read(UC_ARM_REG_R2)
        calls.append(name)
        if capture is not None:capture.append({"helper":name,"r0":r0,"r1":r1,"r2":r2})
        if name=='video_devdata':result=dev
        elif name=='__memzero':uc.mem_write(r0,b'\0'*r1);result=0
        elif name=='strncpy':
            raw=bytes(uc.mem_read(r1,r2)).split(b'\0',1)[0];uc.mem_write(r0,(raw+b'\0'*r2)[:r2]);result=r0
        elif name=='fmGetSigStrength':result=station_valid
        elif name=='si470x_read':result=register_value
        elif name in ['si470x_write','icx1087_AdcMixMute','msleep']:result=0
        else:
            assert r1==state;uc.mem_write(state,struct.pack('<I',r2));result=0
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    for reg,value in [(UC_ARM_REG_R0,inode),(UC_ARM_REG_R1,file),(UC_ARM_REG_R2,command),(UC_ARM_REG_R3,arg),(UC_ARM_REG_SP,0x90f000),(UC_ARM_REG_LR,0xa00000)]:u.reg_write(reg,value)
    u.emu_start(symbols['fm_do_ioctl'],0,count=2000)
    assert u.reg_read(UC_ARM_REG_PC)==0xa00000
    return u.reg_read(UC_ARM_REG_R0),bytes(u.mem_read(arg,128)),calls
checks=[]
for khz in [75900,76000,82500,90000,108000,108100]:
    result,data,calls=replay(0x4004760f,struct.pack('<I',khz*16))
    valid=76000<=khz<=108000
    assert result==(0 if valid else 0xffffffff)
    assert ('fmSetFreq' in calls)==valid
    if valid:assert struct.unpack_from('<I',data)[0]==khz
    checks.append({'operation':'set frequency','khz':khz,'accepted':valid})
result,data,calls=replay(0x8004760e,b'');assert result==0 and struct.unpack_from('<I',data)[0]==82500*16
checks.append({'operation':'get frequency','khz':82500,'encoded':82500*16})
result,data,calls=replay(0x803c7601,b'');assert result==0 and data.split(b'\0',1)[0]==b'Silicon Labs. Tuner' and struct.unpack_from('<I',data,32)[0]==2
for valid in [0,1]:
    result,data,calls=replay(0xc0347604,b'\0'*52,station_valid=valid)
    assert result==0 and data[4:7]==b'FM\0'
    assert struct.unpack_from('<II',data,36)==(76000*16,108000*16)
    assert struct.unpack_from('<H',data,50)[0]==(65535 if valid else 0)
    checks.append({'operation':'get tuner','synthetic_station_valid':valid,'signal_field':65535 if valid else 0})
result,data,calls=replay(0xc0347604,struct.pack('<I',1));assert result==0xffffffea
for index in [5,10,11]:
    result,data,calls=replay(0xc020762b,struct.pack('<I',index))
    assert result==0 and struct.unpack_from('<H',data,4+index*2)[0]==0x4055 and calls[-1]=='si470x_read'
    checks.append({'operation':'private register read','index':index,'halfword_offset':4+index*2,'wire_bytes':32})
# This handler writes 36 bytes although its ioctl encodes 32. This is an ABI
# discrepancy, not a claim about the kernel usercopy allocator's actual bounds.
result,data,calls=replay(0xc020762c,b'\0'*32+b'\xaa'*8)
assert result==0 and data[32:36]==b'\0'*4 and data[36:40]==b'\xaa'*4
checks.append({'operation':'private read-all ABI mismatch','encoded_bytes':32,'observed_written_bytes':36,'used_by_app':False})
# Verify the public audio command used to quiesce a failed tuner before close.
result,audio,calls=replay(0x80287610,b'\0'*40)
assert result==0 and struct.unpack_from('<H',audio,32)[0]==2
packet=bytearray(audio[:40]);struct.pack_into('<I',packet,12,struct.unpack_from('<I',packet,12)[0]|1)
trace=[];result,_,calls=replay(0x40287611,bytes(packet),capture=trace)
inner=[item['r0']for item in trace if item['helper']=='icx1087_AdcMixMute']
assert result==0 and inner==[1,1,2]
checks.append({'operation':'quiesce with audio mute','request':'0x40287611','inner_mute_arguments':inner,'hardware_bus_virtual':True})
trace=[];packet=bytearray(32);packet[0]=5;struct.pack_into('<H',packet,2,0x1c60)
result,_,_=replay(0xc020762a,bytes(packet),capture=trace)
writes=[item for item in trace if item['helper']=='si470x_write']
assert result==0 and len(writes)==1 and writes[0]['r1']==5 and writes[0]['r2']==0x1c60
checks.append({'operation':'wide-band configuration write ABI','command':'0xc020762a','register':5,'value':0x1c60,'register_byte':0,'value_halfword_offset':2,'hardware_bus_virtual':True})
report={'passed':True,'module_sha256':ctx['hashlib'].sha256(module).hexdigest(),'checks':checks,'scope':'Original relocated fm_do_ioctl ARM instructions; fake video_devdata, memzero, strncpy, fmGetSigStrength, fmSetFreq and si470x_read','limits':['No actual fmSetFreq or fmGetSigStrength body in dispatcher replay.','No physical device, RF tuning, audio output, module open/release or lifecycle ownership tested.','Si470x name is driver identity, not confirmed chip part number.'],'hardware_tested':False}
(work/'ioctl-dispatch.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
