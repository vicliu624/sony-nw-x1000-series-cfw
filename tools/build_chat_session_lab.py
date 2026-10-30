"""Build only the explicit client/owner hardware lab. Never deploy or execute."""
from pathlib import Path
import hashlib
import json
import subprocess
from app_registry import ROOT
OUT=ROOT/'work/chat-session-lab';OUT.mkdir(parents=True,exist_ok=True)
LIB=ROOT/'work/arm-signal-tests/lib';RESOLVER=ROOT/'work/stock-resolver-probe'
sources=['tools/fixtures/chat_session_lab.c','runtime/apps/espnow-chat/chat_client.c','runtime/store/start.c','runtime/store/start.S']
artifact=OUT/'chat-session-lab.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-D_DEFAULT_SOURCE','-DHB_STORE_SONY_LIBC',
    '-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie',
    '-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',
    '-I'+str(ROOT/'sdk/include'),'-I'+str(ROOT/'work/espnow-chat-app'),'-I'+str(ROOT/'work/espnow-stock-reload-lab'),*sources,
    str(ROOT/'work/espnow-native-library/0.1.0-dev.8/sdk/lib/libxnow.a'),str(RESOLVER/'libcnmgr.so.1'),
    '-Wl,--no-as-needed',str(RESOLVER/'libpthread.so.0'),str(LIB/'libc.so.6'),str(LIB/'ld-linux.so.3'),'-lgcc','-o',str(artifact)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(LIB/'ld-linux.so.3'),'--library-path',f'{LIB}:{RESOLVER}',str(artifact),'--help'],check=True,timeout=15)
report={'built':True,'bytes':artifact.stat().st_size,'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),
    'md5':hashlib.md5(artifact.read_bytes()).hexdigest(),'device_written':False}
(OUT/'build.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
