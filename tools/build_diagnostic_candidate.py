"""Build a local Japanese X1000 diagnostic UPG for review, never installation.

Requires explicit --prepare-local-review. Never invokes an updater or player.
"""
from pathlib import Path
import argparse,copy,gzip,hashlib,io,json,re,shutil,subprocess,sys,tarfile
from evidence_checks import verify_report
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack,STOCK_SHA256
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--prepare-local-review',action='store_true')
parser.add_argument('--diagnostic-report',default='work/diagnostic-app-review-4/build.json')
parser.add_argument('--revision',type=int,default=1)
args=parser.parse_args();assert args.prepare_local_review and args.revision>0
version=(ROOT/'VERSION').read_text().strip()
output=ROOT/'dist'/version/('diagnostic-review-'+str(args.revision));assert not output.exists(),'Preserve existing review output.'
work=ROOT/'work'/('diagnostic-candidate-'+version+'-'+str(args.revision));work.mkdir(exist_ok=False)
review=ROOT/'work'/('libc-product-review-'+version+'-r4')
manifest=json.loads((review/'manifest.json').read_text())
for row in manifest['files']:
 path=review/row['path'];assert path.resolve().is_relative_to(review.resolve()) and not path.is_symlink()
 assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
diagnostic=verify_report(ROOT,args.diagnostic_report);assert diagnostic['passed'] and diagnostic['storage_writes_implemented'] is False
stock=ROOT/'work/updater-jp/NW_WM_FW.UPG';assert sha(stock)==STOCK_SHA256
_,components=unpack(stock.read_bytes())
for index,data in enumerate(components):assert data==(ROOT/f'work/upg-jp/verified-{index}.bin').read_bytes()
tool=ROOT/'third_party/rockbox-upgtools/upgtool';assert tool.is_file()
component_paths=[]
for index,data in enumerate(components):
 path=work/f'original-{index}.bin';path.write_bytes(data);component_paths.append(path)
def rockbox_create(path,parts,log):
 run=subprocess.run([str(tool),'--no-color','--create','-k','466c8cd0','-s','daefe603',str(path),*[str(p) for p in parts]],capture_output=True,text=True,timeout=120)
 log.write_text(run.stdout+run.stderr);assert run.returncode==0 and path.is_file(),log
roundtrip=work/'original-roundtrip.UPG';rockbox_create(roundtrip,component_paths,work/'roundtrip.log');assert sha(roundtrip)==STOCK_SHA256
overlays={row['path'].removeprefix('system-overlay/'):review/row['path'] for row in manifest['files'] if row['path'].startswith('system-overlay/')}
assert len(overlays)==15
tar_path=work/'candidate-rootfs.tar';changes=[]
with tarfile.open(fileobj=io.BytesIO(components[3]),mode='r:gz') as source,tarfile.open(tar_path,'w',format=tarfile.GNU_FORMAT) as target:
 for member in source:
  item=copy.copy(member);name=member.name.removeprefix('./')
  assert not name.startswith('/') and '..' not in name.split('/')
  if name in overlays:
   assert member.isfile();before=source.extractfile(member).read();after=overlays[name].read_bytes();item.size=len(after)
   target.addfile(item,io.BytesIO(after));changes.append({'path':name,'before_bytes':len(before),'after_bytes':len(after),'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(after).hexdigest()})
  elif member.isfile():target.addfile(item,source.extractfile(member))
  else:target.addfile(item)
assert {row['path'] for row in changes}==set(overlays)
new_root=work/'candidate-rootfs.tar.gz'
with tar_path.open('rb') as source,new_root.open('wb') as target,gzip.GzipFile(filename='',mode='wb',fileobj=target,mtime=0) as compressed:shutil.copyfileobj(source,compressed)
metadata=('name','type','mode','uid','gid','mtime','linkname','uname','gname','devmajor','devminor','pax_headers')
with tarfile.open(fileobj=io.BytesIO(components[3]),mode='r:gz') as before,tarfile.open(new_root,'r:gz') as after:
 a=before.getmembers();b=after.getmembers();assert len(a)==len(b)==1432
 for original,current in zip(a,b):
  assert all(getattr(original,key)==getattr(current,key) for key in metadata),original.name
  name=original.name.removeprefix('./')
  if original.isfile():
   actual=after.extractfile(current).read();expected=overlays[name].read_bytes() if name in overlays else before.extractfile(original).read()
   assert actual==expected,name
output.mkdir(parents=True)
firmware=output/'firmware';firmware.mkdir();candidate=firmware/'DIAGNOSTIC-REVIEW-ONLY.UPG'
rockbox_create(candidate,[*component_paths[:3],new_root],work/'candidate-create.log')
_,decoded=unpack(candidate.read_bytes(),require_stock=False)
assert decoded[:3]==components[:3] and decoded[3]==new_root.read_bytes()
extract_prefix=work/'independent-'
run=subprocess.run([str(tool),'--no-color','--extract','-k','466c8cd0','-s','daefe603','-o',str(extract_prefix),str(candidate)],capture_output=True,text=True,timeout=120)
(work/'independent-extract.log').write_text(run.stdout+run.stderr);assert run.returncode==0
for index,data in enumerate(decoded):assert (work/f'independent-{index}.bin').read_bytes()==data
shutil.copytree(review/'external',output/'external')
diag_source=(ROOT/diagnostic['artifact']).parent;shutil.copytree(diag_source,output/'external/HOMEBREW/apps/diagnostics')
materials=output/'review';materials.mkdir();shutil.copyfile(ROOT/'runtime/apps/diagnostics/diagnostics.c',materials/'diagnostics.c')
shutil.copyfile(ROOT/args.diagnostic_report,materials/'diagnostic-build.json')
shutil.copyfile((ROOT/args.diagnostic_report).parent/'diagnostics.png',materials/'diagnostics-PC-TEST-DATA.png')
# Recheck the prior dense local image against every current overlay, read-only.
dense_path=ROOT/'sources/native-stock-ext2-population.json';dense=json.loads(dense_path.read_text())
profile=next(p for p in dense['profiles'] if p['profile']=='candidate-with-registration')
image=(ROOT/profile['image']).resolve();assert image.is_relative_to(ROOT/'work') and image.is_file()
fsck=subprocess.run(['e2fsck','-f','-n',str(image)],capture_output=True,text=True,timeout=120)
(work/'model-fsck.log').write_text(fsck.stdout+fsck.stderr);assert fsck.returncode==0
for i,(name,path) in enumerate(sorted(overlays.items())):
 assert re.fullmatch(r'[A-Za-z0-9_./-]+',name)
 dumped=work/f'model-file-{i}.bin'
 run=subprocess.run(['debugfs','-R',f'dump /{name} {dumped}',str(image)],capture_output=True,text=True,timeout=30)
 assert run.returncode==0 and dumped.is_file() and dumped.read_bytes()==path.read_bytes(),name
stats=subprocess.check_output(['debugfs','-R','stats',str(image)],text=True,stderr=subprocess.DEVNULL)
def stat_value(name):return int(re.search(r'^'+re.escape(name)+r':\s+(\d+)',stats,re.M).group(1))
remaining=(stat_value('Free blocks')-stat_value('Reserved block count'))*stat_value('Block size')
assert remaining==profile['available_nonreserved_bytes']==29024256
lib=ROOT/'work/arm-signal-tests/lib'
launcher=output/'external/HOMEBREW/launcher/app'
base=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(launcher)]
for mode in ('--catalog','--check'):
 run=subprocess.run(base+[mode,str(output/'external/HOMEBREW/apps')],capture_output=True,text=True,timeout=15)
 assert run.returncode==0,(mode,run.stdout,run.stderr)
 if mode=='--check':assert set(run.stdout.splitlines())=={'store VERIFIED','graphics-demo VERIFIED','diagnostics VERIFIED'}
 (materials/(mode.removeprefix('--')+'.txt')).write_text(run.stdout)
report={'version':version,'profile':'local-diagnostic-review','revision':args.revision,'target':'Japanese NW-X1050/NW-X1060 stock 1.11; only user-reported X1060 available',
 'firmware_created':True,'ready_to_flash':False,'device_program_executed':False,'device_written':False,'hardware_tested':False,
 'upg_sha256':sha(candidate),'upg_bytes':candidate.stat().st_size,'original_upg_roundtrip_identical':True,'independent_rockbox_extraction_matches':True,
 'original_installer_kernel_initrd_unchanged':True,'original_components_sha256':[hashlib.sha256(p).hexdigest() for p in components[:3]],
 'rootfs_entries':1432,'rootfs_metadata_preserved':True,'new_system_paths':0,'system_changes':changes,
 'logical_system_growth_bytes':sum(c['after_bytes']-c['before_bytes'] for c in changes),
 'local_dense_ext2_model':{'bytes':profile['image_bytes'],'available_nonreserved_bytes':remaining,'current_overlay_files_read_back':15,'readonly_fsck_exit':fsck.returncode,'image_sha256':sha(image),'physical_capacity_verified':False},
 'external_apps':['store','graphics-demo','diagnostics'],'diagnostics_sha256':diagnostic['sha256'],'diagnostics_bytes':diagnostic['bytes'],
 'limits':['Not installed or hardware-qualified; Sony GUI recovery, real USB/FAT/Wi-Fi and matching recovery remain unverified.',
           'Original installer formats root before extraction; unchanged behavior is not rollback protection.',
           '148MiB dense image is a local model, not a read of the device root partition.',
           'Diagnostic screenshot contains PC TEST DATA; no measured device geometry or saved device logs.'],
 'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),ROOT/'VERSION',ROOT/'AGENTS.md',review/'manifest.json',ROOT/args.diagnostic_report,ROOT/'runtime/apps/diagnostics/diagnostics.c',stock,tool,dense_path]}}
(materials/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
(materials/'changes.json').write_text(json.dumps(changes,indent=2)+'\n')
(output/'REVIEW.md').write_text('# Local diagnostic candidate — do not install\n\n'
 'Prepared for local review only. No installation or device execution has been authorized.\n\n'
 'The UPG preserves Sony 1.11 installation script, kernel and initrd. Rootfs replaces the same 15 R4 files and preserves archive metadata. External programs belong in HOMEBREW on user storage; Device Check adds read-only proc status, refresh and BACK. It creates no log files.\n\n'
 'Review verification.json and changes.json. The 148MiB local model has 29,024,256 bytes available after reserved blocks; actual internal partition capacity and recovery are unverified. Sony GUI/display/USB/Wi-Fi behavior is not hardware-qualified. The original installer formats root before extraction.\n\n'
 'The screenshot is from virtual I/O and explicitly shows PC TEST DATA. Do not treat its 155189248-byte MTD1 value as a device measurement.\n\n'
 'No updater executable, installer script, DSP model, test kernel, preload library, Python runtime or ROM is included. No public release was made.\n',encoding='utf-8')
shutil.copyfile(ROOT/'docs/STATUS.md',output/'REVIEW.md')
# Review text is a maintained input; regenerate rather than relabel old evidence.
report['source_hashes']['docs/STATUS.md']=sha(ROOT/'docs/STATUS.md')
report['source_hashes']['tools/verify_diagnostic_candidate.py']=sha(ROOT/'tools/verify_diagnostic_candidate.py')
(materials/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
files=[p for p in sorted(output.rglob('*')) if p.is_file()]
(output/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(output))+'\n' for p in files))
print(json.dumps({'output':str(output.relative_to(ROOT)),'upg_sha256':report['upg_sha256'],'upg_bytes':report['upg_bytes'],'rootfs_metadata_preserved':True,'unchanged_components':[0,1,2],'local_model_free_bytes':remaining,'ready_to_flash':False},indent=2))
