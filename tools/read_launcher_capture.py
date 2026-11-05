"""Decode a copied diagnostic record on the PC; never access a device implicitly."""
import argparse,json,re
from app_registry import ROOT
from review_managed_remote_profile import receipt,digest
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--review',required=True);p.add_argument('--trace',required=True);a=p.parse_args()
rp,build=receipt(a.review);seed=rp.parent/'launcher-capture.bin';assert digest(seed)==build['seed_sha256']
path=Path(a.trace).resolve();raw=path.read_bytes();assert len(raw)==4096 and raw[:32]==seed.read_bytes()[:32], 'Wrong size or capture identity'
assert raw[4032:]==seed.read_bytes()[4032:], 'Out-of-bounds tail mutation'
payload=raw[32:4032].split(b'\0',1)[0].decode('ascii',errors='strict')
footer=re.search(r'CAPTURE_END status=(\d+) done=([01]) fault=([01])\n$',payload)
report=dict(trace_sha256=digest(path),capture_started=payload.startswith('CAPTURE_BEGIN\n'),
 child_path_refused=payload.startswith('CHILD_PATH_REFUSED\n'),
 exec_errno=[int(x) for x in re.findall(r'EXEC_FAILED errno=(\d+)',payload)],
 stages=re.findall(r'\[X1-LAUNCH-ENTRY\] ([a-z.]+)',payload),capture_complete=bool(footer),
 hardware_success_proven=False,device_accessed=False)
if footer:report.update(wait_status=int(footer[1]),child_reaped=footer[2]=='1',capture_fault=footer[3]=='1')
print(json.dumps(report,indent=2))
