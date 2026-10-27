"""Regression: release failure must block launching an app or reporting success."""
from pathlib import Path
import contextlib,hashlib,io,json,runpy,subprocess
ROOT=Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):base=runpy.run_path(str(ROOT/'tools/test_posix_full_loop.py'))
work=ROOT/'work/release-failure-review';work.mkdir(exist_ok=True)
fixture=base['fixture'];needle='if(!fb_open&&!touch_open){owned=0;releases++;}return 0;'
assert fixture.count(needle)==1
fixture=fixture.replace(needle,'if(!fb_open&&!touch_open){owned=0;releases++;}return a==10?-5:0;')
fixture=fixture[:fixture.index('int main(int argc,char **argv)')]+r'''
int main(int argc,char **argv) {
 assert(argc==2);
 unsigned stack[]={3,(unsigned)argv[0],(unsigned)"--native",(unsigned)argv[1],0,0};
 int result=hb_entry(stack);
 assert(result!=0&&event==2&&acquires==1&&releases==1&&maps==unmaps);
 assert(!owned&&!fb_open&&!touch_open&&!owned_file_count&&!direct_child&&!reaped_count);
 return 0;
}
'''
checks=[];tracked=[Path(__file__),base['wrappers'],ROOT/'tools/test_posix_full_loop.py']
for name in ('launch','return'):
 body=fixture
 if name=='return':body=body.replace('unsigned x=event<2?80:30,y=event<2?60:400;','unsigned x=30,y=400;')
 generated=work/(name+'.c');generated.write_text(base['prefix']+body+base['wrappers'].read_text(encoding='utf-8-sig'))
 artifact=work/(name+'.arm');lib=base['lib'];sources=[str(generated),*base['sources'][1:]]
 subprocess.run(['arm-linux-gnueabi-gcc','-DHB_USE_POSIX_FILES','-DHB_USE_POSIX_DEVICE_IO','-D_DEFAULT_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*['-Wl,--wrap='+s for s in ('ioctl','mmap64','munmap','poll','x1000_oabi_call','open64','close','fork','waitpid','kill','execve')],*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
 result=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(artifact),str(ROOT/'work/libc-launcher-review/apps')],capture_output=True,text=True,timeout=15)
 assert result.returncode==0,(name,result.returncode,result.stderr)
 checks.append(name);tracked.extend([generated,artifact,lib/'libc.so.6',lib/'ld-linux.so.3',*[ROOT/p for p in sources[1:]]])
report={'passed':True,'checks':checks,'scope':'device-close error after cleanup attempts; no app launch/reacquire and nonzero exit','hardware_tested':False,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked}}
(ROOT/'sources/native-release-failure-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Release failure: launch blocked; normal return does not report success.')

