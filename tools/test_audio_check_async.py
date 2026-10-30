"""Private per-intent audio validation worker: actual host threading, modeled Moma."""
import hashlib,json,os,subprocess
from app_registry import ROOT
w=ROOT/'work/audio-check-async';w.mkdir(exist_ok=True);windows=os.name=='nt'
sources=['runtime/platform/player/'+n+'.c' for n in ('audio_check_async','metadata_async','local_identity')]+['tools/fixtures/audio_check_async.c']
flags=['-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
if windows:sources+=['tools/fixtures/windows_pthread.c']
else:flags+=['-fsanitize=address,undefined','-pthread']
out=w/('test-windows.exe' if windows else 'test');subprocess.run(['clang' if windows else 'gcc',*flags,*sources,'-o',str(out)],cwd=ROOT,check=True);subprocess.run([str(out)],check=True,timeout=30)
command=['clang','--target=armv5te-none-eabi','-ffreestanding','-fno-builtin','-I'+str(ROOT/'tools/fixtures/freestanding')] if windows else ['arm-linux-gnueabi-gcc']
subprocess.run([*command,'-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-Wframe-larger-than=2048','-c',str(ROOT/'runtime/platform/player/audio_check_async.c'),'-o',str(w/'audio-check.arm.o')],check=True)
report=dict(passed=True,host='windows-win32-shim' if windows else 'linux-pthread',sanitizers=not windows,arm_compiler='windows-clang' if windows else 'gnu',device_accessed=False,checks=['no read for invalid intent generation','old ID result cannot satisfy newer intent','unsupported audio validation propagated','same ID with new intent requires fresh validation','source loss revokes observation','cancelled validation drains and closes client','no metadata text reader used','wrong thread refused before native source readiness','ID tail bytes do not change logical intent'],source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/audio_check_async.h','runtime/platform/player/metadata_async.h','tools/test_audio_check_async.py']},limits=['Native type validation is modeled here; original Moma instructions are tested separately. No GUI submission, Sony threading/runtime or hardware qualification.'])
(w/('report-windows.json' if windows else 'report.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
