"""Reject mixed first-use files before creating test materials; PC-only private inputs."""
import argparse,copy,json,subprocess,sys,tempfile
from pathlib import Path
from app_registry import ROOT
parser=argparse.ArgumentParser(description=__doc__)
for name in ('firmware-review','first-use-plan','core2-review','pairing-review'):parser.add_argument('--'+name,required=True)
args=parser.parse_args();plan=json.loads((ROOT/args.first_use_plan).read_text())
area=ROOT/'work/managed-material-negative-tests';area.mkdir(exist_ok=True)
before=set((ROOT/'work/managed-test-materials').iterdir());checked=[]
with tempfile.TemporaryDirectory(dir=area) as directory:
 for target in ('runtime/owner.arm','runtime/config.bin','session.keys'):
  changed=copy.deepcopy(plan)
  next(row for row in changed['files'] if row['relative']==target)['sha256']='0'*64
  path=Path(directory)/'plan.private.json';path.write_text(json.dumps(changed))
  run=subprocess.run([sys.executable,str(ROOT/'tools/prepare_managed_test_materials.py'),
   '--firmware-review',args.firmware_review,'--first-use-plan',str(path),
   '--core2-review',args.core2_review,'--pairing-review',args.pairing_review],cwd=ROOT,capture_output=True,text=True)
  expected='External transport pairing mismatch' if target=='session.keys' else 'Firmware/external runtime mismatch'
  if run.returncode==0 or expected not in run.stderr:raise RuntimeError('Unexpected mismatch result: '+run.stderr)
  checked.append(target)
if set((ROOT/'work/managed-test-materials').iterdir())!=before:raise RuntimeError('Mixed inputs created materials')
print(json.dumps(dict(passed=True,rejected_mixed_inputs=checked,materials_created=False,device_accessed=False,secrets_printed=False),indent=2))
