"""Execute JP PIC/APIC parser before/after alignment fix; native file IO modeled."""
import argparse,hashlib,io,json,struct,time
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
from app_registry import ROOT
from stock_artwork_fix import compose
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path);p.add_argument('--library',type=Path);p.add_argument('--file-list',type=Path,help='Explicit private source paths, e.g. a Windows-enumerated library');args=p.parse_args()
stock=(ROOT/'work/targets-jp/SpiderApp').read_bytes();assert hashlib.sha256(stock).hexdigest()=='80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85'
patched,composition=compose(stock);assert len(patched)==len(stock)
for data in (patched,stock[:0x3139cc-0x8000]+b'\0'*4+stock[0x3139cc-0x8000+4:]):
 try:compose(data)
 except ValueError:pass
 else:raise AssertionError('Unexpected parser instructions accepted')
elf=ELFFile(io.BytesIO(stock));symbols={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
image=b'\xff\xd8\xff\xe0'+bytes(range(1,200))*3;cases=[];rows=[]
for version in (2,3):
 for encoding,description in ((0,b'Front cover\0'),(1,b'\xff\xfe'+('Front cover'+'\0').encode('utf-16-le')),(1,b'\xfe\xff'+('Front cover'+'\0').encode('utf-16-be')),(1,b'\xff\xfe\0\0')):
  payload=bytes((encoding,))+(b'JPG' if version==2 else b'image/jpeg\0')+b'\x03'+description+image
  position=32;header=b'PIC'+len(payload).to_bytes(3,'big') if version==2 else b'APIC'+len(payload).to_bytes(4,'big')+bytes(2)
  file=bytes(position)+header+payload+bytes(256)
  cases.append((f'v{version}-e{encoding}-{description[:2].hex()}-{len(description)}',version,file,position,len(payload),image))
source_inputs=([args.source] if args.source else [])+(sorted(args.library.rglob('*.mp3')) if args.library else [])
if args.file_list:source_inputs += [Path(p) for p in json.loads(args.file_list.read_text())]
source_checks=[]
if source_inputs:
 from mutagen.id3 import ID3
 for index,source in enumerate(source_inputs):
  tag=ID3(source);assert tag.version==(2,3,0);pictures=tag.getall('APIC')
  if not pictures:continue
  with source.open('rb') as f:original=f.read(tag.size+256)
  source_checks.append((source,len(original),hashlib.sha256(original).hexdigest()))
  front=next((a for a in pictures if int(a.type)==3),pictures[0]);pos=10
  while original[pos:pos+4]!=b'APIC':pos+=10+int.from_bytes(original[pos+4:pos+8],'big')
  cases.append(('real-track' if args.source else f'library-{index}',3,original,pos,int.from_bytes(original[pos+4:pos+8],'big'),front.data))
for name,version,file,position,size,expected in cases:
 for fixed,data in ((False,stock),(True,patched)):
  u=Uc(UC_ARCH_ARM,UC_MODE_ARM);program=ELFFile(io.BytesIO(data))
  for s in program.iter_segments():
   if s['p_type']!='PT_LOAD':continue
   a=int(s['p_vaddr']);base=a&~4095;u.mem_map(base,(a-base+int(s['p_memsz'])+4095)&~4095);u.mem_write(a,s.data())
  area=0x71000000;u.mem_map(area,0x100000);ctx=area;out=area+0x1000;length=area+0x800;done=area+0xfff00;sp=area+0xfe000;reads=[]
  put=lambda a,v:u.mem_write(a,struct.pack('<I',v));get=lambda a:struct.unpack('<I',u.mem_read(a,4))[0]
  put(ctx+0x28,int(version==3));put(ctx+0x68,position);put(ctx+0x9c,size);put(length,len(expected)+3)
  def hook(cpu,pc,n,unused):
   if pc==done:cpu.emu_stop();return
   def finish(value=0):cpu.reg_write(UC_ARM_REG_R0,value);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
   if pc==0x31b780:
    context,offset,target,count=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
    requested=get(count);assert context==ctx+0x14 and offset+requested<=len(file)
    reads.append((offset,requested));cpu.mem_write(target,file[offset:offset+requested]);finish();return
   if pc==symbols['memcpy']:
    a,b,count=[cpu.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2)];cpu.mem_write(a,bytes(cpu.mem_read(b,count)));finish(a)
  u.hook_add(UC_HOOK_CODE,hook)
  for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),(ctx,0x41504943 if version==3 else 0x50494300,0,out)):u.reg_write(r,v)
  put(sp,0);put(sp+4,length);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_LR,done)
  u.emu_start(0x312f0c,done+4,count=2000000);assert u.reg_read(UC_ARM_REG_PC)==done and u.reg_read(UC_ARM_REG_R0)==0
  result=bytes(u.mem_read(out,get(length)));correct=result==(b'PNG' if expected.startswith(b'\x89PNG') else b'JPG')+expected
  if fixed:assert correct,(name,reads,result[:12].hex())
  if name=='real-track' and not fixed:assert result[:5]==b'JPG\0\xff' and not correct
  rows.append(dict(case=name,fixed=fixed,correct=correct,first_bytes=result[:8].hex(),image_bytes=len(expected),native_reads=reads))
for source,count,before in source_checks:
 with source.open('rb') as f:assert hashlib.sha256(f.read(count)).hexdigest()==before
folder=ROOT/'work/stock-apic-tests'/str(time.time_ns());folder.mkdir(parents=True)
report=dict(passed=True,cases=rows,original_parser_executed=True,file_io_and_context_modeled=True,real_track_checked=bool(source_inputs),real_covers_checked=len(source_checks),source_unchanged=True,device_accessed=False,composition=composition,
 source_hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in ['tools/test_stock_apic.py','tools/stock_artwork_fix.py']},
 limits=['This executes original parser instructions with supplied frame offsets and original file bytes; the file callback and memcpy are modeled.','Native catalog discovery, cover decoder, physical display and scan/cache invalidation require device acceptance.'])
(folder/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
