"""Actual unchanged r3 store: fetch HTTPS catalog with real TLS, virtual devices."""
from pathlib import Path
from workflow_paths import composition_path,work_area,evidence_path,stamp_report,write_report
import ssl,contextlib,hashlib,io,json,runpy,shutil,subprocess,tempfile,re,struct,zlib
from local_store_https import repository_fixture
ROOT=Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):base=runpy.run_path(str(ROOT/'tools/test_libc_production_ui.py'))
work=work_area(ROOT,'production-store-trust-review')
composition=base['composition'];store=composition/'external/HOMEBREW/apps/store/app';preload=base['preload'];lib=base['lib']
expected=next(r['sha256'] for r in base['manifest']['files'] if r['path']=='external/HOMEBREW/apps/store/app');assert hashlib.sha256(store.read_bytes()).hexdigest()==expected
with repository_fixture(ROOT/'work/hello-app/package') as fixture:
 wrong_root=ROOT/'work/external-tls-probe/bearssl-0.6/samples/cert-root-rsa.pem'
 wrong_ca=ssl.PEM_cert_to_DER_cert(wrong_root.read_text())
 (fixture['configuration']/'ca.der').write_bytes(wrong_ca)
 config_path=fixture['configuration']/'repository.conf';lines=config_path.read_text().splitlines();config_path.write_text('\n'.join(('ca_sha256='+hashlib.sha256(wrong_ca).hexdigest()) if line.startswith('ca_sha256=') else line for line in lines)+'\n')
 prefix=fixture['area']/'sysroot';(prefix/'lib').mkdir(parents=True)
 resolver=json.loads((ROOT/'sources/native-stock-resolver-probe.json').read_text())
 for name in ('libc.so.6','ld-linux.so.3','libcares.so.2','librt.so.1','libpthread.so.0'):
  original=ROOT/'work/stock-resolver-probe'/name;assert hashlib.sha256(original.read_bytes()).hexdigest()==resolver['libraries'][name]['sha256'];shutil.copyfile(original,prefix/'lib'/name)
 home=prefix/'contents/HOMEBREW';home.mkdir(parents=True)
 shutil.copytree(fixture['configuration'],home/'repository');(home/'cache').mkdir();(home/'packages').mkdir();(home/'apps').mkdir()
 before={p.name:p.read_bytes() for p in (home/'repository').iterdir()}
 settings={'LD_PRELOAD':str(preload),'HB_TEST_MODE':'loop','HB_TEST_CHILD':'1','HB_TEST_TARGET':'store','HB_TEST_NETWORK':'1','HB_TEST_PREFIX':str(prefix),'HB_TEST_FRAME':str(work/'catalog.rgb565')}
 command=['qemu-arm','-strace','-cpu','arm926','-L',str(prefix),'-0','/contents/HOMEBREW/apps/store/app']
 for key,value in settings.items():command+=['-E',key+'='+value]
 try:run=subprocess.run(command+[str(store)],cwd=ROOT,capture_output=True,text=True,timeout=35)
 except subprocess.TimeoutExpired as error:
  (work/'last-run.log').write_bytes(error.stderr or b'');raise
 (work/'last-run.log').write_text(run.stderr)
 assert run.returncode==0,(run.returncode,run.stderr[-6000:])
 assert 'STORE ERROR' in run.stderr and 'STORE CATALOG' not in run.stderr,run.stderr[-10000:]
 assert fixture['requests']==[],fixture['requests']
 assert {p.name:p.read_bytes() for p in (home/'repository').iterdir()}==before
 assert not list((home/'cache').iterdir()) and not list((home/'packages').iterdir()) and not list((home/'apps').iterdir())
 assert hashlib.sha256(store.read_bytes()).hexdigest()==expected
 operations=[line for line in run.stderr.splitlines() if re.search(r'\b(?:bind|connect|sendto)\(',line,re.I)]
 assert operations and all('127.0.0.1' in line for line in operations),operations
 raw=(work/'catalog.rgb565').read_bytes();assert len(raw)==240*432*2;rgb=bytearray()
 for offset in range(0,len(raw),2):
  value=int.from_bytes(raw[offset:offset+2],'little');rgb.extend((((value>>11)&31)*255//31,((value>>5)&63)*255//63,(value&31)*255//31))
 def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
 scan=b''.join(b'\0'+rgb[y*720:(y+1)*720] for y in range(432))
 (work/'catalog.png').write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',240,432,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan))+chunk(b'IEND',b''))
 report={'passed':True,'loopback_network_operations':len(operations),'unchanged_store_sha256':expected,'actual_store_untrusted_CA_rejected':True,'HTTP_request_not_sent':True,'request_paths':fixture['requests'],'configuration_unchanged':True,'cache_packages_empty':True,'trace':run.stderr,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [wrong_root,work/'catalog.rgb565',work/'catalog.png',ROOT/'sources/native-stock-resolver-probe.json',*[ROOT/'work/stock-resolver-probe'/name for name in resolver['libraries']],Path(__file__),ROOT/'tools/local_store_https.py',ROOT/'tools/test_libc_production_ui.py',ROOT/'tools/fixtures/device_preload.c',store,preload,composition/'manifest.json']},'hardware_tested':False,'limits':['Actual store ELF and real loopback HTTPS; virtual display/touch and test pathname translation.','No HTTP request or installation; BACK from certificate error page.','No physical Wi-Fi, Sony UI/proxy or USB handoff qualification.']}
 write_report(ROOT,'native-production-store-trust-tests.json',report)
print('Actual selected store rejected unknown server CA before HTTP; temporary files removed, no install.')

