"""Original manager lookup with native configuration parsing or bounded record fixtures."""
from pathlib import Path
import io,struct,hashlib
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC

def lookup(root,packet,records=None,core_state=2,config_bytes=None,details=None,session=None):
 raw=(Path(root)/'work/targets-jp/sysmgrd').read_bytes();assert hashlib.sha256(raw).hexdigest()=='131b7d1fd3e20d9a7cc695b938da5f28ecec35fc56538370e85f915adaeadff0'
 assert len(packet)==276
 words=list(struct.unpack('<5I',packet[:20]));assert words[0]==276 and words[3]==36 and words[4]>0
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x8000,0x40000)
 elf=ELFFile(io.BytesIO(raw));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
 for segment in elf.iter_segments():
  if segment['p_type']=='PT_LOAD':u.mem_write(segment['p_vaddr'],segment.data())
 u.mem_map(0x60000000,0x20000);u.mem_map(0x50000000,4096)
 core,table,ipc,request,end=0x60000000,0x60008000,0x60006000,0x60006100,0x50000000
 put=lambda p,v:u.mem_write(p,struct.pack('<I',v))
 parsing=config_bytes is not None;position=0;allocations=[]
 if parsing:assert records is None and 0<len(config_bytes)<=8192 and b'\0' not in config_bytes
 else:
  assert records is not None
  put(core,len(records));put(core+4,table)
  for index,record in enumerate(records):
   address=table+index*0x510;put(address,int(record['id'],0));u.mem_write(address+4,record['name'].encode()+b'\0')
 u.mem_write(ipc,struct.pack('<II',core,44));u.mem_write(request,packet);replies=[];comparisons=[]
 def string(p):return bytes(u.mem_read(p,256)).split(b'\0',1)[0].decode()
 def hook(uc,pc,size,data):
  nonlocal position
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
  if parsing:
   word=lambda p:struct.unpack('<I',uc.mem_read(p,4))[0]
   if pc==symbols['fopen']:assert string(a[0])=='/fixture/AppList.conf';result=77
   elif pc==symbols['fgetpos']:put(a[1],position)
   elif pc==symbols['fsetpos']:position=word(a[1])
   elif pc==symbols['fseek']:assert a[1:]==[0,0];position=0
   elif pc==symbols['fgets']:
    if position<len(config_bytes):
     last=config_bytes.find(b'\n',position);last=len(config_bytes) if last<0 else last+1
     piece=config_bytes[position:min(last,position+a[1]-1)];uc.mem_write(a[0],piece+b'\0');position+=len(piece);result=a[0]
   elif pc==symbols['malloc']:
    assert not allocations and 0<a[0]<=0x7000 and a[0]%0x510==0;allocations.append(a[0]);result=table
   elif pc==symbols['getpwnam']:
    assert string(a[0])=='app';put(0x60017008,100);put(0x6001700c,100);result=0x60017000
   elif pc==symbols['memcpy']:uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));result=a[0]
   elif pc==symbols['__strtok_r']:
    cursor=a[0] or word(a[2]);separators=string(a[1]).encode()
    while uc.mem_read(cursor,1)[0] in separators:cursor+=1
    start=cursor
    while uc.mem_read(cursor,1)[0] and uc.mem_read(cursor,1)[0] not in separators:cursor+=1
    if uc.mem_read(cursor,1)[0]:uc.mem_write(cursor,b'\0');cursor+=1
    put(a[2],cursor);result=start if string(start) else 0
   elif pc==symbols['__strtol_internal']:result=int(string(a[0]),0)
   elif pc==symbols['strlen']:result=len(string(a[0]))
   elif pc==symbols['strcmp']:result=0 if string(a[0])==string(a[1]) else 1
   elif pc in (0x1c888,0x1c8c8):raise AssertionError('Original parser rejected configuration')
   elif pc not in (symbols['getuid'],symbols['getgid'],symbols['fclose']):return
   uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
  if pc not in (0x9abc,0xa188,0x1c5ac,0x16d18):return
  if pc==0x9abc:
   left,right=string(a[0]),string(a[1]);comparisons.append([left,right]);result=0 if left==right else 1
  elif pc==0x16d18:
   assert a[:2]==[44,words[4]];replies.append(bytes(uc.mem_read(a[2],20)))
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 hook_id=u.hook_add(UC_HOOK_CODE,hook)
 if parsing:
  u.mem_write(0x60001000,b'/fixture/AppList.conf\0')
  for register,value in ((UC_ARM_REG_R0,core),(UC_ARM_REG_R1,0x60001000),(UC_ARM_REG_SP,0x6001f000),(UC_ARM_REG_LR,end)):u.reg_write(register,value)
  u.emu_start(0x1574c,end,count=100000);assert u.reg_read(UC_ARM_REG_PC)==end and u.reg_read(UC_ARM_REG_R0)==0
  count,pointer=struct.unpack('<2I',u.mem_read(core,8));assert 0<count<=16 and pointer==table
  if details is not None:details.update({'native_parser_executed':True,'record_count':count,'table_address':hex(table),'config_sha256':hashlib.sha256(config_bytes).hexdigest()})
  parsing=False
 put(core+0x503c,core_state)
 for register,value in ((UC_ARM_REG_R0,ipc),(UC_ARM_REG_R1,request),(UC_ARM_REG_SP,0x6001f000),(UC_ARM_REG_LR,end)):u.reg_write(register,value)
 u.emu_start(0x1084c,end,count=10000);assert u.reg_read(UC_ARM_REG_PC)==end and len(replies)==1
 u.hook_del(hook_id)
 if session is not None:session.update({'emulator':u,'core':core,'table':table,'queries':1,'config_sha256':hashlib.sha256(config_bytes).hexdigest() if config_bytes is not None else None})
 return replies[0],comparisons


def request_in_session(session,packet,details=None):
 """Run a stock APF name/argv/battery/USB-state service on retained RAM."""
 assert len(packet) in (20,24,276)
 words=list(struct.unpack('<5I',packet[:20]));operation=words[3]
 assert operation in (1,7,8,35,36) and words[0]==len(packet) and len(packet)==(276 if operation==36 else 24 if operation==1 else 20) and words[4]>0
 reply_size={1:16,7:24,8:20,35:1044,36:20}[operation]
 u=session['emulator'];core=session['core'];table=session['table']
 count,pointer=struct.unpack('<2I',u.mem_read(core,8));assert 0<count<=16 and pointer==table
 before=bytes(u.mem_read(table,count*0x510));core_state=bytes(u.mem_read(core+0x503c,4))
 ipc,request,end=0x60006000,session.get('request_address',0x60006100),0x50000000
 assert list(struct.unpack('<2I',u.mem_read(ipc,8)))==[core,44]
 u.mem_write(request,packet);replies=[];comparisons=[];queued=[];usb_queries=[]
 def string(address):return bytes(u.mem_read(address,256)).split(b'\0',1)[0].decode()
 def hook(uc,pc,size,data):
  a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];result=0
  if pc==0x9abc:
   left,right=string(a[0]),string(a[1]);comparisons.append([left,right]);result=0 if left==right else 1
  elif pc==0x16d18:
   assert a[:2]==[44,words[4]];replies.append(bytes(uc.mem_read(a[2],reply_size)))
  elif operation==8 and pc==0x9a5c:
   assert a[0]==session['usb_fd_fixture'] and a[1]==0x80046701
   value=session['usb_raw_state_fixture'];assert 0<=value<=4
   uc.mem_write(a[2],struct.pack('<I',value));usb_queries.append({'fd_fixture':a[0],'request':hex(a[1]),'raw_state_fixture':value})
  elif operation==1 and pc==0x1967c:
   assert a[0]==77 and a[2]==52;queued.append(list(struct.unpack('<5I',uc.mem_read(a[1],20))))
  elif pc==0x99d8:uc.mem_write(a[0],bytes(uc.mem_read(a[1],a[2])));result=a[0]
  elif pc not in (0xa188,0x1c5ac,0x1a4f0,0x1a508,0x12034):return
  uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
 handle=u.hook_add(UC_HOOK_CODE,hook)
 try:
  for register,value in ((UC_ARM_REG_R0,ipc),(UC_ARM_REG_R1,request),(UC_ARM_REG_SP,0x6001f000),(UC_ARM_REG_LR,end)):u.reg_write(register,value)
  u.emu_start({1:0xf75c,7:0xfb1c,8:0xfb88,35:0x10750,36:0x1084c}[operation],end,count=30000);assert u.reg_read(UC_ARM_REG_PC)==end and len(replies)==1
 finally:u.hook_del(handle)
 assert bytes(u.mem_read(table,count*0x510))==before
 assert list(struct.unpack('<2I',u.mem_read(core,8)))==[count,table] and bytes(u.mem_read(core+0x503c,4))==core_state
 session['queries']+=1
 if details is not None:details.update({'native_parser_executed':False,'retained_native_parser_table':True,'same_manager_instance':True,'record_count':count,'table_address':hex(table),'config_sha256':session['config_sha256'],'table_sha256_unchanged':hashlib.sha256(before).hexdigest(),'query_number':session['queries'],'operation':operation,'queued_notifications':queued,'usb_state_queries_virtual':usb_queries})
 return replies[0],comparisons


def lookup_in_session(session,packet,details=None):
 assert len(packet)==276 and struct.unpack_from('<I',packet,12)[0]==36
 return request_in_session(session,packet,details=details)
