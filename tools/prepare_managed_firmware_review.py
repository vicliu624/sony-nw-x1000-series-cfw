"""Build a private diagnostic UPG from a reviewed layout; never installs or publishes."""
import argparse,copy,gzip,hashlib,io,json,sys,tarfile,time
from app_registry import ROOT
from review_managed_remote_profile import private,receipt,digest
from review_managed_root_capacity import inventory
from release_firmware import pack
sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack

def cold_start_review(path,layout):
 report_path,report=receipt(path)
 if (not report.get('passed') or not report.get('actual_dso_executed') or
     report.get('failed_firmware_sha256') or report.get('expected_command7_result')!='delegate stock'):
  raise ValueError('Passing corrected exact-DSO cold routing review required')
 expected=layout['files']['usr/local/lib/libx1000-player.so']['sha256']
 if report.get('library_sha256')!=expected:raise ValueError('Cold routing review uses another SDK library')
 for name,sha in report['guest_artifact_hashes'].items():
  evidence=(ROOT/name).resolve()
  if not evidence.is_relative_to(ROOT) or not evidence.is_file() or digest(evidence)!=sha:
   raise ValueError('Cold routing guest evidence changed: '+name)
 return report_path

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--layout-review',required=True)
 parser.add_argument('--capacity-review',required=True)
 parser.add_argument('--localization-firmware',required=True)
 parser.add_argument('--cold-dso-review',required=True,help='Fresh exact-library cold prepare/activation regression')
 parser.add_argument('--settings-count-review',help='Exact native Settings constructor/count regression')
 parser.add_argument('--prepare-exit-review',required=True,help='Fresh native exit idle/live wireless regression')
 parser.add_argument('--remote-page-replay',help='Exact composed Remote page menu and wireless-entry replay')
 args=parser.parse_args();lp,layout=receipt(args.layout_review)
 remote_replay=None
 if layout.get('native_remote_page_review'):
  if not args.remote_page_replay:raise ValueError('Remote page replay required for this layout')
  remote_replay,page=receipt(args.remote_page_replay)
  cases={row['case']:row for row in page.get('cases',[])}
  expected_player=layout['files'][layout['player_payload_path']]['sha256']
  if (not page.get('passed') or page.get('candidate_sha256')!=expected_player or
      not {'entry-and-cancel','query-unavailable','wireless-busy','wireless-restored','wireless-other-row'}<=cases.keys()):
   raise ValueError('Remote page replay does not qualify the selected player')
 cold=cold_start_review(args.cold_dso_review,layout)
 exit_path,exit_report=receipt(args.prepare_exit_review)
 exits={row['case']:row for row in exit_report.get('cases',[])}
 if not exit_report.get('passed') or exits.get('factory-radio-unbound',{}).get('native_prepare_calls')!=1 or exits.get('owned-radio-unbound',{}).get('native_prepare_calls')!=0:
  raise ValueError('Idle/live unbound native exit regression required')
 count_review=None
 if layout['host_build'].get('settings_visible_count_composition'):
  if not args.settings_count_review:raise ValueError('Settings count regression required')
  count_review,count=receipt(args.settings_count_review)
  if (not count.get('passed') or not count.get('exact_host_composition_verified') or
      count.get('kind')!='native-settings-descriptor-count' or
      not count.get('original_settings_request_generated') or
      not count.get('native_pool_and_widget_records_executed') or
      not count.get('baseline_reproduces_ten') or count.get('unchanged_template_count')!=155):
   raise ValueError('Exact Settings count regression did not pass')
  if count['composition']['candidate_sha256']!=layout['files'][layout['player_payload_path']]['sha256']:
   raise ValueError('Settings count regression uses another player')
 cp=private(args.capacity_review);capacity=json.loads(cp.read_text())
 source=private(args.localization_firmware)
 if not capacity['passed'] or capacity['layout_review_sha256']!=digest(lp) or digest(source)!=layout['localization_input_sha256']:raise ValueError('Review/input identity mismatch')
 _,parts=unpack(source.read_bytes(),require_stock=False)
 originals=[private('work/upg-jp/verified-'+str(i)+'.bin').read_bytes() for i in range(4)]
 if hashlib.sha256(pack(originals)).hexdigest()!='002b6720b59f093a84440f554ffabe29f5879646839a5a28d43487b5cb41914b':raise ValueError('Original roundtrip mismatch')
 if parts[:3]!=originals[:3]:raise ValueError('Installer/kernel/initrd differs')
 overlay={}
 for name,row in layout['files'].items():
  path=private(lp.parent/'root-overlay'/name);data=path.read_bytes()
  if len(data)!=row['bytes'] or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Overlay changed')
  overlay[name]=(data,int(row['mode'],8))
 raw=io.BytesIO()
 with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as old,tarfile.open(fileobj=raw,mode='w',format=tarfile.GNU_FORMAT) as new:
  members=old.getmembers();names={m.name.removeprefix('./').rstrip('/') for m in members};written=set()
  for member in members:
   entry=copy.copy(member);name=entry.name.removeprefix('./').rstrip('/')
   if name in overlay:
    if not entry.isfile():raise ValueError('Overlay replaces non-file')
    data,mode=overlay[name];entry.size=len(data);entry.mode=mode;new.addfile(entry,io.BytesIO(data));written.add(name)
   else:new.addfile(entry,old.extractfile(member) if member.isfile() else None)
  missing_dirs=set()
  for name in overlay.keys()-written:
   parent=name.rsplit('/',1)[0]
   while parent not in names:
    missing_dirs.add(parent);parent=parent.rsplit('/',1)[0] if '/' in parent else ''
    if not parent:break
  for name in sorted(missing_dirs,key=lambda p:(p.count('/'),p)):
   entry=tarfile.TarInfo('./'+name);entry.type=tarfile.DIRTYPE;entry.mode=0o755;entry.uid=entry.gid=0;entry.mtime=0;new.addfile(entry)
  for name in sorted(overlay.keys()-written):
   data,mode=overlay[name];entry=tarfile.TarInfo('./'+name);entry.mode=mode
   entry.uid=layout['files'][name].get('uid',0);entry.gid=layout['files'][name].get('gid',0)
   entry.mtime=0;entry.size=len(data);new.addfile(entry,io.BytesIO(data))
 root=gzip.compress(raw.getvalue(),mtime=0)
 result=pack([*originals[:3],root]);_,decoded=unpack(result,require_stock=False)
 if decoded[:3]!=originals[:3] or decoded[3]!=root:
  failure=ROOT/'work/managed-roundtrip-failure'/str(time.time_ns());failure.mkdir(parents=True)
  (failure/'REJECTED.UPG').write_bytes(result)
  expected=[*originals[:3],root]
  rows=[dict(component=i,expected_bytes=len(a),actual_bytes=len(b),
             expected_sha256=hashlib.sha256(a).hexdigest(),actual_sha256=hashlib.sha256(b).hexdigest(),
             first_difference=next((j for j,(x,y) in enumerate(zip(a,b)) if x!=y),None))
        for i,(a,b) in enumerate(zip(expected,decoded))]
  (failure/'failure.json').write_text(json.dumps(dict(rejected=True,components=rows),indent=2)+'\n')
  raise ValueError('Final component roundtrip mismatch; rejected evidence: '+str(failure))
 stock=inventory(originals[3]);final=inventory(decoded[3])
 delta=sum(r['bytes'] for r in final.values())-sum(r['bytes'] for r in stock.values())
 if delta!=capacity['regular_file_delta_bytes']:raise ValueError('Final payload differs from capacity review')
 expected={row['path']:row['candidate'] for row in capacity['changed_paths']}
 for name in stock.keys()|final.keys():
  if name in expected:
   if final.get(name)!=expected[name]:raise ValueError('Final reviewed path differs: '+name)
  elif name not in missing_dirs and stock.get(name)!=final.get(name):raise ValueError('Undeclared root change: '+name)
 out=ROOT/'work/managed-firmware-review'/str(time.time_ns());out.mkdir(parents=True)
 target=out/'DIAGNOSTIC-REVIEW-ONLY.UPG';target.write_bytes(result)
 report=dict(prepared=True,analysis_only=True,ready_to_flash=False,installed=False,device_accessed=False,
  artifact=target.relative_to(ROOT).as_posix(),bytes=len(result),sha256=digest(target),
  original_roundtrip_verified=True,original_installer_kernel_initrd_preserved=True,
  final_root_inventory_verified=True,regular_file_delta_bytes=delta,new_directories=sorted(missing_dirs),
  layout_review_sha256=digest(lp),capacity_review_sha256=digest(cp),
  cold_dso_review=cold.relative_to(ROOT).as_posix(),settings_count_review=count_review.relative_to(ROOT).as_posix() if count_review else None,
  prepare_exit_review=exit_path.relative_to(ROOT).as_posix(),
  remote_page_replay=remote_replay.relative_to(ROOT).as_posix() if remote_replay else None,
  source_hashes={name:digest(ROOT/name) for name in ('tools/prepare_managed_firmware_review.py','tools/review_managed_root_capacity.py','tools/review_managed_remote_profile.py','tools/release_firmware.py','scripts/upg.py','scripts/upg_crypto.py')},
  inputs={path.relative_to(ROOT).as_posix():digest(path) for path in (lp,cp,source,cold,exit_path,count_review,remote_replay) if path},
  limits=['Private diagnostic candidate, not hardware qualified or released.',
   'Original updater reformats system storage; interruption or install failure can still brick the device.',
   'File inventory does not establish physical partition margin, sleep/USB/RF or recovery.',
   'External first-use files and controller provisioning are separate; no automatic installation.'])
 (out/'review.json').write_text(json.dumps(report,indent=2)+'\n')
 (ROOT/'work/managed-firmware-review-latest.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(prepared=True,review=(out/'review.json').relative_to(ROOT).as_posix(),bytes=len(result),ready_to_flash=False,device_accessed=False),indent=2))
if __name__=='__main__':main()
