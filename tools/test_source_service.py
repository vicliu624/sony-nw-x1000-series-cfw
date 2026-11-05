"""Native source-service adapter plus real intent state machine, PC only."""
import hashlib,json,os,subprocess,sys
from app_registry import ROOT
managed='--managed' in sys.argv
w=ROOT/('work/source-service-managed' if managed else 'work/source-service');w.mkdir(exist_ok=True);windows=os.name=='nt'
sources=['runtime/platform/player/'+n+'.c' for n in ('source_service','source_intent','local_identity')]+['tools/fixtures/source_service.c']
if managed:sources=sources[:-1]+['runtime/platform/player/client.c','runtime/platform/player/managed.c']+['runtime/platform/services/'+n+'.c' for n in ('session','request','events')]+['tools/fixtures/source_service_managed.c']
flags=['-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
if not windows:flags+=['-fsanitize=address,undefined']
out=w/('test-windows.exe' if windows else 'test');subprocess.run(['clang' if windows else 'gcc',*flags,*sources,'-o',str(out)],cwd=ROOT,check=True);subprocess.run([str(out)],check=True,timeout=10)
compiler=['clang','--target=armv5te-none-eabi','-ffreestanding','-fno-builtin','-I'+str(ROOT/'tools/fixtures/freestanding')] if windows else ['arm-linux-gnueabi-gcc']
subprocess.run([*compiler,'-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-Wframe-larger-than=2048','-c',str(ROOT/sources[0]),'-o',str(w/'service.arm.o')],check=True)
report=dict(passed=True,device_accessed=False,host='windows-clang' if windows else 'gcc',sanitizers=not windows,checks=['pending explicit polls reuse intent generation','new target or revision starts fresh validation','post-admission explicit command is a new intent','wrong owner cannot advance intent','revocation cancels pending work','source loss requires a new explicit intent','generation overflow refuses without submission','close waits for drain and rejects new commands'],source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/source_service.h','runtime/platform/player/source_intent.h','tools/test_source_service.py']},limits=['Validation worker, native GUI/submission and drain primitives are modeled.','This does not install the service in a physical player or qualify an original-loader DSO.'])
if managed:
 report['managed_adapter']=True
 report['checks']=['same request ID never advances intent','new explicit ID advances pending validation','accepted request not replayed','64-bit revision retained','revoked/closed client cannot submit','another session explicitly replaces pending target','source loss and global close preserve submission bounds']
 report['source_hashes']['tools/fixtures/source_service.c']=hashlib.sha256((ROOT/'tools/fixtures/source_service.c').read_bytes()).hexdigest()
 if not windows:
  from player_arm_guest import stock_libraries
  libs=stock_libraries();binary=w/'managed.arm'
  subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-stack-protector','-nostdlib','-no-pie','-fno-pie','-Wl,--hash-style=sysv,--build-id=none',*sources,'runtime/store/start.c','runtime/store/start.S',str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
  run=subprocess.run(['qemu-arm','-cpu','arm926',str(libs['ld-linux.so.3']),'--library-path',str(libs['libc.so.6'].parent),str(binary)],cwd=ROOT,capture_output=True,text=True,timeout=10)
  assert run.returncode==0 and 'MANAGED_SOURCE_SERVICE_PASS' in run.stdout,run.stdout+run.stderr
  report['original_libc_arm_executed']=True;report['arm_stdout']=run.stdout
  report['arm_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
  report['input_hashes']={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'runtime/store/start.c',ROOT/'runtime/store/start.S',libs['libc.so.6'],libs['ld-linux.so.3']]}
 for folder in ('runtime/platform/player','runtime/platform/services'):
  for header in (ROOT/folder).glob('*.h'):report['source_hashes'][header.relative_to(ROOT).as_posix()]=hashlib.sha256(header.read_bytes()).hexdigest()
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
