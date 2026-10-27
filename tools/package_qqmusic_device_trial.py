"""Local X1060 native UI/account trial package; never installs or flashes."""
from pathlib import Path
import hashlib,json,shutil,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/qqmusic-device-trial-1'
build=json.loads((work/'native/build.json').read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
assert not build['host_session_fixture'] and not build['imports_enabled']
assert sha(work/'native/app')==build['app_sha256']
for name,digest in build['sources'].items():assert sha(ROOT/name)==digest
version=(ROOT/'VERSION').read_text().strip()
out=ROOT/'dist'/version/'qqmusic-x1060-device-trial-1'
out.mkdir(parents=True,exist_ok=False)
app=out/'HOMEBREW/apps/qqmusic';(app/'resources').mkdir(parents=True)
(app/'lib').mkdir()
shutil.copyfile(work/'native/app',app/'app');(app/'app').chmod(0o755)
font=ROOT/'work/qqmusic-font/NotoSansCJKsc-Regular.otf'
assert sha(font)=='2c76254f6fc379fddfce0a7e84fb5385bb135d3e399294f6eeb6680d0365b74b'
shutil.copyfile(font,app/'resources'/font.name)
for name,source in [('libcares.so.2','work/stock-resolver-probe'),('librt.so.1','work/stock-resolver-probe'),('libpthread.so.0','work/stock-resolver-probe'),('libm.so.6','work/qqmusic-codec')]:
    shutil.copyfile(ROOT/source/name,app/'lib'/name)
(app/'app.ini').write_text(f'api=1\nid=qqmusic\nname=QQ Music Trial\nversion=0.1.0-alpha.1\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={(app/"app").stat().st_size}\nsha256={sha(app/"app")}\n')
files=sorted(p for p in app.rglob('*') if p.is_file())
(app/'files.sha256').write_text('HBFILES1\n'+''.join(f'{sha(p)} {p.stat().st_size} {p.relative_to(app).as_posix()}\n' for p in files))
licenses=out/'LICENSES';licenses.mkdir()
for source,name in [('work/qqmusic-font/OFL.txt','Noto-OFL.txt'),('third_party/qqmusic-stb/LICENSE','stb-LICENSE.txt'),('work/external-tls-probe/bearssl-0.6/LICENSE.txt','BearSSL-LICENSE.txt')]:shutil.copyfile(ROOT/source,licenses/name)
shutil.copyfile(ROOT/'docs/apps/QQ_MUSIC.md',out/'README.md')
review=out/'REVIEW';review.mkdir();shutil.copyfile(work/'native/build.json',review/'build.json')
# Load from the assembled package, resolving private libs through its RPATH.
lib=ROOT/'work/arm-signal-tests/lib'
loader=lib/'ld-linux.so.3'
checks=[]
for option,expected in [('--help','Imports remain disabled'),('--version',version)]:
    result=subprocess.run(['qemu-arm','-cpu','arm926',str(loader),'--library-path',str(lib),str(app/'app'),option],capture_output=True,text=True,check=True,timeout=10)
    assert expected in result.stdout
    checks.append(option)
identity={'kind':'native X1060 first hardware trial; NOT complete music-import delivery','target':'Japanese NW-X1060 stock 1.11','imports_enabled':False,'hardware_qualified':False,'ready_to_flash':False,'host_adapter_included':False,'account_data_included':False,'expected_user_volume_source':'/dev/mtdblock/2','expected_mount':'/contents','source_is_stock_reference_not_hardware_observation':True,'requires_existing_homebrew_entry':True,'local_only_stock_libraries':True,'assembled_package_loader_checks':checks,'app_sha256':sha(app/'app')}
(review/'package.json').write_text(json.dumps(identity,indent=2)+'\n')
entries=sorted(p for p in out.rglob('*') if p.is_file())
(out/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(out).as_posix()}\n' for p in entries))
archive=out.with_suffix('.zip');assert not archive.exists()
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,6) as z:
    for p in sorted(out.rglob('*')):
        if p.is_file():z.write(p,p.relative_to(out).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for p in out.rglob('*'):
        if p.is_file():assert z.read(p.relative_to(out).as_posix())==p.read_bytes()
    assert not any(n.endswith(('.upg','.py','.private.json')) for n in z.namelist())
digest=sha(archive);archive.with_suffix('.zip.sha256').write_text(f'{digest}  {archive.name}\n')
print(json.dumps({'zip':str(archive),'bytes':archive.stat().st_size,'sha256':digest,**identity},indent=2))
