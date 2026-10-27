"""Install a published real ARM app through the store, then execute read-only."""
from pathlib import Path
import runpy,subprocess,tempfile,json,hashlib,os,socket,ssl,argparse
from evidence_checks import verify_report
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--launcher-build-report');parser.add_argument('--report',default='sources/native-real-app-install-tests.json');options=parser.parse_args()
launcher_build=verify_report(ROOT,options.launcher_build_report) if options.launcher_build_report else None
built=runpy.run_path(str(ROOT/'tools/build_hello_app.py'))
transport=runpy.run_path(str(ROOT/'tools/test_package_download_tasks.py'))
publisher=runpy.run_path(str(ROOT/'tools/publish_repository.py'))
config_tool=runpy.run_path(str(ROOT/'tools/prepare_repository_config.py'))
work=ROOT/'work/real-app-install-tests';work.mkdir(exist_ok=True)
version=(ROOT/'VERSION').read_text().strip();package=ROOT/'work/hello-app/package';program=(package/'app').read_bytes();manifest=(package/'app.ini').read_bytes();index=(package/'files.sha256').read_bytes()
assert len(program)>4096 and len(program)<8000 # Exercises multi-chunk client body writes.
runtime=transport['runtime'];crypto=transport['crypto'];tls=transport['tls']
with socket.socket() as reservation:reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
with tempfile.TemporaryDirectory(prefix='fixture-',dir=work) as temporary:
 base=Path(temporary);publication=base/'repository';published=publisher['publish']([package],f'https://localhost:{port}/',publication);catalog=(publication/'web/catalog.txt').read_bytes()
 def array(name,data):return 'static const unsigned char '+name+'[]={'+','.join(str(b) for b in (data or b'\0'))+'};\n'
 header=array('PLAN_MF',manifest)+array('PLAN_IX',index)+array('PLAN_BODY_0',program)+array('PLAN_BODY_1',b'')+array('PLAN_BODY_2',b'')+array('PUBLISHED_CATALOG',catalog)
 header+='static const unsigned char *PLAN_BODIES[]={PLAN_BODY_0,PLAN_BODY_1,PLAN_BODY_2};\nstatic const unsigned PLAN_SIZES[]={'+str(len(program))+',0,0};\nstatic const char *PLAN_PATHS[]={"app","assets/icon.bin","empty.dat"};\n'
 (work/'package_task_fixture.h').write_text(header)
 source=(ROOT/'tools/test_repository_remote_store.c').read_text().replace('../runtime/','../../runtime/').replace('demo','hello').replace('0.1.0',version).replace('unsigned char response[4096]','unsigned char response[8192]')
 anchor='served[3]=(const unsigned char *)listing;sizes[3]=(unsigned)count;';assert source.count(anchor)==1;source=source.replace(anchor,'assert((unsigned)count==sizeof PUBLISHED_CATALOG&&!memcmp(listing,PUBLISHED_CATALOG,sizeof PUBLISHED_CATALOG));served[3]=PUBLISHED_CATALOG;sizes[3]=sizeof PUBLISHED_CATALOG;')
 anchor='if(!strcmp(scenario,"complete"))assert(requests==6);';assert source.count(anchor)==1;source=source.replace(anchor,'if(!strcmp(scenario,"complete"))assert(requests==4);')
 anchor='int config_fd=open(config_path,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);assert(config_fd>=0&&write(config_fd,config_text,(unsigned)text_bytes)==text_bytes&&!close(config_fd));'
 assert source.count(anchor)==1
 source=source.replace(anchor,'int config_fd=open(config_path,O_RDONLY|O_NOFOLLOW);char prepared[4096];assert(config_fd>=0&&read(config_fd,prepared,sizeof prepared)==text_bytes&&!memcmp(prepared,config_text,(unsigned)text_bytes)&&!close(config_fd));')
 generated=work/'driver.c';generated.write_text(source)
 sources=[p for p in transport['sources'] if p not in ('tools/test_download_task.c','tools/download_file_faults.c')]+['tools/repository_record_faults.c',str(generated)]+['runtime/store/'+name+'.c' for name in ('repository','remote_store','metadata_cache','metadata_fetch','remote_catalog','remote_list','package_resume','download_intent','download_record','payload_cache_cleanup','partial_cleanup','download_recovery','package_job','job_ui','canvas')]+['runtime/native/frontend.c']+['runtime/store/'+name+'.c' for name in ('package_assemble','bundle_posix','install_posix','transaction','stage_posix','cleanup_posix','pending_plan')]
 subprocess.run(['arm-linux-gnueabi-gcc','-std=c99','-Os','-Wall','-Wextra','-Werror','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC','-DHB_PLAN_TASKS','-DHB_PACKAGE_ASSEMBLE','-nostdlib','-no-pie','-Wl,--hash-style=sysv','-Wl,--wrap=write,--wrap=fsync,--wrap=close','-Wl,-rpath-link,'+str(runtime),'-I'+str(work),'-I'+str(crypto/'inc'),'-I'+str(crypto/'samples'),'-I'+str(runtime),*sources,str(tls/'arm-build/libbearssl.a'),str(runtime/'libcares.so.2'),str(runtime/'libc.so.6'),str(runtime/'ld-linux.so.3'),'-lgcc','-o',str(work/'test.arm')],cwd=ROOT,check=True)
 cache=base/'cache';packages=base/'packages';apps=base/'apps';configuration=base/'configuration'
 for path in (cache,packages,apps):path.mkdir()
 (apps/'unrelated').write_bytes(b'KEEP');ca=ssl.PEM_cert_to_DER_cert((crypto/'samples/cert-root-rsa.pem').read_text());selected_ca=base/'selected-ca.der';selected_ca.write_bytes(ca)
 prepared_config=config_tool['prepare'](published['catalog_url'],publication/'web/catalog.txt',selected_ca,configuration)
 configuration=configuration/'HOMEBREW/repository'
 config_before={p.name:p.read_bytes() for p in configuration.iterdir()}
 run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(work/'test.arm')],capture_output=True,text=True,timeout=45,env=dict(os.environ,HB_META_TEST_PORT=str(port),HB_TASK_SCENARIO='complete',HB_TASK_CACHE=str(cache),HB_TASK_PACKAGES=str(packages),HB_TASK_APPS=str(apps),HB_TEST_REPOSITORY=str(configuration),HB_TEST_CA_HASH=hashlib.sha256(ca).hexdigest()))
 assert run.returncode==0,(run.returncode,run.stderr[-12000:]);installed=apps/'hello/app';assert installed.read_bytes()==program and (apps/'hello/app.ini').read_bytes()==manifest and (apps/'hello/files.sha256').read_bytes()==index
 assert {p.name:p.read_bytes() for p in configuration.iterdir()}==config_before
 assert not list(cache.iterdir()) and not list(packages.iterdir()) and (apps/'unrelated').read_bytes()==b'KEEP'
 if launcher_build:
  assert launcher_build['passed'] is True
  launcher=ROOT/launcher_build['artifact'];launcher_digest=hashlib.sha256(launcher.read_bytes()).hexdigest();assert launcher_digest==launcher_build['sha256']
  launcher_command=['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(launcher)]
 else:
  launcher=ROOT/('work/integration-'+version+'/external/HOMEBREW/launcher/app')
  launcher_digest=hashlib.sha256(launcher.read_bytes()).hexdigest()
  assert launcher_digest=='b01a35198ef0c7be01a08d4db2f619b2cd93993543b91715fa30d09e9fe61615'
  launcher_command=['qemu-arm','-cpu','arm926','-strace',str(launcher)]
 launcher_checks=[]
 for mode,expected in [('--catalog','hello\tHello Walkman\n'),('--check','hello VERIFIED\n')]:
  checked=subprocess.run(launcher_command+[mode,str(apps)],capture_output=True,text=True,timeout=15)
  # The unrelated regular-file sentinel is deliberately rejected as an app.
  assert checked.returncode==1 and checked.stdout==expected,(mode,checked.returncode,checked.stdout,checked.stderr)
  assert not any(call in checked.stderr.lower() for call in ('socket(','connect(','bind(','sendto(','/dev/fb','/dev/icx_touch_screen'))
  launcher_checks.append({'mode':mode,'exit':checked.returncode,'stdout':checked.stdout,'trace':checked.stderr})
 executed=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(runtime/'ld-linux.so.3'),'--library-path',str(runtime),str(installed),'--help'],capture_output=True,text=True,timeout=15)
 assert executed.returncode==0 and 'Hello Walkman' in executed.stdout and '/dev/fb/' not in executed.stderr and '/dev/icx_touch_screen' not in executed.stderr,(executed.returncode,executed.stderr)
 assert not any(call in executed.stderr.lower() for call in ('socket(','connect(','bind(','sendto(')),executed.stderr
 # A later change on visible storage must not pass launcher's pre-exec check.
 changed=bytearray(program);changed[-1]^=1;installed.write_bytes(changed)
 rejected=subprocess.run(launcher_command+['--check',str(apps)],capture_output=True,text=True,timeout=15)
 assert rejected.returncode==3 and 'hello VERIFIED' not in rejected.stdout,(rejected.returncode,rejected.stdout)
 launcher_checks.append({'mode':'--check after payload corruption','exit':rejected.returncode,'stdout':rejected.stdout,'trace':rejected.stderr})
 installed.write_bytes(program)
 # Invalid manifest must disappear from discovery rather than be executable.
 (apps/'hello/app.ini').write_bytes(manifest.replace(b'exec=app',b'exec=other'))
 rejected=subprocess.run(launcher_command+['--catalog',str(apps)],capture_output=True,text=True,timeout=15)
 assert rejected.returncode==1 and not rejected.stdout,(rejected.returncode,rejected.stdout)
 launcher_checks.append({'mode':'--catalog after invalid manifest','exit':rejected.returncode,'stdout':rejected.stdout,'trace':rejected.stderr})
 (apps/'hello/app.ini').write_bytes(manifest)
 assert installed.read_bytes()==program and (apps/'unrelated').read_bytes()==b'KEEP'
 report={'all_bounded_checks_passed':True,'physical_device_access':False,'program_bytes':len(program),'program_sha256':hashlib.sha256(program).hexdigest(),'published_catalog_sha256':hashlib.sha256(catalog).hexdigest(),'publisher_catalog_used_byte_for_byte':True,'generated_repository_config_used':True,'repository_config_unchanged':True,'repository_config_sha256':prepared_config['config_sha256'],'installed_app_executed_read_only':True,'launcher_sha256':launcher_digest,'launcher_checks':launcher_checks,'corrupt_payload_rejected':True,'invalid_manifest_hidden':True,'executed_output':executed.stdout,'cache_packages_empty':True,'unrelated_data_preserved':True,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources+['tools/test_repository_remote_store.c','tools/download_file_faults.c','tools/publish_repository.py','tools/prepare_repository_config.py','tools/inspect_repository_config.c'] if not Path(p).is_absolute()},'generator_source':'tools/test_real_app_install.py','generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'generated_driver_sha256':hashlib.sha256(source.encode()).hexdigest(),'trace':run.stderr,'execution_trace':executed.stderr,'limits':['Local TLS with public test CA/key; no remote publication or physical player.','Actual native console ABI app, not successful display/touch/Sony return qualification.','Fixture server serves this real native app in one TLS record; client writes it in multiple chunks.','Generated driver parameterizes existing fixture ID/version/body, not production runtime code.']}
 if launcher_build:report['source_hashes'][options.launcher_build_report]=hashlib.sha256((ROOT/options.launcher_build_report).read_bytes()).hexdigest()
 report['launcher_backend']='stock-libc' if launcher_build else 'freestanding'
 output=(ROOT/options.report).resolve();assert output.is_relative_to(ROOT/'sources') and output.suffix=='.json'
 output.write_text(json.dumps(report,indent=2)+'\n');print('Published real C app downloaded, installed, byte-checked and executed under original-libc ARM/QEMU.')
