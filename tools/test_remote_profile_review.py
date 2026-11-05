"""Reject unusable private factory reviews before compiler/target activity."""
import argparse,copy,hashlib,json,time
from pathlib import Path
import build_player_host as host
parser=argparse.ArgumentParser();parser.add_argument('--profile',type=Path,required=True);args=parser.parse_args()
profile=args.profile.resolve();assert profile.is_relative_to(host.ROOT/'work')
original=json.loads(profile.read_text());out=host.ROOT/'work/remote-profile-review-tests'/str(time.time_ns());out.mkdir(parents=True)
def forbidden(*args,**kwargs):raise AssertionError('Invalid profile reached compiler')
host.subprocess.run=forbidden
flags=dict(engine_provider=True,native_prepare=True,builtin_localization=True,native_remote_settings=True,native_wireless_settings=True,native_rf_gate=True)
refusals=[]
for name in ('finite','artifact-hash','source-hash'):
 data=copy.deepcopy(original)
 if name=='finite':data['reusable_sessions']=False
 if name=='artifact-hash':data['sha256']='0'*64
 if name=='source-hash':data['source_hashes'][next(iter(data['source_hashes']))]='0'*64
 path=out/(name+'.json');path.write_text(json.dumps(data))
 try:host.build(**flags,remote_profile=path)
 except ValueError:refusals.append(name)
 else:raise AssertionError(name)
for name,options in (('outside-work',dict(flags,remote_profile=host.ROOT/'VERSION')),('missing-pairing',dict(remote_profile=profile))):
 try:host.build(**options)
 except ValueError:refusals.append(name)
 else:raise AssertionError(name)
print(json.dumps(dict(passed=True,device_accessed=False,compiler_invoked=False,refusals=refusals,source_hashes={p:hashlib.sha256((host.ROOT/p).read_bytes()).hexdigest() for p in ('tools/build_player_host.py','tools/test_remote_profile_review.py')},profile_sha256=hashlib.sha256(profile.read_bytes()).hexdigest()),indent=2))
