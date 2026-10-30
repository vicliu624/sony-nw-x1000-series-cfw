"""Actual observer with stock/full code, negative callbacks, ARM GET-only CLI."""
from pathlib import Path
import ctypes,hashlib,json,subprocess
from build_radio_inspector import ROOT,OUT,VERSION,RANGES,INPUTS,profile_data
from marvell_firmware import parse
from prepare_espnow_radio_candidate import memory
subprocess.run([str(ROOT/'.venv/bin/python'),str(ROOT/'tools/build_radio_inspector.py')],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
class Range(ctypes.Structure):_fields_=[('address',ctypes.c_uint32),('bytes',ctypes.c_uint32)]
class Profile(ctypes.Structure):_fields_=[('name',ctypes.c_char_p),('digest',ctypes.c_uint8*32)]
class Result(ctypes.Structure):_fields_=[(n,ctypes.c_uint32) for n in ('profile','flags','activation','q','root','child','mac','security')]+[('present',ctypes.c_uint8),('byte',ctypes.c_uint8)]
Read=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32))
sources=['runtime/platform/espnow/inspect/observe.c','runtime/native/sha256.c'];shared=OUT/'observe.so';subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',*sources,'-o',str(shared)],cwd=ROOT,check=True)
lib=ctypes.CDLL(str(shared));lib.xnow_radio_observe.argtypes=[ctypes.c_void_p,Read,ctypes.POINTER(Range),ctypes.c_uint,ctypes.POINTER(Profile),ctypes.c_uint,ctypes.POINTER(Result)]
profiles_data=profile_data();profiles=(Profile*len(profiles_data))(*[Profile(r['name'].encode(),(ctypes.c_uint8*32).from_buffer_copy(bytes.fromhex(r['fingerprint_sha256']))) for r in profiles_data]);ranges=(Range*len(RANGES))(*[Range(*r) for r in RANGES])
state={0xc0014528:0x8203,0xc0014684:0,0xc00146e0:0,0xc000ee48:0xc000e000,0xc000e008:0xc000e100,0xc000e1c0:0,0x8000a300:0x10000000,0x8000200c:0x01000000};rows=[]
def run(index,mode):
    loaded=memory(parse(INPUTS[index][1].read_bytes()));words=dict(state);seen=[]
    if mode=='bad-code':loaded[RANGES[0][0]]^=1
    if mode=='bad-root':words[0xc000ee48]=0x80002000
    if mode=='bad-child':words[0xc000e008]=0xc0017da0
    if mode=='absent':words[0xc000ee48]=0
    @Read
    def read(_,address,out):
        seen.append(address)
        if mode=='io-error' and address==0xc0014528:return -1
        if address in words:
            value=words[address]
            if mode=='changing' and address==0xc0014528 and seen.count(address)==2:value^=1
        elif all(address+i in loaded for i in range(4)):value=int.from_bytes(bytes(loaded[address+i] for i in range(4)),'little')
        else:return -1
        out[0]=value;return 0
    result=Result();ctypes.memset(ctypes.byref(result),0xa5,ctypes.sizeof(result));before=bytes(result)
    rc=lib.xnow_radio_observe(None,read,ranges,len(ranges),profiles,len(profiles),ctypes.byref(result));expected={'stable':0,'absent':0,'bad-code':-3,'io-error':-2,'bad-root':-5,'bad-child':-5,'changing':-4}[mode];assert rc==expected,(mode,rc)
    if rc:assert bytes(result)==before
    else:assert result.profile==index and result.flags==0x8203 and result.present==(mode!='absent')
    if mode=='bad-code':assert 0x8000a300 not in seen
    if mode=='bad-root':assert 0x80002008 not in seen
    if mode=='bad-child':assert 0xc0017e60 not in seen
    rows.append({'profile':index,'mode':mode,'result':rc,'reads':len(seen),'output_preserved_on_failure':rc!=0})
for index in (0,1):
    for mode in ('stable','absent','bad-code','io-error','bad-root','bad-child','changing'):run(index,mode)
loaded=memory(parse(INPUTS[0][1].read_bytes()));words={a:int.from_bytes(bytes(loaded[a+i] for i in range(4)),'little') for start,n in RANGES for a in range(start,start+n,4)};words.update(state)
info=OUT/'driver-info.txt';info.write_text('driver=sd8686-9.70.3.p32-26409.p51-(FP4)\n');(OUT/'radio_inspect_mock.h').write_text('#define INSPECT_DRIVER_INFO '+json.dumps(str(info))+'\nstatic const unsigned mock_words[][2]={'+','.join('{'+hex(a)+','+hex(v)+'}' for a,v in sorted(words.items()))+'};\n')
target=OUT/'inspect-mock.arm';L=ROOT/'work/arm-signal-tests/lib';native_sources=['runtime/platform/espnow/inspect/main.c',*sources,'tools/fixtures/radio_inspect_ioctl.c','runtime/store/start.c','runtime/store/start.S']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-march=armv5te','-marm','-mfloat-abi=soft','-fno-builtin','-fno-pie','-fno-stack-protector','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-I'+str(OUT),*['-Wl,--wrap='+n for n in ('fopen','fopen64','socket','close','ioctl')],*native_sources,str(L/'libc.so.6'),str(L/'ld-linux.so.3'),'-lgcc','-o',str(target)],cwd=ROOT,check=True)
base=['qemu-arm','-cpu','arm926',str(L/'ld-linux.so.3'),'--library-path',str(L),str(target),'--inspect'];p=subprocess.run(base,capture_output=True,text=True,timeout=30,check=True);observed=json.loads(p.stdout);assert observed['flags']=='00008203' and observed['context_byte']==0 and observed['hardware_admission_verified'] is False
info.write_text('wrong-driver\n');p=subprocess.run(base,capture_output=True,text=True,timeout=30);assert p.returncode==69;info.write_text('driver=sd8686-9.70.3.p32-26409.p51-(FP4)\n')
dependencies=[*native_sources,'runtime/platform/espnow/inspect/observe.h','tools/build_radio_inspector.py','tools/test_radio_inspector.py'];report={'passed':True,'version':VERSION,'observer_cases':rows,'arm926_stock_libc_cli':observed,'arm_ioctl_mock_enforces_get_only':True,'wrong_driver_refused':True,'real_driver_or_mmio_used':False,'device_accessed':False,'installed':False,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in dependencies}}
(OUT/'tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('source_hashes','observer_cases')},indent=2))
