"""Populate stock-mkfs LOCAL FILE images using debugfs, including dense file blocks.

Never mounts an image or accesses a device. Stock ARM mkfs runs in qemu-user;
debugfs population is a controlled substitute for stock tar on a mounted FS.
"""
from pathlib import Path,PurePosixPath
import hashlib,io,json,re,shutil,stat,struct,subprocess,tarfile,tempfile
ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION').read_text().strip();candidate=ROOT/'work'/('integration-'+version)
manifest=json.loads((candidate/'manifest.json').read_text());assert manifest['version']==version
previous=json.loads((ROOT/'sources/native-local-ext2-measurement.json').read_text())
sysroot=(ROOT/previous['experiment_directory']/'tree').resolve();assert sysroot.is_relative_to((ROOT/'work').resolve())
archive=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(archive).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
assert shutil.disk_usage(ROOT/'work').free>1024**3
area=Path(tempfile.mkdtemp(prefix='stock-ext2-populated-',dir=ROOT/'work')).resolve();tree=area/'tree';tree.mkdir()
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
    members=tar.getmembers();links={m.name.removeprefix('./') for m in members if m.issym()}
    assert (sysroot/'bin/busybox').read_bytes()==tar.extractfile('./bin/busybox').read()
    for m in members:
        path=PurePosixPath(m.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert m.isfile() or m.isdir() or m.issym()
        assert all(str(p) not in links for p in path.parents)
    tar.extractall(tree,filter='fully_trusted')
def quote(value):
    assert not any(char in value for char in ('"','\\','\n','\r','\0'))
    return '"'+value+'"'
def command_run(command,log,timeout=180):
    result=subprocess.run(command,capture_output=True,text=True,timeout=timeout)
    (area/log).write_text(result.stdout+result.stderr)
    assert result.returncode==0,result.stdout+result.stderr
    return result
def populate(profile):
    image=area/(profile+'.img');assert image.parent==area and not image.exists()
    with image.open('xb') as f:f.truncate(148*1048576)
    assert stat.S_ISREG(image.stat().st_mode) and not image.is_symlink()
    command_run(['qemu-arm','-cpu','arm926','-L',str(sysroot),str(sysroot/'bin/busybox'),'mke2fs','-F','-b','4096',str(image)],profile+'-mkfs.log')
    commands=[];files=[]
    for m in sorted((m for m in members if m.isdir()),key=lambda m:len(PurePosixPath(m.name).parts)):
        name=m.name.removeprefix('./').rstrip('/')
        if name and name not in ('.','lost+found'):commands.append('mkdir '+quote('/'+name))
    for m in members:
        name=m.name.removeprefix('./').rstrip('/')
        if not name or name=='.':continue
        target='/'+name
        if m.isfile():
            source=tree/name;assert source.resolve().is_relative_to(tree.resolve()) and not source.is_symlink()
            commands.append('write '+quote(str(source))+' '+quote(target))
            blocks=(source.stat().st_size+4095)//4096
            if blocks:commands.append('fallocate '+quote(target)+' 0 '+str(blocks-1))
            files.append({'path':target,'bytes':source.stat().st_size,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
        elif m.issym():commands.append('symlink '+quote(target)+' '+quote(m.linkname))
        mode=(stat.S_IFREG if m.isfile() else stat.S_IFDIR if m.isdir() else stat.S_IFLNK)|m.mode
        for field,value in (('mode','0'+format(mode,'o')),('uid',str(m.uid)),('gid',str(m.gid)),('mtime',str(int(m.mtime)))):
            commands.append('set_inode_field '+quote(target)+' '+field+' '+value)
    script=area/(profile+'-populate.commands');script.write_text('\n'.join(commands)+'\n')
    result=command_run(['debugfs','-w','-f',str(script),str(image)],profile+'-populate.log')
    assert not re.search(r'(Could not|not found|No space|Usage:|File not found|while (?:writing|allocating|creating|opening))',result.stderr,re.I),result.stderr[-2000:]
    command_run(['e2fsck','-f','-n',str(image)],profile+'-fsck.log')
    verify=area/(profile+'-verify');verify.mkdir()
    # Dump regular files only; symlinks are never followed during verification.
    dump=area/(profile+'-verify.commands')
    dump.write_text('\n'.join('dump '+quote(item['path'])+' '+quote(str(verify/str(i))) for i,item in enumerate(files))+'\n')
    command_run(['debugfs','-f',str(dump),str(image)],profile+'-verify.log')
    for i,item in enumerate(files):
        actual=(verify/str(i)).read_bytes();assert len(actual)==item['bytes'] and hashlib.sha256(actual).hexdigest()==item['sha256'],item['path']
    with image.open('rb') as f:f.seek(1024);sb=f.read(1024)
    inode_count,blocks,reserved,free,free_inodes=struct.unpack_from('<5I',sb)
    assert struct.unpack_from('<H',sb,56)[0]==0xef53
    assert struct.unpack_from('<H',sb,88)[0]==128 and struct.unpack_from('<3I',sb,92)==(0,2,1)
    return {'profile':profile,'image':image.relative_to(ROOT).as_posix(),'image_bytes':image.stat().st_size,
            'inode_count':inode_count,'used_inodes':inode_count-free_inodes,'used_bytes':(blocks-free)*4096,
            'reserved_bytes':reserved*4096,'available_nonreserved_bytes':(free-reserved)*4096,
            'verified_regular_files':len(files),'dense_regular_file_blocks':True,'readonly_fsck_exit':0}
rows=[populate('stock')]
for entry in manifest['files']:
    if not entry['path'].startswith('system-overlay/'):continue
    relative=entry['path'][len('system-overlay/'):];destination=tree/relative
    assert destination.resolve().is_relative_to(tree.resolve()) and destination.is_file() and not destination.is_symlink()
    content=(candidate/entry['path']).read_bytes();assert hashlib.sha256(content).hexdigest()==entry['sha256']
    mode=destination.stat().st_mode;destination.chmod(mode|stat.S_IWUSR);destination.write_bytes(content);destination.chmod(mode)
config=tree/'etc/AppList.conf';content=config.read_bytes();fragment=(candidate/'review/AppList.fragment.NOT_INSTALLED').read_bytes()
mode=config.stat().st_mode;config.chmod(mode|stat.S_IWUSR)
if not content.endswith(fragment):config.write_bytes(content+(b'' if content.endswith(b'\n') else b'\n')+fragment)
config.chmod(mode)
rows.append(populate('candidate-with-registration'))
report={'version':version,'scope':__doc__,'profiles':rows,'used_growth_bytes':rows[1]['used_bytes']-rows[0]['used_bytes'],
        'candidate_available_nonreserved_bytes':rows[1]['available_nonreserved_bytes'],
        'experiment_directory':area.relative_to(ROOT).as_posix(),'physical_device_access':False,'capacity_qualified':False,
        'limits':['Stock mkfs on ordinary148MiB files; actual-device capacity and MTD behavior unverified.',
                  'Host debugfs writes files, allocates zero blocks and sets archive inode mode/uid/gid/mtime; not stock tar/kernel filesystem execution.',
                  'Every regular file is dumped and SHA-256 compared; symlink targets/permissions not independently read back here.',
                  'No mount, updater, UPG creation, NVP access or device write.']}
(ROOT/'sources/native-stock-ext2-population.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
