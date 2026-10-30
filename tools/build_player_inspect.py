"""Build a reviewable native schema diagnostic; never deploys or executes on player."""
from pathlib import Path
import hashlib,json,os,sqlite3,subprocess,tarfile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/player-inspect';work.mkdir(exist_ok=True)
with tarfile.open(ROOT/'work/upg-jp/verified-3.bin','r:gz') as archive:
 for source,dest in [('usr/lib/libsqlite3.so.0.8.6','libsqlite3.so.0'),('lib/libdl-2.3.3.so','libdl.so.2'),('lib/libpthread-0.10.so','libpthread.so.0')]:
  data=archive.extractfile('./'+source).read();(work/dest).write_bytes(data)
assert hashlib.sha256((work/'libsqlite3.so.0').read_bytes()).hexdigest()=='41f58a3490919b88fe6683e20bee818ac4e9e3e9bc17ce4106b917df5309fe4c'
lib=ROOT/'work/arm-signal-tests/lib';source='runtime/platform/player/inspect_main.c';flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
libraries=[str(work/name) for name in ('libsqlite3.so.0','libdl.so.2','libpthread.so.0')]+[str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc']
def build(path,extra=()):subprocess.run(['arm-linux-gnueabi-gcc',*flags,*extra,source,'runtime/store/start.c','runtime/store/start.S',*libraries,'-o',str(path)],cwd=ROOT,check=True)
app=work/'player-schema-inspect.arm';build(app);fixture=work/'fixture.arm';build(fixture,['-DXW_INSPECT_FIXTURE'])
env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD');base=['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(work)+':'+str(lib)]
for args,expected in [(['--help'],0),(['--version'],0),([],64),(['--inspect','/etc/passwd'],64),(['--fixture','/db/MTPDB.dat'],64),(['--fixture-types','/db/MTPDB.dat'],64),(['--inspect-types','/etc/passwd'],64)]:
 r=subprocess.run(base+[str(app),*args],env=env,capture_output=True,text=True,timeout=10);assert r.returncode==expected,(args,r.stderr);assert '/db/' not in r.stderr and '/contents/' not in r.stderr
path=work/'synthetic.db'
if path.exists():path.unlink()
with sqlite3.connect(path) as db:
 db.executescript('CREATE TABLE object_body(object_id INTEGER PRIMARY KEY,parent_id INTEGER,reference_id INTEGER,object_type INTEGER,tree_id INTEGER,child_index INTEGER,media_type INTEGER,format INTEGER,title TEXT,m1_id INTEGER,m2_id INTEGER,m3_id INTEGER); CREATE TABLE schema(prop_type INTEGER,meta_id INTEGER,data_type INTEGER,prop_name TEXT);')
 db.executemany('INSERT INTO schema VALUES(?,?,?,?)',[(1,2,115,'ARTIST'),(1,3,115,'ALBUM')]);db.execute("INSERT INTO object_body(object_id,object_type,media_type,format,title) VALUES(1,0,1,2,'PRIVATE TEST SONG MUST NOT APPEAR')");db.execute("INSERT INTO object_body(object_id,object_type,media_type,format,title) VALUES(2,1,1,3,'PRIVATE TEST LIST MUST NOT APPEAR')");db.execute("INSERT INTO object_body(object_id,object_type,media_type,format,title) VALUES(3,0,1,2,'PRIVATE TEST PATH MUST NOT APPEAR')");db.execute("INSERT INTO object_body(object_id,object_type,media_type,format) VALUES(4,NULL,NULL,NULL)")
before=hashlib.sha256(path.read_bytes()).hexdigest()
r=subprocess.run(base+[str(fixture),'--fixture',str(path)],env=env,capture_output=True,text=True,timeout=15);assert r.returncode==0,r.stdout+r.stderr
assert 'ARTIST' in r.stdout and 'ALBUM' in r.stdout and 'PRIVATE TEST SONG' not in r.stdout
assert before==hashlib.sha256(path.read_bytes()).hexdigest() and not path.with_name('synthetic.db-journal').exists()
(work/'fixture-output.txt').write_text(r.stdout)
types=subprocess.run(base+[str(fixture),'--fixture-types',str(path)],env=env,capture_output=True,text=True,timeout=15);assert types.returncode==0,types.stdout+types.stderr
assert '0\t1\t2\t2' in types.stdout and '1\t1\t3\t1' in types.stdout and 'NULL\tNULL\tNULL\t1' in types.stdout
assert 'PRIVATE TEST' not in types.stdout and 'object_id' not in types.stdout
assert before==hashlib.sha256(path.read_bytes()).hexdigest() and not path.with_name('synthetic.db-journal').exists()
assert not any('O_WRONLY' in line or 'O_RDWR' in line or 'O_CREAT' in line for line in types.stderr.splitlines() if 'open(' in line)
(work/'fixture-types-output.txt').write_text(types.stdout)
missing=work/'must-not-create.db'
assert not missing.exists()
absent=subprocess.run(base+[str(fixture),'--fixture-types',str(missing)],env=env,capture_output=True,text=True,timeout=15)
assert absent.returncode==2 and not missing.exists()
with sqlite3.connect(path) as db:
 db.executemany('INSERT INTO object_body(object_id,object_type,media_type,format) VALUES(?,?,?,?)',[(100+n,0,1,100+n) for n in range(129)])
limited_hash=hashlib.sha256(path.read_bytes()).hexdigest()
limited=subprocess.run(base+[str(fixture),'--fixture-types',str(path)],env=env,capture_output=True,text=True,timeout=15)
assert limited.returncode==1 and 'row_limit_exceeded=128' in limited.stdout and 'result=ERROR' in limited.stdout
assert limited_hash==hashlib.sha256(path.read_bytes()).hexdigest() and not path.with_name('synthetic.db-journal').exists()


report=dict(passed=True,artifact=str(app.relative_to(ROOT)),sha256=hashlib.sha256(app.read_bytes()).hexdigest(),bytes=app.stat().st_size,device_accessed=False,read_only_fixture=True,song_data_not_queried=True,aggregate_type_counts_verified=True,missing_database_not_created=True,row_limit_refusal_verified=True,source_sha256=hashlib.sha256((ROOT/source).read_bytes()).hexdigest(),limits=['Production diagnostic has not run on hardware.','Fixture bypasses LinuxThreads process teardown only; stock SQLite query functions execute.'])
(work/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
(work/'REVIEW.md').write_text('Read-only diagnostic, not an SDK backend or firmware package.\n\nArtifact: player-schema-inspect.arm. Keep original Sony libraries on the player; do not copy the local library extraction.\nRun manually only after authorization: ./player-schema-inspect.arm --inspect /db/MTPDB.dat\nIf unavailable, explicitly inspect /contents/MTPDB.dat instead. No automatic path fallback.\nOptional second command: ./player-schema-inspect.arm --inspect-types /db/MTPDB.dat\nAggregate mode reports only object_type/media_type/format/count, including NULL values. No titles, paths, object IDs or playlist names. It is a bounded read-only scan, not a library refresh. No control command or persisted log.\nNo device deployment or execution was performed by this builder.\n')
