"""Exercise unchanged launcher ARM signal handlers under QEMU, never hardware."""
from pathlib import Path
import hashlib,json,subprocess,gzip,io,tarfile
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/arm-signal-tests';work.mkdir(exist_ok=True)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
lib=work/'lib';lib.mkdir(exist_ok=True)
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for original,alias in [('libc-2.3.3.so','libc.so.6'),('ld-2.3.3.so','ld-linux.so.3')]:
  payload=tar.extractfile('./lib/'+original).read()
  (lib/original).write_bytes(payload)
  if not (lib/alias).exists():(lib/alias).symlink_to(original)
  assert (lib/alias).read_bytes()==payload
functions=(ROOT/'runtime/native/linux_signals.c').read_text()
prefix='#include "'+str(ROOT/'runtime/native/linux_signals.h')+'"\n'+ 'extern long x1000_oabi_call(long,long,long,long,long,long,long);\nstatic volatile int stop_requested;\n'
suffix="""
int main(void){
 if(hb_stop_signals_install(&stop_requested))return 10;
 long pid=x1000_oabi_call(20,0,0,0,0,0,0);
 if(pid<=0)return 11;
 for(int i=0;i<2;i++){
  stop_requested=0;
  if(x1000_oabi_call(37,pid,15,0,0,0,0)<0||stop_requested!=1)return 12;
 }
 stop_requested=0;
 if(x1000_oabi_call(37,pid,2,0,0,0,0)<0||stop_requested!=1)return 13;
 return 0;
}
"""
generated=work/'launcher_signals.c';generated.write_text(prefix+suffix)
sources=[str(generated),'runtime/native/linux_signals.c','runtime/native/syscalls.S','runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(work/'test.arm')],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(work/'test.arm')],capture_output=True,text=True,timeout=15)
assert run.returncode==0,(run.returncode,run.stderr)
assert run.stderr.lower().count('rt_sigreturn(')>=3,run.stderr
assert not any(c in run.stderr.lower() for c in ('socket(','connect(','/dev/fb','/dev/icx_touch_screen'))
report={'all_bounded_checks_passed':True,'physical_device_access':False,'function_sha256':hashlib.sha256(functions.encode()).hexdigest(),'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['runtime/native/platform_arm.c','runtime/native/linux_signals.c','runtime/native/linux_signals.h','runtime/native/syscalls.S','runtime/store/start.c','runtime/store/start.S']},'cases':['SIGTERM delivered and returned twice','SIGINT delivered and returned after SIGTERM'],'trace':run.stderr,'exit':run.returncode,'limits':['QEMU user-mode ARM926 with original libc/loader; Linux host implements signal delivery.','Current separately linked signal module and preserved OABI assembly, not original Sony kernel signal implementation.','No child lifecycle, Sony IPC, display or USB qualification.']}
(ROOT/'sources/native-arm-signal-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('ARM launcher signal delivery/return: repeated SIGTERM and SIGINT passed.')
