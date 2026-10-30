"""Run pinned unmodified ESP-IDF CCMP source through parameter-recording AES stubs."""
from pathlib import Path
import argparse,hashlib,json,subprocess
from Crypto.Cipher import AES
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/espressif-ccmp-boundary';OUT.mkdir(parents=True,exist_ok=True)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--idf-root',type=Path,required=True);p.add_argument('--host-cc',default='gcc');args=p.parse_args()
    original=args.idf_root/'components/wpa_supplicant/src/crypto/ccmp.c';raw=original.read_bytes();digest=hashlib.sha256(raw).hexdigest();assert digest=='01296aa4c5b571fb003949b6da84d233b4c88b1b0c7beb2a896e860a6a680222'
    source=OUT/'ccmp.upstream.c';source.write_bytes(raw);include=OUT/'include';include.mkdir(exist_ok=True)
    for name in ('utils/includes.h','utils/common.h','common/ieee802_11_defs.h','crypto/aes.h','crypto/aes_wrap.h'):
        f=include/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('/* Test definitions are force-included from the maintained boundary shim. */\n')
    B=ROOT/'work/external-tls-probe/bearssl-0.6';hostlib=ROOT/'work/repository-config-tools/bearssl-host/libbearssl.a';armlib=ROOT/'work/external-tls-probe/arm-build/libbearssl.a'
    assert hashlib.sha256((ROOT/'work/bearssl-0.6.tar.gz').read_bytes()).hexdigest()=='6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14'
    sources=[str(source),'tools/fixtures/espressif_ccmp_boundary.c','runtime/platform/espnow/xnow_ccmp.c','runtime/platform/espnow/xnow_wire.c'];flags=['-std=c99','-Wall','-Wextra','-Werror','-DCONFIG_IEEE80211W','-DESPRESSIF_USE','-I'+str(include),'-I'+str(B/'inc'),'-include',str(ROOT/'tools/fixtures/espressif_ccmp_boundary.h')]
    host=OUT/'boundary.host';hostobj=OUT/'upstream.host.o'
    # Upstream PV1 helper intentionally leaves keyid unused; relax only its TU.
    subprocess.run([args.host_cc,*flags,'-Wno-unused-parameter','-fsanitize=address,undefined','-g','-c',str(source),'-o',str(hostobj)],cwd=ROOT,check=True)
    subprocess.run([args.host_cc,*flags,'-fsanitize=address,undefined','-g',str(hostobj),*sources[1:],str(hostlib),'-o',str(host)],cwd=ROOT,check=True)
    L=ROOT/'work/arm-signal-tests/lib';arm=OUT/'boundary.arm';armobj=OUT/'upstream.arm.o';armflags=['-Os','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector']
    for name,expected in [('libc.so.6','5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812'),('ld-linux.so.3','2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de')]:assert hashlib.sha256((L/name).read_bytes()).hexdigest()==expected
    subprocess.run(['arm-linux-gnueabi-gcc',*flags,*armflags,'-Wno-unused-parameter','-c',str(source),'-o',str(armobj)],cwd=ROOT,check=True)
    subprocess.run(['arm-linux-gnueabi-gcc',*flags,*armflags,'-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',str(armobj),*sources[1:],'runtime/store/start.c','runtime/store/start.S',str(armlib),str(L/'libc.so.6'),str(L/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
    runs=[]
    for target,command in [('host',[str(host)]),('arm926',['qemu-arm','-cpu','arm926',str(L/'ld-linux.so.3'),'--library-path',str(L),str(arm)])]:
        r=subprocess.run(command,capture_output=True,text=True,timeout=30,check=True);lines=r.stdout.splitlines();sealed=bytes.fromhex(next(s[7:] for s in lines if s.startswith('NATIVE ')));pn=0x010203040506;aad=sealed[:2]+sealed[4:22]+bytes(2);nonce_tail=sealed[10:16]+pn.to_bytes(6,'big');results={}
        for priority in (0,16):
            cipher=AES.new(bytes(16),AES.MODE_CCM,nonce=bytes([priority])+nonce_tail,mac_len=8);cipher.update(aad)
            try:plain=cipher.decrypt_and_verify(sealed[32:-8],sealed[-8:]);results[str(priority)]=True;assert plain==bytes.fromhex('7f18fe3401020304dd0518fe340401')
            except ValueError:results[str(priority)]=False
        assert results=={'0':False,'16':True};runs.append({'target':target,'upstream_calls':[s for s in lines if s.startswith('CALL ')],'native_frame_nonce_profiles_authenticate':results,'native_frame_sha256':hashlib.sha256(sealed).hexdigest()})
    report={'passed':True,'host_compiler':subprocess.check_output([args.host_cc,'--version'],text=True).splitlines()[0],'idf_source_sha256':digest,'source_url':'https://github.com/espressif/esp-idf/blob/v5.5.1/components/wpa_supplicant/src/crypto/ccmp.c','unmodified_upstream_translation_unit':True,'aes_callback_stub_records_only':True,'native_crypto_independently_verified':True,'runs':runs,'parameter_discrepancy_confirmed':True,'espnow_hardware_wire_profile_proven':False,'mic_verification_must_not_be_disabled':True,'device_accessed':False,'sources':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['tools/fixtures/espressif_ccmp_boundary.c','tools/fixtures/espressif_ccmp_boundary.h','tools/test_espressif_ccmp_boundary.py','runtime/platform/espnow/xnow_ccmp.c']}}
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2))
if __name__=='__main__':main()
