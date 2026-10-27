"""Bounded stock WLAN init/load analysis; no scripts, commands or devices executed."""
from pathlib import Path
import hashlib,io,json,struct,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:
    daemon=tar.extractfile('./usr/local/bin/cnmgr_daemon').read()
    driver=tar.extractfile('./lib/modules/sd8686.ko').read()
    netstart=tar.extractfile('./etc/init.d/netstart').read()
assert hashlib.sha256(daemon).hexdigest()=='351eb99a05ae9a6baf00c8d8fd6e5e16129cc58dc6f300cf5f43d0fc5ad4eb35'
assert hashlib.sha256(driver).hexdigest()=='2cce84755878b1f697491d00f4c3e23829d3a1271b3bf8a634ceb88fe3928a69'
elf=ELFFile(io.BytesIO(daemon));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
rows=[]
for mode,entry in [('initialize',0xfcb4),('power-on-prefix',0x11284),('request-power-on-prefix',0xba18)]:
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x100000)
    for segment in elf.iter_segments():
        if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
    assert struct.unpack('<I',u.mem_read(0xbb7c+3*4,4))[0]==0xbe40
    label_pointer=struct.unpack('<I',u.mem_read(0xcb48,4))[0]
    assert bytes(u.mem_read(label_pointer,80)).split(b'\0',1)[0]==b'CNMGR_DAEMON_MAIN_REQ_KIND_POWER_ON'
    u.mem_map(0x200000,0x10000);u.mem_map(0x300000,0x20000);obj,end=0x200000,0x200100
    mutexes=[];commands=[];opened=[];request_reads=[]
    if mode=='request-power-on-prefix':u.mem_write(obj,struct.pack('<I',42))
    def string(p):return bytes(u.mem_read(p,512)).split(b'\0',1)[0].decode()
    def hook(uc,pc,size,unused):
        if pc==end:uc.emu_stop();return
        if pc==symbols['pthread_mutex_init']:
            mutexes.append(uc.reg_read(UC_ARM_REG_R0)-obj)
        elif pc==symbols['system']:
            commands.append(string(uc.reg_read(UC_ARM_REG_R0)))
        elif pc==symbols['open']:
            opened.append(string(uc.reg_read(UC_ARM_REG_R0)));uc.emu_stop();return
        elif mode=='request-power-on-prefix' and pc==symbols['read']:
            assert uc.reg_read(UC_ARM_REG_R0)==42 and uc.reg_read(UC_ARM_REG_R2)==1020
            udata=struct.pack('<I',3)+b'\0'*1016
            uc.mem_write(uc.reg_read(UC_ARM_REG_R1),udata);request_reads.append({'kind':3,'bytes':1020})
            uc.reg_write(UC_ARM_REG_R0,1020);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
        elif mode=='request-power-on-prefix' and pc==symbols['memset']:
            uc.mem_write(uc.reg_read(UC_ARM_REG_R0),bytes([uc.reg_read(UC_ARM_REG_R1)&255])*uc.reg_read(UC_ARM_REG_R2))
        elif mode=='request-power-on-prefix' and pc in (0xa14c,0xa760,0x2327c):pass
        else:return
        uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    u.hook_add(UC_HOOK_CODE,hook)
    u.reg_write(UC_ARM_REG_R0,obj);u.reg_write(UC_ARM_REG_R1,0);u.reg_write(UC_ARM_REG_SP,0x31f000);u.reg_write(UC_ARM_REG_LR,end)
    u.emu_start(entry,end,count=3000)
    if mode=='initialize':
        assert u.reg_read(UC_ARM_REG_PC)==end and u.reg_read(UC_ARM_REG_R0)==0
        assert mutexes==[16,40] and not commands and not opened
        assert bytes(u.mem_read(obj,13))==b'\xff'*8+b'\0'*5
    else:
        assert len(opened)==1
        assert commands==['/usr/local/bin/wlanapi.sh stop','/usr/local/bin/wlanapi.sh unload',
                          '/usr/local/bin/wlanapi.sh load','/usr/local/bin/wlanapi.sh start']
        if mode=='request-power-on-prefix':assert request_reads==[{'kind':3,'bytes':1020}]
    rows.append({'mode':mode,'entry':hex(entry),'mutex_offsets':mutexes,'captured_system_requests':commands,
                 'stopped_before_open':opened,'supplied_requests':request_reads})
driver_elf=ELFFile(io.BytesIO(driver));symtab=driver_elf.get_section_by_name('.symtab')
relocs={r['r_offset']:r for r in driver_elf.get_section_by_name('.rel.text').iter_relocations()}
assert symtab.get_symbol(relocs[0x978]['r_info_sym']).name=='alloc_etherdev'
assert symtab.get_symbol(relocs[0xbf8]['r_info_sym']).name=='register_netdev'
gpl_path=ROOT/'work/downloads/linux-kernel-2.6.10.local.tgz'
with tarfile.open(gpl_path) as tar:eth=tar.extractfile('./net/ethernet/eth.c').read()
assert b'return alloc_netdev(sizeof_priv, "eth%d", ether_setup);' in eth
assert netstart.index(b'ifconfig eth0 >')<netstart.index(b'\tcheckconf\n')
report={'daemon_sha256':hashlib.sha256(daemon).hexdigest(),'driver_sha256':hashlib.sha256(driver).hexdigest(),
        'power_on_request_kind':3,'power_on_request_label':'CNMGR_DAEMON_MAIN_REQ_KIND_POWER_ON',
        'eth_source_sha256':hashlib.sha256(eth).hexdigest(),'default_interface_template':'eth%d',
        'cases':rows,'all_passed':True,'physical_device_access':False,
        'limits':['Original daemon init and power-on prefix execute only in Unicorn; system/mutex calls virtual and execution stops before open.',
                  'Kernel alloc_etherdev source and actual driver relocation agree on allocation mechanism; actual interface number/name not observed.',
                  'No full daemon request loop/startup scheduling or actual driver load; eth0 before S70 remains unproven.',
                  'No netconfig/payload generated or installed; no host or device commands executed from captured system strings.']}
report['limits'].append('Request-prefix case injects one1020-byte kind3 request; source application, FIFO scheduling and early-boot occurrence not verified.')
(ROOT/'sources/native-stock-network-entry.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
