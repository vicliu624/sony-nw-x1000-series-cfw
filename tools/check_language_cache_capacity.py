"""Measure resource feedback in a copied PC ext2 model; never player storage."""
from pathlib import Path
import json,hashlib,re,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'work/language-cache-capacity-review-1';out.mkdir(exist_ok=False)
source=ROOT/'work/external-language-capacity-review-3/candidate-model.img';image=out/'candidate-model.img';assert source.is_file() and not source.is_symlink();assert out.resolve().is_relative_to((ROOT/'work').resolve());shutil.copyfile(source,image)
overlay={'usr/local/bin/SpiderApp':ROOT/'work/external-language-bridge-10-process-cache-final/SpiderApp.external-language.analysis-only.elf'}

def stats(p):
 s=subprocess.check_output(['debugfs','-R','stats',str(p)],text=True,stderr=subprocess.DEVNULL)
 return {k:int(re.search(r'^'+re.escape(k)+r':\s+(\d+)',s,re.M).group(1)) for k in ['Free blocks','Reserved block count','Block size','Free inodes']}
before=stats(image);commands=[]
for name,path in overlay.items():
 assert re.fullmatch(r'[A-Za-z0-9_./-]+',name) and path.is_file()
 if not name.endswith('ucs2-dev-sid-999-99.swd'):commands.append('rm /'+name)
 commands.extend(['write '+str(path)+' /'+name,'set_inode_field /'+name+' mode '+('0100755' if name.endswith('/SpiderApp') else '0100644'),'fallocate /'+name+' 0 '+str((path.stat().st_size+4095)//4096-1)])
script=out/'commands';script.write_text('\n'.join(commands)+'\n')
p=subprocess.run(['debugfs','-w','-f',str(script),str(image)],capture_output=True,text=True);(out/'debugfs.log').write_text(p.stdout+p.stderr);assert p.returncode==0
p=subprocess.run(['e2fsck','-f','-n',str(image)],capture_output=True,text=True);(out/'fsck.log').write_text(p.stdout+p.stderr);assert p.returncode==0
files=[]
for i,(name,path) in enumerate(overlay.items()):
 dumped=out/('readback-'+str(i));subprocess.run(['debugfs','-R','dump /'+name+' '+str(dumped),str(image)],check=True,capture_output=True);assert dumped.read_bytes()==path.read_bytes()
 files.append({'path':name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
after=stats(image);assert after['Free inodes']==before['Free inodes']
report={'passed':True,'scope':'Copied ordinary PC ext2 file with fully allocated modified files; not Sony installer/hardware capacity','image':str(image.relative_to(ROOT)),'before':before,'after':after,'extra_allocated_bytes':(before['Free blocks']-after['Free blocks'])*after['Block size'],'available_nonreserved_bytes':(after['Free blocks']-after['Reserved block count'])*after['Block size'],'new_inodes':0,'readback_files':files,'filesystem_check_exit':p.returncode,'metadata_preservation_claimed':False,'physical_capacity_verified':False,'ready_to_flash':False,'baseline_model_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['passed','extra_allocated_bytes','available_nonreserved_bytes','new_inodes','ready_to_flash']},indent=2))
