"""Publish verified assets via a draft; published version releases are immutable."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,tempfile
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--repository',required=True);p.add_argument('--tag',required=True);a=p.parse_args()
 folder=a.directory.resolve()
 if not (folder/'release-manifest.json').is_file():
  manifests=list(folder.rglob('release-manifest.json'))
  if len(manifests)!=1 or not manifests[0].resolve().is_relative_to(folder):raise ValueError('Cannot identify unique artifact root')
  folder=manifests[0].parent
 manifest=json.loads((folder/'release-manifest.json').read_text());expected={}
 if a.tag!='v'+manifest['version'] or a.repository!=manifest['repository']:raise ValueError('Release identity mismatch')
 commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
 tagged=subprocess.check_output(['git','rev-parse',a.tag+'^{commit}'],text=True).strip()
 if manifest.get('source_commit')!=commit or tagged!=commit:raise ValueError('Artifact/tag/source commit mismatch')
 for line in (folder/'SHA256SUMS').read_text().splitlines():
  sha,name=line.split('  ',1)
  if Path(name).name!=name or hashlib.sha256((folder/name).read_bytes()).hexdigest()!=sha:raise ValueError('Asset hash mismatch: '+name)
  expected[name]=sha
 expected['SHA256SUMS']=hashlib.sha256((folder/'SHA256SUMS').read_bytes()).hexdigest()
 if set(expected)!={p.name for p in folder.iterdir() if p.is_file()}:raise ValueError('Unexpected release file')
 def gh(*args,check=True):return subprocess.run(['gh',*args],capture_output=True,text=True,check=check)
 endpoint='repos/'+a.repository+'/releases/tags/'+a.tag
 result=gh('api',endpoint,check=False)
 if result.returncode:
  if '404' not in result.stderr:raise RuntimeError(result.stderr)
  gh('release','create',a.tag,'--repo',a.repository,'--verify-tag','--draft','--prerelease','--title','X1000 '+a.tag+' (experimental)','--notes-file',str(folder/'RELEASE_NOTES.md'))
 else:
  existing=json.loads(result.stdout)
  if not existing['draft']:raise FileExistsError('Published release is immutable; use a new version')
  if not {asset['name'] for asset in existing['assets']}<=set(expected):raise ValueError('Draft has unexpected assets')
 files=[str(folder/name) for name in sorted(expected)]
 gh('release','upload',a.tag,'--repo',a.repository,'--clobber',*files)
 release=json.loads(gh('api',endpoint).stdout);assets={x['name']:x for x in release['assets']}
 if set(assets)!=set(expected):raise ValueError('Remote inventory differs')
 for name,sha in expected.items():
  asset=assets[name]
  if asset['size']!=(folder/name).stat().st_size:raise ValueError('Remote size mismatch: '+name)
  if asset.get('digest'):
   if asset['digest']!='sha256:'+sha:raise ValueError('Remote digest mismatch: '+name)
  else:
   with tempfile.TemporaryDirectory(prefix='release-readback-') as temporary:
    gh('release','download',a.tag,'--repo',a.repository,'--pattern',name,'--dir',temporary)
    if hashlib.sha256((Path(temporary)/name).read_bytes()).hexdigest()!=sha:raise ValueError('Remote readback mismatch: '+name)
 gh('release','edit',a.tag,'--repo',a.repository,'--draft=false','--prerelease')
 print('Published and verified: https://github.com/'+a.repository+'/releases/tag/'+a.tag)
if __name__=='__main__':main()
