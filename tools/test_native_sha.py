"""Known/reference digest comparisons for the streaming C SHA-256 used at launch."""
import ctypes,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
subprocess.run(['gcc','-shared','-fPIC','-O2',str(ROOT/'runtime/native/sha256.c'),'-o',str(ROOT/'work/native-sha.so')],check=True)
class State(ctypes.Structure):_fields_=[('h',ctypes.c_uint*8),('used',ctypes.c_uint),('total',ctypes.c_ulonglong),('block',ctypes.c_ubyte*64)]
lib=ctypes.CDLL(str(ROOT/'work/native-sha.so'));cases=[]
for n in [0,1,3,55,56,63,64,65,127,128,129,4095,4096,4097,1000000]:
    data=bytes((i*17+3)&255 for i in range(n))
    for step in [7,4096]:
        state=State();lib.hb_sha256_init(ctypes.byref(state))
        for off in range(0,n,step):
            part=data[off:off+step];b=(ctypes.c_ubyte*len(part)).from_buffer_copy(part);lib.hb_sha256_update(ctypes.byref(state),b,len(part))
        out=(ctypes.c_ubyte*32)();lib.hb_sha256_final(ctypes.byref(state),out);actual=bytes(out).hex();assert actual==hashlib.sha256(data).hexdigest()
        cases.append({'bytes':n,'chunk':step,'sha256':actual})
report={'scope':'host C implementation compared with Python hashlib; ARM file hashing separately tested','cases':cases}
(ROOT/'sources/native-sha-tests.json').write_text(json.dumps(report,indent=2));print(str(len(cases))+' streaming SHA-256 reference comparisons passed')
