"""RF-init orchestration on ARM926/Sony libc; original-tool exec is substituted."""
import hashlib
import json
from pathlib import Path
import resource
import subprocess

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/espnow-rf-init-arm';OUT.mkdir(parents=True,exist_ok=True)
LIB=ROOT/'work/arm-signal-tests/lib'
for name,digest in {
    'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812',
    'ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de',
}.items():
    if hashlib.sha256((LIB/name).read_bytes()).hexdigest()!=digest:raise ValueError('unqualified libc')
sources=['tools/test_xnow_rf_init.c','runtime/platform/espnow/xnow_rf_init.c',
         'runtime/store/start.c','runtime/store/start.S']
app=OUT/'test'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror',
                '-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0',
                '-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie',
                '-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv',
                '-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',
                *sources,'-Wl,--wrap=execve',str(LIB/'libc.so.6'),str(LIB/'ld-linux.so.3'),
                '-lgcc','-o',str(app)],cwd=ROOT,check=True)
def limit_test_descriptors():resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
run=subprocess.run(['qemu-arm','-cpu','arm926',str(LIB/'ld-linux.so.3'),
                    '--library-path',str(LIB),str(app)],capture_output=True,text=True,
                   preexec_fn=limit_test_descriptors,timeout=30)
if run.returncode:raise RuntimeError(run.stdout+run.stderr)
report={'passed':True,'stdout':run.stdout,'stderr':run.stderr,
        'sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'sony_libc':True,'qemu_arm926':True,
        'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},
        'test_process_fd_limit':128,'stock_tool_exec_substituted':True,
        'real_fork_pipe_wait_executed':True,'device_accessed':False,'rf_initialization_qualified':False}
(OUT/'report.json').write_text(json.dumps(report,indent=2));print(run.stdout.strip())
