"""Check PC proposal bytes against the actual C counter store on temporary test data."""
import json,subprocess,tempfile,time
from app_registry import ROOT
from prepare_remote_pn_proposal import records
out=ROOT/'work/remote-pn-proposal-tests'/str(time.time_ns());out.mkdir(parents=True)
binary=out/'check'
sources=['tools/fixtures/remote_pn_proposal.c','runtime/platform/espnow/xnow_pn_file.c','runtime/native/sha256.c']
subprocess.run(['gcc-12','-std=c99','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined',*sources,'-o',str(binary)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(dir=out) as folder:
 from pathlib import Path
 for name,data in records(bytes.fromhex('020102030405'),bytes.fromhex('02060708090a'),bytes(range(32))).items():(Path(folder)/name).write_bytes(data)
 run=subprocess.run([str(binary),folder],capture_output=True,text=True)
 if run.returncode:raise RuntimeError(run.stdout+run.stderr)
 assert 'REMOTE_PN_PROPOSAL_C_READER_AND_NO_RESET_PASS' in run.stdout
print(json.dumps(dict(passed=True,actual_c_storage_reader=True,reserve_and_duplicate_provision_checked=True,host_sanitizers=True,device_accessed=False,pairing_files_modified=False),indent=2))
