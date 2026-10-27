"""Offline dynamic link probe against original libc; not a firmware/app build."""
from pathlib import Path
import gzip,hashlib,io,json,subprocess,tarfile,tempfile,shutil
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/store-stock-link';work.mkdir(exist_ok=True)
version=(ROOT/'VERSION').read_text().strip();candidate=ROOT/'work'/('integration-'+version)
protected=[ROOT/'VERSION',candidate/'manifest.json']+[candidate/f['path'] for f in json.loads((candidate/'manifest.json').read_text())['files']]
def candidate_snapshot():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
before=candidate_snapshot()
packed=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(packed).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(gzip.decompress(packed))) as tar:
 for name in ('libc-2.3.3.so','ld-2.3.3.so'):
  (work/name).write_bytes(tar.extractfile('./lib/'+name).read())
sources=['install_posix','transaction','stage_posix','cleanup_posix','pending_plan','cleanup_plan','bundle_posix','inventory','package','stock_fs_bridge','stock_stat64','session','session_local','view','canvas','ui_loop','catalog_posix','catalog_view','catalog_loop','browser','termination','app']
paths=[ROOT/'runtime/store'/(s+'.c') for s in sources]+[ROOT/'runtime/native/sha256.c',ROOT/'runtime/native/frontend.c',ROOT/'tools/store_link_smoke.c',ROOT/'tools/store_link_fault.c',ROOT/'tools/store_link_start.S']
flags=['-Os','-march=armv5te','-marm','-mfloat-abi=soft','-ffreestanding','-fno-builtin','-fno-pie','-DHB_STORE_SONY_LIBC']
objects=[]
for source in paths:
 obj=work/(source.stem+'.o');subprocess.run(['arm-linux-gnueabi-gcc',*flags,'-c',str(source),'-o',str(obj)],check=True);objects.append(str(obj))
out=work/'store-link-probe'
command=['arm-linux-gnueabi-gcc','-nostdlib','-no-pie','-Wl,--wrap=rename,--wrap=write,--wrap=unlink','-Wl,--hash-style=sysv','-Wl,--dynamic-linker=/lib/ld-linux.so.3','-Wl,-rpath-link,'+str(work),*objects,str(work/'libc-2.3.3.so'),str(work/'ld-2.3.3.so'),'-lgcc','-o',str(out)]
result=subprocess.run(command,capture_output=True,text=True)
report={'physical_device_access':False,'link_passed':result.returncode==0,'link_diagnostics':result.stderr,'native_ready':False,'limits':['Scripted UI and local installer probe, not a deployable store application.','QEMU uses host filesystem; display presentation and touch source are simulated.','No physical-device execution, storage writes or firmware package.']}
if result.returncode==0:
 elf=ELFFile(io.BytesIO(out.read_bytes()))
 report['interpreter']=[s.get_interp_name() for s in elf.iter_segments() if s['p_type']=='PT_INTERP']
 report['needed']=[t.needed for t in elf.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED']
 report['binary_sha256']=hashlib.sha256(out.read_bytes()).hexdigest()
 tags=[t.entry.d_tag for t in elf.get_section_by_name('.dynamic').iter_tags()]
 assert 'DT_HASH' in tags and 'DT_GNU_HASH' not in tags
 report['hash_style']='sysv'
 # Resolve only original runtime files, never the host cross sysroot.
 alias=work/'libc.so.6'
 if not alias.exists():alias.symlink_to('libc-2.3.3.so')
 try:
  with tempfile.TemporaryDirectory(prefix='files-',dir=work) as temp:
   base=Path(temp);fixture=base/'fixture.dat';fixture.write_bytes(b'stock-file-fixture\n')
   apps=base/'apps';apps.mkdir();(apps/'unrelated.dat').write_bytes(b'KEEP')
   payload=out.read_bytes()
   for revision in (1,2,3):
    package=base/('package'+str(revision));package.mkdir();(package/'assets').mkdir()
    manifest=f'api=1\nid=demo\nname=Demo\nversion=0.1.{revision}\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(payload)}\nsha256={hashlib.sha256(payload).hexdigest()}\n'.encode()
    files={'app':payload,'app.ini':manifest,'assets/theme.dat':('theme '+str(revision)).encode()}
    for name,data in files.items():(package/name).write_bytes(data)
    index=b'HBFILES1\n'+b''.join(f'{hashlib.sha256(data).hexdigest()} {len(data)} {name}\n'.encode() for name,data in sorted(files.items()))
    (package/'files.sha256').write_bytes(index)
   (base/'package3/assets/theme.dat').write_bytes(b'corrupt-resource')
   def fingerprint(folder):
    return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
   sources_before={i:fingerprint(base/('package'+str(i))) for i in (1,2,3)}
   inbox=base/'inbox';inbox.mkdir();shutil.copytree(base/'package1',inbox/'demo')
   shutil.copytree(base/'package3',inbox/'bad');(inbox/'linked').symlink_to(base/'package1',target_is_directory=True)
   (inbox/'.ignored').mkdir();inbox_before=fingerprint(inbox)
   run=subprocess.run(['qemu-arm','-cpu','arm926','-strace',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(out),str(fixture),temp,str(apps),str(base/'package1'),str(base/'package2'),str(base/'package3'),str(inbox)],capture_output=True,text=True,timeout=15)
   if run.returncode==0:
    expected={str(p.relative_to(base/'package2')):p.read_bytes() for p in (base/'package2').rglob('*') if p.is_file()}
    actual={str(p.relative_to(apps/'demo')):p.read_bytes() for p in (apps/'demo').rglob('*') if p.is_file()}
    assert actual==expected and (apps/'unrelated.dat').read_bytes()==b'KEEP'
    assert {p.name for p in apps.iterdir()}=={'demo','unrelated.dat','.store-lock'}
    assert sources_before=={i:fingerprint(base/('package'+str(i))) for i in (1,2,3)}
    report['resource_install_update_recover_verified']=True
    report['scripted_ARM_touch_ui_with_real_installer']=True
    assert fingerprint(inbox)==inbox_before
    report['stock_libc_catalog_scan']={'valid_packages':1,'rejected_entries':2,'cancel_clears_list':True,'inbox_unchanged':True,'draw_select_and_install_selected_source':True}
    report['stock_libc_refusal_paths']={'insufficient_space':True,'cancelled':True,'corrupt_resource':True,'final_live_matches_second_package':True,'source_packages_unchanged':True}
    interruptions=[]
    for operation,nth in [('apply',1),('apply',2),('write',2),('write',4),('unlink',1),('unlink',3)]:
     fault_root=base/('fault-apps-'+operation+str(nth));fault_root.mkdir()
     shutil.copytree(base/'package1',fault_root/'demo')
     (fault_root/'save.dat').write_bytes(b'KEEP SAVE')
     def transaction(action,point):
      return subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(out),'--transaction',action,str(fault_root),str(base/'package2'),str(point)],capture_output=True,text=True,timeout=15)
     interrupted=transaction(operation,nth);assert interrupted.returncode==90,(operation,nth,interrupted.returncode,interrupted.stderr)
     interrupted_roles={role:sorted(fingerprint(fault_root/role)) for role in ('demo','.install-demo','.backup-demo') if (fault_root/role).is_dir()}
     recovered=transaction('recover',0);assert recovered.returncode==0,(nth,recovered.returncode,recovered.stderr)
     live=fingerprint(fault_root/'demo')
     assert live in (sources_before[1],sources_before[2]),(nth,'incomplete recovered LIVE')
     recovered_revision=1 if live==sources_before[1] else 2
     retried=transaction('apply',0);assert retried.returncode==0,(nth,retried.returncode,retried.stderr)
     assert fingerprint(fault_root/'demo')==sources_before[2]
     assert {p.name for p in fault_root.iterdir()}=={'demo','save.dat','.store-lock'}
     assert (fault_root/'save.dat').read_bytes()==b'KEEP SAVE'
     interruptions.append({'operation':'rename' if operation=='apply' else operation,'after_successful_call':nth,'interrupted_roles':interrupted_roles,'interrupted_exit':90,'recovery_exit':0,'recovered_revision':recovered_revision,'retry_installed_second_revision':True,'save_unchanged':True})
    assert sources_before=={i:fingerprint(base/('package'+str(i))) for i in (1,2,3)}
    report['interruption_recovery']=interruptions
    cancel_root=base/'cancel-apps';cancel_root.mkdir();shutil.copytree(base/'package1',cancel_root/'demo')
    (cancel_root/'save.dat').write_bytes(b'KEEP SAVE')
    cancelled=subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(out),'--cancel-copy',str(cancel_root),str(base/'package2')],capture_output=True,text=True,timeout=15)
    assert cancelled.returncode==0,('copy cancellation',cancelled.returncode,cancelled.stderr)
    assert fingerprint(cancel_root/'demo')==sources_before[1]
    assert (cancel_root/'save.dat').read_bytes()==b'KEEP SAVE'
    assert {p.name for p in cancel_root.iterdir()}=={'demo','save.dat','.store-lock'}
    report['external_stop_during_copy']={'passed':True,'trigger':'after second successful write','initial_result':'recovery required; further writes stopped','new_install_blocked':True,'old_live_unchanged':True,'explicit_recovery_complete':True,'save_unchanged':True}
    signal_root=base/'signal-apps';signal_root.mkdir();shutil.copytree(base/'package1',signal_root/'demo')
    signal_test=subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(out),'--signal-copy',str(signal_root),str(base/'package2')],capture_output=True,text=True,timeout=15)
    assert signal_test.returncode==0,('signal copy',signal_test.returncode,signal_test.stderr)
    assert fingerprint(signal_root/'demo')==sources_before[1]
    assert {p.name for p in signal_root.iterdir()}=={'demo','.store-lock'}
    report['stock_libc_SIGTERM_during_copy']={'passed':True,'repeated_signal_handled':True,'previous_handler_restored':True,'old_live_preserved':True,'explicit_recovery_complete':True}
    selection_root=base/'selection-apps';selection_root.mkdir();shutil.copytree(base/'package1',selection_root/'demo')
    selected=base/'selected-package';replacement=base/'replacement-package'
    shutil.copytree(base/'package1',selected);shutil.copytree(base/'package2',replacement)
    changed=subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(out),'--selection-change',str(selection_root),str(selected),str(replacement)],capture_output=True,text=True,timeout=15)
    assert changed.returncode==0,('selection change',changed.returncode,changed.stderr)
    assert fingerprint(selection_root/'demo')==sources_before[1]
    assert {p.name for p in selection_root.iterdir()}=={'demo'}
    assert fingerprint(selected)==sources_before[2] and fingerprint(base/'selected-package-old')==sources_before[1]
    report['changed_valid_package_before_confirmation']={'passed':True,'same_path_replaced_by_another_valid_version':True,'rejected_before_lock_or_transaction_files':True,'live_unchanged':True}
    browser_root=base/'browser-apps';browser_root.mkdir()
    browser_checks=[]
    for mode in ('--browser','--browser-stop','--browser-error'):
     prior=fingerprint(browser_root)
     browser_run=subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(out),mode,str(browser_root),str(inbox)],capture_output=True,text=True,timeout=15)
     assert browser_run.returncode==0,(mode,browser_run.returncode,browser_run.stderr)
     if mode=='--browser':assert fingerprint(browser_root/'demo')==sources_before[1]
     else:assert fingerprint(browser_root)==prior
     browser_checks.append({'scenario':mode,'exit':0})
    assert fingerprint(inbox)==inbox_before
    report['unified_browser_checks']=browser_checks
    app_root=base/'app-scope-apps';app_root.mkdir();app_checks=[]
    self_packages=base/'self-packages';self_packages.mkdir();shutil.copytree(base/'package1',self_packages/'demo')
    own=self_packages/'store';own.mkdir();(own/'app').write_bytes(payload)
    (own/'app.ini').write_text(f'api=1\nid=store\nname=Store update\nversion=9.0.0\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(payload)}\nsha256={hashlib.sha256(payload).hexdigest()}\n')
    self_before=fingerprint(self_packages)
    for mode in ('--app','--app-open-fail','--app-stop-open','--app-self'):
     prior=fingerprint(app_root)
     app_run=subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(out),mode,str(app_root),str(self_packages if mode=='--app-self' else inbox)],capture_output=True,text=True,timeout=15)
     assert app_run.returncode==0,(mode,app_run.returncode,app_run.stderr)
     if mode=='--app':assert fingerprint(app_root/'demo')==sources_before[1]
     else:assert fingerprint(app_root)==prior
     app_checks.append({'scenario':mode,'open_close_exactly_once':True,'passed':True})
    report['app_scope_checks']=app_checks
    assert fingerprint(self_packages)==self_before
    scan_checks=[]
    for label,ids,invalid,expected in [('sorted',['zeta','alpha'],0,2),('max32',[f'p{i:02}' for i in range(32)],0,32),('over33',[f'p{i:02}' for i in range(33)],0,-1),('children64',[],64,0),('children65',[],65,-1)]:
     folder=base/label;folder.mkdir()
     for id in ids:
      child=folder/id;child.mkdir()
      manifest=f'api=1\nid={id}\nname={id}\nversion=0.1.0\ntarget=sony-nw-x1000-jp\nexec=app\nbytes={len(payload)}\nsha256={hashlib.sha256(payload).hexdigest()}\n'.encode()
      (child/'app').write_bytes(payload);(child/'app.ini').write_bytes(manifest)
     for i in range(invalid):(folder/f'invalid{i:02}').write_bytes(b'not a directory')
     prior=fingerprint(folder)
     sorted_ids=sorted(ids)
     check=subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(out),'--scan',str(folder),str(expected),str(invalid),sorted_ids[0] if sorted_ids else '-',sorted_ids[-1] if sorted_ids else '-'],capture_output=True,text=True,timeout=30)
     assert check.returncode==0,(label,check.returncode,check.stderr)
     assert fingerprint(folder)==prior
     scan_checks.append({'case':label,'expected_valid_count':expected,'passed':True,'files_unchanged':True})
    alias_root=base/'inbox-alias';alias_root.symlink_to(inbox,target_is_directory=True)
    check=subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(out),'--scan',str(alias_root),'-1','0','-','-'],capture_output=True,text=True,timeout=15)
    assert check.returncode==0,('root alias',check.returncode,check.stderr)
    scan_checks.append({'case':'noncanonical-symlink-root','passed':True})
    report['stock_libc_catalog_boundaries']=scan_checks
  report['qemu_smoke']={'exit':run.returncode,'stdout':run.stdout,'stderr':run.stderr,'passed':run.returncode==0 and run.stdout=='stock-libc-smoke-ok\n'}
 except subprocess.TimeoutExpired:
  report['qemu_smoke']={'passed':False,'timeout_seconds':15}
 # Same objects/startup/runtime, one link option changed: retain the exact
 # loader failure as a negative control for the compatibility regression.
 control=work/'gnu-hash-control'
 control_command=[x.replace('--hash-style=sysv','--hash-style=gnu') if x.startswith('-Wl,--hash-style=') else x for x in command]
 control_command[-1]=str(control)
 subprocess.run(control_command,check=True,capture_output=True,text=True)
 control_elf=ELFFile(io.BytesIO(control.read_bytes()))
 control_tags=[t.entry.d_tag for t in control_elf.get_section_by_name('.dynamic').iter_tags()]
 assert 'DT_GNU_HASH' in control_tags and 'DT_HASH' not in control_tags
 try:
  negative=subprocess.run(['qemu-arm','-cpu','arm926',str(work/'ld-2.3.3.so'),'--library-path',str(work),str(control)],capture_output=True,text=True,timeout=15)
  report['gnu_hash_negative_control']={'exit':negative.returncode,'stdout':negative.stdout,'stderr':negative.stderr,'reproduced_SIGSEGV':negative.returncode==-11}
 except subprocess.TimeoutExpired:
  report['gnu_hash_negative_control']={'reproduced_SIGSEGV':False,'timeout_seconds':15}
report['source_hashes']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
assert before==candidate_snapshot()
report['candidate_version']=version;report['candidate_unchanged']=True
(ROOT/'sources/native-store-stock-link.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('source_hashes','qemu_smoke')},indent=2))
print('QEMU smoke passed:',report.get('qemu_smoke',{}).get('passed',False))
raise SystemExit(result.returncode or (0 if report.get('qemu_smoke',{}).get('passed') and report.get('gnu_hash_negative_control',{}).get('reproduced_SIGSEGV') else 2))
