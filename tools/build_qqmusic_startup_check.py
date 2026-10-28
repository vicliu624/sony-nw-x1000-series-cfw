"""Build small local on-screen startup probe; no login, deployment or flashing."""
from pathlib import Path
import subprocess,json,hashlib,zipfile,shutil
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-startup-check';work.mkdir(exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
sources=['runtime/apps/qqcheck/qqmusic_startup_check.c','runtime/apps/qqmusic/qqmusic_workspace.c','runtime/apps/qqmusic/qqmusic_wifi_link.c','runtime/apps/qqmusic/qqmusic_volume.c','runtime/apps/qqmusic/qqmusic_storage.c','runtime/apps/qqmusic/qqmusic_asset.c','runtime/native/sha256.c','runtime/native/linux_devices.c','runtime/native/frontend.c','runtime/native/linux_signals.c','runtime/native/syscalls.S','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c','runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=gnu99','-Os','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(work/'app')],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(work/'app'),'--help'],check=True)
report={'source_hashes':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},'app_sha256':hashlib.sha256((work/'app').read_bytes()).hexdigest(),'real_device_tested':False,'account_accessed':False,'purpose':'Narrow human feedback loop for immediate pre-UI exit. No fix claimed.'}
(work/'build.json').write_text(json.dumps(report,indent=2)+'\n')
out=ROOT/'dist/0.1.0-dev.16/qqmusic-startup-check-5';out.mkdir(parents=True,exist_ok=False)
app=out/'HOMEBREW/apps/qqcheck';app.mkdir(parents=True);shutil.copyfile(work/'app',app/'app');(app/'app').chmod(0o755)
(app/'app.ini').write_text(f'api=1\nid=qqcheck\nname=QQ Startup Check\nversion=0.1.0-alpha.5\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={(app/"app").stat().st_size}\nsha256={report["app_sha256"]}\n')
(app/'files.sha256').write_text('HBFILES1\n'+''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()} {p.stat().st_size} {p.name}\n' for p in sorted(app.iterdir()) if p.is_file()))
shutil.copyfile(ROOT/'docs/apps/DIAGNOSTICS.md',out/'README.md')
shutil.copyfile(work/'build.json',out/'build.json')
archive=out.with_suffix('.zip');assert not archive.exists()
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,6) as z:
 for path in sorted(out.rglob('*')):
  if path.is_file():z.write(path,path.relative_to(out).as_posix())
with zipfile.ZipFile(archive) as z:
 assert not z.testzip()
 for path in out.rglob('*'):
  if path.is_file():assert z.read(path.relative_to(out).as_posix())==path.read_bytes()
print(json.dumps({'zip':str(archive),'bytes':archive.stat().st_size,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),**report},indent=2))
