"""Collect reviewed external X1000 apps. No updater, launcher, ROM, account or player I/O."""
from pathlib import Path
import hashlib,json,shutil,zipfile,subprocess,io,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1];project=(ROOT/'VERSION').read_text().strip();version=(ROOT/'config/app-collection/VERSION').read_text().strip();dist=ROOT/'dist'/project
base=dist/'first-device-test-candidate8/02_PLAYER_FILES/HOMEBREW/apps'
items=[
 ('dictionary',dist/'dictionary/0.1.0-alpha.1/PLAYER/HOMEBREW/apps/dictionary','Offline English-Chinese dictionary with data, font and multi-tap input'),
 ('tamagotchi-id',dist/'emulator-apps/0.1.0-alpha.3/PLAYER/HOMEBREW/apps/tamagotchi-id','Color iD emulator, 128x128 viewport and virtual buttons; compatible ROM required'),
 ('gbc',dist/'emulator-apps/0.1.0-alpha.3/PLAYER/HOMEBREW/apps/gbc','GB/GBC emulator with 160x144 viewport and virtual controls; ROM required'),
 ('device-info',dist/'apps/device-info/HOMEBREW/apps/device-info','Read-only CPU, memory, kernel, mounted capacity and MTD information'),
 ('store',base/'store','Store requiring explicit repository configuration; SETUP NEEDED may be expected'),
 ('key-check',ROOT/'work/key-check-review/key-check','Read-only key event observer: node/type/code/value'),
 ('diagnostics',base/'diagnostics','Legacy Device Check: basic proc, memory and partition observations'),
 ('graphics-demo',base/'graphics-demo','Graphics example: tap to change color; bottom button returns'),
]
out=dist/'app-packs'/version;assert not out.exists(),'Preserve existing collection';out.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# All DT_NEEDED must already be in the unmodified stock firmware; do not bundle Sony libraries.
sonames=set()
with tarfile.open(ROOT/'work/upg-jp/verified-3.bin','r:gz')as archive:
 for m in archive:
  if m.name.startswith(('./lib/','./usr/lib/')):sonames.add(Path(m.name).name)
rows=[]
for ident,source,description in items:
 assert source.is_dir() and ident!='qqmusic'
 for p in source.rglob('*'):assert not p.is_symlink(),p
 metadata={}
 for line in (source/'app.ini').read_text().splitlines():
  k,v=line.split('=',1);assert k not in metadata;metadata[k]=v
 assert metadata['id']==ident and metadata['target']=='sony-nw-x1000-jp'and metadata['exec']=='app'
 app=source/'app';assert app.stat().st_size==int(metadata['bytes']) and sha(app)==metadata['sha256']
 elf=ELFFile(io.BytesIO(app.read_bytes()));assert elf.header['e_machine']=='EM_ARM'
 dynamic=elf.get_section_by_name('.dynamic');needed=[t.needed for t in dynamic.iter_tags()if t.entry.d_tag=='DT_NEEDED']if dynamic else[]
 assert set(needed)<=sonames,(ident,needed)
 dest=out/'HOMEBREW/apps'/ident;shutil.copytree(source,dest)
 # Standardize legacy two-file apps to the same inventory without changing ELF/manifest.
 files=sorted(p for p in dest.rglob('*')if p.is_file()and p.name!='files.sha256')
 expected='HBFILES1\n'+''.join(f'{sha(p)} {p.stat().st_size} {p.relative_to(dest).as_posix()}\n'for p in files)
 if (dest/'files.sha256').exists():assert (dest/'files.sha256').read_text()==expected,ident
 (dest/'files.sha256').write_text(expected)
 rows.append({'id':ident,'name':metadata['name'],'version':metadata['version'],'description':description,'bytes':app.stat().st_size,'sha256':sha(app),'source':str(source.relative_to(ROOT)),'needed_from_stock':needed})
assert len(rows)==8 and len({r['id']for r in rows})==8
for ident in ['gbc','tamagotchi-id']:(out/'HOMEBREW/data'/ident/'roms').mkdir(parents=True)
# Keep copied player files separate from PC-only licensing, review and source materials.
shutil.copytree(dist/'dictionary/0.1.0-alpha.1/LICENSES',out/'LICENSES/dictionary')
(out/'LICENSES/emulators').mkdir(parents=True)
for src,name in [('third_party/gnuboy/COPYING','gnuboy-GPL2.txt'),('third_party/gnuboy/PROVENANCE.md','gnuboy-PROVENANCE.md'),('third_party/tama-id/core/LICENSE','tama-GPL3.txt'),('third_party/tama-id/core/PROVENANCE.md','tama-core-PROVENANCE.md'),('third_party/tama-id/PROVENANCE.md','tama-adapter-PROVENANCE.md')]:shutil.copyfile(ROOT/src,out/'LICENSES/emulators'/name)
(out/'LICENSES/store').mkdir(parents=True)
shutil.copyfile(ROOT/'work/external-tls-probe/bearssl-0.6/LICENSE.txt',out/'LICENSES/store/BearSSL-LICENSE.txt')
# Preserve the corresponding sources already shipped with the two emulator/dictionary candidates.
shutil.copytree(dist/'dictionary/0.1.0-alpha.1/SOURCE',out/'SOURCE/dictionary')
shutil.copytree(dist/'emulator-apps/0.1.0-alpha.3/SOURCE',out/'SOURCE/emulators')
(out/'SOURCE/diagnostics').mkdir(parents=True)
for name in ['device_info_app.c','device_info_data.c','device_info_data.h','device_info_space.c','key_check.c','diagnostics.c','graphics_demo.c']:
 group='device-info' if name.startswith('device_info_') else {'key_check.c':'key-check','diagnostics.c':'diagnostics','graphics_demo.c':'graphics-demo'}[name]
 shutil.copyfile(ROOT/'runtime/apps'/group/name,out/'SOURCE/diagnostics'/name)
(out/'REVIEW').mkdir()
for source,name in [(dist/'dictionary/0.1.0-alpha.1/REVIEW/tests.json','dictionary-tests.json'),(dist/'emulator-apps/0.1.0-alpha.3/REVIEW/tests.json','emulator-tests.json'),(dist/'apps/device-info/review/tests.json','device-info-tests.json'),(ROOT/'work/key-check-review/build.json','key-check-build.json')]:shutil.copyfile(source,out/'REVIEW'/name)
(out/'DOCS').mkdir()
for name in ['apps/EMULATORS.md','apps/DICTIONARY.md','apps/DEVICE_INFO.md','BUILD.md','apps/FM_RADIO.md']:
 target=out/'DOCS'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'docs'/name,target)
# Build an explicit inventory, including unfinished/non-GUI programs that are intentionally not installed.
manifest={'bundle_version':version,'project_version':project,'target':'Japanese NW-X1050/NW-X1060 Homebrew','apps':rows,'excluded':[{'id':'qqmusic','reason':'Excluded from this collection; no account/cache/cookies/private data'},{'id':'fm-radio','reason':'Separate experimental FM package, outside this collection'},{'id':'hello','reason':'Console development example, not a touch application'}],'launcher_included':False,'firmware_included':False,'ROM_or_save_included':False,'hardware_qualification':'See per-app reports; combined bundle is not hardware-qualified'}
(out/'APP_LIST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
listing='''# X1000 application collection

| Name | Version | Description |
| --- | --- | --- |
'''+''.join(f"| {r['name']} | {r['version']} | {r['description']} |\n" for r in rows)
(out/'APP_LIST.md').write_text(listing)
readme='''# X1000 application collection

This legacy collection packages eight explicitly selected local candidates. It
does not update the launcher, install firmware, remove other apps, or include
QQ account data, ROMs or saves. Preserve all existing data and rollback packages.

Merge only the included HOMEBREW directory into visible storage when deployment
has been explicitly authorized. Keep DOCS, LICENSES, SOURCE, REVIEW and checksums
on the computer. Eject USB before opening the launcher. Supply lawful compatible
ROMs separately; consult each app guide and report for behavior and limitations.

Package/ELF checks are offline evidence, not combined hardware qualification.
'''
(out/'README.md').write_text(readme)
# Verify actual production launcher can discover all eight and validate their ELFs.
lib=ROOT/'work/arm-signal-tests/lib';launcher=dist/'first-device-test-candidate8/02_PLAYER_FILES/HOMEBREW/launcher/app';checks=[]
for command in ['--catalog','--check']:
 result=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(launcher),command,str(out/'HOMEBREW/apps')],capture_output=True,text=True,timeout=30)
 assert result.returncode==0,(command,result.stdout,result.stderr)
 lines=result.stdout.splitlines();assert len(lines)==8 and all(any(line.startswith(r['id']+'\t')or line.startswith(r['id']+' ')for line in lines)for r in rows),(command,lines)
 checks.append({'command':command,'exit':result.returncode,'stdout':result.stdout})
assert not (out/'HOMEBREW/launcher').exists()
for p in (out/'HOMEBREW').rglob('*'):
 if p.is_file():assert '/data/'not in p.as_posix()and 'qqmusic'not in p.as_posix().lower()
(out/'REVIEW/collection-check.json').write_text(json.dumps({'passed':True,'checks':checks,'apps':len(rows),'player_file_count':sum(p.is_file()for p in(out/'HOMEBREW').rglob('*')),'device_written':False,'firmware_created':False},indent=2)+'\n')
(out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n'for p in sorted(out.rglob('*'))if p.is_file()))
z=out.parent/('NW-X1000-app-pack-'+version+'.zip');assert not z.exists()
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,6)as archive:
 for p in sorted(out.rglob('*')):
  if p.is_file():archive.write(p,p.relative_to(out).as_posix())
  elif not any(p.iterdir()):archive.writestr(p.relative_to(out).as_posix()+'/',b'')
with zipfile.ZipFile(z)as archive:
 assert archive.testzip() is None
 for p in out.rglob('*'):
  if p.is_file():assert archive.read(p.relative_to(out).as_posix())==p.read_bytes()
print(json.dumps({'zip':str(z),'bytes':z.stat().st_size,'sha256':sha(z),'apps':[r['name']for r in rows],'launcher_included':False,'device_written':False},ensure_ascii=False,indent=2))

