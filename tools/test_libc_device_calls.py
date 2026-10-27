"""Probe libc device-operation ABI using an ordinary ELF file and pipe only."""
from pathlib import Path
import hashlib,json,subprocess,io
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/libc-device-call-review';work.mkdir(exist_ok=True);lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
elf=ELFFile(io.BytesIO((lib/'libc.so.6').read_bytes()))
symbol=next(s for s in elf.get_section_by_name('.dynsym').iter_symbols() if s.name=='ioctl')
address=symbol['st_value'];segment=next(p for p in elf.iter_segments() if p['p_type']=='PT_LOAD' and p['p_vaddr']<=address<p['p_vaddr']+p['p_filesz'])
code=segment.data()[address-segment['p_vaddr']:address-segment['p_vaddr']+16]
assert code[:12].hex()=='360090ef010a70e31eff2f31'
modern=work/'modern_ioctl.c';modern.write_text('#include <sys/ioctl.h>\nint probe(int fd, void *p){return ioctl(fd,0x4600,p);}\n'.replace('\\n','\n'))
# Compiler output is evidence of the selected headers, not a runtime payload.
subprocess.run(['arm-linux-gnueabi-gcc','-c',str(modern),'-o',str(work/'modern_ioctl.o')],check=True)
undefined=subprocess.run(['arm-linux-gnueabi-nm','-u',str(work/'modern_ioctl.o')],capture_output=True,text=True,check=True).stdout
assert '__ioctl_time64' in undefined
files=['tools/fixtures/libc_device_calls.c','runtime/store/start.c','runtime/store/start.S'];artifact=work/'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-D_DEFAULT_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*files,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
before=hashlib.sha256(artifact.read_bytes()).hexdigest()
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(artifact),str(artifact)],cwd=ROOT,capture_output=True,text=True,timeout=10)
assert run.returncode==0,(run.returncode,run.stderr)
assert hashlib.sha256(artifact.read_bytes()).hexdigest()==before
assert '/dev/fb' not in run.stderr and '/dev/icx_touch' not in run.stderr
tracked=[ROOT/f for f in files]+[Path(__file__),lib/'libc.so.6',lib/'ld-linux.so.3']
report={'passed':True,'stock_ioctl_address':address,'stock_ioctl_bytes':code.hex(),'modern_header_undefined':undefined,'artifact':str(artifact.relative_to(ROOT)),'sha256':before,'checks':['ioctl ordinary file returns ENOTTY','libc mmap64 offset zero maps ELF bytes','munmap and close','poll empty pipe then ready pipe','input unchanged'],'trace':run.stderr,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'hardware_tested':False,'limits':['Library calls run on QEMU host kernel; Sony driver not exercised.','Mmap probe uses offset zero, matching framebuffer request; not arbitrary offset compatibility.','No display geometry/ioctl structure or driver handoff qualification.']}
(ROOT/'sources/native-libc-device-call-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Stock libc ioctl/mmap/munmap/poll: ordinary file/pipe ABI probe passed, no display access.')

