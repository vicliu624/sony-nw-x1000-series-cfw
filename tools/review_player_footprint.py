"""Read-only file/memory accounting for a player composition; no rootfs/UPG output."""
import argparse,gzip,hashlib,io,json,posixpath,tarfile
from pathlib import Path
from elftools.elf.elffile import ELFFile
from app_registry import ROOT

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--composition',type=Path,required=True)
 parser.add_argument('--output',type=Path,required=True)
 parser.add_argument('--layout',type=Path,help='Optional fresh work directory with three review-only files and metadata; no installer')
 args=parser.parse_args();directory=(ROOT/args.composition).resolve();output=(ROOT/args.output).resolve()
 if not directory.is_relative_to(ROOT/'work') or not output.is_relative_to(ROOT/'work') or output.exists():raise ValueError('Use existing composition and fresh output under work/')
 baseline=directory/'SpiderApp.home-language-player.analysis-only.elf'
 payload=directory/'SpiderApp.home-language-player-met.analysis-only.elf'
 composition=json.loads((directory/'report.json').read_text())
 if not composition['passed'] or digest(payload)!=composition['combined_sha256']:raise ValueError('Composition identity mismatch')
 for name,expected in {**composition['source_hashes'],**composition['home_source_hashes']}.items():
  if digest(ROOT/name)!=expected:raise ValueError('Stale composition: '+name)
 library=ROOT/'work/player-host/libx1000-player-analysis.so';host=json.loads((ROOT/'work/player-host/build.json').read_text())
 if digest(library)!=host['library_sha256']:raise ValueError('Service identity mismatch')
 for name,expected in host['source_hashes'].items():
  if digest(ROOT/name)!=expected:raise ValueError('Stale service build: '+name)
 wrapper=ROOT/'work/player-bootstrap-system/SpiderApp.bootstrap.analysis-only.arm'
 bootstrap=json.loads((ROOT/'work/player-bootstrap-system/report.json').read_text())
 if digest(wrapper)!=bootstrap['production_default_wrapper_sha256']:raise ValueError('Bootstrap identity mismatch')
 for name,expected in bootstrap['source_hashes'].items():
  if digest(ROOT/name)!=expected:raise ValueError('Stale bootstrap build: '+name)
 root=ROOT/'work/upg-jp/verified-3.bin'
 if digest(root)!='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5':raise ValueError('Pinned original rootfs required')
 proposed=['usr/local/lib/x1000-player/SpiderApp','usr/local/lib/libx1000-player.so']
 with tarfile.open(fileobj=io.BytesIO(gzip.decompress(root.read_bytes()))) as archive:
  entries={m.name.removeprefix('./'):m for m in archive.getmembers()}
  if any(name in entries for name in proposed):raise ValueError('New path already exists in original rootfs')
  original=entries['usr/local/bin/SpiderApp'];dependencies=[]
  original_attributes={key:getattr(original,key) for key in ('mode','uid','gid','uname','gname','mtime')}
  elf=ELFFile(io.BytesIO(library.read_bytes()))
  for tag in elf.get_section_by_name('.dynamic').iter_tags():
   if tag.entry.d_tag!='DT_NEEDED':continue
   name='lib/'+tag.needed;entry=entries.get(name)
   if entry is None:raise ValueError('Dependency missing from original rootfs: '+name)
   resolved=name;seen=set()
   while entries[resolved].issym():
    if resolved in seen:raise ValueError('Dependency symlink loop')
    seen.add(resolved);target=entries[resolved].linkname
    resolved=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(posixpath.dirname(resolved),target))
    if resolved not in entries:raise ValueError('Dependency symlink target missing: '+resolved)
   if not entries[resolved].isfile():raise ValueError('Dependency target is not a regular file')
   dependencies.append({'path':name,'type':'symlink' if entry.issym() else 'file','link':entry.linkname if entry.issym() else None})
 # Existing main executable is relocated, not duplicated. The default wrapper
 # takes its old path. Other baseline resources are identical in this delta.
 growth=payload.stat().st_size-baseline.stat().st_size+wrapper.stat().st_size+library.stat().st_size
 mapped=sum(int(s['p_memsz']) for s in elf.iter_segments() if s['p_type']=='PT_LOAD')
 report={'passed':True,'scope':'Logical file-byte delta against current Homebrew/language composition, not partition or peak-RAM qualification',
  'logical_increment_bytes':growth,'main_payload_increment_bytes':payload.stat().st_size-baseline.stat().st_size,
  'bootstrap_bytes':wrapper.stat().st_size,'service_file_bytes':library.stat().st_size,'service_mapped_segment_bytes':mapped,
  'service_bss_bytes':int(elf.get_section_by_name('.bss')['sh_size']),
  'existing_dependencies':dependencies,'original_main_mode':oct(original.mode),'relocation_not_duplication':True,
  'new_regular_files':2,'new_directory':'usr/local/lib/x1000-player',
  'physical_capacity_verified':False,'filesystem_allocation_measured':False,'peak_memory_measured':False,
  'firmware_package_created':False,'device_accessed':False,'ready_to_flash':False,
  'limits':['Filesystem blocks, directory/inode allocation and installer transient requirements are not logical byte totals.',
            'DSO memory excludes page rounding, allocator/worker stacks, native objects, language copies and original player memory.',
            'Moving the payload is a proposed layout only; no original file or startup configuration is changed.'],
  'inputs':{str(p.relative_to(ROOT)):digest(p) for p in [baseline,payload,library,wrapper,root,Path(__file__)]}}
 if args.layout:
  layout=(ROOT/args.layout).resolve()
  if not layout.is_relative_to(ROOT/'work') or layout.exists():raise ValueError('Select fresh review layout under work/')
  layout.mkdir(parents=True)
  files=[]
  for name,source,attributes in (
   ('usr/local/bin/SpiderApp',wrapper,original_attributes),
   ('usr/local/lib/x1000-player/SpiderApp',payload,original_attributes),
   ('usr/local/lib/libx1000-player.so',library,dict(original_attributes,mode=0o644))):
   destination=layout/'files'/name;destination.parent.mkdir(parents=True,exist_ok=True)
   destination.write_bytes(source.read_bytes())
   if digest(destination)!=digest(source):raise ValueError('Review layout readback mismatch')
   files.append(dict(path=name,bytes=destination.stat().st_size,sha256=digest(destination),intended_tar_attributes=attributes))
  manifest=dict(analysis_only=True,installable=False,activation_environment='X1000_PLAYER_SERVICE=1 (not configured)',files=files,
   directories=[dict(path='usr/local/lib/x1000-player',mode=0o755,uid=0,gid=0)],
   startup_scripts_changed=False,app_list_changed=False,firmware_created=False,physical_device_access=False,
   limits=['Attributes are declared metadata; Windows/DrvFS file ownership is not an installation attribute proof.',
           'No copy/install/activation script is provided. Do not put these files on a player.',
           'Requires the matching Homebrew resource overlay; these three files are not a complete firmware.',
           'Full SpiderApp runtime, lifecycle and capacity are unqualified.'])
  (layout/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
  (layout/'README.txt').write_text('ANALYSIS ONLY - NOT AN INSTALLATION PACKAGE\nThree-file review layout for the optional original-player service.\nNo boot script, AppList edit, updater or firmware image is included.\nDo not copy to a player. Read manifest.json and docs/sdk/PLAYER.md.\n')
  report['review_layout']=layout.relative_to(ROOT).as_posix()
  report['review_layout_manifest_sha256']=digest(layout/'manifest.json')
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
