"""Review an idle-exit candidate against the physically failed999846fd package.

PC-only artifact review. No device operations, firmware qualification or repair
claim. Preserve the earlier unexplained packing rejection in the verdict.
"""
import argparse
import gzip
import hashlib
import io
import json
import sys
import tarfile
import time
from app_registry import ROOT
from review_managed_remote_profile import receipt, private, digest
from review_managed_root_capacity import inventory
from release_firmware import pack
from prepare_startup_fix_review import same_loaded_program
sys.path.insert(0, str(ROOT / 'scripts'))
from upg import unpack


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixed-review', required=True)
    p.add_argument('--previous-upg', required=True)
    args = p.parse_args()
    rp, review = receipt(args.fixed_review)
    target = rp.parent / 'startup-delta.json'
    if target.exists():
        raise ValueError('Refuse to replace an existing delta review')
    previous = private(args.previous_upg)
    if digest(previous) != '999846fdc45810edba004059a41bfb267038e3e343970c89695c727302e54ca2':
        raise ValueError('Expected the pinned physically failed package')
    candidate = private(review['artifact'])
    if digest(candidate) != review['sha256']:
        raise ValueError('Candidate changed')
    _, old = unpack(previous.read_bytes(), require_stock=False)
    _, new = unpack(candidate.read_bytes(), require_stock=False)
    if old[:3] != new[:3]:
        raise ValueError('Installation script/kernel/initrd changed')
    before, after = inventory(old[3]), inventory(new[3])
    changed = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
    layout_name = next(k for k in review['inputs'] if '/player-system-layout/' in k)
    lp, layout = receipt(layout_name)
    if digest(lp) != review['inputs'][layout_name]:
        raise ValueError('Layout receipt changed')
    if before.keys() != after.keys():
        raise ValueError('Unexpected file/directory additions or removals')
    allowed = {'usr/local/lib/libx1000-player.so', 'usr/local/lib/x1000-player/SpiderApp',
               'usr/local/bin/SpiderApp'}
    allowed.update(k for k in layout['files'] if k.startswith('usr/local/share/gemini/res/'))
    if not set(changed) <= allowed:
        raise ValueError('Unexpected changes: ' + repr(set(changed) - allowed))
    def wrapper(root):
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(root)), mode='r:') as archive:
            return archive.extractfile('./usr/local/bin/SpiderApp').read()
    wrapper_review = same_loaded_program(wrapper(old[3]), wrapper(new[3]))
    stock = inventory(private('work/upg-jp/verified-3.bin').read_bytes())
    metadata_restored = []
    for name in changed:
        a, b = before[name], after[name]
        metadata = lambda row: {k: v for k, v in row.items() if k not in ('sha256', 'bytes')}
        if metadata(a) != metadata(b):
            if not name.startswith('usr/local/share/gemini/res/') or metadata(b) != metadata(stock[name]):
                raise ValueError('Metadata changed outside exact stock-resource restoration: ' + name)
            metadata_restored.append(name)
        expected = layout['files'][name]
        if b['sha256'] != expected['sha256'] or b['bytes'] != expected['bytes']:
            raise ValueError('Not the reviewed overlay: ' + name)
    # Full-stream decoding, independent extraction and repeated container packing.
    gzip.decompress(new[3])
    extraction = rp.parent / 'rockbox-check'
    for i, component in enumerate(new):
        if component != (extraction / ('part-' + str(i) + '.bin')).read_bytes():
            raise ValueError('Independent Rockbox extraction mismatch')
    for _ in range(3):
        rebuilt = pack(new)
        disk = candidate.read_bytes()
        decoded = unpack(rebuilt, require_stock=False)[1]
        if rebuilt != disk or decoded != new:
            failure=ROOT/'work/container-repeat-failure'/str(time.time_ns())
            failure.mkdir(parents=True)
            (failure/'rebuilt.upg').write_bytes(rebuilt)
            (failure/'disk.upg').write_bytes(disk)
            rows=[]
            for i,(a,b) in enumerate(zip(new,decoded)):
                (failure/('expected-'+str(i)+'.bin')).write_bytes(a)
                (failure/('decoded-'+str(i)+'.bin')).write_bytes(b)
                rows.append(dict(component=i,equal=a==b,expected_sha256=hashlib.sha256(a).hexdigest(),
                                 decoded_sha256=hashlib.sha256(b).hexdigest(),
                                 first_difference=next((j for j,(x,y) in enumerate(zip(a,b)) if x!=y),None)))
            (failure/'failure.json').write_text(json.dumps(dict(rebuilt_equal_disk=rebuilt==disk,
                rebuilt_sha256=hashlib.sha256(rebuilt).hexdigest(),disk_sha256=hashlib.sha256(disk).hexdigest(),
                components=rows),indent=2)+'\n')
            raise ValueError('Container reproducibility/roundtrip failed: '+str(failure))
    report = dict(passed=True, kind='homebrew-idle-exit-regression-delta',
                  candidate_sha256=digest(candidate), previous_sha256=digest(previous),
                  changed_paths=changed, stock_resource_metadata_restored=metadata_restored,
                  wrapper=wrapper_review,
                  original_installer_kernel_initrd_unchanged=True,
                  independent_rockbox_components_equal=True, repeated_container_roundtrips=3,
                  firmware_installed=False, physical_boot_verified=False,
                  earlier_packing_rejection_unexplained=True,
                  limits=['This review does not reproduce or qualify physical Homebrew entry.',
                          'The first rejected in-memory build was not retained; its cause is unknown.'],
                  source_hashes={'tools/review_homebrew_candidate_delta.py':
                                 digest(ROOT / 'tools/review_homebrew_candidate_delta.py')})
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
