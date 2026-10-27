"""Original recovery worker loads its eight real packed groups; virtual file/OS services."""
import runpy,struct,json,hashlib,sys,re,argparse
p=argparse.ArgumentParser();p.add_argument("--native-cancel-ticket",action="store_true");args=p.parse_args()
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_SP
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];root=n['ROOT'];sys.path.insert(0,str(root/'scripts'));from resources import parse_tgp
groups=[0,1,2,3,9,15,16,17];files={g:(root/f'work/resource-analysis/TEXGRP{g:02d}.DAT').read_bytes() for g in groups}
provenance=json.loads((root/'sources/native-worker-resource-requests.json').read_text())
expected_hashes={f['group']:f['sha256'] for f in provenance['cases'][0]['stock_group_files']}
assert all(hashlib.sha256(data).hexdigest()==expected_hashes[g] for g,data in files.items())
base={g:0x70000000+g*0x1000000 for g in groups};streams={};requests=[];unmaps=[];closes=[];boundaries=[];cancel_checks=[]
for g,data in files.items():u.mem_map(base[g],(len(data)+4095)&~4095);u.mem_write(base[g],data)
def group_at(address):
 value=bytes(u.mem_read(address,128)).split(b'\0')[0].decode();m=re.fullmatch(r'/usr/local/share/GUI/skinRom/TEXGRP(\d\d)\.DAT',value);assert m,value;g=int(m[1]);assert g in files;return g
def hook(uc,pc,size,data):
 if args.native_cancel_ticket and pc==0x117fc:
  cancel_checks.append(n['word'](0x60015000+12));return
 if args.native_cancel_ticket and pc in (0x337930,0x337948):
  uc.reg_write(UC_ARM_REG_R0,0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
 if pc==0xf6a58:
  requests.append(uc.reg_read(UC_ARM_REG_R2));return
 virtual=(0xe324,0x132774,0x132834,0x132800,0xe09c,0xdafc,0xd6b8,0xd808,0xd574,0xd85c,0xdb08,0x3397f4,0xd934,0xd6f4,0x3387c0,0x338dd4,0x3ce08,0x3d6dc,0x33c528,0xf5714,0xb4a54,0xb52dc,0x117fc)
 if pc not in virtual:return
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)];result=0
 if pc in (0x3387c0,0x338dd4):result=1 if pc==0x338dd4 else 0
 elif pc==0xd574:u.mem_write(a[0],bytes([a[1]&255])*a[2]);result=a[0]
 elif pc==0xd85c:u.mem_write(a[0],bytes(u.mem_read(a[1],a[2])));result=a[0]
 elif pc==0xdb08:result=len(bytes(u.mem_read(a[0],128)).split(b'\0')[0])
 elif pc==0x3397f4:
  fmt=bytes(u.mem_read(a[3],128)).split(b'\0')[0].decode();text=(fmt%n['word'](uc.reg_read(UC_ARM_REG_SP))).encode();assert len(text)<a[1];u.mem_write(a[0],text+b'\0');result=len(text)
 elif pc==0xe324:assert a[0]==30;result=4096
 elif pc==0x132774:streams[a[0]]=group_at(a[2])
 elif pc==0x132834:assert a[3]==32;u.mem_write(a[2],files[streams[a[0]]][:32])
 elif pc==0x132800:streams.pop(a[0],None)
 elif pc==0xe09c:assert a[1]==0;result=100+group_at(a[0])
 elif pc==0xdafc:
  g=n['word'](uc.reg_read(UC_ARM_REG_SP))-100;assert a==[0,(len(files[g])+4095)&~4095,3,2];result=base[g]
 elif pc==0xd934:
  g=next(g for g in groups if base[g]==a[0]);assert a[1]==(len(files[g])+4095)&~4095;unmaps.append(g)
 elif pc==0xd6f4:g=a[0]-100;assert g in groups;closes.append(g)
 elif pc==0xd6b8:
  left=bytes(u.mem_read(a[0],a[2])).split(b'\0')[0];right=bytes(u.mem_read(a[1],a[2])).split(b'\0')[0];result=0 if left==right else 1
 elif pc==0xd808:assert a[1];result=a[0]//a[1];uc.reg_write(UC_ARM_REG_R1,a[0]%a[1])
 else:boundaries.append(hex(pc))
 uc.reg_write(UC_ARM_REG_R0,result);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def call(pc,values):
 for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),values):u.reg_write(reg,value)
 u.reg_write(UC_ARM_REG_SP,0x60008000);u.reg_write(UC_ARM_REG_LR,0x50000000)
 try:u.emu_start(pc,0x50000000,count=20000000)
 except Exception as exc:raise AssertionError((hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR)),requests)) from exc
 assert u.reg_read(UC_ARM_REG_PC)==0x50000000
 return u.reg_read(UC_ARM_REG_R0)
manager=0x7a0660;catalog=call(0xf647c,())
assert call(0x11e9b8,(manager,))==0;call(0xf6488,(catalog,))
if args.native_cancel_ticket:
 call(0x3365bc,(0x60015000,0))
 u.mem_write(0x613f00+0x4c,struct.pack('<I',0x60015000))
assert call(0x11a04,(0,))==0 and requests==groups,requests
expected=sum(len(parse_tgp(d)) for d in files.values());assert expected==550
assert n['word'](manager)==8 and n['word'](manager+0x30294)==expected
lookup=0x60010000;assert call(0xf6c58,(catalog,0,51,lookup))==0
handle=n['word'](lookup);image=manager+0x192a4+handle*88
assert list(struct.unpack('<3I',u.mem_read(image,12)))==[78,78,0x10008]
assert call(0xf6bfc,(catalog,))==0
assert n['word'](manager)==0 and n['word'](manager+0x30294)==0
assert sorted(unmaps)==groups and sorted(closes)==groups
r={'SpiderApp_sha256':n['digest'],'scope':'Original recovery worker loads eight actual DAT groups,registers/maps550 images and releases all','mode_fixture':0,'groups':groups,'images_loaded':expected,'groups_after_release':0,'images_after_release':0,'unmapped_groups':unmaps,'closed_groups':closes,'virtual_worker_boundaries':sorted(set(boundaries)),'files':[{'group':g,'bytes':len(files[g]),'sha256':hashlib.sha256(files[g]).hexdigest()} for g in groups],'limits':['Mode getter3d6dc supplies0; real current device mode not established.','File/mmap/libc/directory services virtual; callback117fc supplies no cancellation, status UI and post-load display helpers virtual.','Not connected to combined Home test, real process/thread/driver or actual rendering.']}
if args.native_cancel_ticket:
 r['unmapped_groups']=unmaps.copy();r['closed_groups']=closes.copy()
 assert cancel_checks and all(v==0 for v in cancel_checks)
 assert call(0x3365d8,(0x60015000,))==0
 assert call(0x117fc,())==0x106
 requests.clear();unmaps.clear();closes.clear();cancel_checks.clear()
 status=call(0x11a04,(0,))
 assert status==0x106 and requests==[0],(status,requests)
 assert n['word'](manager)==1 and n['word'](manager+0x30294)==139
 assert call(0xf6bfc,(catalog,))==0
 assert n['word'](manager)==0 and n['word'](manager+0x30294)==0 and unmaps==[0] and closes==[0]
 call(0x336634,(0x60015000,));assert call(0x117fc,())==0
 r['native_cancellation']={'ticket_init':'0x3365bc','cancel':'0x3365d8','predicate':'0x117fc','clear':'0x336634','worker_return':hex(status),'groups_requested_after_cancel':requests.copy(),'images_before_cancelled_cleanup':139,'images_after_cleanup':0,'unmapped_after_cancel':unmaps.copy(),'closed_after_cancel':closes.copy(),'clear_restores_predicate0':True}
 r['limits']=['Mode0, ticket storage/owner binding and mutex handle supplied; mutex operations virtual.', 'Native ticket init/cancel/predicate/clear execute. Cancel is requested before worker start; first packed group still loads before cancellation check.', 'Filesystem/mmap/libc/status UI/display helpers virtual; no concurrent OS cancellation or USB/APF stop-source qualification.']
(root/('sources/native-worker-cancel-ticket.json' if args.native_cancel_ticket else 'sources/native-worker-asset-loading.json')).write_text(json.dumps(r,indent=2)+'\n');print('Original worker loaded/released',expected,'images in',len(groups),'groups')
