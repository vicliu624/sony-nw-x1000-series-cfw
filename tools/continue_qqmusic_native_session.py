"""PC-only handoff from our pinned, idle ARM process to a complete new build.

No account data files or login requests. Verified state crosses an anonymous
pipe in RAM. Never targets the official client or a physical device.
"""
from qqmusic_font_config import FONT_BYTES,FONT_SHA256,FONT_NAME
import hashlib,json,os,signal,struct,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
old=Path(sys.argv[1]).resolve();new=(old/sys.argv[2]/'app').resolve()
assert old.is_relative_to(ROOT/'work/qqmusic-live-session')
manifest=json.loads((old/'manifest.json').read_text())
original=(old/manifest['binary']).resolve()
assert original.is_relative_to(old)
assert hashlib.sha256(original.read_bytes()).hexdigest()==manifest['binary_sha256']
build=json.loads((new.parent/'build.json').read_text())
assert hashlib.sha256(new.read_bytes()).hexdigest()==build['app_sha256']
for name,digest in (build['sources']|build.get('included_sources',{})).items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
meta=json.loads((old/'runtime-layout.json').read_text())
assert meta['binary_sha256']==manifest['binary_sha256']
layout=meta['offsets'];pids=[]
for path in Path('/proc').iterdir():
    if not path.name.isdigit():continue
    try:
        args=(path/'cmdline').read_bytes().split(b'\0')
        if (path/'comm').read_text().strip()=='qemu-arm' and str(original).encode() in args and str(old).encode() in args:pids.append(int(path.name))
    except (FileNotFoundError,PermissionError):pass
assert len(pids)==1
lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';math=ROOT/'work/qqmusic-codec'
command=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',f'{lib}:{resolver}:{math}',str(new)]
count=int(subprocess.check_output(command+['--host-continuation-size']))
assert 65536<count<300000
target=old/(sys.argv[2]+'-run');target.mkdir(mode=0o700,exist_ok=False)
pid=pids[0];secret=None
os.kill(pid,signal.SIGSTOP)
try:
    for _ in range(100):
        state=Path(f'/proc/{pid}/stat').read_text().split(')')[-1].split()[0]
        if state=='T':break
        time.sleep(.001)
    assert state=='T'
    with open(f'/proc/{pid}/mem','rb',buffering=0) as memory:
        def read(at,n):memory.seek(at);return memory.read(n)
        def u32(at):return struct.unpack('<I',read(at,4))[0]
        def u64(at):return struct.unpack('<Q',read(at,8))[0]
        pattern=struct.pack('<3I',*meta['functions']);hits=[]
        for row in Path(f'/proc/{pid}/maps').read_text().splitlines():
            fields=row.split();label=fields[5] if len(fields)>5 else ''
            if 'rw' not in fields[1] or label not in ('','[heap]'):continue
            lo,hi=[int(v,16) for v in fields[0].split('-')]
            if hi-lo>64*1024*1024:continue
            block=read(lo,hi-lo);start=0
            while True:
                hit=block.find(pattern,start)
                if hit<0:break
                start=hit+1;base=lo+hit-layout[0]-4
                try:
                    if u32(base+layout[1])==5 and u32(base+layout[2])==7 and not u32(base+layout[4]) and not u64(base+layout[5]):hits.append(base)
                except (OSError,struct.error):pass
        assert len(hits)==1
        secret=bytearray(read(hits[0],count));assert len(secret)==count
finally:os.kill(pid,signal.SIGCONT)
process=None
try:
    process=subprocess.Popen(command+['--host-continue',str(target),str(ROOT/'work/qqmusic-font/QQMusicUI.otf')],stdin=subprocess.PIPE,cwd=ROOT)
    process.stdin.write(struct.pack('<I',count));process.stdin.write(secret);process.stdin.flush()
    secret[:]=b'\0'*len(secret);secret=None
    print('Complete native build running; verified own-app session continued in RAM; no login requested.',flush=True)
    for line in sys.stdin:
        if not (line.startswith('tap ') or line.strip()=='stop'):continue
        process.stdin.write(line.encode('ascii'));process.stdin.flush()
        if line.strip()=='stop':break
    process.wait()
finally:
    if secret is not None:secret[:]=b'\0'*len(secret)
    if process is not None and process.poll() is None:process.terminate();process.wait()
