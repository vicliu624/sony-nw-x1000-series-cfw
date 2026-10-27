"""Read-only Device Info tests on host and actual ARM ELF; virtual devices only."""
from pathlib import Path
import subprocess,os,json,hashlib,shutil,re,struct,zlib
ROOT=Path(__file__).resolve().parents[1];w=ROOT/'work/device-info-tests';w.mkdir(exist_ok=True);fixture=w/'fixture';lib=ROOT/'work/arm-signal-tests/lib'
files={'proc/cpuinfo':'Processor: ARMv6-compatible processor rev 5 (v6l)\nHardware: Example board\nCPU architecture: 6\nFeatures: swp half thumb fastmult vfp edsp java\nBogoMIPS: 265.42\n','proc/meminfo':'MemTotal: 60000 kB\nMemFree: 12000 kB\nBuffers: 2048 kB\nCached: 8192 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB\n','proc/mounts':'/dev/mtdblock/1 / ext2 rw 0 0\n/dev/mtdblock/2 /contents vfat rw 0 0\nproc /proc proc rw 0 0\n/dev/example /media/with\\040space ext2 ro 0 0\n','proc/mtd':'dev: size erasesize name\nmtd0: 00100000 00020000 "boot"\nmtd1: 09400000 00020000 "rootfs"\nmtd2: 800000000 00020000 "user storage"\n','proc/sys/kernel/osrelease':'2.6.10-fixture\n','proc/sys/kernel/ostype':'Linux\n','proc/version':'Linux version 2.6.10-fixture (offline test)\n','proc/uptime':'12345.67 8901.23\n','usr/local/share/genesys/GENESYS_VERSION':'TEST-BUILD\n'}
for name,data in files.items():p=fixture/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
flags=['-std=c99','-Os','-Wall','-Wextra','-Werror','-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-fno-builtin','-fno-stack-protector'];sources=['tools/test_device_info.c','runtime/apps/device-info/device_info_data.c','runtime/apps/device-info/device_info_space.c'];results=[]
subprocess.run(['gcc',*flags,*sources,'-o',str(w/'test-host')],cwd=ROOT,check=True)
r=subprocess.run([str(w/'test-host'),str(fixture)],capture_output=True,text=True,timeout=15);assert r.returncode==0,r.stderr;results.append({'test':'host-model','stdout':r.stdout,'exit':r.returncode})
subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--build-id=none',*sources,'runtime/store/start.c','runtime/store/start.S',str(lib/'libc.so.6'),str(lib/'ld-linux.so.3'),'-lgcc','-o',str(w/'test-arm')],cwd=ROOT,check=True)
cmd=['qemu-arm','-cpu','arm926',str(lib/'ld-linux.so.3'),'--library-path',str(lib)]
r=subprocess.run(cmd+[str(w/'test-arm'),str(fixture)],capture_output=True,text=True,timeout=15);assert r.returncode==0,(r.returncode,r.stderr);results.append({'test':'actual-ARM-data-model','stdout':r.stdout,'exit':r.returncode})
app=ROOT/'work/device-info-build/HOMEBREW/apps/device-info/app';r=subprocess.run(cmd[:3]+['-strace']+cmd[3:]+[str(app),'--dump'],env={**os.environ,'HB_INFO_ROOT':str(fixture)},capture_output=True,text=True,timeout=15);assert r.returncode==0,r.stderr
for s in ['Example board','58.5 MiB','11.7 MiB','Available RAM: Unavailable','32.0 GiB','148.0 MiB','user storage','with space','2.6.10-fixture','PC TEST DATA']:assert s in r.stdout,s
assert 'statfs(' not in r.stderr
for line in r.stderr.splitlines():
 if ' open(' in line:assert 'O_RDONLY' in line,line
 if re.search(r' write\(',line):assert re.search(r'write\([12],',line),line
(w/'dump.txt').write_text(r.stdout);(w/'dump.trace').write_text(r.stderr);results.append({'test':'actual-ARM-fixture-dump-read-only','exit':r.returncode})
# Pinned libc really exports the legacy OABI statfs wrapper, not modern time64.
dis=subprocess.run(['arm-linux-gnueabi-objdump','-d','--start-address=0xa0050','--stop-address=0xa0060',str(lib/'libc.so.6')],capture_output=True,text=True,check=True).stdout;assert 'ef900063' in dis;(w/'stock-statfs.disasm').write_text(dis)
prefix=w/'sysroot';(prefix/'lib').mkdir(parents=True,exist_ok=True)
for name in ('libc.so.6','ld-linux.so.3'):shutil.copyfile(lib/name,prefix/'lib'/name)
source=(ROOT/'tools/fixtures/device_preload.c').read_text();source=re.sub(r'static int max_events\(void\)\{[^\n]*\}', 'static int max_events(void){return 8;}',source)
start=source.index(' case 0x80045401:');end=source.index('\n default:',start)
source=source[:start]+''' case 0x80045401:{static const unsigned x[]={80,80,80,80,80,80,30,30};static const unsigned y[]={250,150,150,150,250,250,400,400};static const unsigned down[]={1,1,0,1,1,0,1,0};assert(event<8);unsigned rx=(x[event]*2929+239)/240,ry=((431-y[event])*5281+431)/432;unsigned char*b=argument;memset(b,0,16);b[1]=down[event];b[2]=rx>>8;b[3]=rx;b[4]=ry>>8;b[5]=ry;event++;break;}'''+source[end:]
(w/'virtual-devices.c').write_text(source.replace('#include "../../runtime/native/font.inc"','#include "'+str(ROOT/'runtime/native/font.inc')+'"'))
objects=[]
for i,p in enumerate([w/'virtual-devices.c',ROOT/'runtime/native/syscalls.S']):
 obj=w/('preload-'+str(i)+'.o');subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-D_GNU_SOURCE','-march=armv5te','-marm','-mfloat-abi=soft','-fPIC','-c',str(p),'-o',str(obj)],check=True);objects.append(str(obj))
preload=w/'virtual-devices.so';subprocess.run(['arm-linux-gnueabi-gcc','-shared','-nostdlib','-Wl,--hash-style=sysv',*objects,str(lib/'libc.so.6'),'-lgcc','-o',str(preload)],check=True)
r=subprocess.run(['qemu-arm','-cpu','arm926','-L',str(prefix),'-E','LD_PRELOAD='+str(preload),'-E','HB_INFO_ROOT='+str(fixture),'-E','HB_TEST_FRAME='+str(w/'frame.rgb565'),str(app)],capture_output=True,text=True,timeout=15);(w/'ui.log').write_text(r.stderr);assert r.returncode==0,(r.returncode,r.stderr);assert r.stderr.count('VDEV FRAME')==3 and 'VDEV RELEASE COMPLETE' in r.stderr,r.stderr
results.append({'test':'actual-ARM-UI-swipe-next-previous-close','exit':r.returncode,'frames':3})
raw=(w/'frame.rgb565').read_bytes();rgb=bytearray()
for i in range(0,len(raw),2):n=int.from_bytes(raw[i:i+2],'little');rgb.extend((((n>>11)&31)*255//31,((n>>5)&63)*255//63,(n&31)*255//31))
def chunk(k,b):return struct.pack('>I',len(b))+k+b+struct.pack('>I',zlib.crc32(k+b)&0xffffffff)
scan=b''.join(b'\0'+rgb[y*720:(y+1)*720] for y in range(432));(w/'screen.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
report={'passed':True,'actual_app_sha256':hashlib.sha256(app.read_bytes()).hexdigest(),'checks':results,'hardware_tested':False,'device_written':False,'scope':'PC host + actual ARM/Sony libc; proc/space/display fixtures. No physical capacity or HOME qualification.'};(w/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
