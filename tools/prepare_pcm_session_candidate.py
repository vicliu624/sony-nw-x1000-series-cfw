"""Prepare candidate9 PCM session handoff locally; never run updater or touch player."""
from pathlib import Path
import argparse,copy,gzip,hashlib,io,json,shutil,struct,subprocess,sys,tarfile,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'));from upg import unpack

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-local-review',required=True,action='store_true');parser.parse_args()
 version=(ROOT/'VERSION').read_text().strip();d=ROOT/'dist'/version;base=d/'diagnostic-review-8';out=d/'diagnostic-review-9';w=ROOT/'work/candidate9-build';kit=d/'first-device-test-candidate9';assert not any(p.exists() for p in [out,w,kit])
 old=base/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG';assert sha(old)=='ebbe63571060b6dbd21dac7fa20ad1c5463428dc7eb13cb966f066715ef5e248'
 entry=ROOT/'work/pcm-session-entry-source';elf=entry/'SpiderApp.session.analysis-only.elf';source_meta=json.loads((entry/'session-report.json').read_text());assert sha(elf)==source_meta['new_sha256'] and source_meta['fresh_source_rebuild_equals_single_byte_patch']
 switch=json.loads((entry/'switcher-report.json').read_text());assert switch['passed'] and switch['candidate_sha256']==sha(elf);assert any(t.get('native_packet_words')==[1060,0,1,6,55,0x30001,1,0]for t in switch['native_homebrew_switch']['trace'])
 launcher=ROOT/'work/pcm-session-launcher/launcher.elf';build=json.loads((launcher.parent/'build.json').read_text());assert build['passed'] and sha(launcher)==build['sha256']
 for name,digest in build['source_hashes'].items():assert sha(ROOT/name)==digest,name
 reports=[]
 for case in ['normal','invalid','crash']:
  p=ROOT/('work/pcm-handoff-mode1/current-'+case+'/report.json');r=json.loads(p.read_text());assert r['passed'] and not r['hardware_tested'];assert next(x['sha256']for x in r['external_input_hashes']if x['path']=='external/HOMEBREW/launcher/app')==sha(launcher)
  for name,digest in r['source_hashes'].items():assert sha(ROOT/name)==digest,name
  reports.append(p)
 _,parts=unpack(old.read_bytes(),require_stock=False);w.mkdir();(out/'firmware').mkdir(parents=True)
 with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz')as src,tarfile.open(w/'rootfs.tar','w',format=tarfile.GNU_FORMAT)as dst:
  members=src.getmembers();assert len(members)==1433;changed=[]
  for m in members:
   item=copy.copy(m)
   if not m.isfile():dst.addfile(item);continue
   before=src.extractfile(m).read();after=elf.read_bytes()if m.name.removeprefix('./')=='usr/local/bin/SpiderApp'else before
   if before!=after:
    assert hashlib.sha256(before).hexdigest()==source_meta['base_sha256'];assert len(after)==len(before);diff=[i for i,(a,b)in enumerate(zip(before,after))if a!=b];assert diff==[0x4ce1c0]and before[diff[0]]==0 and after[diff[0]]==1;changed.append(m.name.removeprefix('./'))
   item.size=len(after);dst.addfile(item,io.BytesIO(after))
  assert changed==['usr/local/bin/SpiderApp']
 root=gzip.compress((w/'rootfs.tar').read_bytes(),compresslevel=9,mtime=0);inputs=[]
 for i,data in enumerate(parts[:3]+[root]):
  p=w/f'part-{i}.bin';p.write_bytes(data);inputs.append(p)
 tool=ROOT/'third_party/rockbox-upgtools/upgtool';upg=out/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG'
 for name,command in [('create',[str(tool),'--no-color','--create','-k','466c8cd0','-s','daefe603',str(upg),*[str(p)for p in inputs]]),('extract',[str(tool),'--no-color','--extract','-k','466c8cd0','-s','daefe603','-o',str(w/'independent-'),str(upg)])]:
  r=subprocess.run(command,capture_output=True,text=True);(w/(name+'.log')).write_text(r.stdout+r.stderr);assert r.returncode==0
 _,decoded=unpack(upg.read_bytes(),require_stock=False)
 for i,data in enumerate(decoded):assert data==inputs[i].read_bytes()==(w/f'independent-{i}.bin').read_bytes()
 shutil.copytree(base/'external',out/'external');shutil.copyfile(launcher,out/'external/HOMEBREW/launcher/app')
 # Normal GBC consumes PCM; it no longer inspects or manages Sony processes.
 gbc=ROOT/'work/emulator-apps/gbc/package';gbc_build=json.loads((ROOT/'work/emulator-apps/gbc/build.json').read_text());assert sha(gbc/'app')==gbc_build['sha256']
 for name,digest in gbc_build['source_hashes'].items():assert sha(ROOT/name)==digest,name
 app_test=json.loads((ROOT/'work/emulator-app-tests/report.json').read_text());assert app_test['passed'];assert next(t['app_sha256']for t in app_test['cases']if t['case']=='gbc-production-storage-rejection-and-touch-return')==sha(gbc/'app')
 audio_test=json.loads((ROOT/'work/gbc-audio-integration/report.json').read_text());assert audio_test['passed']and audio_test['production_app_sha256']==sha(gbc/'app')
 assert b'DSP PID'not in(gbc/'app').read_bytes()
 shutil.copytree(gbc,out/'external/HOMEBREW/apps/gbc')
 review=out/'review';review.mkdir()
 for p in [*reports,entry/'session-report.json',entry/'switcher-report.json',entry/'build.json',launcher.parent/'build.json',ROOT/'work/emulator-app-tests/report.json',ROOT/'work/gbc-audio-integration/report.json']:
  shutil.copyfile(p,review/(p.parent.name+'-'+p.name))
 report={'profile':'pcm-session-handoff-local-review','revision':9,'version':version,'base_upg_sha256':sha(old),'upg_sha256':sha(upg),'upg_bytes':upg.stat().st_size,'rootfs_entries':1433,'changed_system_files':['usr/local/bin/SpiderApp'],'changed_system_bytes':1,'instruction_va':'0x4d61c0','before':'mov r3,#0','after':'mov r3,#1','native_switch_mode':1,'native_quit_notice':4,'original_installer_kernel_initrd_unchanged':decoded[:3]==parts[:3],'logical_system_growth_from_original_bytes':50556,'capacity_model_available_nonreserved_bytes':29003776,'capacity_model_reused_reason':'identical paths, metadata and file sizes to candidate8','launcher_sha256':sha(launcher),'gbc_sha256':sha(gbc/'app'),'platform_owns_handoff':True,'gbc_scans_or_stops_sony_process':False,'hardware_tested':False,'ready_to_flash':False,'device_written':False}
 (review/'verification.json').write_text(json.dumps(report,indent=2)+'\n');(out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n'for p in sorted(out.rglob('*'))if p.is_file()))
 kit.mkdir();shutil.copytree(ROOT/'work/candidate6-first-device-inputs/sony-updater',kit/'01_PC_UPDATE');shutil.copyfile(upg,kit/'01_PC_UPDATE/NW_WM_FW.UPG');shutil.copytree(out/'external',kit/'02_PLAYER_FILES');shutil.copytree(review,kit/'03_RECORDS')
 shutil.copyfile(ROOT/'docs/HARDWARE.md',kit/'START_HERE.md')
 assert sha(kit/'01_PC_UPDATE/FWUpdater.exe')=='3cf7eb2e354d2e6d3f0cddd06ab67755696579a0d2cc85b68672ecc44ccb3c1c'
 (kit/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(kit).as_posix()+'\n'for p in sorted(kit.rglob('*'))if p.is_file()))
 z=d/('NW-X1060-'+version+'-candidate9-pcm-session-manual-test.zip');assert not z.exists()
 with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,6)as a:
  for p in sorted(kit.rglob('*')):
   if p.is_file():a.write(p,p.relative_to(kit).as_posix())
 with zipfile.ZipFile(z)as a:
  assert a.testzip()is None
  for p in kit.rglob('*'):
   if p.is_file():assert a.read(p.relative_to(kit).as_posix())==p.read_bytes()
 (w/'package-audit.json').write_text(json.dumps({**report,'zip_sha256':sha(z),'zip_readback_passed':True},indent=2)+'\n');print(json.dumps({**report,'zip':str(z),'zip_sha256':sha(z)},indent=2))
if __name__=='__main__':main()
