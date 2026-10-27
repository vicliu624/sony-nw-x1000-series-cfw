"""Build an external graphical C example; no deployment or device execution."""
from pathlib import Path
import hashlib,json,subprocess,argparse
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--review-output',default='work/graphics-demo-review');options=parser.parse_args()
work=(ROOT/options.review_output).resolve();assert work.is_relative_to(ROOT/'work') and work!=ROOT/'work';assert not any(part.startswith(('integration-','product-review-','libc-product-review-')) for part in work.relative_to(ROOT/'work').parts);work.mkdir(parents=True,exist_ok=True)
lib=ROOT/'work/arm-signal-tests/lib'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
flags=['-DHB_USE_POSIX_DEVICE_IO','-D_DEFAULT_SOURCE','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3']
startup=['runtime/store/start.c','runtime/store/start.S'];library=[str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc']
base=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)]
sources=['runtime/apps/graphics-demo/graphics_demo.c','runtime/native/frontend.c','runtime/native/linux_devices.c','runtime/native/linux_device_io_posix.c','runtime/native/linux_signals_posix.c',*startup]
folder=work/'apps/graphics-demo';folder.mkdir(parents=True,exist_ok=True);artifact=folder/'app'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,*sources,*library,'-o',str(artifact)],cwd=ROOT,check=True)
symbols=subprocess.check_output(['arm-linux-gnueabi-nm',str(artifact)],text=True);assert 'x1000_oabi_call' not in symbols and 'x1000_rt_sigreturn' not in symbols
help_run=subprocess.run(base+[str(artifact),'--help'],cwd=ROOT,capture_output=True,text=True,timeout=10);assert help_run.returncode==0 and 'BACK TO APPS' in help_run.stdout
fixture_sources=['runtime/apps/graphics-demo/graphics_demo.c','runtime/native/frontend.c','tools/fixtures/graphics_demo.c',*startup]
test=work/'fixture.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-DHB_DEMO_TEST',*fixture_sources,*library,'-o',str(test)],cwd=ROOT,check=True)
subprocess.run(base+[str(test)],cwd=ROOT,check=True,timeout=10)
version=(ROOT/'VERSION').read_text().strip();data=artifact.read_bytes();digest=hashlib.sha256(data).hexdigest()
manifest=f'api=1\nid=graphics-demo\nname=Native C Graphics\nversion={version}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(data)}\nsha256={digest}\n'.encode();(folder/'app.ini').write_bytes(manifest)
files={'app':data,'app.ini':manifest};(folder/'files.sha256').write_text('HBFILES1\n'+''.join(f'{hashlib.sha256(v).hexdigest()} {len(v)} {k}\n' for k,v in sorted(files.items())))
launcher=ROOT/'work/libc-launcher-review/launcher.elf'
check=subprocess.run(base+[str(launcher),'--check',str(work/'apps')],cwd=ROOT,capture_output=True,text=True,timeout=10);assert check.returncode==0 and check.stdout=='graphics-demo VERIFIED\n',check
tracked=[ROOT/f for f in set(sources+fixture_sources)]+[Path(__file__),ROOT/'VERSION',ROOT/'runtime/native/font.inc',ROOT/'runtime/native/linux_devices.h',ROOT/'runtime/native/linux_device_io.h',ROOT/'runtime/native/linux_signals.h',ROOT/'runtime/native/frontend.h',lib/'libc.so.6',lib/'ld-linux.so.3',launcher]
report={'passed':True,'artifact':str(artifact.relative_to(ROOT)),'bytes':len(data),'sha256':digest,'checks':['ARM help entry','virtual tap changes colour and back exits','open failure','stop cleanup','device error cleanup','close error surfaced','libc launcher verifies external app'],'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},'hardware_tested':False,'firmware_created':False,'limits':['Actual graphical ELF only ran --help; interaction tests link virtual device functions.','No actual display/touch or Sony UI transition tested.','App package is review-only, not installed.']}
(work/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},indent=2))



