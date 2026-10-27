"""Build standalone native candidate from explicit non-account profile. PC only."""
from pathlib import Path
import argparse,hashlib,json,subprocess,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--profile',required=True);parser.add_argument('--output',required=True);parser.add_argument('--live-session',action='store_true',help='PC-only front-panel adapter, never a device package');parser.add_argument('--device-full',action='store_true',help='Native main with real workspace guard and full MGG import');parser.add_argument('--public-installation',action='store_true');args=parser.parse_args()
assert not (args.live_session and args.device_full)
def unique(pairs):
 result={}
 for k,v in pairs:
  if k in result:raise ValueError('duplicate profile key')
  result[k]=v
 return result
profile_path=Path(args.profile).resolve();profile=json.loads(profile_path.read_text(),object_pairs_hook=unique)
assert set(profile) in ({'source','resources','comm','guid','ca_files'},{'source','resources','comm','guid','ca_files','qimei_payload'})
assert isinstance(profile['source'],str) and profile['source'].startswith('/dev/') and len(profile['source'])<=512
assert profile['resources']=='/contents/HOMEBREW/apps/qqmusic/resources'
keys={'ct','cv','tmeLoginType','QIMEI36','OpenUDID','udid','aid','phonetype','os_ver','chid','tmeAppID'}
assert isinstance(profile['comm'],dict) and set(profile['comm'])==keys
assert all(isinstance(v,str) and len(v.encode())<=128 and (v or k=='QIMEI36') for k,v in profile['comm'].items())
qimei_payload=profile.get('qimei_payload')
if not profile['comm']['QIMEI36']:assert isinstance(qimei_payload,dict) and qimei_payload
if qimei_payload is not None:assert isinstance(qimei_payload,dict)
qimei_payload=json.dumps(qimei_payload,ensure_ascii=False,separators=(',',':')) if qimei_payload is not None else None
if qimei_payload is not None:assert len(qimei_payload.encode())<=3072
assert profile['comm']['ct']=='11' and profile['comm']['tmeLoginType']=='2'
assert isinstance(profile['guid'],str) and 1<=len(profile['guid'])<=64 and all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in profile['guid'])
comm=json.dumps(profile['comm'],ensure_ascii=False,separators=(',',':'));assert len(comm.encode())<=1024
assert isinstance(profile['ca_files'],list) and 1<=len(profile['ca_files'])<=8
certs=[(profile_path.parent/p).resolve().read_bytes() for p in profile['ca_files']];assert all(1<=len(c)<=8192 for c in certs)
output=Path(args.output).resolve();assert output.is_relative_to(ROOT/'work') and not output.exists();output.mkdir(parents=True)
def literal(s):return '"'+''.join('\\x%02x'%b for b in s.encode())+'"'
header=['/* Generated non-account profile; not hardware qualification. */']
if args.public_installation:
 assert args.device_full
 header.append('#define QQ_PROFILE_GENERATED_IDENTITY 1')
header.append('#define QQ_PROFILE_QIMEI_PAYLOAD '+(literal(qimei_payload) if qimei_payload is not None else '((const char *)0)'))
for key,value in [('SOURCE',profile['source']),('RESOURCES',profile['resources']),('COMM',comm),('GUID',profile['guid'])]:header.append('#define QQ_PROFILE_'+key+' '+literal(value))
header.append('#define QQ_PROFILE_CA_COUNT '+str(len(certs)))
for i,c in enumerate(certs):header.append('static const unsigned char ca_%d[]={%s};'%(i,','.join(str(b) for b in c)))
header+=['static const unsigned char *const qq_profile_ca[]={'+','.join('ca_%d'%i for i in range(len(certs)))+'};','static const size_t qq_profile_ca_size[]={'+','.join(str(len(c)) for c in certs)+'};']
(output/'qqmusic_profile.h').write_text('\n'.join(header)+'\n')
lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe';math=ROOT/'work/qqmusic-codec/libm.so.6'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
modules=('session','protocol','json','credential','catalog','cgi','cookie','http','response','login','app','resource','export','ui','image','runtime','identity','qimei','tls','network','loop','devices','entry','program','asset','volume','storage','main')
sources=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in modules]
sources+=['runtime/store/'+n+'.c' for n in ('https_url','resolver','connect_step','socket_step','tls_socket_step','deadline','tls_platform','stock_tls_compat','stock_fs_bridge','stock_stat64','start')]
sources+=['runtime/store/start.S','runtime/native/sha256.c','runtime/native/linux_devices.c','runtime/native/frontend.c','runtime/native/linux_signals.c','runtime/native/syscalls.S']
if args.live_session:
 sources.remove('runtime/apps/qqmusic/qqmusic_main.c');sources.remove('runtime/native/linux_signals.c')
 sources+=['tools/fixtures/qqmusic_live_session.c','runtime/native/linux_signals_posix.c']
app=output/'app';version=(ROOT/'VERSION').read_text().strip()
if args.live_session or args.device_full:
 mode='device-app' if args.device_full else 'live-session'
 subprocess.run([sys.executable,'tools/build_qqmusic_codec.py','--'+mode,str(output)],cwd=ROOT,check=True)
 codec_build=json.loads((ROOT/('work/qqmusic-codec/build-'+mode+'.json')).read_text())
 sources=list(codec_build['source_hashes'])
 shutil.copyfile(ROOT/('work/qqmusic-codec/'+mode+'.arm'),app)
else:
 subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-DHB_STORE_LIBC_CLOCK','-DHB_STORE_SONY_LIBC','-DHB_BUILD_VERSION="'+version+'"','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--disable-new-dtags,-rpath,$ORIGIN/lib','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(resolver),'-I'+str(resolver),'-I'+str(output),'-I'+str(crypto/'bearssl-0.6/inc'),'-isystem','third_party/qqmusic-stb',*sources,str(crypto/'arm-build/libbearssl.a'),str(resolver/'libcares.so.2'),str(resolver/'librt.so.1'),str(math),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
for option,expected in [('--help','X1060 QQ Music'),('--version',version)]:
 result=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(resolver)+':'+str(math.parent),str(app),option],cwd=ROOT,capture_output=True,text=True,check=True,timeout=10);assert expected in result.stdout
 assert '/dev/' not in result.stderr and '/proc/self/mounts' not in result.stderr
result=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(resolver)+':'+str(math.parent),str(app)],cwd=ROOT,capture_output=True,text=True,timeout=10);assert result.returncode==64
report={'built':True,'hardware_qualified':False,'ready_to_deploy':False,'imports_enabled':False,'standalone_help_and_version_passed':True,'app_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'ca_sha256':[hashlib.sha256(c).hexdigest() for c in certs],'profile_sha256':hashlib.sha256((output/'qqmusic_profile.h').read_bytes()).hexdigest(),'sources':{s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in sources},'limits':['Explicit profile is not independent user-volume or service-identity qualification.','No native device execution, installation, download or stock indexing verification.']}
report['host_session_fixture']=args.live_session
if args.live_session:report['imports_enabled']=True
if args.device_full:report['imports_enabled']=True;report['requires_usb_disconnected']=True;report['workspace_lock_is_not_usb_exclusion']=True
if args.live_session:report['included_sources']={'runtime/apps/qqmusic/qqmusic_main.c':hashlib.sha256((ROOT/'runtime/apps/qqmusic/qqmusic_main.c').read_bytes()).hexdigest()}
(output/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('sources','included_sources')},indent=2))

