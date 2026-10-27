"""PC adapter for the real ARM program, not a Windows QQ Music implementation.

prepare only verifies TLS trust chains and builds; it never requests a QR.
run keeps the same native process alive; stdin accepts `tap X Y` / `stop`.
Only native code handles QQ, identity, cookies, account and catalog parsing.
"""
from qqmusic_font_config import FONT_BYTES,FONT_SHA256,FONT_NAME
import argparse,concurrent.futures,hashlib,json,secrets,socket,ssl,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'work/qqmusic-live-session'
parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
sub.add_parser('prepare');run=sub.add_parser('run');run.add_argument('directory')
resume=sub.add_parser('resume');resume.add_argument('directory')
options=parser.parse_args()
def root_for(host):
 context=ssl.create_default_context()
 with socket.create_connection((host,443),timeout=15) as raw:
  with context.wrap_socket(raw,server_hostname=host) as tls:
   chain=tls._sslobj.get_verified_chain()
   return host,ssl.PEM_cert_to_DER_cert(chain[-1].public_bytes())
if options.action=='prepare':
 BASE.mkdir(exist_ok=True);directory=Path(tempfile.mkdtemp(prefix='session-',dir=BASE))
 hosts=('api.tencentmusic.com','u.y.qq.com','ssl.ptlogin2.qq.com','ssl.ptlogin2.graph.qq.com','graph.qq.com','y.qq.com','y.gtimg.cn')
 roots={};host_roots={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  for host,root in pool.map(root_for,hosts):
   digest=hashlib.sha256(root).hexdigest();roots[digest]=root;host_roots[host]=digest
 assert 1<=len(roots)<=8
 certificates=[]
 for digest,root in roots.items():
  name=f'ca-{digest}.der';(directory/name).write_bytes(root);certificates.append(name)
 # App-owned installation identifiers, never copied from official clients or
 # another project. Preserve this build profile for this installation's run.
 guid=secrets.token_hex(16);aid=secrets.token_hex(8)
 payload={'androidId':aid,'platformId':1,'appKey':'0AND0HD6FE4HY80F','appVersion':'20.9.0.8',
  'beaconIdSrc':'','brand':'Sony','channelId':'10003505','cid':'','imei':'','imsi':'','mac':'',
  'model':'NW-X1060','networkType':'wifi','oaid':'','osVersion':'Linux (Sony NW-X1060)',
  'qimei':'','qimei36':'','sdkVersion':'1.2.13.6','targetSdkVersion':'','audit':'',
  'userId':'{}','packageId':'com.tencent.qqmusic','deviceType':'Walkman','sdkName':'','reserved':'{}'}
 profile={'source':'/dev/mock-user','resources':'/contents/HOMEBREW/apps/qqmusic/resources',
  'guid':guid,'ca_files':certificates,'qimei_payload':payload,
  'comm':{'ct':'11','cv':'20090008','tmeLoginType':'2','QIMEI36':'','OpenUDID':guid,'udid':guid,
          'aid':aid,'phonetype':'Sony NW-X1060','os_ver':'Linux','chid':'10003505','tmeAppID':'qqmusic'}}
 profile_path=directory/'installation.private.json';profile_path.write_text(json.dumps(profile),encoding='utf8');profile_path.chmod(0o600)
 (directory/'trust.json').write_text(json.dumps(host_roots,indent=2)+'\n')
if options.action in ('prepare','resume'):
 if options.action=='resume':
  directory=Path(options.directory).resolve();assert directory.is_relative_to(BASE.resolve()) and directory.is_dir()
  profile_path=directory/'installation.private.json';profile=json.loads(profile_path.read_text())
  host_roots=json.loads((directory/'trust.json').read_text()) if (directory/'trust.json').exists() else {name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in profile['ca_files']}
  if 'y.gtimg.cn' not in host_roots:
   host,root=root_for('y.gtimg.cn');digest=hashlib.sha256(root).hexdigest();name=f'ca-{digest}.der'
   if name not in profile['ca_files']:(directory/name).write_bytes(root);profile['ca_files'].append(name)
   host_roots[host]=digest;(directory/'trust.json').write_text(json.dumps(host_roots,indent=2)+'\n')
  profile['source']='/dev/mock-user';profile_path.write_text(json.dumps(profile),encoding='utf8');profile_path.chmod(0o600)
 native=directory/'native'
 if native.exists():native=directory/('native-rebuild-'+secrets.token_hex(4))
 subprocess.run([sys.executable,'tools/build_qqmusic_native.py','--profile',str(profile_path),'--output',str(native),'--live-session'],cwd=ROOT,check=True)
 manifest={'kind':'PC panel adapter for actual ARM app','directory':str(directory.relative_to(ROOT)),
  'binary':str((native/'app').relative_to(directory)),'binary_sha256':hashlib.sha256((native/'app').read_bytes()).hexdigest(),
  'trust_roots':host_roots,'account_accessed_during_prepare':False,'qr_requested_during_prepare':False,'device_accessed_during_prepare':False,
  'imports_bound':True,'physical_storage_simulated':True,'limits':['Actual native account/catalog/worker/download/codec/journal pipeline; physical display, touch and mount observations are PC fixtures.','Writes stay in this private PC workspace; no player access or hardware qualification.','Not a device installation package.']}
 (directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
else:
 directory=Path(options.directory).resolve();assert directory.is_relative_to(BASE.resolve()) and directory.is_dir()
 manifest=json.loads((directory/'manifest.json').read_text());app=(directory/manifest['binary']).resolve();assert app.is_relative_to(directory)
 assert hashlib.sha256(app.read_bytes()).hexdigest()==manifest['binary_sha256']
 build=json.loads((app.parent/'build.json').read_text())
 for name,digest in (build['sources']|build.get('included_sources',{})).items():
  source=(ROOT/name).resolve();assert source.is_relative_to(ROOT)
  if hashlib.sha256(source.read_bytes()).hexdigest()!=digest:raise RuntimeError('Source changed: resume this installation build before running; no QR requested')
 font=ROOT/'work/qqmusic-font/QQMusicUI.otf'
 assert hashlib.sha256(font.read_bytes()).hexdigest()==FONT_SHA256
 lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';math=ROOT/'work/qqmusic-codec'
 process=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(resolver)+':'+str(math),str(app),'--host-session',str(directory),str(font)],cwd=ROOT)
 sys.exit(process.returncode)
