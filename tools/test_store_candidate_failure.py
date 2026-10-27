"""Run actual candidate against a regular-file fake display in QEMU only."""
from pathlib import Path
import hashlib,json,re,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
build=json.loads((ROOT/'sources/native-store-app-build.json').read_text())
app=ROOT/build['artifact'];assert hashlib.sha256(app.read_bytes()).hexdigest()==build['sha256']
runtime=ROOT/'work/store-app-candidate';work=ROOT/'work/store-candidate-failure';work.mkdir(exist_ok=True)
# No fallback to a real host display is acceptable if QEMU prefix routing fails.
assert not Path('/dev/fb/0').exists() and not Path('/dev/icx_touch_screen').exists()
with tempfile.TemporaryDirectory(prefix='sysroot-',dir=work) as temp:
 root=Path(temp);fake=root/'dev/fb/0';fake.parent.mkdir(parents=True);fake.write_bytes(b'ORDINARY FILE - NOT A DISPLAY\n')
 before=fake.read_bytes()
 run=subprocess.run(['qemu-arm','-cpu','arm926','-L',str(root),'-strace',str(runtime/'ld-2.3.3.so'),'--library-path',str(runtime),str(app),'--native'],capture_output=True,text=True,timeout=15)
 assert run.returncode==2,(run.returncode,run.stdout,run.stderr)
 found=re.search(r'open\("/dev/fb/0",[^\n]* = (\d+)\n',run.stderr)
 assert found,run.stderr
 fd=int(found.group(1));tail=run.stderr[found.end():]
 assert re.search(r'ioctl\('+str(fd)+r',[^\n]*errno=25',tail),tail
 assert re.search(r'close\('+str(fd)+r'\) = 0',tail),tail
 assert '/dev/icx_touch_screen' not in run.stderr and 'mmap2(' not in tail
 assert fake.read_bytes()==before
 report={'all_bounded_checks_passed':True,'physical_device_access':False,'candidate_sha256':build['sha256'],'QEMU_native_failure_exit':run.returncode,'fake_display':'regular file under QEMU prefix','geometry_query_failed_ENOTTY':True,'display_descriptor_closed':True,'touch_not_opened':True,'fixture_unchanged':True,'trace':run.stderr,'limits':['Actual candidate and OABI instructions; only unsupported regular-file display failure path.','QEMU user-mode host syscall translation, not Sony kernel or device.','No successful display/touch/install test of deployed binary; not hardware qualification.']}
 (ROOT/'sources/native-store-candidate-failure.json').write_text(json.dumps(report,indent=2)+'\n')
print('Actual store candidate: fake-display ENOTTY cleanup passed, no real devices.')
