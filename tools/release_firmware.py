"""Source-built Japanese 1.11 Homebrew/cache firmware composition, PC only."""
from pathlib import Path
import copy,gzip,hashlib,io,json,struct,subprocess,sys,tarfile
from Crypto.Cipher import DES
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack,KEY,SIGNATURE
from resources import append_stx,parse_stx,parse_tgp,append_bgra_texture
from language_pack import manifest

def pack(parts):
 cipher=DES.new(KEY,DES.MODE_ECB);entries=[];body=bytearray();offset=64
 for data in parts:
  entries.append((offset,len(data)));padded=data+bytes((-len(data))%8);body.extend(cipher.encrypt(padded));offset+=len(padded)
 header=struct.pack('<8sII',SIGNATURE,4,0)+b''.join(struct.pack('<II',*e) for e in entries)
 encrypted=cipher.encrypt(header)+body
 return hashlib.md5(encrypted).digest()+encrypted

def add_language_cache(raw,work):
 image=ELFFile(io.BytesIO(raw));imports={s.name:s['st_value'] for s in image.get_section_by_name('.dynsym').iter_symbols()}
 binds={'hb_stock_open':imports['open'],'hb_stock_read':imports['read'],'hb_stock_close':imports['close'],'hb_stock_malloc':imports['malloc'],'hb_stock_free':imports['free'],'hb_stock_fxstat':imports['__fxstat'],'hb_stock_stx_context':0xec864,'hb_stock_stx_file':0xec8e4,'hb_stock_stx_language':0xec9c4,'hb_stock_stx_cleanup':0xec870,'hb_stock_mmap':imports['mmap'],'hb_stock_munmap':imports['munmap']}
 writable=[(i,s) for i,s in enumerate(image.iter_segments()) if s['p_type']=='PT_LOAD' and s['p_flags']&2]
 assert len(writable)==1
 index,rw=writable[0];end=rw['p_vaddr']+rw['p_memsz'];cache=(end+7)&~7;cache_end=cache+64
 assert (cache_end+4095)//4096==(end+4095)//4096
 binds['hb_language_cache']=cache
 for name in ('memset','memcpy','memcmp','strcmp','strcpy','strcat','strlen'):binds[name]=imports[name]
 linker=work/'language.ld'
 linker.write_text('ENTRY(hb_language_getter)\nSECTIONS { . = 0x4d8000; .text : { *(.text*) *(.rodata*) } .data : { *(.data*) } .bss : { *(.bss*) *(COMMON) } /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) *(.note*) } ASSERT(SIZEOF(.data)==0,"No writable data") ASSERT(SIZEOF(.bss)==0,"No BSS") ASSERT(.<0x4de004,"Gap exceeded") }\n'+''.join(k+' = '+hex(v)+';\n' for k,v in binds.items()))
 objects=[]
 for i,source in enumerate(['runtime/apps/language/process_cache_entry.S','runtime/apps/language/process_cache.c','runtime/apps/language/package.c','runtime/native/sha256.c']):
  obj=work/f'language-{i}.o';subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-ffreestanding','-c',source,'-o',str(obj)],cwd=ROOT,check=True);objects.append(str(obj))
 elf=work/'language.elf';binary=work/'language.bin'
 subprocess.run(['arm-linux-gnueabi-gcc','-nostdlib','-static','-Wl,--build-id=none','-Wl,-T,'+str(linker),*objects,'-lgcc','-o',str(elf)],check=True)
 subprocess.run(['arm-linux-gnueabi-objcopy','-O','binary',str(elf),str(binary)],check=True)
 code=binary.read_bytes();compiled=ELFFile(io.BytesIO(elf.read_bytes()));symbols={s.name:s['st_value'] for s in compiled.get_section_by_name('.symtab').iter_symbols() if s.name}
 loads=[s for s in image.iter_segments() if s['p_type']=='PT_LOAD']
 def at(va,n):return next(s['p_offset']+va-s['p_vaddr'] for s in loads if s['p_vaddr']<=va and va+n<=s['p_vaddr']+s['p_filesz'])
 start=at(0x4d8000,len(code));assert raw[start:start+len(code)]==bytes(len(code));out=bytearray(raw);out[start:start+len(code)]=code
 struct.pack_into('<I',out,image['e_phoff']+index*image['e_phentsize']+20,cache_end-rw['p_vaddr'])
 bss=image.get_section_by_name('.bss');assert bss['sh_addr']+bss['sh_size']==end
 bss_index=next(i for i,s in enumerate(image.iter_sections()) if s.name=='.bss')
 struct.pack_into('<I',out,image['e_shoff']+bss_index*image['e_shentsize']+20,cache_end-bss['sh_addr'])
 for va,before,name,opcode in [(0x3a25c,0xeb01dea5,'hb_language_getter',0xeb000000),(0xec46c,0xea000154,'hb_language_wording',0xea000000),(0xec870,0xe92d4030,'hb_language_cleanup_entry',0xea000000)]:
  off=at(va,4);assert struct.unpack_from('<I',raw,off)[0]==before;delta=symbols[name]-va-8;assert delta%4==0 and -(1<<25)<=delta<(1<<25);struct.pack_into('<I',out,off,opcode|((delta>>2)&0xffffff))
 checked=ELFFile(io.BytesIO(out));assert next(s for s in checked.iter_segments() if s['p_type']=='PT_LOAD' and s['p_flags']&2).data()==rw.data()
 return bytes(out)

def build(work,player):
 work=Path(work);work.mkdir(parents=True,exist_ok=False)
 original=[(ROOT/f'work/upg-jp/verified-{i}.bin').read_bytes() for i in range(4)]
 stock=pack(original);assert hashlib.sha256(stock).hexdigest()=='002b6720b59f093a84440f554ffabe29f5879646839a5a28d43487b5cb41914b'
 from build_home_feedback import build as home_build
 spider,symbols,home_report=home_build(work/'home')
 descriptor=symbols['hb_error_descriptor'];parsed=ELFFile(io.BytesIO(spider))
 descriptor_offset=next(s['p_offset']+descriptor-s['p_vaddr'] for s in parsed.iter_segments() if s['p_type']=='PT_LOAD' and s['p_vaddr']<=descriptor and descriptor+48<=s['p_vaddr']+s['p_filesz'])
 editable=bytearray(spider);struct.pack_into('<I',editable,descriptor_offset+4,99999);struct.pack_into('<I',editable,descriptor_offset+20,0);spider=bytes(editable)
 spider=add_language_cache(spider,work)
 overlays={'usr/local/bin/SpiderApp':spider};wordings={}
 with tarfile.open(fileobj=io.BytesIO(original[3]),mode='r:gz') as t:
  for m in t:
   if m.isfile() and m.name.startswith('./usr/local/share/gemini/res/stx/') and m.name.endswith('.stx'):
    data,tid=append_stx(t.extractfile(m).read(),'Homebrew');data,error_tid=append_stx(data,'Homebrew unavailable.\nCheck HOMEBREW.');assert tid==7308 and error_tid==7309;overlays[m.name[2:]]=data
    wordings[Path(m.name).stem.removeprefix('ucs2-dev-')]=data
  from PIL import Image
  texture_path='usr/local/share/GUI/skinRom/TEXGRP00.DAT'
  textures=t.extractfile('./'+texture_path).read()
  if len(parse_tgp(textures))!=139:raise ValueError('Unexpected original texture count')
  icon=Image.open(ROOT/'assets/icons/homebrew-shadow-v2-64.png').convert('RGBA')
  if icon.size!=(64,64):raise ValueError('Homebrew icon dimensions')
  overlays[texture_path],texture_id=append_bgra_texture(textures,64,64,icon.tobytes('raw','BGRA'))
  if texture_id!=139:raise ValueError('Homebrew icon index')
  old=t.extractfile('./etc/AppList.conf').read();assert b'0x00030001' not in old
  overlays['etc/AppList.conf']=old+(b'' if old.endswith(b'\n') else b'\n')+b'0x00030001 * /contents/HOMEBREW/launcher/app --native\n'
  for collection,count in [(10,10),(11,9)]:
   path=f'usr/local/share/gemini/res/swd/ucs2-dev-sid-000-{collection}.swd';raw=t.extractfile('./'+path).read()
   overlays[path]=raw.rstrip()+f'\n\ntid.{count}:\t"tid-{tid}"\t; homebrew\n'.encode()
  unpacked=io.BytesIO()
  with tarfile.open(fileobj=unpacked,mode='w',format=tarfile.GNU_FORMAT) as dest:
   for m in t.getmembers():
    entry=copy.copy(m);data=overlays.get(m.name.removeprefix('./')) if m.isfile() else None
    if m.isfile():
     if data is None:data=t.extractfile(m).read()
     entry.size=len(data);dest.addfile(entry,io.BytesIO(data))
    else:dest.addfile(entry)
   name='usr/local/share/gemini/res/swd/ucs2-dev-sid-999-99.swd'
   assert './'+name not in t.getnames()
   data=b'; Homebrew launch error\ntype:\t"dialog" ""\nsid:\t"sid-999-99"\n\nitem:\t"Homebrew" ""\nperson:\t""\n\ntid.0:\t"tid-7309"\n'
   entry=copy.copy(t.getmember('./usr/local/share/gemini/res/swd/ucs2-dev-sid-347-00.swd'));entry.name='./'+name;entry.size=len(data);dest.addfile(entry,io.BytesIO(data));overlays[name]=data
 root=gzip.compress(unpacked.getvalue(),compresslevel=9,mtime=0)
 result=pack([*original[:3],root]);_,decoded=unpack(result,require_stock=False);assert decoded[:3]==original[:3] and decoded[3]==root
 (work/'NW_WM_FW.UPG').write_bytes(result)
 from test_homebrew_firmware_icon import verify as verify_homebrew_icon
 verify_homebrew_icon(work/'NW_WM_FW.UPG')
 # English and Chinese translation files are derived from the same stock table.
 from wording import complete_missing,replace_verified_texts
 raw=wordings['en'];before=parse_stx(raw)
 missing={int(i):s for i,s in json.loads((ROOT/'translations/x1000-en-missing.json').read_text())['translations'].items()}
 raw=complete_missing(raw,wordings['jp'],missing)
 changes={int(i):s for i,s in json.loads((ROOT/'translations/x1000-en-japanese-fallbacks.json').read_text())['translations'].items()}
 raw=replace_verified_texts(raw,{i:parse_stx(raw)[i] for i in changes},changes)
 wordings['en']=raw
 for ident,code in [('zh-CN','cs'),('zh-TW','ct')]:
  document=json.loads((ROOT/f'translations/x1000-{ident}.json').read_text());changes={int(i):s for i,s in document['translations'].items()}
  old=parse_stx(wordings[code]);missing={i:s for i,s in changes.items() if not old[i]}
  full=complete_missing(wordings[code],wordings['jp'],missing);other={i:s for i,s in changes.items() if i not in missing}
  wordings[code]=replace_verified_texts(full,{i:old[i] for i in other},other)
 for ident,code,name in [('jp','jp','Japanese'),('en','en','English'),('zh-CN','cs','Simplified Chinese'),('zh-TW','ct','Traditional Chinese')]:
  folder=Path(player)/'HOMEBREW/languages'/ident;folder.mkdir(parents=True,exist_ok=True)
  data=None if ident=='jp' else wordings[code]
  (folder/'language.ini').write_bytes(manifest(ident,name,code,data))
  if data:(folder/'wording.stx').write_bytes(data)
 report={'firmware_sha256':hashlib.sha256(result).hexdigest(),'original_roundtrip_verified':True,'original_installer_kernel_initrd_preserved':True,'language_cache':'process-owned','system_changes':sorted(overlays),'hardware_qualified':False,'flashed':False,'historical_candidate_dependency':False}
 (work/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
 return work/'NW_WM_FW.UPG',report

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--player',type=Path,required=True);args=parser.parse_args()
 print(json.dumps(build(args.output,args.player)[1],indent=2))
