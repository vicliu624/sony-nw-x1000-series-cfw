"""Incremental grouped reader: native boundary modeled, explicit host/ARM scope."""
from pathlib import Path
import hashlib,json,os,subprocess
from app_registry import ROOT
w=ROOT/'work/group-reader';w.mkdir(exist_ok=True)
sources=['runtime/platform/player/group_reader.c','runtime/platform/player/query_snapshot.c','runtime/platform/player/local_identity.c','tools/fixtures/group_reader.c']
windows=os.name=='nt';output=w/('test.exe' if windows else 'test')
flags=['-std=c11','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation']
if not windows:flags+=['-fsanitize=address,undefined']
subprocess.run(['clang' if windows else 'gcc',*flags,*sources,'-o',str(output)],cwd=ROOT,check=True)
subprocess.run([str(output)],cwd=ROOT,check=True,timeout=15)
native_sources=sources[:-1]+['runtime/platform/player/group_native.c','tools/fixtures/group_native.c']
native_output=w/('native-test.exe' if windows else 'native-test')
subprocess.run(['clang' if windows else 'gcc',*flags,*native_sources,'-o',str(native_output)],cwd=ROOT,check=True)
subprocess.run([str(native_output)],cwd=ROOT,check=True,timeout=15)
for source in ('runtime/platform/player/group_reader.c','runtime/platform/player/group_native.c'):
 command=['clang','--target=armv5te-none-eabi','-ffreestanding','-fno-builtin','-I'+str(ROOT/'tools/fixtures/freestanding')] if windows else ['arm-linux-gnueabi-gcc']
 subprocess.run([*command,'-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-c',str(ROOT/source),'-o',str(w/(Path(source).stem+'.o'))],check=True)
report=dict(passed=True,host='windows-clang' if windows else 'linux-gcc',host_sanitizers=not windows,arm_compile=True,arm_compiler="windows-clang" if windows else "gnu",supported_gnu_build=not windows,device_accessed=False,checks=['one reader call per step','offset across groups and empty groups','partial final page and observed total','unknown group count ends explicitly','past-end offset refusal','atomic I/O and malformed-ID failures','captured ordinal missing is stale','shuffle refusal','reset cancels pending result','client closed after every native step including invalid/final steps','failed close preserves output'],source_hashes={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sorted(set(sources+native_sources+['runtime/platform/player/group_reader.h','runtime/platform/player/group_native.h','tools/fixtures/freestanding/string.h','tools/test_group_reader.py']))},limits=['Reader is modeled; this does not execute Sony Moma, ARM instructions or native grouped ordering.','Public queue integration and shuffled grouped traversal remain unfinished.','On Windows, ARM objects use freestanding Clang; GNU/ASan/UBSan and original-loader checks are not run.'])
(w/('report-windows.json' if windows else 'report.json')).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
