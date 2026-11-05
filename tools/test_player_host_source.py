"""Analysis-host source registration/attachment, with modeled lifecycle endpoints."""
import hashlib,json,os,subprocess
from app_registry import ROOT
w=ROOT/'work/player-host-source';w.mkdir(exist_ok=True);windows=os.name=='nt'
sources=['runtime/platform/player/host_source.c','runtime/platform/player/host_service.c','tools/fixtures/player_host_source.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
if not windows:flags+=['-fsanitize=address,undefined']
out=w/('test-windows.exe' if windows else 'test');subprocess.run(['clang' if windows else 'gcc',*flags,*sources,'-o',str(out)],cwd=ROOT,check=True)
for args in ([],['--host']):subprocess.run([str(out),*args],check=True,timeout=10)
compiler=['clang','--target=armv5te-none-eabi','-ffreestanding','-fno-builtin','-I'+str(ROOT/'tools/fixtures/freestanding')] if windows else ['arm-linux-gnueabi-gcc']
for name in ('host_source','host_service','host_hook'):
 subprocess.run([*compiler,'-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-Wframe-larger-than=2048','-c',str(ROOT/'runtime/platform/player'/f'{name}.c'),'-o',str(w/f'{name}.arm.o')],check=True)
report=dict(passed=True,device_accessed=False,host='windows-clang' if windows else 'gcc',sanitizers=not windows,checks=['no selection adapter before owner GUI registration','busy or wrong-owner GUI cannot register','broker owner required','existing native PLAY_ITEM is not overridden','initialized adapter retained across busy attachment','capability appears only after successful attachment','ticks do not issue commands'],source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/host_hook.c','runtime/platform/player/host_hook.h','runtime/platform/player/host_service.c','tools/test_player_host_source.py']},limits=['Adapter initialization and broker attach are modeled here; separate tests execute their implementations.','ARM objects compile; full GNU DSO/linker, original loader and physical startup remain unqualified.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
