"""Real host thread/cache lifecycle; native Moma calls are explicitly modeled."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1];work=ROOT/'work/player-metadata-async';work.mkdir(exist_ok=True)
sources=['runtime/platform/player/metadata_async.c','runtime/platform/player/local_identity.c','tools/fixtures/player_metadata_async.c'];app=work/'host'
if '--artwork' in sys.argv:
 work=ROOT/'work/player-artwork-async';work.mkdir(exist_ok=True);app=work/'host'
 sources[-1]='tools/fixtures/player_artwork_async.c'
arguments=[];extra=[]
if '--ownership' in sys.argv:
 work=ROOT/'work/player-metadata-ownership'/str(time.time_ns());work.mkdir(parents=True);app=work/'host'
 sources[-1]='tools/fixtures/media_reader_ownership.c';extra=['-Wl,--wrap=pthread_create']
 arguments=[flag for flag in ('--early-refusal','--cleanup-failure','--queued-close-failure','--start-failure-cleanup','--read-success-cleanup') if flag in sys.argv]
 if not arguments:arguments=["--early-refusal"]
subprocess.run(['gcc-12','-std=c99','-O1','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-pthread',*extra,*sources,'-o',str(app)],cwd=ROOT,check=True)
run=subprocess.run([str(app),*arguments],capture_output=True,text=True,timeout=15);(work/'host.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stdout+run.stderr
report=dict(passed=True,scenario=arguments or (["ownership-early-refusal"] if "--ownership" in sys.argv else []),host_sanitizers=True,real_threads=True,native_media_modeled=True,device_accessed=False,stdout=run.stdout,source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources+['runtime/platform/player/metadata_async.h','runtime/platform/player/artwork.h','tools/fixtures/player_metadata_async.c','tools/test_player_metadata_async.py']},limits=['This uses host pthreads, not an emulated/physical Sony LinuxThreads worker.','Original native media ABI/lifetime is covered separately by test_stock_media.py.'])
(work/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
