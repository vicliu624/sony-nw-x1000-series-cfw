"""Source-built Japanese 1.11 Homebrew/cache firmware composition, PC only."""
from pathlib import Path
import copy,gzip,hashlib,io,json,struct,subprocess,sys,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack,KEY,SIGNATURE
from upg_crypto import encrypt_verified
from resources import append_stx,parse_stx,parse_tgp,append_bgra_texture
from language_pack import manifest

def pack(parts):
 entries=[];body=bytearray();offset=64
 for data in parts:
  entries.append((offset,len(data)));padded=data+bytes((-len(data))%8)
  if padded[:len(data)]!=data:raise ValueError('UPG component padding copy mismatch')
  encoded=encrypt_verified(padded,KEY)
  start=len(body);body.extend(encoded)
  if body[start:]!=encoded:raise ValueError('UPG encrypted body assembly mismatch')
  offset+=len(padded)
 header=struct.pack('<8sII',SIGNATURE,4,0)+b''.join(struct.pack('<II',*e) for e in entries)
 encrypted=encrypt_verified(header,KEY)+body
 if encrypted[48:]!=body:raise ValueError('UPG header/body assembly mismatch')
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

def complete_wordings(wordings):
 from wording import complete_missing,replace_verified_texts
 raw=wordings['en']
 missing={int(i):s for i,s in json.loads((ROOT/'translations/x1000-en-missing.json').read_text())['translations'].items()}
 raw=complete_missing(raw,wordings['jp'],missing)
 changes={int(i):s for i,s in json.loads((ROOT/'translations/x1000-en-japanese-fallbacks.json').read_text())['translations'].items()}
 wordings['en']=replace_verified_texts(raw,{i:parse_stx(raw)[i] for i in changes},changes)
 for ident,code in [('zh-CN','cs'),('zh-TW','ct')]:
  document=json.loads((ROOT/f'translations/x1000-{ident}.json').read_text());changes={int(i):s for i,s in document['translations'].items()}
  old=parse_stx(wordings[code]);missing={i:s for i,s in changes.items() if not old[i]}
  full=complete_missing(wordings[code],wordings['jp'],missing);other={i:s for i,s in changes.items() if i not in missing}
  wordings[code]=replace_verified_texts(full,{i:old[i] for i in other},other)

def verify_homebrew_icon_root(root):
    from PIL import Image

    with tarfile.open(fileobj=io.BytesIO(root),mode='r:gz') as tar:
        image=tar.extractfile('./usr/local/bin/SpiderApp').read()
        data=tar.extractfile('./usr/local/share/GUI/skinRom/TEXGRP00.DAT').read()
    elf=ELFFile(io.BytesIO(image));loads=[s for s in elf.iter_segments() if s['p_type']=='PT_LOAD']
    def word(address):
        for s in loads:
            if s['p_vaddr']<=address and address+4<=s['p_vaddr']+s['p_filesz']:
                return struct.unpack_from('<I',image,s['p_offset']+address-s['p_vaddr'])[0]
        raise AssertionError('unmapped icon word')
    assert word(0x4f7930)==140,'icon catalog count regressed'
    a,b=word(0xb5984),word(0xb5988)
    assert [word(a+i*4) for i in range(11)]==[54,55,56,57,58,59,60,61,62,63,139],'Homebrew reused Settings in mode1'
    assert [word(b+i*4) for i in range(10)]==[62,54,56,57,58,59,63,61,60,139],'Homebrew reused Settings in mode2'
    records=parse_tgp(data);assert len(records)==140
    with tarfile.open(ROOT/'work/upg-jp/verified-3.bin',mode='r:gz') as original:
        stock=original.extractfile('./usr/local/share/GUI/skinRom/TEXGRP00.DAT').read()
    assert data[32:len(stock)]==stock[32:],'original texture altered'
    icon=records[139];assert (icon['width'],icon['height'],icon['format'])==(64,64,16)
    pixels=data[icon['offset']+32:icon['offset']+32+icon['bytes']]
    assert pixels==Image.open(ROOT/'assets/icons/homebrew-shadow-v2-64.png').convert('RGBA').tobytes('raw','BGRA')
    assert hashlib.sha256(data).hexdigest()=='4aefed358aa6aba176b38d7767ab71b87ed5ed7b3ba803552a1e799d13e49bf0','accepted shadow artwork changed'

def compose_localized_root(work, stock_root, *, builtin_localization):
 if hashlib.sha256(stock_root).hexdigest()!='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5':
  raise ValueError('Original Sony root identity mismatch')
 from build_home_feedback import build as home_build
 from builtin_language import enable_settings,normalize_home_feedback
 home,symbols,_=home_build(work/'home')
 spider=normalize_home_feedback(home,symbols)
 if builtin_localization:
  spider=enable_settings(spider)
 else:spider=add_language_cache(spider,work)
 overlays={'usr/local/bin/SpiderApp':spider};wordings={}
 with tarfile.open(fileobj=io.BytesIO(stock_root),mode='r:gz') as t:
  for m in t:
   if m.isfile() and m.name.startswith('./usr/local/share/gemini/res/stx/') and m.name.endswith('.stx'):
    data,tid=append_stx(t.extractfile(m).read(),'Homebrew');data,error_tid=append_stx(data,'Homebrew unavailable.\nCheck HOMEBREW.');assert tid==7308 and error_tid==7309;overlays[m.name[2:]]=data
    wordings[Path(m.name).stem.removeprefix('ucs2-dev-')]=data
  complete_wordings(wordings)
  if builtin_localization:
   from language_pack import validate_wording
   for code in ('jp','en','cs','ct'):
    texts=validate_wording(wordings[code]);japanese=parse_stx(wordings['jp'])
    if any(text and (i>=len(texts) or not texts[i]) for i,text in enumerate(japanese)):
     raise ValueError('Incomplete built-in wording: '+code)
    overlays['usr/local/share/gemini/res/stx/ucs2-dev-'+code+'.stx']=wordings[code]
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
 return gzip.compress(unpacked.getvalue(),compresslevel=9,mtime=0),wordings,sorted(overlays)

def build(work,player,*,builtin_localization=False):
 work=Path(work);work.mkdir(parents=True,exist_ok=False)
 original=[(ROOT/f'work/upg-jp/verified-{i}.bin').read_bytes() for i in range(4)]
 stock=pack(original);assert hashlib.sha256(stock).hexdigest()=='002b6720b59f093a84440f554ffabe29f5879646839a5a28d43487b5cb41914b'
 root,wordings,changes=compose_localized_root(work,original[3],builtin_localization=builtin_localization)
 result=pack([*original[:3],root]);_,decoded=unpack(result,require_stock=False);assert decoded[:3]==original[:3] and decoded[3]==root
 verify_homebrew_icon_root(decoded[3])
 (work/'NW_WM_FW.UPG').write_bytes(result)
 # English and Chinese translation files are derived from the same stock table.
 for ident,code,name in ([] if builtin_localization else [('jp','jp','Japanese'),('en','en','English'),('zh-CN','cs','Simplified Chinese'),('zh-TW','ct','Traditional Chinese')]):
  folder=Path(player)/'HOMEBREW/languages'/ident;folder.mkdir(parents=True,exist_ok=True)
  data=None if ident=='jp' else wordings[code]
  (folder/'language.ini').write_bytes(manifest(ident,name,code,data))
  if data:(folder/'wording.stx').write_bytes(data)
 report={'firmware_sha256':hashlib.sha256(result).hexdigest(),'original_roundtrip_verified':True,'original_installer_kernel_initrd_preserved':True,'language_cache':'stock-system-resources' if builtin_localization else 'process-owned','native_language_settings':builtin_localization,'external_language_files_generated':not builtin_localization,'system_changes':changes,'hardware_qualified':False,'flashed':False,'historical_candidate_dependency':False}
 (work/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
 return work/'NW_WM_FW.UPG',report

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--player',type=Path)
 parser.add_argument('--builtin-localization',action='store_true')
 parser.add_argument('--root-only',action='store_true',help='Build only a built-in localization root tarball under work/')
 args=parser.parse_args()
 if args.root_only:
  if args.player is not None:parser.error('--root-only has no --player output')
  from sdk_build import fresh_work
  work=fresh_work(args.output)
  root,_,changes=compose_localized_root(work,(ROOT/'work/upg-jp/verified-3.bin').read_bytes(),builtin_localization=True)
  verify_homebrew_icon_root(root)
  path=work/'localized-root.tar.gz';path.write_bytes(root)
  print(json.dumps(dict(root=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(root).hexdigest(),system_changes=changes,firmware_created=False),indent=2))
 else:
  if args.player is None:parser.error('--player is required for a firmware build')
  print(json.dumps(build(args.output,args.player,builtin_localization=args.builtin_localization)[1],indent=2))
