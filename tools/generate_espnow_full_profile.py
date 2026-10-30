"""Render a compiled internal runtime profile from a verified full-radio build."""
from pathlib import Path
import argparse,hashlib,json
from build_espnow_full_radio import ROOT,construct

def render(directory):
 directory=Path(directory);manifest=json.loads((directory/'manifest.json').read_text())
 stock=(directory/'stock/sd8686.bin').read_bytes();image,derived=construct(stock,directory/'radio.elf')
 if image!=(directory/'candidate/sd8686.bin').read_bytes():raise ValueError('candidate/ELF mismatch')
 for name in ('profile','candidate_sha256','controls','immutable_segments','startup_only_segments'):
  if derived[name]!=manifest[name]:raise ValueError('manifest mismatch: '+name)
 for item in manifest['immutable_segments']:
  if item['address']&3 or item['bytes']&3 or item['address']==0x17328:raise ValueError('invalid runtime range')
 l=manifest['controls'];text='/* Generated internal exact-image profile. Reclaimed scatter data excluded. */\n'
 text+='#include "xnow_full_guard.h"\nstatic const struct xnow_full_fingerprint xnow_full_ranges[]={\n'
 for r in manifest['immutable_segments']:
  text+=' {0x%xu,%du,{'%(r['address'],r['bytes'])+','.join('0x'+r['sha256'][i:i+2] for i in range(0,64,2))+'}},\n'
 text+='};\nstatic const struct xnow_full_profile xnow_full_compiled_profile={{0x%xu,0x%xu,0x%xu},sizeof(xnow_full_ranges)/sizeof(xnow_full_ranges[0]),xnow_full_ranges};\n'%(l['xnow_full_tx']['address'],l['xnow_full_rx']['address'],l['xnow_tx_completion']['address'])
 return text
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('build',type=Path);p.add_argument('output',type=Path);a=p.parse_args();out=a.output.resolve()
 if not out.is_relative_to((ROOT/'work').resolve()):raise ValueError('output must remain under project work')
 out.write_text(render(a.build));print(hashlib.sha256(out.read_bytes()).hexdigest())
