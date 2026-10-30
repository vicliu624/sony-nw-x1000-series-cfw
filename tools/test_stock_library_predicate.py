"""Compare the ARM query builder against Sony's executed list initialization."""
from pathlib import Path
import hashlib,io,json,struct,subprocess,tarfile,re,sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/stock-library-predicate';work.mkdir(exist_ok=True)
sources=['runtime/platform/player/stock_query.c','tools/fixtures/stock_info_host.c']
app=work/'query.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--build-id=none,-Ttext=0x50000000,-e,_start',*sources,'-lgcc','-o',str(app)],cwd=ROOT,check=True)
stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(stock).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
for raw in (stock,app.read_bytes()):
 for segment in ELFFile(io.BytesIO(raw)).iter_segments():
  if segment['p_type']!='PT_LOAD':continue
  a=int(segment['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(segment['p_memsz'])+4095)&~4095);u.mem_write(a,segment.data())
area=0x71000000;u.mem_map(area,65536);base=0x66e158;built=area+8192;done=area+16384;stop=[None]
def hook(uc,pc,size,data):
 if pc==0xb93a0 and uc.reg_read(UC_ARM_REG_R2)==base+0xdfc:stop[0]=uc.reg_read(UC_ARM_REG_LR)
 if pc==stop[0] or pc==done:uc.emu_stop()
u.hook_add(UC_HOOK_CODE,hook)
u.reg_write(UC_ARM_REG_R0,base);u.reg_write(UC_ARM_REG_SP,area+65520);u.reg_write(UC_ARM_REG_LR,done)
u.emu_start(0x47cac,done+4,count=100000)
assert stop[0] and u.reg_read(UC_ARM_REG_PC)==stop[0]
def tree(address,depth=0):
 assert depth<8
 row=struct.unpack('<8I',u.mem_read(address,32))
 if row[0] in (9,10):return (row[:6],tree(row[6],depth+1),tree(row[7],depth+1))
 assert row[6:]==(0,0);return row
original=tree(base+200)
elf=ELFFile(io.BytesIO(app.read_bytes()));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
u.reg_write(UC_ARM_REG_R0,built);u.reg_write(UC_ARM_REG_SP,area+65520);u.reg_write(UC_ARM_REG_LR,done)
u.emu_start(symbols['xw_stock_track_query_build'],done+4,count=10000)
assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==0
assert tree(built+128)==original
original_entries=struct.unpack('<6I',u.mem_read(struct.unpack('<I',u.mem_read(base+0xa88,4))[0],24))
assert struct.unpack('<I',u.mem_read(base+0xa88+4,4))[0]==3
assert struct.unpack('<2I',u.mem_read(built+160,8))==(built+168,3)
assert struct.unpack('<6I',u.mem_read(built+168,24))==original_entries
# Execute the original view/depth selector, without modeling its table reads.
frame=area+2048
for reg,value in ((UC_ARM_REG_R0,frame),(UC_ARM_REG_R1,5),(UC_ARM_REG_R2,0xffffffff),(UC_ARM_REG_R3,0xffffffff),(UC_ARM_REG_SP,area+65520),(UC_ARM_REG_LR,done)):u.reg_write(reg,value)
u.emu_start(0x46d74,done+4,count=10000)
assert u.reg_read(UC_ARM_REG_PC)==done
selected=struct.unpack('<I',u.mem_read(frame+4,4))[0]
assert selected==base+0x4e8
candidate=tree(selected)
assert candidate==(1,2,9,0,3,0,0,0)
assert struct.unpack('<I',u.mem_read(frame+0x118,4))[0]==1
# The same original view's second depth selects the item predicate.
for reg,value in ((UC_ARM_REG_R0,frame),(UC_ARM_REG_R1,5),(UC_ARM_REG_R2,0xffffffff),(UC_ARM_REG_R3,0xffffffff),(UC_ARM_REG_SP,area+65520),(UC_ARM_REG_LR,done)):u.reg_write(reg,value)
u.emu_start(0x46d74,done+4,count=10000)
assert u.reg_read(UC_ARM_REG_PC)==done
member_predicate=tree(struct.unpack('<I',u.mem_read(frame+28+4,4))[0])
assert member_predicate==(1,0,9,0,0,0,0,0)
assert struct.unpack('<I',u.mem_read(frame+0x118,4))[0]==2
# Original table selects sort0 for the list names and sort13 for members.
assert struct.unpack('<I',u.mem_read(0x4e5b3c+5*128+4,4))[0]==0
assert struct.unpack('<I',u.mem_read(0x4e5b3c+5*128+8,4))[0]==13
member_sort=struct.unpack('<2I',u.mem_read(struct.unpack('<I',u.mem_read(base+0xdfc,4))[0],8))
assert member_sort==(0x22,0)
label_offset=stock.index(b'MOMA_METADATA_KEY_CHILDINDEX\0')
segments=ELFFile(io.BytesIO(stock)).iter_segments()
label_addresses=[int(seg['p_vaddr'])+label_offset-int(seg['p_offset']) for seg in segments if seg['p_type']=='PT_LOAD' and int(seg['p_offset'])<=label_offset<int(seg['p_offset'])+int(seg['p_filesz'])]
assert len(label_addresses)==1
registry_offset=stock.index(struct.pack('<I',label_addresses[0]))
assert struct.unpack_from('<I',stock,registry_offset-4)[0]==member_sort[0]
for members,expected in ((0,candidate),(1,member_predicate)):
 for reg,value in ((UC_ARM_REG_R0,built),(UC_ARM_REG_R1,members),(UC_ARM_REG_SP,area+65520),(UC_ARM_REG_LR,done)):u.reg_write(reg,value)
 u.emu_start(symbols['xw_stock_list_query_build'],done+4,count=10000)
 assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==0
 assert tree(built+128)==expected
 assert struct.unpack('<2I',u.mem_read(built+160,8))==(built+168,1 if members else 3)
 assert struct.unpack('<' + ('2I' if members else '6I'),u.mem_read(built+168,8 if members else 24))==(member_sort if members else original_entries)
# Resolve the visible menu label from the same pinned original rootfs.
sys.path.insert(0,str(ROOT/'scripts'))
from resources import parse_stx
rootfs=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(rootfs).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
resource_checks=[]
with tarfile.open(fileobj=io.BytesIO(rootfs),mode='r:gz') as archive:
 jp=archive.extractfile('./usr/local/share/gemini/res/stx/ucs2-dev-jp.stx').read();labels=parse_stx(jp)
 for sid in ('239-00','239-01'):
  name='./usr/local/share/gemini/res/swd/ucs2-dev-sid-'+sid+'.swd'
  swd=archive.extractfile(name).read();text=swd.decode('utf-8')
  resource_type=re.search(r'type:\s*"([^"]+)"',text).group(1)
  mapping={int(slot):int(tid) for slot,tid in re.findall(r'tid\.(\d+):\s*"tid-(\d+)"',text)}
  assert mapping[5]==501 and labels[mapping[5]]=='プレイリスト'
  assert mapping[6]==446 and labels[mapping[6]]=='フォルダ'
  resource_checks.append(dict(sid=sid,resource_type=resource_type,playlist_slot=5,playlist_tid=501,folder_slot=6,folder_tid=446,sha256=hashlib.sha256(swd).hexdigest()))
report=dict(passed=True,device_accessed=False,original_initializer='0x47cac',original_predicate_offset=200,normalized_tree=original,original_menu_labels=resource_checks,original_jp_stx_sha256=hashlib.sha256(jp).hexdigest(),music_view5_selector_verified=True,view5_format_predicate=candidate,view5_member_predicate=member_predicate,view5_member_sort=member_sort,original_sort_entries=original_entries,source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources+['runtime/platform/player/stock_query.h','tools/test_stock_library_predicate.py']},limits=['Original initializer prefix and predicate helpers execute without replacing their semantics.','Predicate/sort equivalence and original view5 selection are verified; its user-visible label, real database contents, playlist membership and runtime integration remain unqualified.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
