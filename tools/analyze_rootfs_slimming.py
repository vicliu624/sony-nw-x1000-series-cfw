"""PC-only footprint/dependency/strip measurement. Does not change device or UPG."""
from pathlib import Path
import hashlib,io,json,math,subprocess,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
work=ROOT/'work/rootfs-slimming-review';work.mkdir(parents=True,exist_ok=True)
archive=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(archive).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as t:
 files={m.name.removeprefix('.'):t.extractfile(m).read() for m in t if m.isfile()}
groups={
 'factory_assets':'/usr/local/share/mptapp/',
 'factory_program':'/usr/local/bin/mptapp',
 'tests':'/usr/local/test/',
 'browser_fonts':'/usr/local/share/WBROWSER/',
 'japanese_input':'/usr/local/share/genesys/',
 'dictionaries':'/usr/local/share/dic/',
 'sony_fonts':'/usr/local/share/gemini/res/font/',
 'sony_ui':'/usr/local/share/GUI/',
}
summary={}
for name,prefix in groups.items():
 chosen={p:b for p,b in files.items() if p.startswith(prefix)}
 references=[p for p,b in files.items() if not p.startswith(prefix) and prefix.rstrip('/').encode() in b]
 summary[name]={'prefix':prefix,'regular_file_bytes':sum(map(len,chosen.values())),'file_count':len(chosen),'literal_external_references':references,'reference_limit':'Literal-byte references only, not dynamic path construction or runtime coverage.'}
elfs=[];debug=[]
for path,data in files.items():
 if data[:4]!=b'\x7fELF':continue
 elf=ELFFile(io.BytesIO(data))
 dynamic=elf.get_section_by_name('.dynamic')
 needed=[tag.needed for tag in dynamic.iter_tags() if tag.entry.d_tag=='DT_NEEDED'] if dynamic else []
 ds=sum(s['sh_size'] for s in elf.iter_sections() if s.name.startswith(('.debug','.zdebug','.stab')))
 elfs.append({'path':path,'bytes':len(data),'needed':needed,'debug_section_bytes':ds,'type':elf['e_type']})
 if ds:
  target=work/'stripped-debug'/path.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True)
  original=work/'original-elf'/path.lstrip('/');original.parent.mkdir(parents=True,exist_ok=True);original.write_bytes(data)
  subprocess.run(['arm-linux-gnueabi-strip','--strip-debug','-o',str(target),str(original)],check=True,capture_output=True)
  out=target.read_bytes();after=ELFFile(io.BytesIO(out))
  for s in elf.iter_sections():
   if s['sh_flags']&2:
    peer=after.get_section_by_name(s.name)
    assert peer is not None and peer.data()==s.data(),(path,s.name)
  debug.append({'path':path,'before':len(data),'after':len(out),'saved':len(data)-len(out),'data_block_savings_model':(math.ceil(len(data)/4096)-math.ceil(len(out)/4096))*4096,'allocated_section_bytes_identical':True,'limitations':'Allocated section equality is not execution/loader/module qualification.'})
report={'player_modified':False,'firmware_created':False,'stock_rootfs_sha256':hashlib.sha256(archive).hexdigest(),'groups':summary,'elfs':elfs,'strip_debug_measurements':debug,'strip_debug_saved_bytes':sum(x['saved'] for x in debug),'strip_debug_data_block_savings_model':sum(x['data_block_savings_model'] for x in debug),'limits':['Offline stock rootfs, not every currently installed file.','Models omit filesystem metadata/indirect-block changes and cannot be summed with overlapping file-removal groups.','Unused loaded status or absent DT_NEEDED is not proof a component is removable.']}
(work/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'groups':summary,'ELF_count':len(elfs),'debug_ELF_count':len(debug),'strip_debug_saved_bytes':report['strip_debug_saved_bytes'],'largest_debug_savings':sorted(debug,key=lambda r:r['saved'],reverse=True)[:8]},indent=2))
