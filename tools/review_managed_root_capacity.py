"""Compare proposed or packaged root inventories without building an image or UPG."""
import argparse,copy,hashlib,io,json,posixpath,sys,tarfile,time
from pathlib import Path
from app_registry import ROOT
from component_receipts import private,receipt,digest
from sdk_build import fresh_work
sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack

def read_root_input(path, *, root_only, expected=None):
    path = private(path)
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if expected is not None and actual != expected:
        raise ValueError('Localization input mismatch')
    if root_only:
        return path, data, actual
    _, parts = unpack(data, require_stock=False)
    originals = [private(f'work/upg-jp/verified-{i}.bin').read_bytes() for i in range(3)]
    if len(parts) != 4 or parts[:3] != originals:
        raise ValueError('Localization UPG changed Sony installation components')
    return path, parts[3], actual


def read_localization_root(layout, *, legacy_firmware=None):
    """Read the exact base recorded by a layout, including legacy UPG inputs."""
    root_only = 'localization_root' in layout
    if root_only and (legacy_firmware is not None or 'localization_input' in layout):
        raise ValueError('Layout already specifies a localized root archive')
    kind = 'localization_root' if root_only else 'localization_input'
    expected = layout[kind + '_sha256']
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError('Missing localization input identity')
    path = legacy_firmware if legacy_firmware is not None else layout[kind]
    return read_root_input(path, root_only=root_only, expected=expected)


def inventory(raw):
 result={}
 with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
  for item in archive.getmembers():
   name=item.name.removeprefix('./').rstrip('/')
   if name in ('','.'):continue
   if name.startswith('/') or posixpath.normpath(name)!=name or name.startswith('../') or name in result:raise ValueError('Ambiguous archive path: '+name)
   row=dict(kind='file' if item.isfile() else 'directory' if item.isdir() else 'symlink' if item.issym() else 'other',bytes=item.size if item.isfile() else 0,mode=item.mode,uid=item.uid,gid=item.gid)
   if item.isfile():row['sha256']=hashlib.sha256(archive.extractfile(item).read()).hexdigest()
   elif item.issym():row['target']=item.linkname
   else:
    if not item.isdir():row.update(tar_type=item.type.hex(),linkname=item.linkname,devmajor=item.devmajor,devminor=item.devminor)
   result[name]=row
 return result

def compose_root_inventory(base, overlay):
    """Declare the same complete tree the packer will create, without file IO."""
    result = copy.deepcopy(base)
    for name in sorted(overlay):
        if (not isinstance(name, str) or not name or name in ('.', '..') or
                name.startswith('/') or name.startswith('../') or '\\' in name or
                posixpath.normpath(name) != name):
            raise ValueError('Noncanonical overlay path: ' + repr(name))
        row = overlay[name]
        old = result.get(name)
        if old and old['kind'] != 'file':
            raise ValueError('Overlay replaces non-file: ' + name)
        parents = []
        parent = posixpath.dirname(name)
        while parent:
            parents.append(parent)
            parent = posixpath.dirname(parent)
        for parent in reversed(parents):
            if parent in result:
                if result[parent]['kind'] != 'directory':
                    raise ValueError('Overlay ancestor is not a directory: ' + parent)
            else:
                result[parent] = dict(kind='directory', bytes=0, mode=0o755, uid=0, gid=0)
        result[name] = dict(kind='file', bytes=row['bytes'], sha256=row['sha256'],
                            mode=int(row['mode'], 8), uid=old['uid'] if old else row.get('uid', 0),
                            gid=old['gid'] if old else row.get('gid', 0))
    return result

def comparison_input(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    resolved = path.resolve()
    if (path.is_symlink() or not resolved.is_file() or
            not any(resolved.is_relative_to(ROOT / name) for name in ('dist', 'firmware', 'work'))):
        raise ValueError('Expected a local UPG under dist/, firmware/ or work/')
    data = resolved.read_bytes()
    _, parts = unpack(data, require_stock=False)
    return dict(path=resolved.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(data).hexdigest()), parts


def compare_elf(before, after):
    from elftools.elf.elffile import ELFFile

    a, b = (ELFFile(io.BytesIO(data)) for data in (before, after))
    old_segments, new_segments = list(a.iter_segments()), list(b.iter_segments())
    old_sections = {item.name: item for item in a.iter_sections()}
    new_sections = {item.name: item for item in b.iter_sections()}
    changed = []
    for name in sorted(old_sections.keys() | new_sections.keys()):
        x, y = old_sections.get(name), new_sections.get(name)
        if x is None or y is None or x.header != y.header or x.data() != y.data():
            changed.append(name)
    return dict(
        program_headers_and_data_equal=len(old_segments) == len(new_segments) and all(
            x.header == y.header and x.data() == y.data() for x, y in zip(old_segments, new_segments)),
        elf_headers_equal=a.header == b.header,
        changed_sections=changed,
    )


def compare_upgs(before, after):
    baseline, old = comparison_input(before)
    candidate, new = comparison_input(after)
    a, b = inventory(old[3]), inventory(new[3])
    changes = []
    with (tarfile.open(fileobj=io.BytesIO(old[3]), mode='r:gz') as base_archive,
          tarfile.open(fileobj=io.BytesIO(new[3]), mode='r:gz') as candidate_archive):
        base_files, candidate_files = (
            {m.name.removeprefix('./').rstrip('/'): m for m in archive if m.isfile()}
            for archive in (base_archive, candidate_archive)
        )
        for path in sorted(a.keys() | b.keys()):
            original, current = a.get(path), b.get(path)
            if original == current:
                continue
            row = dict(path=path, baseline=original, candidate=current)
            if path in base_files and path in candidate_files and original['sha256'] != current['sha256']:
                with (base_archive.extractfile(base_files[path]) as first,
                      candidate_archive.extractfile(candidate_files[path]) as second):
                    if first.read(4) == second.read(4) == b'\x7fELF':
                        first.seek(0)
                        second.seek(0)
                        row['elf'] = compare_elf(first.read(), second.read())
            changes.append(row)
    return dict(baseline=baseline, candidate=candidate,
                install_components_equal=dict(zip(('installer', 'kernel', 'initrd'),
                                                  (x == y for x, y in zip(old[:3], new[:3])))),
                changed_paths=changes, device_accessed=False, firmware_created=False)


def main():
 parser=argparse.ArgumentParser(description=__doc__)
 source=parser.add_mutually_exclusive_group(required=True)
 source.add_argument('--layout-review',type=Path)
 source.add_argument('--compare-upg',type=Path,nargs=2,metavar=('BASELINE','CANDIDATE'),
                     help='Compare the actual component, root and ELF contents of two local UPGs')
 parser.add_argument('--localization-firmware',type=Path,help='Optional matching UPG for legacy layouts')
 parser.add_argument('--output',type=Path,help='New capacity review directory below work/')
 args=parser.parse_args()
 if args.compare_upg:
  if args.localization_firmware or args.output:
   parser.error('--localization-firmware and --output require --layout-review')
  print(json.dumps(compare_upgs(*args.compare_upg),indent=2))
  return
 layout_path,layout=receipt(args.layout_review)
 _,root,localization_sha=read_localization_root(layout,legacy_firmware=args.localization_firmware)
 if not layout['prepared'] or not layout['analysis_only'] or layout['player_copies_in_final_layout']!=1:raise ValueError('Expected single-player analysis layout')
 original=private('work/upg-jp/verified-3.bin')
 if digest(original)!='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5':raise ValueError('Original root mismatch')
 stock=inventory(original.read_bytes());base=inventory(root)
 for name,row in layout['files'].items():
  path=private(layout_path.parent/'root-overlay'/name)
  if digest(path)!=row['sha256'] or path.stat().st_size!=row['bytes']:raise ValueError('Overlay input mismatch: '+name)
 candidate=compose_root_inventory(base,layout['files'])
 changes=[]
 for name in sorted(stock.keys()|candidate.keys()):
  a=stock.get(name);b=candidate.get(name)
  if a!=b:changes.append(dict(path=name,original=a,candidate=b,delta_bytes=(b or {}).get('bytes',0)-(a or {}).get('bytes',0)))
 total=lambda rows:sum(row['bytes'] for row in rows.values() if row['kind']=='file')
 rounded=lambda rows,block:sum((row['bytes']+block-1)//block*block for row in rows.values() if row['kind']=='file')
 report=dict(passed=True,analysis_only=True,ready_to_flash=False,device_accessed=False,firmware_created=False,
  original_regular_bytes=total(stock),candidate_regular_bytes=total(candidate),regular_file_delta_bytes=total(candidate)-total(stock),
  regular_file_allocation_models=[dict(block_bytes=block,delta_bytes=rounded(candidate,block)-rounded(stock,block)) for block in (1024,4096)],
  changed_paths=changes,layout_review=layout_path.relative_to(ROOT).as_posix(),layout_review_sha256=digest(layout_path),
  new_directories=sorted(name for name,row in candidate.items() if name not in base and row['kind']=='directory'),
  localization_sha256=localization_sha,original_root_sha256=digest(original),
  source_hashes={name:digest(ROOT/name) for name in ('tools/review_managed_root_capacity.py','tools/component_receipts.py','scripts/upg.py','scripts/upg_crypto.py')},
  capacity_margin_verified=False,limitations=['Complete proposed file inventory, not an allocated filesystem image.',
   'Block models omit inode/directory/indirect blocks, reserved space and flash translation/bad blocks.',
   'No current physical free-space measurement or partition-write qualification.',
   'No updater, kernel or initrd is generated or changed.'])
 out=fresh_work(args.output or ROOT/'work/managed-root-capacity'/str(time.time_ns()))
 (out/'review.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(passed=True,review=(out/'review.json').relative_to(ROOT).as_posix(),regular_file_delta_bytes=report['regular_file_delta_bytes'],changed_paths=len(changes),capacity_margin_verified=False),indent=2))
if __name__=='__main__':main()
