"""Real Sony-libc fixed-file writer under generic ARM Linux, no device access."""
import hashlib,json,re,secrets,subprocess,time,zlib,struct
from app_registry import ROOT
from player_arm_guest import stock_libraries,run_guest
from read_parent_entry_trace import decode
out=ROOT/'work/parent-trace-store'/str(time.time_ns());out.mkdir(parents=True)
header=b'X1PARENTTRACE000'+secrets.token_bytes(16);assert len(header)==32
seed=out/'parent-boundary.bin';seed.write_bytes(header+bytes(2048-32))
mounts=out/'mounts';mounts.write_text('rootfs / rootfs rw 0 0\n/dev/mtdblock/2 /contents vfat rw,noatime 0 0\n')
sources=['runtime/platform/player/parent_trace_store.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','tools/fixtures/parent_trace_store.c']
startup=['runtime/store/start.c','runtime/store/start.S'];init_source='tools/fixtures/player_worker_system_init.c'
libs=stock_libraries();app=out/'test.arm';init=out/'init.arm'
flags=['-D_DEFAULT_SOURCE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-no-pie','-nostdlib','-Wl,--hash-style=sysv,--build-id=none']
wrap=['-Wl,--wrap='+name for name in ('fopen','fopen64','open','open64','close','write','fsync')]
links=[str(libs[n]) for n in ('libpthread.so.0','libc.so.6','ld-linux.so.3')]
subprocess.run(['arm-linux-gnueabi-gcc',*flags,*wrap,*sources,*startup,*links,'-lgcc','-o',str(app)],cwd=ROOT,check=True)
subprocess.run(['arm-linux-gnueabi-gcc',*flags,init_source,*startup,*links,'-lgcc','-o',str(init)],cwd=ROOT,check=True)
report=run_guest(out,init,{'test':app,'seed':seed,'fixture-mounts':mounts,'contents/.fixture':seed},libs,['PARENT_TRACE_STORE_PASS','PLAYER_WORKER_CHILD_STATUS=0'])
text=(out/'serial.log').read_text(errors='replace');match=re.search(r'PARENT_TRACE_RECORD_HEX ([0-9a-f]{128})',text)
assert report['passed'] and match,text[-3000:]
record=bytes.fromhex(match[1]);assert record[:4]==b'HBP1' and zlib.crc32(record[:60])==struct.unpack_from('<I',record,60)[0]
file_match=re.search(r'PARENT_TRACE_FILE_HEX (.*?)\r?\nPARENT_TRACE_FILE_END',text,re.S);assert file_match
# Kernel console messages may interrupt a userspace serial write. Remove only
# timestamp-prefixed kernel text; require the exact hex length and all CRCs.
dump=re.sub(r'\[\s*\d+\.\d+\][^\r\n]*','',file_match[1]);dump=''.join(dump.split())
assert re.fullmatch(r'[0-9a-f]{4096}',dump)
captured=bytes.fromhex(dump);assert captured[:32]==header and not any(captured[1056:])
(out/'captured.bin').write_bytes(captured)
for i in range(16):
 row=captured[32+i*64:96+i*64]
 assert row[:4]==b'HBP1' and struct.unpack_from('<II',row,4)==(i+1,i+1)
 assert zlib.crc32(row[:60])==struct.unpack_from('<I',row,60)[0]
decoded=decode(seed.read_bytes(),captured);assert decoded['integrity_valid'] and len(decoded['records'])==16
empty=decode(seed.read_bytes(),seed.read_bytes());assert not empty['recording_present'] and empty['no_records_is_inconclusive']
partial=bytearray(captured);partial[64:96]=bytes(32)
partial_decoded=decode(seed.read_bytes(),bytes(partial));assert len(partial_decoded['records'])==15 and partial_decoded['invalid_slots']==[dict(slot=1,reason='crc32')]
for bad in (captured[:-1],bytes([captured[0]^1])+captured[1:],captured[:-1]+b'!'):
 try:decode(seed.read_bytes(),bad)
 except ValueError:pass
 else:raise AssertionError('Reader accepted wrong size/identity/tail')
report.update(crc32_independently_checked=True,pc_reader_real_record_and_partial_write_checked=True,capture_artifact=(out/'captured.bin').relative_to(ROOT).as_posix(),all_sixteen_slots_and_tail_checked=True,storage_file_bytes=2048,record_bytes=64,maximum_stage_attempts=16,no_retained_record_fd_in_cases=True,
 source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [*sources,*startup,init_source,'runtime/platform/player/parent_trace_store.h','runtime/store/stock_fs_bridge.h','runtime/store/stock_stat64.h','tools/test_parent_trace_store.py','tools/read_parent_entry_trace.py']},
 limits=['Generic kernel and RAM user mount; mount-table text and USB ownership predicate are explicit fixtures, not Sony VFAT/USB qualification.',
 'Fault wrappers inject short-write/fsync failure; ordinary nonce/inode/size checks, stock stat bridge, file IO, seeks, pthread mutex and closing execute.',
 'No parent observer dispatcher or firmware integration yet; bounded IO count is not a hard deadline for blocking filesystem calls.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
(ROOT/'work/parent-trace-store-latest.json').write_text(json.dumps({'review':(out/'report.json').relative_to(ROOT).as_posix()})+'\n')
print(json.dumps(report,indent=2))
