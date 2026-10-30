"""Explicit private-capture validation; no device access and no CI fixture download."""
from pathlib import Path
import hashlib,json,subprocess
from Crypto.Cipher import AES
ROOT=Path(__file__).resolve().parents[1];capture=ROOT/'work/autonomous-espnow-test/live/rx01';OUT=ROOT/'work/physical-ccmp-profile';OUT.mkdir(exist_ok=True)
line=next(x for x in (capture/'journal.txt').read_text().splitlines() if x.startswith('RAW_ACTION '));frame=bytes.fromhex(dict(p.split('=',1) for p in line.split()[1:])['hex'])
pmk=(capture/'pmk.private.bin').read_bytes();lmk=(capture/'lmk.private.bin').read_bytes();payload=(capture/'expected-payload.bin').read_bytes();wire_key=AES.new(pmk,AES.MODE_ECB).encrypt(lmk)
header='/* Private local test capture, excluded from source control. */\n'
for name,data in [('test_pmk',pmk),('test_lmk',lmk),('expected_wire_key',wire_key),('captured',frame),('expected_payload',payload)]:header+='static const unsigned char '+name+'[]={'+','.join(map(str,data))+'};\n'
(OUT/'physical_vector.private.h').write_text(header)
sources=['tools/fixtures/physical_ccmp_profile.c','runtime/platform/espnow/xnow_ccmp.c','runtime/platform/espnow/xnow_wire.c']
bear=ROOT/'work/external-tls-probe/bearssl-0.6';lib=ROOT/'work/arm-signal-tests/lib';flags=['-std=c99','-Wall','-Wextra','-Werror','-I'+str(OUT),'-I'+str(bear/'inc')]
host=OUT/'profile.host';subprocess.run(['gcc',*flags,'-fsanitize=address,undefined','-g',*sources,str(ROOT/'work/repository-config-tools/bearssl-host/libbearssl.a'),'-o',str(host)],cwd=ROOT,check=True)
a=subprocess.run([str(host)],capture_output=True,text=True,check=True,timeout=15)
arm=OUT/'profile.arm';subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-Os','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*sources,'runtime/store/start.c','runtime/store/start.S',str(ROOT/'work/external-tls-probe/arm-build/libbearssl.a'),str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
b=subprocess.run(['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(arm)],capture_output=True,text=True,check=True,timeout=15)
report={'passed':True,'physical_capture_sha256':hashlib.sha256(frame).hexdigest(),'payload_bytes':len(payload),'nonce_prefix':0,'legacy_subtype_aad_mask':True,'wire_key_derivation':'AES-128-ECB(PMK, API LMK)','key_id':3,'host_asan_ubsan':a.stdout,'arm926_stock_libc':b.stdout,'new_live_rf_test_performed':False,'keys_disclosed':False,'scope':'One captured physical IDF5.5.1 S3 frame, native codec only; encrypted endpoint integration and reverse RF pending','source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'runtime/platform/espnow/xnow_ccmp.h','tools/test_physical_ccmp_profile.py']}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'},indent=2))
