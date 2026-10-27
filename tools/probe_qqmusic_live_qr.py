"""Live public QR fetch with native ARM TLS. No account login or cookie import."""
from pathlib import Path
import argparse,hashlib,json,socket,ssl,struct,subprocess,tempfile
import zxingcpp
parser=argparse.ArgumentParser();parser.add_argument('--qimei',action='store_true');options=parser.parse_args()
ROOT=Path(__file__).resolve().parents[1];base=ROOT/('work/qqmusic-live-qimei' if options.qimei else 'work/qqmusic-live-qr');base.mkdir(exist_ok=True);work=Path(tempfile.mkdtemp(prefix='live-',dir=base))
host='api.tencentmusic.com' if options.qimei else 'ssl.ptlogin2.qq.com'
context=ssl.create_default_context()
with socket.create_connection((host,443),timeout=15) as raw:
 with context.wrap_socket(raw,server_hostname=host) as connection:
  chain=connection._sslobj.get_verified_chain();root=ssl.PEM_cert_to_DER_cert(chain[-1].public_bytes());root_path=work/'verified-root.der';root_path.write_bytes(root)
session_root_path=work/'session-root.der'
if options.qimei:
 with socket.create_connection(('u.y.qq.com',443),timeout=15) as raw:
  with context.wrap_socket(raw,server_hostname='u.y.qq.com') as connection:
   chain=connection._sslobj.get_verified_chain();session_root=ssl.PEM_cert_to_DER_cert(chain[-1].public_bytes());session_root_path.write_bytes(session_root)
lib=ROOT/'work/arm-signal-tests/lib';resolver=ROOT/'work/stock-resolver-probe';crypto=ROOT/'work/external-tls-probe';math=ROOT/'work/qqmusic-codec/libm.so.6'
sources=['runtime/apps/qqmusic/qqmusic_'+n+'.c' for n in ('session','protocol','cookie','http','response','tls','network','json','credential','cgi','resource','image')]+['runtime/store/'+n+'.c' for n in ('https_url','resolver','connect_step','socket_step','tls_socket_step','deadline','tls_platform','stock_tls_compat','stock_fs_bridge','stock_stat64','start')]+['runtime/store/start.S','runtime/native/sha256.c','tools/fixtures/qqmusic_live_qr.c']
if options.qimei:sources+=['runtime/apps/qqmusic/qqmusic_qimei.c','runtime/apps/qqmusic/qqmusic_identity.c']
app=work/'live-qr.arm'
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-DHB_STORE_LIBC_CLOCK','-DHB_STORE_SONY_LIBC',*(['-DQQ_LIVE_QIMEI'] if options.qimei else []),'-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(resolver),'-I'+str(resolver),'-I'+str(crypto/'bearssl-0.6/inc'),'-isystem','third_party/qqmusic-stb',*sources,str(crypto/'arm-build/libbearssl.a'),str(resolver/'libcares.so.2'),str(resolver/'librt.so.1'),str(math),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
image=work/'qr.png';pixels=session_root_path if options.qimei else work/'qr.rgb565'
process=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(resolver)+':'+str(math.parent),str(app),str(root_path),str(image),str(pixels)],cwd=ROOT,capture_output=True,timeout=35)
output=process.stdout.splitlines();summary=json.loads(output[0])
if options.qimei and len(output)>1:summary['schema']=json.loads(output[1])
if options.qimei and len(output)>2:summary['session']=json.loads(output[2])
if not options.qimei:summary['independently_decoded']=False
if not options.qimei and summary['valid_png']:
 rgb=bytearray()
 for v in struct.unpack('<%dH'%(summary['width']*summary['height']),pixels.read_bytes()):rgb.extend((((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31))
 decoded=zxingcpp.read_barcode(memoryview(rgb).cast('B',shape=[summary['height'],summary['width'],3]));summary['independently_decoded']=decoded is not None
report={'scope':'live_public_qr_fetch_only','real_qq_service_contacted':True,'device_tested':False,'account_authenticated':False,'root_from_os_verified_chain_sha256':hashlib.sha256(root).hexdigest(),'native':summary,'exit_code':process.returncode,'arm_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},'limits':['Public QR only; no polling/authorization/account/favorites or MGG fetched.','No official client process, cookies or existing device/session imported.','Native ARM runs on PC with current verified time; not Sony Wi-Fi qualification.']}
if options.qimei:
 report['scope']='live_native_qimei_and_anonymous_session'
 report['session_root_from_os_verified_chain_sha256']=hashlib.sha256(session_root).hexdigest()
 report['limits']=['One fresh app-owned installation ID; truthful Sony/Linux descriptor, not a generated Android phone profile.','No QR requested, login, account, favorites or media access.','Native ARM runs on PC; no player writes or hardware validation.']
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');(base/'latest.json').write_text(json.dumps({'report':str((work/'report.json').relative_to(ROOT))},indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
