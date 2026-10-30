"""Original-library read-only catalog ABI probe using synthetic rows. PC only."""
from pathlib import Path
import hashlib,io,json,os,sqlite3,subprocess,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/player-sqlite-ro';work.mkdir(exist_ok=True)
with tarfile.open(ROOT/'work/upg-jp/verified-3.bin','r:gz') as archive:
    raw=archive.extractfile('./usr/lib/libsqlite3.so.0.8.6').read();(work/'libsqlite3.so.0').write_bytes(raw)
    (work/'libdl.so.2').write_bytes(archive.extractfile('./lib/libdl-2.3.3.so').read())
    (work/'libpthread.so.0').write_bytes(archive.extractfile('./lib/libpthread-0.10.so').read())
elf=ELFFile(io.BytesIO(raw));needed=[tag.needed for tag in elf.get_section_by_name('.dynamic').iter_tags() if tag.entry.d_tag=='DT_NEEDED'];print('Original SQLite dependencies:',needed)
database=work/'synthetic.db'
if database.exists():database.unlink()
with sqlite3.connect(database) as connection:
    connection.execute('CREATE TABLE object_body (object_id INTEGER PRIMARY KEY,title TEXT,parent_id INTEGER,reference_id INTEGER,child_index INTEGER)')
    connection.executemany('INSERT INTO object_body VALUES (?,?,?,?,?)',[(11,'Second song',9,101,1),(12,'First song',9,100,0),(13,'Unrelated',8,100,0)])
old=hashlib.sha256(database.read_bytes()).hexdigest();missing=work/'must-not-be-created.db';assert not missing.exists()
lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';source='tools/fixtures/player_sqlite_ro.c';app=work/'probe.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(resolver),source,'runtime/store/start.c','runtime/store/start.S',str(work/'libsqlite3.so.0'),str(work/'libdl.so.2'),str(work/'libpthread.so.0'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
try:
    run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(work)+':'+str(lib)+':'+str(resolver),str(app),str(database),str(missing)],env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),capture_output=True,text=True,timeout=20)
except subprocess.TimeoutExpired as error:
    stdout=error.stdout or b'';stderr=error.stderr or b''
    if isinstance(stdout,bytes):stdout=stdout.decode('utf-8','replace')
    if isinstance(stderr,bytes):stderr=stderr.decode('utf-8','replace')
    (work/'timeout-trace.log').write_text(stdout+stderr)
    (work/'report.json').write_text(json.dumps(dict(passed=False,timed_out=True,device_accessed=False,synthetic_database=True),indent=2)+'\n')
    print((stdout+stderr)[-2500:]);raise
(work/'trace.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr[-6000:]
assert old==hashlib.sha256(database.read_bytes()).hexdigest() and not missing.exists() and not (work/'synthetic.db-journal').exists()
report=dict(passed=True,stock_sqlite_version=run.stdout.splitlines()[0].split(': ',1)[1],library_sha256=hashlib.sha256(raw).hexdigest(),synthetic_database=True,unchanged_database=True,original_libc_arm=True,native_player_provider=False,device_accessed=False,process_exit="fixture uses _exit after sqlite close; LinuxThreads process teardown is not qualified",stdout=run.stdout,source_sha256=hashlib.sha256((ROOT/source).read_bytes()).hexdigest())
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
