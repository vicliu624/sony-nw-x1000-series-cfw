"""Stage exact reviewed Remote binaries and public synthetic inputs in a PC guest.

The candidate's supervisor must match the supplied review byte for byte. Only
owner/service/config files enter the new volatile image. Never read pairing
keys, journals or configuration from a physical player or a private proposal.
"""
import hashlib,json,os,struct,subprocess,tarfile
from pathlib import Path
from app_registry import ROOT
from review_managed_remote_profile import receipt,private,digest
from stock_user_volume import verified_inputs

def prepare_runtime(image,candidate_root,review_path,output,has_launcher=False):
 image=private(image);candidate_root=private(candidate_root);output=output.resolve()
 if output!=image.parent or not output.is_relative_to(ROOT/'work'):raise ValueError('Runtime fixture must stay beside its new guest image')
 with image.open('rb') as file:file.seek(82);kind=file.read(8)
 if image.stat().st_size!=64*1024*1024 or kind!=b'FAT32   ':raise ValueError('Expected the synthetic FAT32 guest image')
 path,review=receipt(review_path)
 if not all(review.get(k) for k in ('built','runtime_config','reusable_sessions','owner_mode_view_forwarded')) or review.get('config_template_embedded') is not False:
  raise ValueError('Expected a reviewed runtime-config, mode-view supervisor')
 supervisor=private(review['artifact'])
 if digest(supervisor)!=review['sha256'] or supervisor.stat().st_size!=review['bytes']:raise ValueError('Changed supervisor')
 with tarfile.open(candidate_root,'r:gz') as tar:
  matches=[m for m in tar if m.name.removeprefix('./')=='usr/local/libexec/x1000-remote-supervisor']
  if len(matches)!=1 or not matches[0].isfile() or matches[0].size!=review['bytes']:raise ValueError('Candidate supervisor missing or different')
  if hashlib.sha256(tar.extractfile(matches[0]).read()).hexdigest()!=review['sha256']:raise ValueError('Mixed firmware and runtime supervisor')
 inputs={}
 for name in ('owner','service'):
  item=review['inputs'][name];local=review['local_inputs'][name];source=private(local['local'])
  expected='/contents/HOMEBREW/data/wireless-remote/runtime/'+name+'.arm'
  if item['path']!=expected or local['sha256']!=item['sha256'] or local['bytes']!=item['bytes'] or source.stat().st_size!=item['bytes'] or digest(source)!=item['sha256']:
   raise ValueError('Mixed/changed Remote runtime: '+name)
  inputs[name+'.arm']=source
 if review['inputs']['config']!={'path':'/contents/HOMEBREW/data/wireless-remote/runtime/config.bin','bytes':80,'runtime_state':True}:
  raise ValueError('Unexpected runtime configuration contract')
 generation=review['generation']+987
 config=b'XWRUN002'+struct.pack('<QQ',generation,123456789)+bytes([2,1,2,3,4,5])+b'\0\0'+bytes(range(1,33))+bytes(range(16))
 target=output/'remote-fixture-config.bin'
 with target.open('xb') as file:file.write(config)
 inputs['config.bin']=target
 tools=verified_inputs();env={**os.environ,'MTOOLSRC':'/dev/null'}
 directories=([] if has_launcher else ['::HOMEBREW'])+['::HOMEBREW/data','::HOMEBREW/data/wireless-remote','::HOMEBREW/data/wireless-remote/runtime']
 subprocess.run([str(tools['mmd']),'-i',str(image),*directories],check=True,capture_output=True,env=env)
 copied={}
 for leaf,source in inputs.items():
  destination='::HOMEBREW/data/wireless-remote/runtime/'+leaf
  subprocess.run([str(tools['mcopy']),'-i',str(image),str(source),destination],check=True,capture_output=True,env=env)
  readback=output/('remote-readback-'+leaf)
  subprocess.run([str(tools['mcopy']),'-i',str(image),destination,str(readback)],check=True,capture_output=True,env=env)
  if digest(readback)!=digest(source):raise ValueError('Runtime FAT readback mismatch: '+leaf)
  copied[leaf]=dict(source=source.relative_to(ROOT).as_posix(),sha256=digest(source),bytes=source.stat().st_size)
 result=dict(physical_device_access=False,synthetic_configuration=True,configuration_seed_generation=generation,
  config_generation_pinned=False,pairing_keys_copied=False,packet_numbers_copied=False,radio_payloads_copied=False,
  supervisor_review=path.relative_to(ROOT).as_posix(),supervisor_review_sha256=digest(path),supervisor_sha256=review['sha256'],
  files=copied,fixture_image_sha256=digest(image),source_sha256=digest(Path(__file__)),
  limits=['Guest lacks physical Sony root/hardware qualification; rejection is expected before radio controller mutations.','No production configuration, keys, PN files or radio payloads are staged.'])
 (output/'remote-runtime-fixture.json').write_text(json.dumps(result,indent=2)+'\n')
 return result
