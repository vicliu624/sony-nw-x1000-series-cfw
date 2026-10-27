"""Regress popup pool lifecycle against the missing-image-init negative control."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True);args=parser.parse_args()
out=(ROOT/args.output).resolve()
if not out.is_relative_to(ROOT/'work'):
    raise ValueError('Output must be inside project work/')
out.mkdir(exist_ok=False)
harness=ROOT/'tools/debug/probe_home_feedback_popup.py'
source_hash=hashlib.sha256(harness.read_bytes()).hexdigest()
rows=[]
for name,message,initialized in [('negative','homebrew',False),('homebrew','homebrew',True),('stock22','stock22',True)]:
    target=out/name
    command=[sys.executable,str(harness),'--message',message,'--output',str(target.relative_to(ROOT))]
    if initialized:command.extend(['--native-image-manager','--prepare-cache','--instruction-budget','20000000'])
    run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=180)
    (out/(name+'.stdout')).write_text(run.stdout)
    (out/(name+'.stderr')).write_text(run.stderr)
    assert run.returncode==0,(name,run.stderr)
    report=json.loads((target/'report.json').read_text())
    assert report['test_sha256']==source_hash and not report['stop']
    assert report['candidate_upg_sha256']=='11f466c94d091c2a7bfb905beb3d94f81ab540dcc0bc33c38597c2ae34daa8cd'
    curve=[report['final_pool']['pool_used']]+[x['pool_used'] for x in report['repeat_cycles']]
    constructor_results=[x['result'] for x in report['constructor_trace'] if x['pc']=='0xf344c']
    if initialized:
        assert report['passed'] and curve==[1,1,1,1]
        assert constructor_results==[0,0,0,0]
        assert report['text_control_kind_before_destroy']==12
        assert len(report['cache_cycles'])==4 and all(c['complete'] and c['nonzero_bytes']>0 for c in report['cache_cycles'])
    else:
        assert not report['passed'] and curve==[2,3,4,5]
        assert constructor_results==[0x1003]*4
    rows.append({'case':name,'image_manager_initialized':initialized,'pool_after_each_close':curve,'native_constructor_results':constructor_results,'text_control_kind':report['text_control_kind_before_destroy'],'painted_cache_cycles':len(report['cache_cycles'])})
result={'passed':True,'scope':'Original popup construction/show/commit/frame callbacks/cache paint/destroy in a PC harness, with original libgcc; not complete composition or hardware','cases':rows,'root_cause_in_harness':'Missing original image-manager initialization made text image allocation fail while outer factory returned zero','firmware_changed':False,'hardware_tested':False,'heap_reuse_qualified':False,'harness_sha256':source_hash,'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(out/'regression.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
