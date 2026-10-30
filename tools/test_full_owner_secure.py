"""Actual managed runtime + durable journals + CCMP; no device/radio access."""
from pathlib import Path
import hashlib,json,subprocess,tempfile
from Crypto.Cipher import AES
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/espnow-full-owner-secure';OUT.mkdir(parents=True,exist_ok=True)
B=ROOT/'work/external-tls-probe/bearssl-0.6';hostlib=ROOT/'work/repository-config-tools/bearssl-host/libbearssl.a';armlib=ROOT/'work/external-tls-probe/arm-build/libbearssl.a'
assert hashlib.sha256((ROOT/'work/bearssl-0.6.tar.gz').read_bytes()).hexdigest()=='6705bba1714961b41a728dfc5debbe348d2966c117649392f8c8139efc83ff14'
namespace='-DXNOW_OWNER_GATE_NAMESPACE="x1000-xnow-full-secure-runtime-test-v1"'
sources=['tools/fixtures/full_owner_secure.c','tools/fixtures/xnow_control_platform.c']+['runtime/platform/espnow/'+n+'.c' for n in ['xnow_owner_runtime','xnow_owner_gate','xnow_handoff_owner','xnow_owner_stream','xnow_owner_commands','xnow_owner_commands_control','xnow_full_control','xnow_session','xnow_manager','xnow_endpoint','xnow_peer','xnow_wire','xnow_full','xnow_endpoint_security','xnow_security','xnow_ccmp','xnow_pn','xnow_pn_file']]+['runtime/native/sha256.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c']
host=OUT/'secure.host';include=['-I',str(B/'inc')]
subprocess.run(['gcc',namespace,'-std=c99','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-g',*include,*sources,str(hostlib),'-o',str(host)],cwd=ROOT,check=True)
LIB=ROOT/'work/arm-signal-tests/lib';arm=OUT/'secure.arm'
for name,digest in {'libc.so.6':'5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812','ld-linux.so.3':'2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de'}.items():assert hashlib.sha256((LIB/name).read_bytes()).hexdigest()==digest
subprocess.run(['arm-linux-gnueabi-gcc',namespace,'-std=c99','-Os','-Wall','-Wextra','-Werror','-DHB_STORE_SONY_LIBC','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3',*include,*sources,'runtime/store/start.c','runtime/store/start.S',str(armlib),str(LIB/'libc.so.6'),str(LIB/'ld-linux.so.3'),'-lgcc','-o',str(arm)],cwd=ROOT,check=True)
rows=[]
for name,command in [('host',[str(host)]),('arm926',['qemu-arm','-cpu','arm926',str(LIB/'ld-linux.so.3'),'--library-path',str(LIB),str(arm)])]:
    with tempfile.TemporaryDirectory(prefix=name+'-',dir=OUT) as temporary:
        p=Path(temporary);data=p/'data';missing=p/'missing';data.mkdir();missing.mkdir()
        r=subprocess.run([*command,str(data),str(missing)],capture_output=True,text=True,timeout=60)
        if r.returncode:print(r.stdout,r.stderr);r.check_returncode()
        frames=[];summary=[]
        for line in r.stdout.splitlines():
            if not line.startswith('TX '):summary.append(line);continue
            _,number,encoded=line.split();pn=int(number);frame=bytes.fromhex(encoded);assert len(frame)==1560 and frame[:2]==bytes.fromhex('d040')
            iv=frame[24:32];assert int.from_bytes(iv[:2]+iv[4:8],'little')==pn
            nonce=b'\x10'+frame[10:16]+pn.to_bytes(6,'big');aad=frame[:2]+frame[4:22]+bytes([frame[22]&15,0])
            cipher=AES.new(bytes([0x16])+bytes(15),AES.MODE_CCM,nonce=nonce,mac_len=8,msg_len=len(frame)-40,assoc_len=len(aad));cipher.update(aad);plain=cipher.decrypt_and_verify(frame[32:-8],frame[-8:])
            payload=bytes(i%256 for i in range(1470));expected=b'\x7f\x18\xfe\x34'+b'\x53'*4
            for offset in range(0,1470,250):
                chunk=payload[offset:offset+250];expected+=bytes([221,len(chunk)+5])+b'\x18\xfe\x34\x04'+bytes([0x12 if offset+len(chunk)<1470 else 2])+chunk
            assert plain==expected
            frames.append({'pn':pn,'frame_sha256':hashlib.sha256(frame).hexdigest(),'independent_aes_ccm_verified':True,'payload_bytes':1470})
        assert [f['pn'] for f in frames]==[1,1025] and not list(missing.glob('*.dat'))
        assert all(f.stat().st_size==80 for f in data.glob('*.dat'))
        rows.append({'target':name,'frames':frames,'summary':summary,'missing_directory_dat_files':0,'journal_records':len(list(data.glob('*.dat')))})
dependencies=[*sources,'tools/fixtures/full_owner_ipc.c','tools/test_xnow_full.c','tools/test_full_owner_secure.py','runtime/platform/espnow/xnow_owner_runtime.h','runtime/platform/espnow/xnow_endpoint_security.h','runtime/platform/espnow/xnow_pn_file.h']
report={'passed':True,'cases':rows,'real_posix_journal_adapter':True,'mocked_user_volume_guard':True,'real_controller_endpoint_backend':True,'stock_driver_actions_mocked':True,'radio_transport_synthetic':True,'over_air_tested':False,'device_accessed':False,'installed':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in dependencies}}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},indent=2))
