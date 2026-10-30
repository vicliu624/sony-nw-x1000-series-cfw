"""Stage and build S31 firmware under ignored work. Never flashes hardware."""
from pathlib import Path
import argparse,hashlib,json,os,re,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[4]
APP=ROOT/'runtime/apps/glass-marble'
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--menuconfig',action='store_true')
a=p.parse_args()
idf=Path(os.environ['IDF_PATH']).resolve();bsp=Path(os.environ['MOSAICO_BSP']).resolve()
def revision(folder):return subprocess.check_output(['git','-C',str(folder),'rev-parse','HEAD'],text=True).strip()
pins=json.loads((ROOT/'sources/esp-mosaico-glass-marble-sources.json').read_text())
for name,folder in [('bsp',bsp),('esp_idf',idf)]:
 if revision(folder)!=pins[name]['revision']:raise ValueError('Wrong pinned '+name+' revision')
stage=ROOT/'work/glass-marble-mosaico-source';stage.mkdir(exist_ok=True)
inputs=[APP/'marble.c',APP/'marble.h',*(APP/'mosaico').rglob('*')]
inputs=[f for f in inputs if f.is_file() and 'managed_components' not in f.parts and '__pycache__' not in f.parts and (f.suffix in ('.c','.h','.txt','.yml','.projbuild') or f.name=='sdkconfig.defaults')]
for source in inputs:
 target=stage/source.relative_to(APP);target.parent.mkdir(parents=True,exist_ok=True)
 if not target.exists() or source.read_bytes()!=target.read_bytes():shutil.copyfile(source,target)
out=ROOT/'work/glass-marble-mosaico-firmware'
config=out/'sdkconfig'
if config.exists():
 text=config.read_text();match=re.search(r'^CONFIG_ESP_MAIN_TASK_STACK_SIZE=(\d+)$',text,re.M)
 if match and int(match[1])<16384:
  text=text[:match.start(1)]+'16384'+text[match.end(1):]
 if config.read_text()!=text:config.write_text(text)
args=[sys.executable,str(idf/'tools/idf.py'),'--preview','-C',str(stage/'mosaico'),'-B',str(out),'-D','SDKCONFIG='+str(out/'sdkconfig')]
if not (out/'sdkconfig').exists():args+=['set-target','esp32s31']
args+=['menuconfig'] if a.menuconfig else ['build']
subprocess.run(args,cwd=ROOT,check=True)
if not a.menuconfig:
 files=[out/'glass_marble.bin',out/'bootloader/bootloader.bin',out/'partition_table/partition-table.bin',out/'flasher_args.json',out/'sdkconfig']
 report={'built':True,'target':'esp32s31','bsp_revision':revision(bsp),'idf_revision':revision(idf),'device_written':False,'hardware_tested':False,'inputs':{f.relative_to(APP).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs},'outputs':{f.relative_to(out).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}
 lock=stage/'mosaico/dependencies.lock'
 if lock.exists():report['dependencies_lock_sha256']=hashlib.sha256(lock.read_bytes()).hexdigest()
 receipt=out/'build-receipt.json';receipt.write_text(json.dumps(report,indent=2)+'\n')
 stack_report=out/'stack-budget.json'
 subprocess.run([sys.executable,str(ROOT/'tools/test_aqua_stack_budget.py'),'--build',str(out),'--report',str(stack_report)],cwd=ROOT,check=True)
 report['stack_budget_passed']=True;report['outputs']['stack-budget.json']=hashlib.sha256(stack_report.read_bytes()).hexdigest()
 receipt.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
