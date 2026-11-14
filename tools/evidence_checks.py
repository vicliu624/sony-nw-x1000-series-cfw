"""Bound saved evidence to current source/artifact bytes; no device qualification."""
from pathlib import Path, PurePosixPath
import hashlib,json
import os
import zipfile

def _file(root,relative):
 path=(root/relative).resolve()
 if not path.is_relative_to(root.resolve()) or not path.is_file():raise ValueError('Missing/outside evidence file: '+str(relative))
 return path

def verify_report(root,relative):
 root=Path(root);report=json.loads(_file(root,relative).read_text())
 if not isinstance(report,dict):raise ValueError('Evidence must be an object: '+relative)
 for field in ('all_bounded_checks_passed','all_passed'):
  if field in report and report[field] is not True:raise ValueError('Failed evidence: '+relative+' '+field)
 for field in ('source_hashes','full_source_hashes','platform_source_hashes'):
  if field not in report:continue
  if not isinstance(report[field],dict):raise ValueError('Invalid source map: '+relative)
  for source,digest in report[field].items():
   if hashlib.sha256(_file(root,source).read_bytes()).hexdigest()!=digest:raise ValueError('Stale source evidence: '+relative+' '+source)
 if 'generator_source' in report:
  if hashlib.sha256(_file(root,report['generator_source']).read_bytes()).hexdigest()!=report.get('generator_sha256'):raise ValueError('Stale generator: '+relative)
 if isinstance(report.get('artifact'),str) and isinstance(report.get('sha256'),str) and isinstance(report.get('bytes'),int):
  payload=_file(root,report['artifact']).read_bytes()
  if len(payload)!=report['bytes'] or hashlib.sha256(payload).hexdigest()!=report['sha256']:raise ValueError('Artifact mismatch: '+relative)
 return report


def source_inventory(root):
    result = {}
    for name in ("runtime", "sdk", "tools", "config", "scripts", "tests", ".github"):
        for directory, children, files in os.walk(root / name):
            children[:] = sorted(child for child in children
                                 if child not in ("__pycache__", ".pio", "managed_components"))
            for filename in sorted(files):
                path = Path(directory) / filename
                if path.suffix not in (".c", ".h", ".cpp", ".hpp", ".S", ".py", ".json",
                                       ".inc", ".yml", ".yaml", ".ini", ".ps1", ".ld") and path.name != "VERSION":
                    continue
                if path.is_file():
                    result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    result["VERSION"] = hashlib.sha256((root / "VERSION").read_bytes()).hexdigest()
    return result


def write_source_snapshot(root, inventory, archive):
    """Retain exactly the hashed text inputs, including uncommitted work."""
    root = root.resolve()
    payloads = {}
    for name, expected in sorted(inventory.items()):
        logical = PurePosixPath(name)
        if logical.is_absolute() or ".." in logical.parts or "\\" in name:
            raise ValueError("Invalid snapshot name: " + name)
        path = root / name
        if (any(part.is_symlink() for part in [path, *path.parents] if part != root)
                or not path.resolve().is_relative_to(root)
                or path.relative_to(root).as_posix() != name):
            raise ValueError("Invalid snapshot input: " + name)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("Source changed before snapshot: " + name)
        payloads[name] = data
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as bundle:
        for name, data in payloads.items():
            entry = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(entry, data)
    return hashlib.sha256(archive.read_bytes()).hexdigest()


def verify_source_snapshot(inventory, archive):
    """Check a shared snapshot against the current source inventory."""
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        stream.seek(0)
        with zipfile.ZipFile(stream) as bundle:
            if sorted(bundle.namelist()) != sorted(inventory):
                raise ValueError('Source snapshot inventory differs')
            for name, expected in inventory.items():
                with bundle.open(name) as source:
                    if hashlib.file_digest(source, 'sha256').hexdigest() != expected:
                        raise ValueError('Source snapshot bytes differ: ' + name)
    return digest
