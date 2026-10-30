"""Real host pthread lifecycle with a deliberately blocked modeled queue reader."""
from pathlib import Path
import subprocess,json,hashlib,os
from app_registry import ROOT
w=ROOT/'work/queue-async';w.mkdir(exist_ok=True)
sources=['runtime/platform/player/'+n+'.c' for n in ('queue_async','group_native','group_reader','query_snapshot','local_identity')]+['tools/fixtures/queue_async.c']
windows=os.name=='nt'
if windows:sources+=['tools/fixtures/windows_pthread.c']
flags=['-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-g']
if not windows:flags+=['-fsanitize=address,undefined','-pthread']
output=w/('test-windows.exe' if windows else 'test')
subprocess.run(['clang' if windows else 'gcc',*flags,*sources,'-o',str(output)],cwd=ROOT,check=True)
subprocess.run([str(output)],cwd=ROOT,check=True,timeout=30)
command=['clang','--target=armv5te-none-eabi','-ffreestanding','-fno-builtin','-I'+str(ROOT/'tools/fixtures/freestanding')] if windows else ['arm-linux-gnueabi-gcc']
subprocess.run([*command,'-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-c',str(ROOT/sources[0]),'-o',str(w/'queue_async.o')],check=True)
report=dict(passed=True,host="windows-win32-shim" if windows else "linux-pthread",sanitizers=not windows,supported_gnu_build=not windows,device_accessed=False,checks=['same task token with changed plan rejects old completion','NULL intent revokes cache and running result','nonblocking stop during read','destroy waits for worker drain','all transferred readers closed','grouped work progresses across separately transferred clients','current group does not invalidate unchanged group query','grouped cancellation drains active native read'],source_hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources+['runtime/platform/player/queue_async.h']},limits=['Windows uses a test-only Win32 pthread surface; Linux uses host pthread. Neither qualifies Sony thread ABI/runtime, native DB or hardware.'])
(w/('report-windows.json' if windows else 'report.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
