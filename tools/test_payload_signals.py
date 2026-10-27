"""Real ARM app payload SIGTERM with independent-process Back/Retry recovery."""
from pathlib import Path
import runpy,ast,subprocess,json,hashlib,tempfile,socket,ssl,os
ROOT=Path(__file__).resolve().parents[1];base=runpy.run_path(str(ROOT/'tools/test_remote_store_signals.py'))
work=ROOT/'work/payload-signal-tests';work.mkdir(exist_ok=True);runtime=base['runtime'];crypto=base['crypto'];tls=base['tls'];previous=base['previous']
text=base['text']
old='if(!strcmp(scenario,"signal-metadata")&&store.stage==HB_REMOTE_CATALOG&&store.metadata.state==HB_METADATA_FETCHING&&store.metadata.task.phase==HB_NET_TRANSFER){hb_repository_record_exit(1);}'
assert text.count(old)==1
text=text.replace(old,'if(*hb_store_termination_flag())return -1;if(!strcmp(scenario,"signal-payload")&&store.stage==HB_REMOTE_PACKAGE&&store.job.state==HB_JOB_FETCH&&store.job.task.phase==HB_NET_TRANSFER){hb_repository_record_exit(1);}')
anchor='if(!strcmp(scenario,"signal-metadata")){assert(result<0'
assert text.count(anchor)==1
text=text.replace(anchor,'if(!strcmp(scenario,"signal-payload")){assert(result<0&&*hb_store_termination_flag()&&store.job.state==HB_JOB_FAILED&&store.job.task.fd==-1&&!store.job.task.dns.channel&&store.job.record.owns);assert(!hb_store_termination_end());if(peer>=0)assert(!close(peer));assert(!close(listener)&&!close(dns));return 0;}'+anchor)
generated=work/'test.c';generated.write_text(text);sources=[str(generated) if p==str(base['generated']) else p for p in base['sources']]
wrapper=work/'offset_write.c'
wrapper.write_text('#include <signal.h>\n#include <stdlib.h>\n#define __wrap_write hb_repository_regular_write\n#include "'+str(ROOT/'tools/download_file_faults.c')+'"\n#undef __wrap_write\nstatic int armed;static unsigned written,target;void hb_repository_record_exit(int enabled){if(!enabled){armed=0;written=0;return;}if(armed)return;armed=1;written=0;target=0;const char*p=getenv("HB_SIGNAL_CUT");if(p)for(;*p;p++)target=target*10+(unsigned)(*p-\'0\');if(!target)target=1;}ssize_t __wrap_write(int fd,const void*data,size_t bytes){if(armed&&bytes){unsigned amount=target-written;if(amount>bytes)amount=(unsigned)bytes;ssize_t n=__real_write(fd,data,amount);if(n>0){written+=(unsigned)n;if(written==target){armed=0;raise(SIGTERM);}}return n;}return hb_repository_regular_write(fd,data,bytes);}\n')
sources=[str(wrapper) if p==str(base['wrapper']) else p for p in sources]
tree=ast.parse((ROOT/'tools/test_remote_store_signals.py').read_text());compile_call=next(n.value for n in tree.body if isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Attribute) and isinstance(n.value.func.value,ast.Name) and n.value.func.value.id=='subprocess' and n.value.func.attr=='run')
context=dict(base,work=work,sources=sources);command=eval(compile(ast.Expression(compile_call.args[0]),'<existing compiler list>','eval'),context);subprocess.run(command,cwd=ROOT,check=True)
traces=[]
def snapshot(folder):return {str(p.relative_to(folder)):p.read_bytes() for p in folder.rglob('*') if p.is_file()}
cuts=(1,4096,len(base['expected']['app'])-1,len(base['expected']['app']));rows=[]
for cut in cuts:
 with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
  folder=Path(temp)
  for name in ('apps','packages','cache','repository'):(folder/name).mkdir()
  (folder/'apps/unrelated').write_bytes(b'KEEP');ca=ssl.PEM_cert_to_DER_cert((crypto/'samples/cert-root-rsa.pem').read_text());(folder/'repository/ca.der').write_bytes(ca)
  with socket.socket() as reserve:reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
  env=dict(os.environ,HB_SIGNAL_CUT=str(cut),HB_META_TEST_PORT=str(port),HB_TEST_REPOSITORY=str(folder/'repository'),HB_TEST_CA_HASH=hashlib.sha256(ca).hexdigest(),HB_TASK_APPS=str(folder/'apps'),HB_TASK_PACKAGES=str(folder/'packages'),HB_TASK_CACHE=str(folder/'cache'))
  command=['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(work/'test.arm')]
  for scenario in ('signal-payload','recover-back','recover-restart'):
   if scenario!='signal-payload':(folder/'repository/repository.conf').unlink()
   run=subprocess.run(command,env=dict(env,HB_TASK_SCENARIO=scenario),capture_output=True,text=True,timeout=30);assert run.returncode==0,(scenario,run.returncode,run.stderr[-6000:]);traces.append(run.stderr)
   if scenario=='signal-payload':
    cache_before=snapshot(folder/'cache');packages_before=snapshot(folder/'packages')
    assert len(cache_before)==1 and list(cache_before.values())==[base['expected']['app'][:cut]]
    assert (folder/'packages/.download-hello.intent').exists() and (folder/'packages/.bundle-hello').is_dir()
    assert snapshot(folder/'apps')=={'unrelated':b'KEEP'}
   elif scenario=='recover-back':assert snapshot(folder/'cache')==cache_before and snapshot(folder/'packages')==packages_before
   else:
    assert snapshot(folder/'apps/hello')==base['expected'] and not list((folder/'cache').iterdir()) and not list((folder/'packages').iterdir())
    executed=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(folder/'apps/hello/app'),'--help'],capture_output=True,text=True,timeout=15);assert executed.returncode==0 and 'Hello Walkman' in executed.stdout;traces.append(executed.stderr)
  assert (folder/'apps/unrelated').read_bytes()==b'KEEP'
 rows.append({'cut_bytes':cut,'back_preserves':True,'retry_installs_and_runs':True})
report={'all_bounded_checks_passed':True,'cases':rows,'physical_device_access':False,'trace':'\n'.join(traces),'payload_first_byte_retained':True,'record_and_partial_bundle_retained':True,'new_process_back_preserves':True,'new_process_explicit_restart_installs':True,'installed_real_ARM_app_executed':True,'app_sha256':hashlib.sha256(base['expected']['app']).hexdigest(),'generator_source':'tools/test_payload_signals.py','generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/test_repository_remote_store.c','tools/download_file_faults.c'] if not Path(p).is_absolute()},'limits':['Local TLS/ARM-QEMU and scripted UI; SIGTERM injected by test write wrapper at exact supplied payload offsets, including full body before completion.','No physical display, Wi-Fi, Sony FAT, IPC or firmware qualification.']}
(ROOT/'sources/native-payload-signal-tests.json').write_text(json.dumps(report,indent=2)+'\n');print('Real ARM payload SIGTERM -> fresh-process Back/Retry -> installed app execution passed.')
