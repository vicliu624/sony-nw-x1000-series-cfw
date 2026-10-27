"""Audit complete delivery inventory and execute the native market validators."""
from pathlib import Path,PurePosixPath
import hashlib,io,json,subprocess,sys,tarfile,zipfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
out=Path(sys.argv[1]).resolve();upload=out/'upload'
def digest(b):return hashlib.sha256(b).hexdigest()
checksums={}
for line in (upload/'SHA256SUMS').read_text().splitlines():
 sha,name=line.split('  ',1)
 if PurePosixPath(name).name!=name or name in checksums:raise ValueError('Unsafe/duplicate checksum entry')
 assert digest((upload/name).read_bytes())==sha,name;checksums[name]=sha
assert set(checksums)=={p.name for p in upload.iterdir() if p.is_file() and p.name!='SHA256SUMS'}
report=json.loads((upload/'release-manifest.json').read_text());policy=json.loads((ROOT/'config/release.json').read_text())
assert sorted(x['id'] for x in report['apps'])==policy['apps']
listing=(upload/'catalog.tsv').read_bytes();assert digest(listing)==report['catalog_sha256']
with tarfile.open(ROOT/'work/upg-jp/verified-3.bin',mode='r:gz') as stock:
 sonames={Path(m.name).name for m in stock if m.name.startswith(('./lib/','./usr/lib/'))}
assert listing.startswith(b'HBSTORE2\n') and len(listing.splitlines())==len(policy['apps'])+1
for row in listing.decode('ascii').splitlines()[1:]:
 ident,version,base,mbytes,msha,ibytes,isha,prefix=row.split('\t')
 get=lambda path:(upload/(prefix+path.encode('ascii').hex())).read_bytes()
 meta=get('app.ini');index=get('files.sha256')
 assert len(meta)==int(mbytes) and digest(meta)==msha and len(index)==int(ibytes) and digest(index)==isha
 values=dict(line.split('=',1) for line in meta.decode('ascii').splitlines());assert values['id']==ident and values['version']==version and values['target']=='sony-nw-x1000-jp'
 elf=ELFFile(io.BytesIO(get('app')));assert elf['e_machine']=='EM_ARM'
 dynamic=elf.get_section_by_name('.dynamic')
 if dynamic:assert all(tag.needed in sonames for tag in dynamic.iter_tags() if tag.entry.d_tag=='DT_NEEDED'),ident
 paths=set()
 for line in index.decode('ascii').splitlines()[1:]:
  sha,size,path=line.split(' ');parts=PurePosixPath(path)
  assert not parts.is_absolute() and '..' not in parts.parts and path not in paths
  assert not path.endswith(('.so','.pem','.key','.gb','.gbc','.gba')) and 'server-key' not in path
  value=get(path);assert len(value)==int(size) and digest(value)==sha;paths.add(path)
 assert {'app','app.ini'}<=paths
 with zipfile.ZipFile(upload/(ident+'-'+version+'.zip')) as z:
  assert z.testzip() is None
  for path in paths|{'files.sha256'}:assert z.read('HOMEBREW/apps/'+ident+'/'+path)==get(path)
sys.path.insert(0,str(ROOT/'scripts'));from upg import unpack
with zipfile.ZipFile(upload/('NW-X1000-'+report['version']+'-firmware.zip')) as z:firmware=z.read('NW_WM_FW.UPG')
assert digest(firmware)==report['firmware']['firmware_sha256'];_,parts=unpack(firmware,require_stock=False)
for i in range(3):assert parts[i]==(ROOT/f'work/upg-jp/verified-{i}.bin').read_bytes()
workspace=ROOT/'work/ci/release-verification';workspace.mkdir(parents=True,exist_ok=True)
sources=['runtime/store/'+n+'.c' for n in ('remote_catalog','download_plan','inventory','package','cleanup_plan','https_url')]+['runtime/native/sha256.c','tools/verify_release_catalog.c']
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',*sources,'-o',str(workspace/'verify-catalog')],cwd=ROOT,check=True)
subprocess.run([str(workspace/'verify-catalog'),str(upload)],check=True)
crypto=ROOT/'work/external-tls-probe/bearssl-0.6'
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-I'+str(crypto/'inc'),'runtime/store/repository.c','runtime/store/https_url.c','runtime/native/sha256.c','tools/inspect_repository_config.c',str(ROOT/'work/repository-config-tools/bearssl-host/libbearssl.a'),'-o',str(workspace/'verify-repository')],cwd=ROOT,check=True)
subprocess.run([str(workspace/'verify-repository'),str(out/'player/HOMEBREW/repository')],check=True)
result={'passed':True,'apps':len(report['apps']),'release_assets_verified':len(checksums),'original_installer_kernel_initrd_preserved':True,'actual_market_parser_and_download_plan_used':True,'private_terminal_key_present':False,'device_accessed':False}
(out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
