"""Local original-libc read-only radio inspector. No install or device commands."""
from pathlib import Path
import hashlib,json,subprocess,sys
from marvell_firmware import parse
from prepare_espnow_radio_candidate import memory,STOCK_SHA
ROOT=Path(__file__).resolve().parents[1];VERSION=(ROOT/'runtime/platform/espnow/inspect/VERSION').read_text().strip();OUT=ROOT/'work/radio-inspect'/VERSION;OUT.mkdir(parents=True,exist_ok=True)
RANGES=[(0x8078,64),(0x88d4,32),(0x54c0,88),(0x6b6c,88),(0xc0006144,64),(0xc5e4,80)]
INPUTS=[('stock-jp-1.11',ROOT/'work/targets-jp/sd8686.bin',STOCK_SHA),('full-radio-experimental-v2',ROOT/'work/espnow-full-radio-review-3/candidate/sd8686.bin','d4b92b65fa502e2c8c94d241e4a293e28db7e98a3afdba0958d8b4f8aa1a5ed8')]
def profile_data():
    rows=[]
    for name,path,expected in INPUTS:
        raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==expected
        loaded=memory(parse(raw));digest=hashlib.sha256(b''.join(bytes(loaded[a+i] for i in range(n)) for a,n in RANGES)).hexdigest();rows.append({'name':name,'path':str(path.relative_to(ROOT)),'input_sha256':expected,'fingerprint_sha256':digest})
    return rows
def main():
    profiles=profile_data();header=OUT/'radio_inspect_profile.h';header.write_text('#define RADIO_INSPECT_VERSION '+json.dumps(VERSION)+'\nstatic const struct xnow_observe_range ranges[]={'+','.join('{'+hex(a)+','+str(n)+'}' for a,n in RANGES)+'};\nstatic const struct xnow_observe_profile profiles[]={'+','.join('{'+json.dumps(r['name'])+',{'+','.join(str(b) for b in bytes.fromhex(r['fingerprint_sha256']))+'}}' for r in profiles)+'};\n')
    sources=['runtime/platform/espnow/inspect/main.c','runtime/platform/espnow/inspect/observe.c','runtime/native/sha256.c','runtime/store/start.c','runtime/store/start.S'];lib=ROOT/'work/arm-signal-tests/lib'
    for name,expected in [('libc.so.6','5afbf3074dfa9ba0478d6670f220ef4d7ec065a255ee856d9093d39210f23812'),('ld-linux.so.3','2f007b0809684fde0ac446ad203135c10b4318eb8c10d4160a9f59b32c3c52de')]:assert hashlib.sha256((lib/name).read_bytes()).hexdigest()==expected
    app=OUT/'radio-inspect';flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-I'+str(OUT)]
    subprocess.run(['arm-linux-gnueabi-gcc',*flags,*sources,str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(app)],cwd=ROOT,check=True)
    base=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib),str(app)];checks=[]
    for arg in ('--help','--version'):
        r=subprocess.run([*base,arg],capture_output=True,text=True,timeout=20,check=True);checks.append({'arg':arg,'stdout':r.stdout})
    report={'built':True,'version':VERSION,'binary_bytes':app.stat().st_size,'binary_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'profiles':profiles,'ranges':RANGES,'checks':checks,'device_accessed':False,'installed':False,'inspect_run_on_device':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,'runtime/platform/espnow/inspect/observe.h','runtime/platform/espnow/inspect/VERSION','tools/build_radio_inspector.py']}}
    (OUT/'build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('source_hashes','profiles','ranges')},indent=2))
if __name__=='__main__':main()
