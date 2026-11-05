"""Join original music menu branches, query selection and metadata projections."""
import hashlib,io,json,re,struct,sys,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
raw=(ROOT/'work/targets-jp/SpiderApp').read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
image=ELFFile(io.BytesIO(raw));segments=[s for s in image.iter_segments() if s['p_type']=='PT_LOAD'];u=Uc(UC_ARCH_ARM,UC_MODE_ARM)
for s in segments:
 a=int(s['p_vaddr']);b=a&~4095;u.mem_map(b,(a-b+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
area=0x71000000;u.mem_map(area,65536);main=area+0x1000;outputs=[area+0x9000+i*4 for i in range(5)];done=area+0xff00;base=0x66e158;initializing=[True];events=[]
get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
put=lambda a,v:u.mem_write(a,struct.pack('<I',v&0xffffffff))
def named_key(name):
 offset=raw.index(name.encode()+b'\0');matches=[int(s['p_vaddr'])+offset-int(s['p_offset']) for s in segments if int(s['p_offset'])<=offset<int(s['p_offset'])+int(s['p_filesz'])];assert len(matches)==1
 pattern=struct.pack('<I',matches[0]);at=raw.index(pattern);assert raw.find(pattern,at+4)<0
 return struct.unpack_from('<I',raw,at-4)[0]
def hook(cpu,pc,size,data):
 if pc==done or(initializing[0] and pc==0x47b48):cpu.emu_stop();return
 value=0
 if pc==0x434b8:value=main
 elif pc==0x41518:assert cpu.reg_read(UC_ARM_REG_R0)==0x10000000;value=0x1122
 elif pc==0x4215c:
  assert cpu.reg_read(UC_ARM_REG_R2)==base+0x4e8;put(get(cpu.reg_read(UC_ARM_REG_SP)+12),1)
 elif pc==0xa57f0:events.append(tuple(cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)))
 elif pc in (0x74608,0x74668,0x1f150):pass
 else:return
 cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def call(pc,*args):
 sp=area+0xf000
 for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
 for i,v in enumerate(args[4:]):put(sp+i*4,v)
 u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done);u.emu_start(pc,done+4,count=200000)
 if not initializing[0]:assert u.reg_read(UC_ARM_REG_PC)==done
 return u.reg_read(UC_ARM_REG_R0)
call(0x47cac,base);assert u.reg_read(UC_ARM_REG_PC)==0x47b48 and u.reg_read(UC_ARM_REG_LR)==0x48778;initializing[0]=False
names=('TITLE','ALBUM','ARTIST','GENRE','RELEASEYEAR','TITLE');views=(0,3,2,1,4,5);rows=[]
for row,(name,view) in enumerate(zip(names,views)):
 u.mem_write(main,bytes(0x7200));events.clear();call(0x87598,0,0,row)
 assert [e for e in events if e[0]==0x530002]==[(0x530002,0,0,view)]
 call(0x44408,main,0,view,0xffffffff);frame=main+view*0x124+0x30
 assert get(main+12)==view and get(frame+4)==view and get(frame+0x120)==1
 call(0x47268,frame,*outputs);predicate,projection,auxiliary,sort,parent=[get(a) for a in outputs]
 key=get(projection+12);expected=named_key('MOMA_METADATA_KEY_'+name);assert key==expected,(row,name,key,expected)
 assert get(projection)==projection+12 and get(projection+4)>0 and get(projection+8)>0
 aggregation=call(0xb8404,projection);assert aggregation==int(row in (1,2,3,4))
 if row==5:assert struct.unpack('<8I',u.mem_read(predicate,32))==(1,named_key('MOMA_METADATA_KEY_FORMAT'),9,0,3,0,0,0)
 else:assert predicate==base+200
 rows.append(dict(menu_row=row,view=view,first_moma_key=key,metadata_name=name,ui_property_index=get(projection+80),aggregation=bool(aggregation),predicate=hex(predicate)))
sys.path.insert(0,str(ROOT/'scripts'));from resources import parse_stx
rootfs=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(rootfs).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(rootfs),mode='r:gz') as t:
 stx=t.extractfile('./usr/local/share/gemini/res/stx/ucs2-dev-jp.stx').read();labels=parse_stx(stx)
 swd=t.extractfile('./usr/local/share/gemini/res/swd/ucs2-dev-sid-239-00.swd').read();text=swd.decode('utf-8',errors='replace')
 mapping={int(slot):int(tid) for slot,tid in re.findall(r'tid\.(\d+):\s*"tid-(\d+)"',text)}
 for row in rows:row['word_tid']=mapping[row['menu_row']];row['original_japanese_label']=labels[row['word_tid']]
 assert [r['word_tid'] for r in rows]==[39,40,41,42,44,501] and rows[-1]['original_japanese_label']=='プレイリスト'
report=dict(passed=True,target_sha256=sha,source_sha256=hashlib.sha256((ROOT/'tools/test_stock_music_search_mapping.py').read_bytes()).hexdigest(),rows=rows,device_accessed=False,word_resource_sha256=hashlib.sha256(swd).hexdigest(),resource_parser_sha256=hashlib.sha256((ROOT/'scripts/resources.py').read_bytes()).hexdigest(),limits=['Original query/projection initialization up to locale-dependent finalization, menu branch, view reset/selection, descriptor and aggregation getter execute.','Menu navigation/render effects, context lookup and availability count result are modeled.','Word-set correspondence is verified; active widget/SWD loading, actual SonicStage database rows and physical playlist membership are not qualified.'])
p=ROOT/'work/player-stock-music-search-mapping';p.mkdir(exist_ok=True);(p/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report,indent=2))
