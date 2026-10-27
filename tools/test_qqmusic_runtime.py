"""Native UI/controller/single-transaction coordinator, synthetic transport."""
from qqmusic_font_config import FONT_BYTES,FONT_SHA256,FONT_NAME
import hashlib,json,struct,subprocess,zlib
from pathlib import Path
import qrcode,zxingcpp
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/qqmusic-runtime';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
lib=ROOT/'work/arm-signal-tests/lib';math=ROOT/'work/qqmusic-codec/libm.so.6'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
font=ROOT/'work/qqmusic-font/QQMusicUI.otf'
qr=qrcode.QRCode(version=3,error_correction=qrcode.constants.ERROR_CORRECT_M,border=0);qr.add_data('walkman-qq-synthetic');qr.make(fit=False);matrix=qr.get_matrix()
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
rows=bytearray()
for y in range(87):rows.append(0);rows.extend(0 if matrix[y//3][x//3] else 255 for x in range(87))
png=work/'qr.png';png.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',87,87,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))
modules=('session','protocol','json','credential','catalog','cgi','cookie','http','response','login','app','resource','export','ui','image','runtime')
core=['runtime/apps/qqmusic/qqmusic_'+name+'.c' for name in modules]+['runtime/store/https_url.c','runtime/native/sha256.c','tools/fixtures/qqmusic_runtime.c']
flags=['-std=c99','-Wall','-Wextra','-Werror','-isystem','third_party/qqmusic-stb']
arm=work/'runtime-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*core,'runtime/store/stock_tls_compat.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S',str(math),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
frame=work/'runtime-qr.rgb565'
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(math.parent),str(arm),str(font),str(png),str(frame)],cwd=ROOT,check=True,timeout=60)
host=work/'runtime-tests.sanitized'
subprocess.run(['gcc-12',*flags,'-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer',*core,'-lm','-o',str(host)],cwd=ROOT,check=True)
subprocess.run([str(host),str(font),str(png),str(work/'host-qr.rgb565')],cwd=ROOT,check=True,timeout=60)
rgb=bytearray()
for value in struct.unpack('<103680H',frame.read_bytes()):rgb.extend((((value>>11)&31)*255//31,((value>>5)&63)*255//63,(value&31)*255//31))
decoded=zxingcpp.read_barcode(memoryview(rgb).cast('B',shape=[432,240,3]));assert decoded and decoded.text=='walkman-qq-synthetic'
report={'passed':True,'scope':'native_runtime_ui_controller_coordinator','synthetic_transport':True,'real_network_tested':False,'device_tested':False,'source_preset_checks':['128 export requests O4 MGG','192 export requests O6 MGG','320 export requests O8 MGG','all request CgiGetEVkey, no M500 or MP3 source fallback'],
 'checks':['touch to QR request and scannable ARM rendered QR','authorization callback and account verification to playlists','favorite songs to selection and authorization','resource transport error retains selection for retry','storage-disabled import refuses success','transport stopped before relogin clears secrets','stale ticket reject','deadline enforced while IO pending','partial start failure cleanup','poll failure cleanup','clock regression cancels IO','closed runtime rejects work'],
 'import_checks':['optional adapter bound explicitly; live replacement refuses','fresh authorization copied before begin returns and runtime clears URL','download progress and confirmed published result rendered','result page persists and continue returns to songs','finished without publication refuses success','review result rendered without success','partial begin failure cancels','touch cancel stops before resource clear','unknown expiry and expired authorization refuse begin','clock before authorization received refuses begin','expiry while downloading cancels','completed download phase can finish local conversion after authorization expiry','clock regression and close cancel before logout','regressing progress fails','premature published state becomes review'],
 'arm_sha256':hashlib.sha256(arm.read_bytes()).hexdigest(),'sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in core+['tools/fixtures/qqmusic_runtime_import.h']+['runtime/apps/qqmusic/qqmusic_'+name+'.h' for name in modules]},
 'limits':['Transport and import backend are synthetic fixtures; binding a backend is not storage or worker qualification.','Native file/network pipeline is separately tested but not yet bound to this scheduler.','No files are published to player storage or stock library.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
