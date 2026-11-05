"""Validate observed original media setup requests against pinned ARM DSP ABI."""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--probe',required=True)
args=parser.parse_args()
directory=(ROOT/args.probe).resolve()
assert directory.is_relative_to(ROOT/'work')
receipt=json.loads((directory/'system-probe.json').read_text())
assert receipt['interdsp_open_probe'] and not receipt['dsp_execution_or_success_modeled']
log=directory/'serial.log'
assert hashlib.sha256(log.read_bytes()).hexdigest()==receipt['source_hashes'][log.relative_to(ROOT).as_posix()]
text=log.read_text(errors='replace')
rows=[[int(x,16) for x in match] for match in re.findall(r'DSP_PROBE_ARGS ([0-9a-f]{8}) ((?:[0-9a-f]{8} ){5}[0-9a-f]{8})',text) for match in [[match[0],*match[1].split()]]]
channels=[r[1:] for r in rows if r[0]==0x40184411]
tasks=[r[1:3] for r in rows if r[0]==0xc0084413]
reads=[r[1:] for r in rows if r[0]==0x80184401]
assert channels==[[direction,channel,0xffffffff,0xffffffff,1,0x1000] for channel in range(3) for direction in range(2)]
assert tasks==[[task,1 if task==2 else 2 if task==3 else 0] for task in range(10)]
assert reads and all(r[:2]==[0,0] and r[2]!=0 and r[3:]==[0x4000,0,0] for r in reads)
report=dict(bounded_request_checks_passed=True,channel_directions=2,channels_per_direction=3,
 buffer_blocks=1,block_words=0x1000,block_bytes=0x4000,task_channels=tasks,
 captured_read_requests=len(reads),nested_read_buffer_dereferenced=False,
 allocation_offsets_requested=True,full_boot_pass=False,physical_failure_reproduced=False,
 findings=['Original media code requests driver-allocated header/buffer offsets (0xffffffff).',
 'SET_CHINFO returns channel metadata to user space; a zero-only success would omit required allocation behavior.',
 'DSP READ takes a 16KiB buffer; message contents and DSP firmware behavior are not yet modeled.'],
 source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),directory/'system-probe.json',log,ROOT/'tools/fixtures/manager_device_preload.c')})
(directory/'dsp-requests.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
