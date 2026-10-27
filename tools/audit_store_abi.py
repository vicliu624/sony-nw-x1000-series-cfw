"""Audit actual ARM object imports against pinned Sony libc; no device execution."""
from pathlib import Path
import argparse,gzip,hashlib,io,json,re,subprocess,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/store-abi-audit';work.mkdir(exist_ok=True)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--require-symbols',action='store_true')
parser.add_argument('--target-bridge',action='store_true',help='Audit private Sony stat view and checked compatibility functions, not native readiness.')
args=parser.parse_args()
if args.target_bridge:work=work/'bridge';work.mkdir(exist_ok=True)
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(raw).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(raw)),mode='r:') as tar:
 libc=tar.extractfile('./lib/libc-2.3.3.so').read();loader=tar.extractfile('./lib/ld-2.3.3.so').read()
libelf=ELFFile(io.BytesIO(libc));exports={s.name for s in libelf.get_section_by_name('.dynsym').iter_symbols() if s['st_shndx']!='SHN_UNDEF' and s.name}
sources=['install_posix.c','transaction.c','stage_posix.c','cleanup_posix.c','pending_plan.c','cleanup_plan.c','bundle_posix.c','inventory.c','package.c']
paths=[ROOT/'runtime/store'/s for s in sources]+[ROOT/'runtime/native/sha256.c']
flags=['-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror']
if args.target_bridge:
 paths += [ROOT/'runtime/store/stock_fs_bridge.c',ROOT/'runtime/store/stock_stat64.c']
 flags += ['-DHB_STORE_SONY_LIBC']
version=(ROOT/'VERSION').read_text().strip();area=ROOT/'work'/('integration-'+version)
protected=[ROOT/'VERSION',area/'manifest.json']+[area/f['path'] for f in json.loads((area/'manifest.json').read_text())['files']]
def snapshot():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before=snapshot();defined=set();required=set();objects=[]
for source in paths:
 out=work/(source.stem+'.arm.o')
 subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-c',str(source),'-o',str(out)],check=True,cwd=ROOT)
 elf=ELFFile(io.BytesIO(out.read_bytes()));imports=[]
 for s in elf.get_section_by_name('.symtab').iter_symbols():
  if not s.name:continue
  if s['st_shndx']=='SHN_UNDEF':required.add(s.name);imports.append(s.name)
  elif s['st_info']['bind'] in ('STB_GLOBAL','STB_WEAK'):defined.add(s.name)
 objects.append({'source':str(source.relative_to(ROOT)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'object_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'flags':hex(elf['e_flags']),'imports':sorted(imports)})
external=required-defined;compiler_runtime=sorted(s for s in external if s.startswith('__aeabi_'))
libc_required=external-set(compiler_runtime);missing=sorted(libc_required-exports)
probe=work/'layout.c';probe.write_text('''#define _XOPEN_SOURCE 700
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <dirent.h>
#include "TARGET_ABI_HEADER"
const unsigned hb_stat_bytes=sizeof(struct stat);
const unsigned hb_stat_size_offset=offsetof(struct stat,st_size);
const unsigned hb_stat_mode_offset=offsetof(struct stat,st_mode);
#ifndef HB_STORE_SONY_LIBC
const unsigned hb_stat_mtime_offset=offsetof(struct stat,st_mtim);
#endif
const unsigned hb_statvfs_bytes=sizeof(struct statvfs);
const unsigned hb_statvfs_frsize_offset=offsetof(struct statvfs,f_frsize);
const unsigned hb_statvfs_bavail_offset=offsetof(struct statvfs,f_bavail);
const unsigned hb_dirent_name_offset=offsetof(struct dirent,d_name);
const unsigned hb_long_bytes=sizeof(long);
'''.replace('TARGET_ABI_HEADER',str(ROOT/'runtime/store/target_abi.h')))
macros=subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-dM','-E',str(probe)],capture_output=True,text=True,check=True).stdout
interesting={m.group(1):m.group(2) for line in macros.splitlines() if (m:=re.match(r'#define (\w+) (.*)',line)) and (m.group(1) in ('_TIME_BITS','_FILE_OFFSET_BITS','_FORTIFY_SOURCE','__USE_FORTIFY_LEVEL','__TIMESIZE','__USE_TIME64_REDIRECTS','__ARM_ARCH','__ARM_EABI__','__SOFTFP__'))}
probe_obj=work/'layout.arm.o';subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-c',str(probe),'-o',str(probe_obj)],check=True)
pe=ELFFile(io.BytesIO(probe_obj.read_bytes()));layout={}
for symbol in pe.get_section_by_name('.symtab').iter_symbols():
 if symbol.name.startswith('hb_') and isinstance(symbol['st_shndx'],int):
  section=pe.get_section(symbol['st_shndx']);offset=symbol['st_value']-section['sh_addr']
  layout[symbol.name]=int.from_bytes(section.data()[offset:offset+4],'little')
frontend=(area/'external/HOMEBREW/launcher/app').read_bytes();fe=ELFFile(io.BytesIO(frontend))
assert before==snapshot()
report={'audit_completed':True,'physical_device_access':False,'candidate_version':version,'candidate_unchanged':True,'compiler_version':subprocess.run(['arm-linux-gnueabi-gcc','-dumpfullversion'],capture_output=True,text=True,check=True).stdout.strip(),'flags':flags,'header_macros':interesting,'current_header_layout':layout,'stock_libc_sha256':hashlib.sha256(libc).hexdigest(),'stock_loader_sha256':hashlib.sha256(loader).hexdigest(),'stock_libc_ELF_flags':hex(libelf['e_flags']),'libc_required_symbols':sorted(libc_required),'missing_stock_libc_symbols':missing,'compiler_runtime_symbols':compiler_runtime,'symbol_coverage_satisfied':not missing,'native_link_compatibility_proven':False,'native_ready':False,'objects':objects,'existing_candidate_has_interpreter':any(s['p_type']=='PT_INTERP' for s in fe.iter_segments()),'limits':['Import/export and current-header layout audit only; no linked store executable or target execution.','Matching names alone cannot prove symbol versions, structure layouts, syscall ABI or target behavior.','Compiler runtime division helpers still need a separately qualified link path.','Do not alias time64 interfaces to old stat functions or package the host prototype as device-ready.','Existing freestanding candidate is not relinked or modified.']}
report['profile']='stock-bridge' if args.target_bridge else 'host-headers'
report['stat_view']='private store view, not libc struct stat' if args.target_bridge else 'modern libc header view'
if args.target_bridge:report['limits'].append('statvfs64, dirent64, target varargs/loader and checked runtime bindings remain separately unqualified.')
(ROOT/('sources/native-store-abi-bridge-audit.json' if args.target_bridge else 'sources/native-store-abi-audit.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('compiler_version','header_macros','current_header_layout','missing_stock_libc_symbols','symbol_coverage_satisfied','native_ready','candidate_unchanged','existing_candidate_has_interpreter')},indent=2))
if args.require_symbols and missing:raise SystemExit(2)
