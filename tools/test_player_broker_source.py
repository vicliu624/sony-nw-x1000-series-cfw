"""SDK client -> broker optional selection adapter, without native side effects."""
import hashlib,json,os,subprocess
from app_registry import ROOT
w=ROOT/'work/player-broker-source';w.mkdir(exist_ok=True);windows=os.name=='nt'
sources=['runtime/platform/player/client.c','runtime/platform/player/player_broker.c','tools/fixtures/player_broker_source.c']
flags=['-std=c11','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
if not windows:flags+=['-fsanitize=address,undefined']
out=w/('test-windows.exe' if windows else 'test');subprocess.run(['clang' if windows else 'gcc',*flags,*sources,'-o',str(out)],cwd=ROOT,check=True);subprocess.run([str(out)],check=True,timeout=10)
compiler=['clang','--target=armv5te-none-eabi','-ffreestanding','-fno-builtin','-I'+str(ROOT/'tools/fixtures/freestanding')] if windows else ['arm-linux-gnueabi-gcc']
subprocess.run([*compiler,'-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-Wframe-larger-than=2048','-c',str(ROOT/'runtime/platform/player/player_broker.c'),'-o',str(w/'broker.arm.o')],check=True)
report=dict(passed=True,device_accessed=False,host='windows-clang' if windows else 'gcc',sanitizers=not windows,checks=['PLAY_ITEM unsupported until adapter attachment','owner only attachment and dispatch','qualified revision required when requested','BUSY and UNCERTAIN forwarded without retry','container selection remains unsupported','clock/source loss revokes pending selection','busy revocation finishes before next submission','definite backend failures revoke selection while BUSY stays transient','failed poll preserves outputs and recovery refreshes availability','ordinary controls retain original backend','close waits for adapter drain and preserves backend lifetime'],source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['runtime/platform/player/player_broker.h','tools/test_player_broker_source.py']},limits=['Selection adapter, clock and source are modeled; this is broker routing/lifecycle, not native player execution.','No source adapter is installed in the host by this test.'])
(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
