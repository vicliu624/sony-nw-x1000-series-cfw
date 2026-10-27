"""Pinned local Ghidra export. No firmware execution, network or device access.
Run under WSL with JDK21 after verifying/extracting the official release.
"""
from pathlib import Path
import argparse,csv,hashlib,json,subprocess,time

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--target',choices=('spider','netfront','daemon'),required=True)
parser.add_argument('--reuse',action='store_true',help='Process previously imported pinned program without reanalysis')
parser.add_argument('--entries',help='Override comma-separated function entries')
parser.add_argument('--callers',action='store_true',help='Also export one level of callers')
args=parser.parse_args()
work=ROOT/'work/stock-wifi-decompiler'
release=json.loads((work/'release-jdk21.json').read_text())
assert release['tag']=='Ghidra_12.1.4_build'
asset=release['assets'][0];archive=work/asset['name']
assert archive.stat().st_size==asset['size']
assert 'sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest()==asset['digest']
ghidra=work/'ghidra_12.1.4_PUBLIC'
assert ghidra.is_dir()
# Python zip extraction on Windows does not restore Unix execution bits.
for binary in ghidra.glob('**/os/linux_x86_64/*'):
    if binary.is_file():binary.chmod(binary.stat().st_mode|0o100)
for shell in (ghidra/'support').glob('*.sh'):
    shell.chmod(shell.stat().st_mode|0o100)
targets={
 'spider':('work/targets-jp/SpiderApp','80b8870b02189443c41f62e8960124820ae999de21ba002e24fe17e9376cea85',
           '3b498,3b158,3b0e0,62acc,b3538,28a700,28834c,72384,6ed0c,b05e8,61414,71a3c,73ec8'),
 'netfront':('work/qqmusic-wifi-research/netfront','fb027a1f3d86753d110b12827d0a462d46a79ff784e42018820f13e8fd4b2f4f',
             '2fb3e8,2fcad4,2fcb70,148b8,14984,14a04,b030'),
 'daemon':('work/qqmusic-wifi/cnmgr_daemon','351eb99a05ae9a6baf00c8d8fd6e5e16129cc58dc6f300cf5f43d0fc5ad4eb35',
           'ba18,a93c,b538,d8b0,efdc')}
relative,digest,addresses=targets[args.target];source=ROOT/relative
if args.entries:addresses=args.entries
assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
out=work/('export-'+args.target);out.mkdir(exist_ok=True)
projects=work/'projects';projects.mkdir(exist_ok=True)
command=['bash',str(ghidra/'support/analyzeHeadless'),str(projects),'stock-'+args.target]
command+=['-process',source.name,'-noanalysis'] if args.reuse else ['-import',str(source),'-overwrite','-max-cpu','2','-analysisTimeoutPerFile','240']
command+=['-scriptPath',str(ROOT/'tools'),'-postScript','ExportStockWifi.java',str(out),addresses]
if args.callers:command+=['callers']
started=time.time()
with (out/'headless.log').open('w') as log:
    completed=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
log_text=(out/'headless.log').read_text(errors='replace')
index=out/'index.tsv'
exported=completed.returncode==0 and 'REPORT SCRIPT ERROR' not in log_text and 'ExportStockWifi.java> Exported ' in log_text and index.exists() and index.stat().st_mtime>=started-1
rows=list(csv.DictReader(index.open(),delimiter='\t')) if exported else []
exported=exported and bool(rows) and all(row['status']=='completed' for row in rows)
manifest={'process_exit':completed.returncode,'target':relative,'target_sha256':digest,
          'export_succeeded':exported,'exported_function_count':len(rows),
          'ghidra_release':release['tag'],'ghidra_archive_sha256':asset['digest'],
          'script_sha256':hashlib.sha256((ROOT/'tools/ExportStockWifi.java').read_bytes()).hexdigest(),
          'physical_device_or_firmware_execution':False,
          'limits':['Inferred decompilation is navigation evidence; verify critical behavior against original instructions.',
                    'Analysis timeout may yield partial results; inspect headless.log and index.tsv before use.']}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
raise SystemExit(0 if exported else 1)
