"""Run a selected Store ELF against a regular-file display in QEMU."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess
from actual_app_fixture import stock_libc
from component_receipts import ROOT, private
from store_test_fixture import workspace

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--app', required=True, type=Path)
app = private(parser.parse_args().app)
app_sha256 = hashlib.sha256(app.read_bytes()).hexdigest()
library = stock_libc()
resolver = ROOT / 'work/stock-resolver-probe'
# No fallback to a real host display is acceptable if QEMU prefix routing fails.
assert not Path('/dev/fb/0').exists() and not Path('/dev/icx_touch_screen').exists()
with workspace('store-display-failure-') as temp:
 root=Path(temp);fake=root/'dev/fb/0';fake.parent.mkdir(parents=True);fake.write_bytes(b'ORDINARY FILE - NOT A DISPLAY\n')
 (root/'lib').mkdir()
 libs = [library/name for name in ('libc.so.6','ld-linux.so.3')]
 libs += [resolver/name for name in ('libcares.so.2','librt.so.1','libpthread.so.0')]
 for source in libs:shutil.copyfile(source, root/'lib'/source.name)
 before=fake.read_bytes()
 run=subprocess.run(['qemu-arm','-cpu','arm926','-L',str(root),'-strace',str(app),'--native'],capture_output=True,text=True,timeout=15)
 assert run.returncode==2,(run.returncode,run.stdout,run.stderr)
 found=re.search(r'open\("/dev/fb/0",[^\n]* = (\d+)\n',run.stderr)
 assert found,run.stderr
 fd=int(found.group(1));tail=run.stderr[found.end():]
 assert re.search(r'ioctl\('+str(fd)+r',[^\n]*errno=25',tail),tail
 assert re.search(r'close\('+str(fd)+r'\) = 0',tail),tail
 assert '/dev/icx_touch_screen' not in run.stderr and 'mmap2(' not in tail
 assert not re.search(r'\b(?:socket|connect|bind|sendto)\(',run.stderr,re.I)
 assert '/contents/HOMEBREW/repository' not in run.stderr
 assert fake.read_bytes()==before
 assert hashlib.sha256(app.read_bytes()).hexdigest() == app_sha256
 report={'all_bounded_checks_passed':True,'physical_device_access':False,'candidate_sha256':app_sha256,'QEMU_native_failure_exit':run.returncode,'fake_display':'regular file under QEMU prefix','geometry_query_failed_ENOTTY':True,'display_descriptor_closed':True,'touch_not_opened':True,'fixture_unchanged':True,'trace':run.stderr,'limits':['Original-libc ARM guest exercising only unsupported-display cleanup.','QEMU user-mode host syscall translation, not Sony kernel or device.']}
 report['source_hashes']={path.relative_to(ROOT).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in (app, Path(__file__), *libs)}
print(json.dumps(report,indent=2))
