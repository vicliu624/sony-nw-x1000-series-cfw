"""Exercise actual C catalog reader with original SQLite and synthetic schema only."""
from pathlib import Path
import hashlib,json,os,sqlite3,subprocess,tarfile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/player-catalog-ro';work.mkdir(exist_ok=True)
with tarfile.open(ROOT/'work/upg-jp/verified-3.bin','r:gz') as archive:
 for source,name in [('usr/lib/libsqlite3.so.0.8.6','libsqlite3.so.0'),('lib/libdl-2.3.3.so','libdl.so.2'),('lib/libpthread-0.10.so','libpthread.so.0')]:
  (work/name).write_bytes(archive.extractfile('./'+source).read())
assert hashlib.sha256((work/'libsqlite3.so.0').read_bytes()).hexdigest()=='41f58a3490919b88fe6683e20bee818ac4e9e3e9bc17ce4106b917df5309fe4c'
paths=[];hashes={}
for name,bad in [('valid.db',0),('unknown-schema.db',1),('wrong-group.db',2),('wrong-type.db',3)]:
 path=work/name
 if path.exists():path.unlink()
 with sqlite3.connect(path) as db:
  db.executescript('CREATE TABLE object_body(object_id INTEGER PRIMARY KEY,reference_id INTEGER,parent_id INTEGER,tree_id INTEGER,object_type INTEGER,child_index INTEGER,media_type INTEGER,format INTEGER,title TEXT,m2_id INTEGER,m3_id INTEGER); CREATE TABLE object_meta_text(id INTEGER PRIMARY KEY,meta_id INTEGER,value TEXT); CREATE TABLE schema(prop_type INTEGER,meta_id INTEGER,data_type INTEGER,prop_name TEXT);')
  db.executemany('INSERT INTO schema VALUES(?,?,?,?)',[(2 if bad==2 else 1,77 if bad==1 else 2,0x77 if bad==3 else 0x73,'ARTIST'),(1,3,0x73,'ALBUM')])
  db.executemany('INSERT INTO object_meta_text VALUES(?,?,?)',[(1,2,'Shared artist'),(2,3,'Shared album')])
  db.executemany('INSERT INTO object_body VALUES(?,?,?,?,?,?,?,?,?,?,?)',[(10,10,0,1,1,0,0,0,'Synthetic playlist',None,None),(100,100,0,0,2,0,0,0,'X'+'\u732b'*100,1,2),(101,101,0,0,2,1,0,0,'Second song',1,2),(102,102,0,0,2,2,0,0,'Corrupt',1,2),(201,100,10,1,3,1,0,0,None,None,None),(202,101,10,1,3,0,0,0,None,None,None),(203,102,10,1,3,2,0,0,None,None,None),(204,999,10,1,3,3,0,0,'Orphan must not appear',None,None),(103,103,0,0,2,3,0,0,'Title only',None,None)])
  db.execute("UPDATE object_body SET title=CAST(X'ff' AS TEXT) WHERE object_id=102")
 paths.append(path);hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0'];sources=['runtime/platform/player/catalog_ro.c','runtime/platform/player/local_identity.c','tools/fixtures/player_catalog_ro.c'];lib=ROOT/'work/arm-signal-tests/lib';app=work/'catalog.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S',*[str(work/n) for n in ('libsqlite3.so.0','libdl.so.2','libpthread.so.0')],str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(work)+':'+str(lib),str(app),*map(str,paths)],env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=20)
(work/'trace.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stdout+run.stderr[-7000:]
for path in paths:assert hashlib.sha256(path.read_bytes()).hexdigest()==hashes[path.name] and not path.with_name(path.name+'-journal').exists()
for line in run.stderr.splitlines():
 if 'open(' in line and any(str(path) in line for path in paths):assert 'O_RDONLY' in line and not any(flag in line for flag in ('O_RDWR','O_WRONLY','O_CREAT')),line
report=dict(passed=True,original_sqlite=True,synthetic_database=True,real_device_accessed=False,stock_queue_supported=False,source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources+['runtime/platform/player/catalog_ro.h','runtime/platform/player/sqlite_abi.h']},stdout=run.stdout,limits=['Catalog tree is not a current playback queue or automatic music-only classification.','Original-library ABI and synthetic-schema behavior are qualified offline; live schema/profile and file ownership remain unqualified.','Fixture _exit excludes legacy LinuxThreads process teardown.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
