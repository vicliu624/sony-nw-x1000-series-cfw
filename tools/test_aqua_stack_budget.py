"""Compile the real S31 call-site frames and enforce the aquarium task stack budget."""
from pathlib import Path
import argparse,hashlib,json,re,shlex,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',type=Path,default=ROOT/'work/glass-marble-mosaico-firmware');parser.add_argument('--report',type=Path);args=parser.parse_args()
 build=args.build.resolve();out=ROOT/'work/aqua-stack-budget'/str(time.time_ns());out.mkdir(parents=True)
 commands=json.loads((build/'compile_commands.json').read_text());receipt=json.loads((build/'build-receipt.json').read_text());frames={};hashes={}
 for suffix,key,source in [('/glass-marble-mosaico-source/marble.c','physics',ROOT/'runtime/apps/glass-marble/marble.c'),('/glass-marble-mosaico-source/mosaico/main/main.c','main',ROOT/'runtime/apps/glass-marble/mosaico/main/main.c')]:
  entry=next(x for x in commands if x['file'].endswith(suffix));staged=Path(entry['file'])
  relative=source.relative_to(ROOT/'runtime/apps/glass-marble').as_posix()
  if hashlib.sha256(source.read_bytes()).hexdigest()!=receipt['inputs'][relative]:raise ValueError('Source differs from built firmware: '+key)
  command=shlex.split(entry['command']);command[command.index(str(staged))]=str(source)
  staged_app=ROOT/'work/glass-marble-mosaico-source'
  command=['-I'+str(ROOT/'runtime/apps/glass-marble') if item.startswith('-I') and Path(item[2:]).resolve()==staged_app.resolve() else item for item in command]
  command[command.index('-o')+1]=str(out/(key+'.o'));command+=['-fstack-usage']
  result=subprocess.run(command,cwd=entry['directory'],capture_output=True,text=True)
  (out/(key+'-compiler.log')).write_text(result.stdout+result.stderr);result.check_returncode()
  for line in (out/(key+'.su')).read_text().splitlines():
   name,size,kind=line.split('\t');function=name.rsplit(':',1)[-1]
   if function in ('gm_step','gm_render','app_main'):frames[function]={'bytes':int(size),'kind':kind}
  hashes[source.relative_to(ROOT).as_posix()]=hashlib.sha256(source.read_bytes()).hexdigest()
 config=(build/'config/sdkconfig.h').read_text();budget=int(re.search(r'#define CONFIG_ESP_MAIN_TASK_STACK_SIZE (\d+)',config)[1])
 minimum=frames['app_main']['bytes']+frames['gm_step']['bytes'];reserve=2048
 passed=budget>=8192 and frames['gm_step']['bytes']<=512 and frames['app_main']['bytes']<=1024 and minimum+reserve<=budget
 report={'passed':passed,'configured_main_stack_bytes':budget,'compiler_frames':frames,'main_plus_physics_minimum_bytes':minimum,'additional_reserve_bytes':reserve,'complete_driver_call_graph_proven':False,'source_sha256':hashes,'device_accessed':False}
 text=json.dumps(report,indent=2)+'\n';(out/'report.json').write_text(text)
 if args.report:
  target=args.report.resolve()
  if not target.is_relative_to((ROOT/'work').resolve()):raise ValueError('Report must remain in project work')
  target.write_text(text)
 print(text);return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
