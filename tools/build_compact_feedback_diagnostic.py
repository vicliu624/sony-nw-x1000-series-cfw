"""Prepare resource-backed feedback UPG for local review only; never install."""
from pathlib import Path
import argparse,copy,gzip,hashlib,io,json,shutil,subprocess,sys,tarfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-local-review',action='store_true');parser.add_argument('--revision',type=int,default=5);args=parser.parse_args();assert args.prepare_local_review and args.revision>4
version=(ROOT/'VERSION').read_text().strip();base=ROOT/'dist'/version/'diagnostic-review-3';out=ROOT/'dist'/version/('diagnostic-review-'+str(args.revision));assert not out.exists()
work=ROOT/'work'/('resource-diagnostic-'+str(args.revision));work.mkdir(exist_ok=False)
subprocess.run([sys.executable,'tools/verify_diagnostic_candidate.py',str(base.relative_to(ROOT))],cwd=ROOT,check=True)
elf_area=ROOT/'work/home-feedback-resource-elf-review-1';resource=ROOT/'work/home-feedback-resource-review-2'
build=json.loads((elf_area/'build.json').read_text());new_elf=elf_area/'SpiderApp.resource.analysis-only.elf';assert sha(new_elf)==build['candidate_sha256']
resource_report=resource/'report.json';resource_data=json.loads(resource_report.read_text());assert resource_data['proposed_sid']==build['sid'] and resource_data['added_tid']==build['tid'];extra='usr/local/share/gemini/res/swd/ucs2-dev-sid-999-99.swd'
overlays={r['path']:resource/'overlay'/r['path'] for r in resource_data['system_entries']}
for r in resource_data['system_entries']:assert sha(overlays[r['path']])==r['new_sha256']
overlays['usr/local/bin/SpiderApp']=new_elf
checks=[(elf_area/'integrated-entry-report.json','tools/test_home_feedback_resource_entry.py'),(elf_area/'controller-cleanup-report.json','tools/test_home_feedback_resource_controller.py'),(elf_area/'resource-elf-layout-report.json','tools/test_home_feedback_resource_elf.py')]
for p,tool in checks:
 j=json.loads(p.read_text());assert j.get('passed',True) and j['candidate_sha256']==build['candidate_sha256'] and j['test_sha256']==sha(ROOT/tool)
metric_report=resource/'real-font-layout-report.json';metrics=json.loads(metric_report.read_text())
assert metrics['passed'] and metrics['actual_font_metrics_verified'] and metrics['metric_functions_not_interposed'] and metrics['candidate_sha256']==build['candidate_sha256'] and metrics['test_sha256']==sha(ROOT/'tools/test_home_feedback_real_font_layout.py')
assert len(metrics['cases'])==11 and all(c['real_font_line_count']==2 and c['height_with_real_font']==80 for c in metrics['cases'])
stock=ROOT/'work/updater-jp/NW_WM_FW.UPG';_,parts=unpack(stock.read_bytes());_,baseparts=unpack((base/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG').read_bytes(),require_stock=False);assert parts[:3]==baseparts[:3]
changes=[];tar_path=work/'rootfs.tar'
with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as original,tarfile.open(fileobj=io.BytesIO(baseparts[3]),mode='r:gz') as prior,tarfile.open(tar_path,'w',format=tarfile.GNU_FORMAT) as target:
 assert len(original.getmembers())==len(prior.getmembers())==1432
 for member in original:
  item=copy.copy(member);name=member.name.removeprefix('./')
  if member.isfile():
   before=original.extractfile(member).read();after=overlays[name].read_bytes() if name in overlays else prior.extractfile(member.name).read()
   item.size=len(after);target.addfile(item,io.BytesIO(after))
   if before!=after:changes.append({'path':name,'before_bytes':len(before),'after_bytes':len(after),'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(after).hexdigest(),'new_file':False})
  else:target.addfile(item)
 assert './'+extra not in original.getnames()
 item=copy.copy(original.getmember('./usr/local/share/gemini/res/swd/ucs2-dev-sid-347-00.swd'));item.name='./'+extra;after=overlays[extra].read_bytes();item.size=len(after);target.addfile(item,io.BytesIO(after));changes.append({'path':extra,'before_bytes':0,'after_bytes':len(after),'after_sha256':hashlib.sha256(after).hexdigest(),'new_file':True})
assert len(changes)==16 and sum(c['new_file'] for c in changes)==1
rootfs=work/'rootfs.tar.gz'
with tar_path.open('rb') as a,rootfs.open('wb') as b,gzip.GzipFile(filename='',fileobj=b,mode='wb',mtime=0) as c:shutil.copyfileobj(a,c)
model=ROOT/'work/home-feedback-resource-capacity-review-2/candidate-model.img';capacity=json.loads((model.parent/'report.json').read_text());assert capacity['passed'] and capacity['available_nonreserved_bytes']==29020160
p=subprocess.run(['e2fsck','-f','-n',str(model)],capture_output=True,text=True);(work/'model-fsck.log').write_text(p.stdout+p.stderr);assert p.returncode==0
with tarfile.open(rootfs,'r:gz') as tar:
 for i,c in enumerate(changes):
  dump=work/('model-readback-'+str(i));subprocess.run(['debugfs','-R','dump /'+c['path']+' '+str(dump),str(model)],check=True,capture_output=True)
  assert dump.read_bytes()==tar.extractfile('./'+c['path']).read()
component_files=[]
for i,data in enumerate(parts[:3]):p=work/('component-'+str(i));p.write_bytes(data);component_files.append(p)
out.mkdir(parents=True);(out/'firmware').mkdir();candidate=out/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG';tool=ROOT/'third_party/rockbox-upgtools/upgtool'
run=subprocess.run([str(tool),'--no-color','--create','-k','466c8cd0','-s','daefe603',str(candidate),*[str(p) for p in component_files],str(rootfs)],capture_output=True,text=True);(work/'create.log').write_text(run.stdout+run.stderr);assert run.returncode==0
_,decoded=unpack(candidate.read_bytes(),require_stock=False);assert decoded[:3]==parts[:3] and decoded[3]==rootfs.read_bytes()
prefix=work/'independent-';run=subprocess.run([str(tool),'--no-color','--extract','-k','466c8cd0','-s','daefe603','-o',str(prefix),str(candidate)],capture_output=True,text=True);(work/'extract.log').write_text(run.stdout+run.stderr);assert run.returncode==0
for i,data in enumerate(decoded):assert (work/('independent-'+str(i)+'.bin')).read_bytes()==data
shutil.copytree(base/'external',out/'external');review=out/'review';review.mkdir()
for p,_ in checks:shutil.copyfile(p,review/p.name)
shutil.copyfile(metric_report,review/'real-font-layout-report.json')
shutil.copyfile(resource_report,review/'resource-manifest.json');shutil.copyfile(model.parent/'report.json',review/'capacity-model.json')
report={'profile':'compact-resource-feedback-local-review','version':version,'revision':args.revision,'upg_sha256':sha(candidate),'upg_bytes':candidate.stat().st_size,'original_components_unchanged':True,'original_entries':1432,'rootfs_entries':1433,'system_changes':changes,'logical_system_growth_bytes':sum(c['after_bytes']-c['before_bytes'] for c in changes),'new_system_paths':[extra],'candidate_elf_sha256':build['candidate_sha256'],'model_available_nonreserved_bytes':29020160,'model_current_files_readback':16,'physical_capacity_verified':False,'actual_font_metrics_verified':True,'font_metrics_scope':'Original en/eu/jp/kr LCF and native metrics in Unicorn; graphics/file/libc still fixtures','hardware_tested':False,'device_written':False,'ready_to_flash':False,'inputs':{str(p.relative_to(ROOT)):sha(p) for p in [stock,base/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG',new_elf,resource_report,metric_report,ROOT/'tools/test_home_feedback_real_font_layout.py',Path(__file__)]}}
(review/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
(out/'REVIEW.md').write_text('# Local resource-feedback candidate — do not install\n\nAdds stock SID/SWD/STX feedback routing to the Homebrew entrance. Preserves Sony installer, kernel and initrd. Replaces 15 existing rootfs files and adds one SWD. External apps are unchanged from diagnostic-review-3.\n\nCompact text was checked with original LCF and native metric functions in the emulator. Graphics, file and libc services remain fixtures. Actual display, input, USB handoff, device capacity and recovery remain unverified. The ext2 model is a PC file, not player storage. No updater is included. ready_to_flash=false.\n',encoding='utf-8')
(out/'REVIEW.md').write_text((ROOT/'docs/STATUS.md').read_text(encoding='utf-8'),encoding='utf-8')
(out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(out))+'\n' for p in sorted(out.rglob('*')) if p.is_file()))
print(json.dumps({k:report[k] for k in ['upg_sha256','upg_bytes','rootfs_entries','logical_system_growth_bytes','ready_to_flash']},indent=2))
