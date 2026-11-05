"""GUI-owner source intent composition; native/worker boundaries are modeled."""
import hashlib,json,os,subprocess
from app_registry import ROOT
w=ROOT/'work/source-intent';w.mkdir(exist_ok=True);windows=os.name=='nt'
sources=['runtime/platform/player/source_intent.c','runtime/platform/player/local_identity.c','tools/fixtures/source_intent.c']
flags=['-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
if not windows:flags+=['-fsanitize=address,undefined']
out=w/('test-windows.exe' if windows else 'test')
subprocess.run(['clang' if windows else 'gcc',*flags,*sources,'-o',str(out)],cwd=ROOT,check=True)
subprocess.run([str(out)],check=True,timeout=10)
compiler=['clang','--target=armv5te-none-eabi','-ffreestanding','-fno-builtin','-I'+str(ROOT/'tools/fixtures/freestanding')] if windows else ['arm-linux-gnueabi-gcc']
subprocess.run([*compiler,'-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-Wframe-larger-than=2048','-c',str(ROOT/sources[0]),'-o',str(w/'source-intent.arm.o')],check=True)
report=dict(passed=True,device_accessed=False,host_compiler='windows-clang' if windows else 'gcc',sanitizers=not windows,checks=['validation precedes native submission','pending validation has no command effects','superseded/cancelled generation cannot submit','same generation cannot change ID','same generation never replays attempted or uncertain submission','source loss requires a new generation','clock regression invalidates pending intent','transient GUI phase and wrong owner do not submit','logical IDs ignore unused tail bytes','generation never wraps','invalid output alias refused','target checking reads a fresh snapshot','wrong track or paused target is not reached','unknown fields and snapshot errors are not success','prior target success is not sticky','unexpected terminal OK does not bypass observation'],source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/source_intent.h','runtime/platform/player/stock_source.h','runtime/platform/player/player.h','runtime/platform/player/provider.h','tools/test_source_intent.py']},limits=['Worker, GUI/native submission and clock inputs modeled; separate tests cover native instructions and threaded validation.','Private composition test only; it does not install or exercise the host endpoint.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
