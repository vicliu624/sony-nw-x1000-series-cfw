"""Build a local-only bounded diagnostic supervisor; no deployment or firmware."""
import argparse,hashlib,json,secrets,subprocess,time
from pathlib import Path
from app_registry import ROOT
from player_arm_guest import stock_libraries
parser=argparse.ArgumentParser(description=__doc__);parser.parse_args()
out=ROOT/'work/launcher-capture'/str(time.time_ns());out.mkdir(parents=True)
header=b'X1CAPTURE0000001'+secrets.token_bytes(16);assert len(header)==32
seed=out/'launcher-capture.bin';seed.write_bytes(header+bytes(4096-32))
(out/'launcher_capture_profile.h').write_text('#define LAUNCHER_CAPTURE_HEADER {'+','.join(str(x) for x in header)+'}\n')
sources=['runtime/apps/diagnostics/launcher_capture.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S']
libs=stock_libraries();binary=out/'launcher-capture.arm'
flags=['-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-no-pie','-fno-stack-protector','-nostdlib','-Wl,--hash-style=sysv,--build-id=none','-I'+str(out)]
subprocess.run(['arm-linux-gnueabi-gcc',*flags,*sources,str(libs['libc.so.6']),str(libs['ld-linux.so.3']),'-lgcc','-o',str(binary)],cwd=ROOT,check=True)
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
report=dict(built=True,artifact=str(binary.relative_to(ROOT)),bytes=binary.stat().st_size,sha256=digest(binary),seed_sha256=digest(seed),device_accessed=False,firmware_created=False,hardware_qualified=False,trace_file_bytes=4096,maximum_payload_bytes=4000,source_hashes={s:digest(ROOT/s) for s in sources+[str(Path(__file__).relative_to(ROOT))]},limits=['Capture requires verified mounted user storage and a preallocated nonce-matched file.','Cannot record a parent switch that never starts the supervisor or a failed storage preflight.','Diagnostic process lifetime only; must not launch apps during this test.'])
(out/'build.json').write_text(json.dumps(report,indent=2)+'\n');(ROOT/'work/launcher-capture-latest.json').write_text(json.dumps({'review':str((out/'build.json').relative_to(ROOT))})+'\n');print(json.dumps(report,indent=2))
