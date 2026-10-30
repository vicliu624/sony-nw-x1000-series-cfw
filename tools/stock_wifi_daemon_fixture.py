"""PC-only original ARM daemon command/event handler fixture, not a device app.
Driver effects and one synthetic AP's validation are modeled. Replies, pending
records and state transitions are produced by original daemon instructions.
"""
from pathlib import Path
import hashlib,io,struct
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_INTR,UC_HOOK_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

class StockWifiDaemon:
    def __init__(self,root,initial_state=0):
        raw=(Path(root)/'work/qqmusic-wifi/cnmgr_daemon').read_bytes()
        self.sha256=hashlib.sha256(raw).hexdigest()
        assert self.sha256=='351eb99a05ae9a6baf00c8d8fd6e5e16129cc58dc6f300cf5f43d0fc5ad4eb35'
        elf=ELFFile(io.BytesIO(raw));self.u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
        self.u.mem_map(0x8000,0x100000)
        for segment in elf.iter_segments():
            if segment['p_type']=='PT_LOAD':self.u.mem_write(segment['p_vaddr'],segment.data())
        self.u.mem_map(0x2000000,0x50000);self.obj=0x2001000;self.end=0x2000100
        self.drivers={s['st_value']:s.name for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name.startswith(('cnmgr_wlan_','cnmgr_ip_')) and s['st_value']}
        for offset,value in ((0,100),(4,101),(8,102),(12,103),(16,0xffffffff),(0x428,104),(0xa080,105),(0xa09c,initial_state),(0xa0b4,1)):
            self.put(self.obj+offset,value)
        self.u.mem_write(self.obj+0xa138,b'A'+bytes(1003))
        self.put(self.obj+0xa138+0x2a0,1)
        self.read_fd=None;self.input=b'';self.replies=[];self.state_writes=[];self.driver_calls=[]
        self.u.hook_add(UC_HOOK_CODE,self.hook)
        self.u.hook_add(UC_HOOK_INTR,self.reject)
        self.u.hook_add(UC_HOOK_MEM_WRITE,self.memory_write)
    def word(self,address):return struct.unpack('<I',self.u.mem_read(address,4))[0]
    def put(self,address,value):self.u.mem_write(address,struct.pack('<I',value))
    @property
    def state(self):return self.word(self.obj+0xa09c)
    @property
    def reference_count(self):return self.word(self.obj+0x13254)
    def reject(self,*unused):raise AssertionError('Unexpected system instruction')
    def memory_write(self,uc,access,address,size,value,unused):
        if address<self.obj+0xa0a0 and address+size>self.obj+0xa09c:self.state_writes.append(value)
    def hook(self,uc,pc,size,unused):
        r0,r1,r2=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
        if pc==self.end:uc.emu_stop();return
        # Read-only original getter body is executed; its lock delivery is a
        # fixture boundary, while the1004-byte memcpy uses the existing bridge.
        if pc==0x1150c:return
        if pc==0x12cfc:
            self.driver_calls.append('cnmgr_ip_cancel_start');return  # original result mutation
        if pc in self.drivers:
            name=self.drivers[pc]
            assert name in ('cnmgr_wlan_power_on','cnmgr_wlan_get_weth','cnmgr_ip_prepare','cnmgr_wlan_config','cnmgr_ip_set_connect_info','cnmgr_wlan_connect','cnmgr_ip_start','cnmgr_wlan_cancel','cnmgr_ip_dhcp_stop','cnmgr_ip_stop','cnmgr_wlan_disconnect'),name
            self.driver_calls.append(name)
        elif pc==0x9fac:
            assert r0==self.read_fd and len(self.input)<=r2,(r0,self.read_fd,r2)
            uc.mem_write(r1,self.input);result=len(self.input)
        elif pc==0x9ae4:
            assert r0 in (102,103) and r2==1012,(r0,r2)
            self.replies.append(('main' if r0==102 else 'sub',bytes(uc.mem_read(r1,r2))));result=r2
        elif pc==0x9a6c:uc.mem_write(r0,bytes([r1&255])*r2);result=r0
        elif pc==0x9b80:uc.mem_write(r0,bytes(uc.mem_read(r1,r2)));result=r0
        elif pc==0x9b14:
            a=bytes(uc.mem_read(r0,r2)).split(b'\0')[0];b=bytes(uc.mem_read(r1,r2)).split(b'\0')[0];result=0 if a==b else 1
        elif pc in (0xa1a0,0x14698,0xa14c,0xa760,0x2327c,0x9d0c,0x9f40):pass
        else:return
        uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    def run(self,entry,channel=0):
        self.replies=[]
        for reg,value in ((UC_ARM_REG_R0,self.obj),(UC_ARM_REG_R1,channel),(UC_ARM_REG_R2,0),(UC_ARM_REG_R3,0),(UC_ARM_REG_SP,0x204f000),(UC_ARM_REG_LR,self.end)):
            self.u.reg_write(reg,value)
        self.u.emu_start(entry,self.end,count=50000)
        assert self.u.reg_read(UC_ARM_REG_PC)==self.end
        return list(self.replies)
    def command(self,channel,packet):
        assert len(packet)==1020
        self.input=packet;self.read_fd=100 if channel=='main' else 101
        return self.run(0xba18,0 if channel=='main' else 1)
    def wlan(self,message):
        self.input=message.encode()+b'\n';self.read_fd=104
        return self.run(0xd8b0)
    def ip(self,event):
        self.input=struct.pack('<I',event);self.read_fd=105
        return self.run(0xb538)
