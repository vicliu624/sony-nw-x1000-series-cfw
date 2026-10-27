"""Real SIGTERM token cancels real local TLS metadata task without discard."""
from pathlib import Path
import runpy,ast,subprocess,tempfile,os,json,hashlib,ssl,socket
ROOT=Path(__file__).resolve().parents[1];previous=runpy.run_path(str(ROOT/'tools/test_package_download_tasks.py'))
work=ROOT/'work/remote-store-signal-tests';work.mkdir(exist_ok=True);runtime=previous['runtime'];crypto=previous['crypto'];tls=previous['tls']
tree=ast.parse((ROOT/'tools/test_repository_remote_store.py').read_text());assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='sources' for t in n.targets));sources=eval(compile(ast.Expression(assignment.value),'<existing source list>','eval'),{'previous':previous})
text=(ROOT/'tools/test_repository_remote_store.c').read_text().replace('../runtime/',str(ROOT/'runtime')+'/')
text='#define _GNU_SOURCE\n#include <signal.h>\n#include "'+str(ROOT/'runtime/store/termination.h')+'"\n'+text.replace('#define _GNU_SOURCE\n','')
anchor='scenario=getenv("HB_TASK_SCENARIO");assert(scenario);';assert text.count(anchor)==1;text=text.replace(anchor,anchor+'assert(!hb_store_termination_begin());')
anchor='(void)ctx;assert(++steps<200000);';assert text.count(anchor)==1;text=text.replace(anchor,anchor+'if(store.stage==HB_REMOTE_CATALOG&&store.metadata.state==HB_METADATA_FETCHING&&store.metadata.task.phase==HB_NET_TRANSFER){hb_repository_record_exit(1);}')
text=text.replace('.stop=&stop,','.stop=hb_store_termination_flag(),')
anchor='int result=hb_remote_store_run(&store,&config,&p,&io);';assert text.count(anchor)==1
text=text.replace(anchor,anchor+'assert(result<0&&*hb_store_termination_flag()&&store.metadata.task.fd==-1&&!store.metadata.task.dns.channel&&store.job.state==HB_JOB_EMPTY);assert(!hb_store_termination_end());assert(!hb_store_termination_begin());struct hb_metadata_cache previous;unsigned char review[HB_METADATA_CACHE_BYTES];memset(review,0xa5,sizeof review);assert(hb_metadata_cache_inspect(config.cache,config.catalog_url,config.catalog_bytes,config.catalog_sha256,hb_store_termination_flag(),review,sizeof review,&previous)==HB_META_CACHE_PREVIOUS);assert(previous.valid&&previous.actual==1&&!previous.complete);for(unsigned i=0;i<config.catalog_bytes;i++)assert(!review[i]);for(unsigned i=config.catalog_bytes;i<sizeof review;i++)assert(review[i]==0xa5);assert(!hb_store_termination_end());if(peer>=0)assert(!close(peer));assert(!close(listener)&&!close(dns));return 0;')
wrapper=work/'signal_write.c'
wrapper.write_text('#include <signal.h>\n#define __wrap_write hb_repository_regular_write\n#include "'+str(ROOT/'tools/download_file_faults.c')+'"\n#undef __wrap_write\nstatic int armed;void hb_repository_record_exit(int enabled){armed=enabled;}ssize_t __wrap_write(int fd,const void*data,size_t bytes){if(armed&&bytes){armed=0;ssize_t n=__real_write(fd,data,1);if(n==1)raise(SIGTERM);return n;}return hb_repository_regular_write(fd,data,bytes);}\n')
sources=[str(wrapper) if p=='tools/repository_record_faults.c' else p for p in sources]
text=text.replace('if(store.stage==HB_REMOTE_CATALOG&&store.metadata.state==HB_METADATA_FETCHING', 'if(!strcmp(scenario,"signal-metadata")&&store.stage==HB_REMOTE_CATALOG&&store.metadata.state==HB_METADATA_FETCHING')
text=text.replace('if(seed_item>=0){','if(seed_item>=0&&!getenv("HB_SIGNAL_EXISTING")){')
text=text.replace('assert(result<0&&*hb_store_termination_flag()', 'if(!strcmp(scenario,"signal-metadata")){assert(result<0&&*hb_store_termination_flag()')
text=text.replace('assert(!close(listener)&&!close(dns));return 0;\n if(!strcmp', 'assert(!close(listener)&&!close(dns));return 0;}\n if(!strcmp')
runpy.run_path(str(ROOT/'tools/build_hello_app.py'))
package=ROOT/'work/hello-app/package';version=(ROOT/'VERSION').read_text().strip()
expected={name:(package/name).read_bytes() for name in ('app','app.ini','files.sha256')}
def array(name,data):return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in (data or b'\0'))+'};\n'
header=array('PLAN_MF',expected['app.ini'])+array('PLAN_IX',expected['files.sha256'])+array('PLAN_BODY_0',expected['app'])+array('PLAN_BODY_1',b'')+array('PLAN_BODY_2',b'')
header+='static const unsigned char *PLAN_BODIES[]={PLAN_BODY_0,PLAN_BODY_1,PLAN_BODY_2};\nstatic const unsigned PLAN_SIZES[]={'+str(len(expected['app']))+',0,0};\nstatic const char *PLAN_PATHS[]={"app","assets/icon.bin","empty.dat"};\n'
(work/'signal_package_fixture.h').write_text(header)
text=text.replace('"package_task_fixture.h"','"'+str(work/'signal_package_fixture.h')+'"').replace('demo','hello').replace('0.1.0',version).replace('unsigned char response[4096]','unsigned char response[8192]').replace('requests==6','requests==4')
generated=work/'test.c';generated.write_text(text);sources=[str(generated) if p=='tools/test_repository_remote_store.c' else p for p in sources]+['runtime/store/termination.c']
subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-DHB_PLAN_TASKS','-DHB_PACKAGE_ASSEMBLE','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--wrap=write,--wrap=fsync,--wrap=close','-Wl,-rpath-link,'+str(runtime),'-I'+str(crypto/'inc'),'-I'+str(crypto/'samples'),'-I'+str(runtime),'-I'+str(previous['work']),'-I'+str(previous['old_work']),*sources,str(tls/'arm-build/libbearssl.a'),str(runtime/'libcares.so.2'),str(runtime/'libc.so.6'),str(runtime/'ld-linux.so.3'),'-lgcc','-o',str(work/'test.arm')],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temp:
 base=Path(temp)
 for name in ('cache','packages','apps','repository'):(base/name).mkdir()
 (base/'apps/unrelated').write_bytes(b'KEEP');ca=ssl.PEM_cert_to_DER_cert((crypto/'samples/cert-root-rsa.pem').read_text());(base/'repository/ca.der').write_bytes(ca)
 with socket.socket() as reservation:reservation.bind(('127.0.0.1',0));fixed_port=reservation.getsockname()[1]
 env=dict(os.environ,HB_META_TEST_PORT=str(fixed_port),HB_TASK_SCENARIO='signal-metadata',HB_TEST_REPOSITORY=str(base/'repository'),HB_TEST_CA_HASH=hashlib.sha256(ca).hexdigest(),HB_TASK_CACHE=str(base/'cache'),HB_TASK_PACKAGES=str(base/'packages'),HB_TASK_APPS=str(base/'apps'))
 run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(work/'test.arm')],env=env,capture_output=True,text=True,timeout=30);assert run.returncode==0,(run.returncode,run.stderr[-12000:])
 assert (base/'apps/unrelated').read_bytes()==b'KEEP' and len(list((base/'apps').iterdir()))==1 and not list((base/'packages').iterdir())
 retained=[{'name':p.name,'bytes':p.stat().st_size} for p in (base/'cache').iterdir()];assert len(retained)==1 and retained[0]['bytes']==1
 before={p.name:p.read_bytes() for p in (base/'cache').iterdir()}
 command=['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(work/'test.arm')]
 (base/'repository/repository.conf').unlink()
 back=subprocess.run(command,env=dict(env,HB_TASK_SCENARIO='meta-back',HB_SIGNAL_EXISTING='1'),capture_output=True,text=True,timeout=30)
 assert back.returncode==0,(back.returncode,back.stderr[-12000:])
 assert {p.name:p.read_bytes() for p in (base/'cache').iterdir()}==before
 (base/'repository/repository.conf').unlink()
 retry=subprocess.run(command,env=dict(env,HB_TASK_SCENARIO='meta-retry',HB_SIGNAL_EXISTING='1'),capture_output=True,text=True,timeout=30)
 assert retry.returncode==0,(retry.returncode,retry.stderr[-12000:])
 assert {str(p.relative_to(base/'apps/hello')):p.read_bytes() for p in (base/'apps/hello').rglob('*') if p.is_file()}==expected
 executed=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(base/'apps/hello/app'),'--help'],capture_output=True,text=True,timeout=15)
 assert executed.returncode==0 and 'Hello Walkman' in executed.stdout,(executed.returncode,executed.stderr)
 assert not any(c in executed.stderr.lower() for c in ('socket(','connect(','/dev/fb','/dev/icx_touch_screen'))
 assert not list((base/'cache').iterdir()) and not list((base/'packages').iterdir()) and (base/'apps/unrelated').read_bytes()==b'KEEP'
 report={'all_bounded_checks_passed':True,'physical_device_access':False,'trace':run.stderr+back.stderr+retry.stderr+executed.stderr,'installed_real_ARM_app_executed':True,'executed_stdout':executed.stdout,'app_bytes':len(expected['app']),'app_sha256':hashlib.sha256(expected['app']).hexdigest(),'generator_source':'tools/test_remote_store_signals.py','generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'generated_driver_sha256':hashlib.sha256(text.encode()).hexdigest(),'write_wrapper_sha256':hashlib.sha256(wrapper.read_bytes()).hexdigest(),'new_process_back_preserves_actual_partial':True,'new_process_explicit_retry_installs':True,'retained_cache':retained,'production_termination_token_used':True,'partial_cache_reviewed_read_only':True,'unverified_data_cleared':True,'task_fd_closed':True,'resolver_channel_closed':True,'unrelated_data_preserved':True,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/test_repository_remote_store.c','tools/download_file_faults.c'] if not Path(p).is_absolute()},'limits':['Actual local DNS/TLS metadata task canceled by actual termination.c SIGTERM token; script UI explicitly returns stop event.','Signal injected by test wrapper after first real body byte; read-only cache review with a fresh state after resetting the lifecycle token, then fresh processes preserve on Back and explicitly discard/retry to install and execute the real ARM Hello app; not a production native-platform test.','Public local test CA, host filesystem and ARM/QEMU; no Wi-Fi, Sony IPC or hardware qualification.']}
 (ROOT/'sources/native-remote-store-signal-tests.json').write_text(json.dumps(report,indent=2)+'\n')
print('Real SIGTERM -> actual local TLS metadata task cancellation -> closed transport/file, no app writes passed.')
