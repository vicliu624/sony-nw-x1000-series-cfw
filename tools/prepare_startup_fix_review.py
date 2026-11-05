"""Freeze a one-library startup correction and an untouched stock recovery option."""
import argparse,hashlib,io,json,shutil,sys,tarfile,time
from elftools.elf.elffile import ELFFile
from app_registry import ROOT
from review_managed_remote_profile import private,receipt,digest
from review_managed_root_capacity import inventory
sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack,STOCK_SHA256

def member(root,name):
 with tarfile.open(fileobj=io.BytesIO(root),mode='r:gz') as archive:return archive.extractfile('./'+name).read()
def same_loaded_program(a,b):
 old=ELFFile(io.BytesIO(a));new=ELFFile(io.BytesIO(b))
 first=list(old.iter_segments());second=list(new.iter_segments())
 if old.header!=new.header or len(first)!=len(second):raise ValueError('ELF layout changed outside SDK library')
 if any(x.header!=y.header or x.data()!=y.data() for x,y in zip(first,second)):raise ValueError('Executable segments changed outside SDK library')
 first={s.name:s for s in old.iter_sections()};second={s.name:s for s in new.iter_sections()}
 if first.keys()!=second.keys():raise ValueError('ELF section set changed')
 changed=[]
 for name,x in first.items():
  y=second[name]
  if x.header!=y.header or x.data()!=y.data():
   if x['sh_flags']&2 or y['sh_flags']&2 or name not in ('.strtab','.symtab'):raise ValueError('Non-metadata section changed: '+name)
   changed.append(name)
 return dict(all_program_segments_identical=True,changed_nonallocated_sections=changed)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fixed-review',required=True);parser.add_argument('--previous-upg',required=True);args=parser.parse_args()
 rp,review=receipt(args.fixed_review);fixed=private(review['artifact']);previous=private(args.previous_upg)
 if digest(fixed)!=review['sha256'] or digest(previous)!='562f8801009a5d36d1e10a6c89aff860446b02d8aabed2fb55f1ac5fd2804270':raise ValueError('Expected exact fixed and reported-failing inputs')
 _,new=unpack(fixed.read_bytes(),require_stock=False);_,old=unpack(previous.read_bytes(),require_stock=False)
 if new[:3]!=old[:3]:raise ValueError('Installer/kernel/initrd changed')
 before=inventory(old[3]);after=inventory(new[3]);changes=sorted(name for name in before.keys()|after.keys() if before.get(name)!=after.get(name))
 library='usr/local/lib/libx1000-player.so'
 if library not in changes:raise ValueError('SDK correction missing')
 metadata={}
 for name in changes:
  if name==library:continue
  if name not in ('usr/local/libexec/x1000-player-start','usr/local/libexec/x1000-remote-supervisor'):raise ValueError('Unrelated system file changed: '+name)
  if {k:v for k,v in before[name].items() if k!='sha256'}!={k:v for k,v in after[name].items() if k!='sha256'}:raise ValueError('Executable attributes changed')
  metadata[name]=same_loaded_program(member(old[3],name),member(new[3],name))
 template=ROOT/'work/candidate6-first-device-inputs/sony-updater'
 if digest(template/'NW_WM_FW.UPG')!=STOCK_SHA256:raise ValueError('Original recovery input differs')
 out=ROOT/'work/startup-fix-review'/str(time.time_ns());out.mkdir(parents=True)
 shutil.copytree(template,out/'01_STARTUP_FIX');shutil.copy2(fixed,out/'01_STARTUP_FIX/NW_WM_FW.UPG')
 shutil.copytree(template,out/'02_ORIGINAL_SONY_RECOVERY')
 (out/'READ_FIRST.md').write_text('''# Startup correction review

The reported candidate stalled at Sony's Creating database screen for more than
ten minutes before any main menu or external app. USB was reconnected by the user.

Two cold SDK routing failures were reproduced in original-instruction ARM replay:
stock preparation was consumed before owner binding, and while the SDK was idle
without wireless authority. The correction preserves the stock call in those
cases and retains blocking when SDK resources are live. Cold cases and existing
routing/handoff regressions pass. This does not prove the physical stall's whole
cause or successful device startup.

01_STARTUP_FIX contains the unchanged Sony updater with the corrected diagnostic
UPG. Runtime code changes are confined to the SDK DSO. Two other executables may
differ only in nonallocated ELF symbol metadata; every program segment and ELF
layout is checked identical. No app, kernel, initrd, installer, language resource
or database is modified by this correction. Preserve installed files and PN counters;
do not copy or reinitialize first-use data. No device program has been executed
or firmware flashed by preparation. Run FWUpdater manually only after reviewing
the risk; keep USB connected throughout any update.

02_ORIGINAL_SONY_RECOVERY contains the exact retained Sony Japanese 1.11 package
with its original updater. It is an alternative for a separate manual recovery
decision, not a guaranteed recovery mode. It removes system homebrew integration.
Do not run both folders in succession without reviewing the first outcome.

Both use Sony's original system-formatting update behavior. An interrupted or
failed installation can still prevent boot/reconnection. Do not format the user
volume, delete the music database or repeatedly reset to test this candidate.
''',encoding='utf-8')
 result=dict(prepared=True,ready_to_flash=False,physical_root_cause_confirmed=False,device_accessed=False,
  previous_sha256=digest(previous),fixed_sha256=digest(fixed),fixed_bytes=fixed.stat().st_size,
  changed_system_files=changes,runtime_changed_system_files=[library],metadata_only_executables=metadata,first_three_components_unchanged=True,external_files_reinstall_required=False,
  stock_recovery_sha256=STOCK_SHA256,
  files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in out.rglob('*') if p.is_file()})
 (out/'review.json').write_text(json.dumps(result,indent=2)+'\n')
 (ROOT/'work/startup-fix-review-latest.json').write_text(json.dumps(dict(directory=out.relative_to(ROOT).as_posix(),**result),indent=2)+'\n')
 print(json.dumps(dict(prepared=True,directory=out.relative_to(ROOT).as_posix(),changed_system_files=changes,fixed_bytes=result['fixed_bytes'],physical_boot_proven=False,device_accessed=False),indent=2))
if __name__=='__main__':main()
