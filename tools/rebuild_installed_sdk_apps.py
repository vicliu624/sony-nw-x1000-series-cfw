"""Rebuild installed SDK consumers locally; never installs or accesses devices."""
import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from app_registry import ROOT
from verify_app_package import verify

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--installed',type=Path,required=True);parser.add_argument('--ids',nargs='*');parser.add_argument('--builder-options',type=Path);args=parser.parse_args()
 source=(ROOT/args.installed).resolve()
 if not source.is_relative_to(ROOT/'work'):raise ValueError('Use a private PC inventory')
 installed=json.loads(source.read_text());sdk=(ROOT/'sdk/VERSION').read_text().strip()
 options=json.loads((ROOT/args.builder_options).read_text()) if args.builder_options else {}
 selected=[r for r in installed if r['contract'] and (r['id'] in args.ids if args.ids is not None else r['id'] not in ('qqmusic','espnow-chat'))]
 out=source.parent/('build-'+str(time.time_ns()));out.mkdir()
 rows=[]
 for item in selected:
  ident=item['id'];receipt=ROOT/'work/sdk-services'/ident/'compiler.jsonl'
  before=len(receipt.read_text().splitlines()) if receipt.exists() else 0
  package=out/'packages'/ident;log=out/(ident+'.log');began=time.monotonic()
  with log.open('w') as stream:
   extra=options.get(ident,[])
   if not isinstance(extra,list) or any(not isinstance(value,str) for value in extra):raise ValueError('Builder options must be string argument lists')
   result=subprocess.run([sys.executable,str(ROOT/'tools/build_app.py'),ident,'--output',str(package),*extra],cwd=ROOT,env=dict(os.environ,QEMU_UNSET_ENV='LD_LIBRARY_PATH,LD_PRELOAD'),stdout=stream,stderr=subprocess.STDOUT)
  row=dict(id=ident,built=result.returncode==0,seconds=round(time.monotonic()-began,2),log=log.relative_to(ROOT).as_posix())
  if not result.returncode:
   try:
    info=verify(package);fresh=[json.loads(line) for line in receipt.read_text().splitlines()[before:]]
    if not fresh or any(r['sdk_version']!=sdk or r['exit'] for r in fresh):raise ValueError('Missing successful current-SDK compiler provenance')
    sha=hashlib.sha256((package/'app').read_bytes()).hexdigest()
    row.update(verified=True,sdk=sdk,compiler_commands=len(fresh),version=info['version'],package=package.relative_to(ROOT).as_posix(),sha256=sha,
     installed_sha256=item['installed_sha256'],binary_changed=sha!=item['installed_sha256'],installed_version=item['installed_version'])
   except (ValueError,OSError,KeyError) as error:row.update(verified=False,error=str(error))
  rows.append(row)
  report=dict(sdk=sdk,apps=rows,device_written=False,all_passed=all(r.get('verified',False) for r in rows) and len(rows)==len(selected))
  (out/'review.json').write_text(json.dumps(report,indent=2)+'\n')
  print(json.dumps(row),flush=True)
 print(json.dumps(dict(review=(out/'review.json').relative_to(ROOT).as_posix(),apps=len(rows),all_passed=report['all_passed'],device_written=False)),flush=True)
if __name__=='__main__':main()
