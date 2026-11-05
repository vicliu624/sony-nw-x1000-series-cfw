"""Compare a corrected candidate to the pinned physically failed first fix."""
import argparse,hashlib,io,json,sys,tarfile
from app_registry import ROOT
from review_managed_remote_profile import receipt,private,digest
from review_managed_root_capacity import inventory
from prepare_startup_fix_review import same_loaded_program
sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fixed-review',required=True);parser.add_argument('--previous-upg',required=True);parser.add_argument('--settings-count-review');args=parser.parse_args()
rp,review=receipt(args.fixed_review);candidate=private(review['artifact']);previous=private(args.previous_upg)
assert digest(candidate)==review['sha256']
assert digest(previous)=='68e6b5d9659dd4bce756cdfa339cbf4af6db8f105b8276ed0de2648c4c4ebb0c'
_,old=unpack(previous.read_bytes(),require_stock=False);_,new=unpack(candidate.read_bytes(),require_stock=False)
assert old[:3]==new[:3]
def files(root):
 with tarfile.open(fileobj=io.BytesIO(root),mode='r:gz') as archive:
  return {m.name.removeprefix('./'):archive.extractfile(m).read() for m in archive if m.isfile()}
a,b=files(old[3]),files(new[3]);before,after=inventory(old[3]),inventory(new[3])
changed=sorted(p for p in before.keys()|after.keys() if before.get(p)!=after.get(p))
allowed={'etc/AppList.conf','usr/local/bin/SpiderApp','usr/local/lib/libx1000-player.so',
 'usr/local/lib/x1000-player','usr/local/lib/x1000-player/SpiderApp',
 'usr/local/libexec/x1000-player-start','usr/local/libexec/x1000-remote-supervisor'}
assert set(changed)<=allowed,changed
body=b['usr/local/lib/x1000-player/SpiderApp']
if args.settings_count_review:
 from native_settings_count import revert
 _,count=receipt(args.settings_count_review)
 assert count['passed'] and count['exact_host_composition_verified']
 body=revert(body,count['composition'])
assert body==a['usr/local/bin/SpiderApp']
assert 'usr/local/libexec/x1000-player-start' not in b
assert a['usr/local/lib/libx1000-player.so']!=b['usr/local/lib/libx1000-player.so']
assert [line.split() for line in b['etc/AppList.conf'].splitlines() if line.split()[:1]==[b'0x00000001']]==[[b'0x00000001',b'*',b'SpiderApp']]
supervisor=same_loaded_program(a['usr/local/libexec/x1000-remote-supervisor'],b['usr/local/libexec/x1000-remote-supervisor'])
report=dict(passed=True,original_installer_kernel_initrd_unchanged=True,player_payload_byte_identical_after_relocation=not bool(args.settings_count_review),player_payload_identical_after_reverting_declared_count_patch=bool(args.settings_count_review),
 supervisor=supervisor,changed_paths=changed,candidate_sha256=digest(candidate),previous_sha256=digest(previous),
 firmware_installed=False,physical_boot_verified=False,
 source_hashes={p:digest(ROOT/p) for p in ['tools/review_startup_candidate_delta.py','tools/prepare_startup_fix_review.py','tools/review_managed_root_capacity.py']})
(rp.parent/'startup-delta.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
