"""Measure stock/candidate on ordinary local ext2 image files, never device paths.

Modern host mke2fs population is not Sony's mkfs+tar implementation. This is a
controlled capacity experiment, not device partition qualification or firmware.
"""
from pathlib import Path,PurePosixPath
import hashlib,io,json,os,shutil,stat,struct,subprocess,tarfile,tempfile
ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION').read_text().strip();candidate=ROOT/'work'/('integration-'+version)
manifest=json.loads((candidate/'manifest.json').read_text());assert manifest['version']==version
definition_bytes=(ROOT/'sources/native-root-partition-definition.json').read_bytes();definition=json.loads(definition_bytes)
assert definition['definition_bytes']==148*1048576 and not definition['capacity_qualified']
archive=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(archive).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
assert shutil.disk_usage(ROOT/'work').free>1024**3,'Local experiment requires at least1GiB free'
area=Path(tempfile.mkdtemp(prefix='ext2-measure-',dir=ROOT/'work')).resolve();tree=area/'tree';tree.mkdir()
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
    members=tar.getmembers();links={m.name.removeprefix('./') for m in members if m.issym()}
    for member in members:
        path=PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert member.isfile() or member.isdir() or member.issym()
        # A symlink may be copied as data, but archive extraction must never traverse one.
        assert all(str(parent) not in links for parent in path.parents)
    tar.extractall(tree,filter='fully_trusted') # Hash-pinned Sony archive, all paths audited above.
rows=[]
def measure(profile,inode_bytes):
    image=area/(profile+'-inode'+str(inode_bytes)+'.img')
    assert image.parent==area and image.suffix=='.img' and not image.exists()
    with image.open('xb') as out:out.truncate(definition['definition_bytes'])
    assert stat.S_ISREG(image.stat().st_mode) and not image.is_symlink()
    command=['mke2fs','-q','-F','-t','ext2','-b','4096','-I',str(inode_bytes),'-m','5','-O','none','-d',str(tree),str(image)]
    result=subprocess.run(command,capture_output=True,text=True,check=True,timeout=120)
    (area/(image.stem+'.mkfs.log')).write_text(result.stdout+result.stderr)
    check=subprocess.run(['e2fsck','-f','-n',str(image)],capture_output=True,text=True,timeout=120)
    (area/(image.stem+'.fsck.log')).write_text(check.stdout+check.stderr)
    assert check.returncode==0,check.stdout+check.stderr
    with image.open('rb') as f:f.seek(1024);sb=f.read(1024)
    assert struct.unpack_from('<H',sb,56)[0]==0xef53
    inodes,blocks,reserved,free,free_inodes=struct.unpack_from('<5I',sb)
    block_bytes=1024<<struct.unpack_from('<I',sb,24)[0];assert block_bytes==4096
    return {'profile':profile,'inode_bytes':inode_bytes,'image':image.relative_to(ROOT).as_posix(),
            'block_bytes':block_bytes,'total_blocks':blocks,'used_bytes':(blocks-free)*block_bytes,
            'free_bytes':free*block_bytes,'reserved_bytes':reserved*block_bytes,
            'available_nonreserved_bytes':max(0,free-reserved)*block_bytes,
            'used_inodes':inodes-free_inodes,'fsck_readonly_exit':check.returncode,'command':command}
for inode_bytes in (128,256):rows.append(measure('stock',inode_bytes))
for entry in manifest['files']:
    if not entry['path'].startswith('system-overlay/'):continue
    relative=entry['path'][len('system-overlay/'):];destination=tree/relative
    assert destination.resolve().is_relative_to(tree.resolve()) and destination.is_file() and not destination.is_symlink()
    data=(candidate/entry['path']).read_bytes();assert hashlib.sha256(data).hexdigest()==entry['sha256']
    mode=destination.stat().st_mode;destination.chmod(mode|stat.S_IWUSR);destination.write_bytes(data);destination.chmod(mode)
# Pending registration evaluated in the candidate scenario; only the local tree is changed.
config=tree/'etc/AppList.conf';original=config.read_bytes();fragment=(candidate/'review/AppList.fragment.NOT_INSTALLED').read_bytes()
mode=config.stat().st_mode;config.chmod(mode|stat.S_IWUSR)
if not original.endswith(fragment):config.write_bytes(original+(b'' if original.endswith(b'\n') else b'\n')+fragment)
config.chmod(mode)
for inode_bytes in (128,256):rows.append(measure('candidate-with-registration',inode_bytes))
deltas=[]
for inode_bytes in (128,256):
    before=next(r for r in rows if r['inode_bytes']==inode_bytes and r['profile']=='stock')
    after=next(r for r in rows if r['inode_bytes']==inode_bytes and r['profile']!='stock')
    deltas.append({'inode_bytes':inode_bytes,'used_growth_bytes':after['used_bytes']-before['used_bytes'],'candidate_available_nonreserved_bytes':after['available_nonreserved_bytes']})
report={'version':version,'scope':__doc__,'definition_report_sha256':hashlib.sha256(definition_bytes).hexdigest(),
        'image_bytes':definition['definition_bytes'],'profiles':rows,'deltas':deltas,
        'host_tools':subprocess.run(['mke2fs','-V'],capture_output=True,text=True).stderr.strip(),
        'experiment_directory':area.relative_to(ROOT).as_posix(),'physical_device_access':False,'capacity_qualified':False,
        'limits':['Local regular files only; no mount, kernel module loading, updater or firmware creation.',
                  'Host mke2fs -d differs from stock mkfs.ext2 followed by tar extraction; zero-block/sparse behavior may differ.',
                  'Both profiles explicitly use no optional ext2 features and5% reserved blocks; stock defaults not established.',
                  'Ownership extraction by unprivileged host may differ; this does not qualify device metadata/boot.',
                  '148MiB module definition still needs matching actual-device partition evidence.']}
(ROOT/'sources/native-local-ext2-measurement.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'directory':report['experiment_directory'],'deltas':deltas,'capacity_qualified':False},indent=2))
