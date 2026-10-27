"""Compare compile-time ARM layouts of pinned GPL stat definitions; no execution."""
from pathlib import Path
import hashlib,io,json,subprocess,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/store-kernel-layout';work.mkdir(exist_ok=True)
archive=ROOT/'work/downloads/linux-kernel-2.6.10.local.tgz'
archive_sha=hashlib.sha256(archive.read_bytes()).hexdigest();assert archive_sha=='286475cbbb0610dab8af914995d3fe1bbc081153b9e0e92698f05a601ef15309'
with tarfile.open(archive) as tar:header=tar.extractfile('./include/asm-arm/stat.h').read()
(work/'stock-kernel-stat.h').write_bytes(header)
source=work/'probe.c';source.write_text('''#include "stock-kernel-stat.h"
const unsigned hb_kernel_stat_bytes=sizeof(struct stat);
const unsigned hb_kernel_stat64_bytes=sizeof(struct stat64);
const unsigned hb_kernel_stat64_mode=__builtin_offsetof(struct stat64,st_mode);
const unsigned hb_kernel_stat64_nlink=__builtin_offsetof(struct stat64,st_nlink);
const unsigned hb_kernel_stat64_size=__builtin_offsetof(struct stat64,st_size);
const unsigned hb_kernel_stat64_ino=__builtin_offsetof(struct stat64,st_ino);
''')
rows=[]
for abi in ('apcs-gnu','aapcs-linux'):
 out=work/(abi+'.o');flags=['-std=c99','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-mabi='+abi,'-fno-pie','-fno-pic','-ffreestanding','-fno-builtin','-Wall','-Wextra','-Werror']
 subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-c',str(source),'-o',str(out)],check=True)
 elf=ELFFile(io.BytesIO(out.read_bytes()));values={}
 for symbol in elf.get_section_by_name('.symtab').iter_symbols():
  if symbol.name.startswith('hb_') and isinstance(symbol['st_shndx'],int):
   section=elf.get_section(symbol['st_shndx']);offset=symbol['st_value']-section['sh_addr']
   values[symbol.name]=int.from_bytes(section.data()[offset:offset+4],'little')
 rows.append({'compile_abi':abi,'flags':flags,'ELF_flags':hex(elf['e_flags']),'layout':values})
report={'inspection_completed':True,'physical_device_access':False,'GPL_archive_sha256':archive_sha,'kernel_stat_header_sha256':hashlib.sha256(header).hexdigest(),'compile_time_views':rows,'actual_kernel_layout_qualified':False,'limits':['Same pinned kernel header compiled under two alignment ABIs; neither is asserted to match the actual Sony kernel build.','Kernel syscall buffer layout and libc API structure layout are separate contracts.','No stock syscall, target library or device program executed.','Not a reason to alias modern time64 APIs to old functions; actual kernel/libc conversion must be established.']}
(ROOT/'sources/stock-kernel-stat-layout.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
