"""PC-only actual ARMv5/stock-libc renderer and touch fixture."""
from qqmusic_font_config import FONT_BYTES,FONT_SHA256,FONT_NAME
import argparse,hashlib,json,struct,subprocess,zlib
import qrcode,zxingcpp
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-directory');args=parser.parse_args()
work=ROOT/'work/qqmusic-ui-native';work.mkdir(exist_ok=True)
(work/'report.json').unlink(missing_ok=True)
frames=work/'frames';frames.mkdir(exist_ok=True)
def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
fixture=qrcode.QRCode(version=3,error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=1,border=0)
fixture.add_data('walkman-qq-synthetic');fixture.make(fit=False);matrix=fixture.get_matrix();assert len(matrix)==29
qr_rows=bytearray()
for y in range(87):qr_rows.append(0);qr_rows.extend(0 if matrix[y//3][x//3] else 255 for x in range(87))
qr=work/'synthetic-qr.png';qr.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',87,87,8,0,0,0,0))+chunk(b'IDAT',zlib.compress(qr_rows))+chunk(b'IEND',b''))
font=ROOT/'work/qqmusic-font/QQMusicUI.otf'
assert hashlib.sha256(font.read_bytes()).hexdigest()==FONT_SHA256
lib=ROOT/'work/arm-signal-tests/lib';mathlib=ROOT/'work/qqmusic-codec/libm.so.6'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():
 assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==digest
modules=('session','protocol','json','credential','catalog','cgi','cookie','http','response','login','app','resource','export','ui')
core=['runtime/apps/qqmusic/qqmusic_'+name+'.c' for name in modules]+['runtime/apps/qqmusic/qqmusic_image.c','runtime/store/https_url.c','runtime/native/sha256.c','tools/fixtures/qqmusic_ui.c']
common=['-std=c99','-Wall','-Wextra','-Werror','-isystem','third_party/qqmusic-stb']
arm=work/'ui-tests.arm'
subprocess.run(['arm-linux-gnueabi-gcc',*common,'-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*core,'runtime/store/stock_tls_compat.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),str(mathlib),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)+':'+str(mathlib.parent),str(arm),str(font),str(frames),str(qr)],cwd=ROOT,check=True,timeout=60)
host=work/'ui-tests.sanitized'
subprocess.run(['gcc-12',*common,'-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer',*core,'-lm','-o',str(host)],cwd=ROOT,check=True)
hostframes=work/'host-frames';hostframes.mkdir(exist_ok=True)
subprocess.run([str(host),str(font),str(hostframes),str(qr)],cwd=ROOT,check=True,timeout=60)
destination=Path(args.output_directory) if args.output_directory else ROOT/'work/previews/qqmusic-native-r2';destination.mkdir(parents=True,exist_ok=True)
for page in (0,1,2,3):
 for dark in (0,1):
  raw=(frames/f'page-{page}-{dark}.rgb565').read_bytes();pixels=struct.unpack('<103680H',raw);rows=bytearray()
  for y in range(432):
   rows.append(0)
   for value in pixels[y*240:(y+1)*240]:rows.extend((((value>>11)&31)*255//31,((value>>5)&63)*255//63,(value&31)*255//31))
  png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')
  (destination/f'page-{page}-{dark}.png').write_bytes(png)
for name in ('qr-live-0','qr-live-1','qr-expired','qr-clock-regressed','qr-cancelled','qr-authorized','clock-error-0','clock-error-1','cert-date-error-0','cert-date-error-1','clock-skew-0','clock-skew-1','import-active-0','import-active-1','import-active-2','import-active-3'):
 raw=(frames/(name+'.rgb565')).read_bytes();pixels=struct.unpack('<103680H',raw);rgb=bytearray()
 for value in pixels:rgb.extend((((value>>11)&31)*255//31,((value>>5)&63)*255//63,(value&31)*255//31))
 decoded=zxingcpp.read_barcode(memoryview(rgb).cast('B',shape=[432,240,3]))
 if name.startswith('qr-live'):assert decoded is not None and decoded.text=='walkman-qq-synthetic'
 else:assert decoded is None,name
 rows=b''.join(b'\0'+rgb[y*720:(y+1)*720] for y in range(432))
 png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')
 (destination/(name+'.png')).write_bytes(png)
report={'scope':'native_c_armv5_stock_abi_ui','synthetic_data':True,'real_account_tested':False,'device_tested':False,
 'frames_rendered':32,'dimensions':[240,432],'touch_checks_passed':True,'host_sanitizers_passed':True,'explicit_device_date_and_certificate_date_screens':True,
 'synthetic_qr_decoded_from_actual_arm_frames':True,'stale_qr_hidden':True,
 'player_or_system_partition_written':False,'arm_sha256':hashlib.sha256(arm.read_bytes()).hexdigest(),
 'limits':['QR payload is synthetic, not a live login code.','Transport loop and device execution are not tested.','All fixtures execute on the PC; no installation or player file writes.']}
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
