"""Real cache-file sinks under project temp dirs, host and stock-libc ARM."""
from pathlib import Path
import subprocess,hashlib,json,gzip,io,tarfile,tempfile
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/download-file-tests';work.mkdir(exist_ok=True)
sources=['runtime/store/download_file.c','runtime/store/download_stream.c','runtime/store/http_response.c','runtime/native/sha256.c','tools/test_download_file.c','tools/download_file_faults.c']
wrap='-Wl,--wrap=write,--wrap=fsync,--wrap=close'
subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror',*sources,wrap,'-o',str(work/'host')],cwd=ROOT,check=True)
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes();assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):(work/name).write_bytes(tar.extractfile('./lib/'+name).read())
alias=work/'libc.so.6'
if not alias.exists():alias.symlink_to('libc-2.3.3.so')
bridge=['runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','runtime/store/stock_tls_compat.c']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Wall','-Wextra','-Werror','-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-nostdlib','-no-pie','-Wl,--hash-style=sysv',*sources,*bridge,'tools/stock_test_start.c','tools/store_link_start.S',wrap,str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(work/'arm')],cwd=ROOT,check=True)
rows=[]
for platform,command in [('host',[str(work/'host')]),('ARM/QEMU',['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(work/'arm')])]:
 for mode in ('ready','discard','hash','cancel','space','exists','link','bad-key','root-alias','replace','write-error','write-after-error','short-write','sync-file','sync-dir','close-error','recheck-file-sync','recheck-dir-sync','recheck-close','recheck-corrupt'):
  with tempfile.TemporaryDirectory(prefix='cache-',dir=work) as temp:
   root=Path(temp);cache=root/'cache';cache.mkdir();actual=cache
   if mode=='exists':(cache/'.fetch-demo').write_bytes(b'KEEP')
   if mode=='link':(root/'keep').write_bytes(b'KEEP');(cache/'.fetch-demo').symlink_to(root/'keep')
   if mode=='root-alias':actual=root/'alias';actual.symlink_to(cache,target_is_directory=True)
   run=subprocess.run(command+[str(actual),mode],capture_output=True,text=True,timeout=15);assert run.returncode==0,(platform,mode,run.returncode,run.stderr)
   names={p.name for p in cache.iterdir()}
   if mode in ('ready','short-write','sync-file','sync-dir','close-error','recheck-file-sync','recheck-dir-sync','recheck-close'):assert names=={'.fetch-demo'} and (cache/'.fetch-demo').read_bytes()==b'abc'
   elif mode=='recheck-corrupt':assert names=={'.fetch-demo'} and (cache/'.fetch-demo').read_bytes()==b'abd'
   elif mode=='exists':assert names=={'.fetch-demo'} and (cache/'.fetch-demo').read_bytes()==b'KEEP'
   elif mode=='link':assert (cache/'.fetch-demo').is_symlink() and (root/'keep').read_bytes()==b'KEEP'
   elif mode=='replace':assert names=={'.fetch-demo','.fetch-demo-saved'} and (cache/'.fetch-demo').read_bytes()==b'KEEP' and (cache/'.fetch-demo-saved').read_bytes()==b'abc'
   else:assert not names,(platform,mode,names)
   rows.append({'platform':platform,'case':mode,'passed':True})
report={'all_bounded_checks_passed':True,'physical_device_access':False,'cases':rows,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+bridge},'limits':['Host temporary filesystem and QEMU, not Sony FAT/power-loss qualification.','Single inactive file; no package assembly, rename publication, app activation or network.','Quiescent caller-owned cache; no concurrent mutation or OS confinement guarantee.','Injected fsync/write errors and error after actual close; not exhaustive I/O ambiguity or process interruption.']}
(ROOT/'sources/native-download-file-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Download cache file:',len(rows),'host/ARM cases passed.')
