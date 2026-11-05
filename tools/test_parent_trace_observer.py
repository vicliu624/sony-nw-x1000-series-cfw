"""Exact ARM capsules -> diagnostic PID shim -> observer -> fixed-file backend."""
import argparse,hashlib,io,json,re,subprocess,time
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from review_managed_remote_profile import receipt,digest
from player_arm_guest import stock_libraries,run_guest
from read_parent_entry_trace import decode
from native_settings_count import offset
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capsule-review',required=True);a=p.parse_args();rp,capsule=receipt(a.capsule_review)
out=ROOT/'work/parent-observer-pair'/str(time.time_ns());out.mkdir(parents=True)
original=(ROOT/'runtime/platform/player/parent_entry_trace.S').read_text();assert original.count('\n.text\n')==1
trace_asm=out/'capsules.S';trace_asm.write_text(original.replace('\n.text\n','\n.section .parent_capsule,"ax",%progbits\n'))
candidate=ROOT/capsule['artifact'];assert digest(candidate)==capsule['sha256']
candidate_bytes=candidate.read_bytes();at=offset(candidate_bytes,capsule['slot'],capsule['code_bytes'])
code=candidate_bytes[at:at+capsule['code_bytes']];assert code==(rp.parent/'trace.bin').read_bytes()
digest_bytes=hashlib.sha256(code).digest()
array=lambda values:'{'+','.join(str(v) for v in values)+'}'
defines={'XW_TEST_TRACE_START':capsule['slot'],'XW_TEST_TRACE_BYTES':len(code),'XW_TEST_TRACE_DIGEST':array(digest_bytes),'XW_TEST_TRACE_CALLERS':array(capsule['observer_callers'])}
for short,symbol in [('LAUNCH','parent_trace_launch'),('LOOKUP','parent_trace_lookup'),('RETURN','parent_trace_lookup_return'),('SWITCH','parent_trace_switch')]:defines['XW_TEST_TRACE_'+short]=capsule['symbols'][symbol]
(out/'parent_observer_profile.h').write_text(''.join('#define '+k+' '+str(v)+'\n' for k,v in defines.items()))
import secrets
header=b'X1PARENTTRACE000'+secrets.token_bytes(16);seed=out/'seed.bin';seed.write_bytes(header+bytes(2016))
mounts=out/'mounts';mounts.write_text('rootfs / rootfs rw 0 0\n/dev/mtdblock/2 /contents vfat rw,noatime 0 0\n')
sources=['runtime/platform/player/parent_trace_observer.c','runtime/platform/player/parent_trace_store.c','runtime/platform/player/host_pid.S','runtime/native/sha256.c','runtime/store/stock_fs_bridge.c','runtime/store/stock_stat64.c','tools/fixtures/parent_trace_observer.c','tools/fixtures/parent_observer_stubs.S']
startup=['runtime/store/start.c','runtime/store/start.S'];init_source='tools/fixtures/player_worker_system_init.c';libs=stock_libraries();app=out/'test.arm';init=out/'init.arm'
flags=['-D_DEFAULT_SOURCE','-DXW_PLAYER_CAPTURE_ARG2','-DXW_PLAYER_PARENT_TRACE','-U_FORTIFY_SOURCE','-D_FORTIFY_SOURCE=0','-std=c99','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-march=armv5te','-marm','-mfloat-abi=soft','-fno-pie','-no-pie','-nostdlib','-I'+str(out),'-Wl,--hash-style=sysv,--build-id=none']
layout=['-Wl,--section-start=.parent_capsule=0x4d8e00,--section-start=.parent_pid_stub=0xda84,--section-start=.parent_resume_stubs=0xb0000,--section-start=.parent_switch_stub=0x2681e8,--defsym=parent_trace_getpid=0xda84,--defsym=parent_trace_original_switch=0x2681e8,--wrap=fopen,--wrap=fopen64']
links=[str(libs[n]) for n in ('libpthread.so.0','libc.so.6','ld-linux.so.3')]
subprocess.run(['arm-linux-gnueabi-gcc',*flags,*layout,*sources,str(trace_asm),*startup,*links,'-lgcc','-o',str(app)],cwd=ROOT,check=True)
elf=ELFFile(io.BytesIO(app.read_bytes()));assert elf.get_section_by_name('.parent_capsule').data()==code
subprocess.run(['arm-linux-gnueabi-gcc',*flags,init_source,*startup,*links,'-lgcc','-o',str(init)],cwd=ROOT,check=True)
report=run_guest(out,init,{'test':app,'seed':seed,'fixture-mounts':mounts,'contents/.fixture':seed},libs,['PARENT_OBSERVER_PAIRED_PASS','PLAYER_WORKER_CHILD_STATUS=0'])
text=(out/'serial.log').read_text(errors='replace');assert report['passed'],text[-3000:]
match=re.search(r'PARENT_OBSERVER_FILE_HEX (.*?)\r?\nPARENT_OBSERVER_FILE_END',text,re.S);assert match
dump=''.join(re.sub(r'\[\s*\d+\.\d+\][^\r\n]*','',match[1]).split());assert re.fullmatch('[0-9a-f]{4096}',dump)
data=bytes.fromhex(dump);decoded=decode(seed.read_bytes(),data);assert decoded['integrity_valid'] and [r['stage'] for r in decoded['records']]==[1,2,3,4,5]
(out/'captured.bin').write_bytes(data)
report.update(capsule_artifact_sha256=digest(candidate),capsule_review_sha256=digest(rp),exact_capsules_match_review=True,actual_six_argument_pid_shim=True,observer_store_and_crc_reader_paired=True,record_failure_does_not_change_fixture_native_result=True,
 source_hashes={s:digest(ROOT/s) for s in [*sources,*startup,init_source,'runtime/platform/player/parent_entry_trace.S','runtime/platform/player/parent_trace_observer.h','runtime/platform/player/parent_trace_store.h','tools/test_parent_trace_observer.py','tools/read_parent_entry_trace.py']},
 limits=['Generic ARM kernel with actual Sony libc/LinuxThreads and file IO on a RAM volume.','The six-argument dispatcher is a fixture, not host_hook.c; ordinary PID delegates to the test raw OABI shim.','GUI/APF continuation targets, mount text, ownership and numeric snapshot are fixtures; real USB guard and original-player integration remain unimplemented.','No firmware, device access, live manager retirement or physical Homebrew qualification.'])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
