"""Real read-only profile checker on mapped filesystem/proc fixtures, no player."""
from pathlib import Path
import hashlib,json,resource,subprocess,tempfile
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/qqmusic-preview-handoff';w.mkdir(exist_ok=True)
core=['runtime/apps/qqmusic/qqmusic_preview_handoff.c','runtime/native/sha256.c','tools/fixtures/qqmusic_preview_handoff.c'];flags=['-std=c99','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin'];wrap=['-Wl,--wrap=open,--wrap=open64,--wrap=opendir,--wrap=readlink,--wrap=lstat,--wrap=__lxstat64,--wrap=getpid,--wrap=getppid']
host=w/'handoff.sanitized';arm=w/'handoff.arm';lib=ROOT/'work/arm-signal-tests/lib'
subprocess.run(['gcc-12',*flags,'-O1','-g','-fsanitize=address,undefined',*core,*wrap,'-o',str(host)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(dir=w) as directory:subprocess.run([str(host),directory],check=True,timeout=15)
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-DHB_STORE_SONY_LIBC','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*core,'runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S',*wrap,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(dir=w) as directory:
 result=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm),directory],capture_output=True,timeout=20)
 assert result.returncode==0,result.stderr.decode(errors="replace")[-2200:]
 assert b'ioctl(' not in result.stderr and b'kill(' not in result.stderr
report={'passed':True,'host_asan_ubsan':True,'stock_arm_fs_bridge':True,'checks':['zero/missing profile refuses before IO','QQ main and helper ancestry accepted','multiple LinuxThreads proxy parents handled','parent birth/reuse mismatch refuses','terminal/direct parent refuses','original SpiderApp present refuses','sound handle held elsewhere refuses','duplicate AppList registration refuses','unknown binary hash refuses','mode0 instruction refuses even with matching supplied hash','malformed proc stat refuses'],'physical_device_accessed':False,'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in core},'limits':['System/proc paths and process identities map to synthetic files; this is not an installed-device qualification.','Passing this filter is not exclusive driver acquisition, hardware output, or actual manager completion.']}
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
