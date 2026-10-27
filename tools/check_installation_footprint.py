"""Pinned installer + ext2 regular-file allocation accounting. No filesystem/device writes.

This is not a partition fit test: actual partition size, mkfs defaults, inode
tables, directories, reserved blocks and bad-block policy remain unqualified.
"""
from pathlib import Path
import hashlib,io,json,tarfile

ROOT=Path(__file__).resolve().parents[1]
version=(ROOT/'VERSION').read_text().strip()
area=ROOT/'work'/('integration-'+version)
manifest=json.loads((area/'manifest.json').read_text())
assert manifest['version']==version and not manifest['flashable_package_created']
archive=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(archive).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
installer=(ROOT/'work/upg-jp/verified-0.bin').read_bytes();script=installer.decode()
assert 'mkfs.ext2 -b 4096 /dev/mtdblock/1' in script
assert 'fwpup -f /contents/$_UPDATE_FN_.UPG -k 1 -r 3 | tar -xvzf -' in script
assert script.index('mkfs.ext2')<script.index('if [ ! -f /contents/')<script.index('| tar -xvzf -')
BLOCK=4096;POINTERS=BLOCK//4
def allocation(size):
    data=(size+BLOCK-1)//BLOCK;remaining=max(0,data-12);indirect=0
    if remaining:
        indirect+=1;remaining=max(0,remaining-POINTERS)
    if remaining:
        take=min(remaining,POINTERS**2);indirect+=1+(take+POINTERS-1)//POINTERS;remaining-=take
    if remaining:
        indirect+=1+(remaining+POINTERS**2-1)//(POINTERS**2)+(remaining+POINTERS-1)//POINTERS
    return {'data_blocks':data,'indirect_blocks':indirect,'allocated_bytes':(data+indirect)*BLOCK}
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
    regular={member.name.removeprefix('./'):member for member in tar.getmembers() if member.isfile()}
    originals={name:tar.extractfile(member).read() for name,member in regular.items() if name=='etc/AppList.conf'}
    rows=[]
    for entry in manifest['files']:
        prefix='system-overlay/'
        if not entry['path'].startswith(prefix):continue
        name=entry['path'][len(prefix):];assert name in regular
        content=(area/entry['path']).read_bytes()
        assert hashlib.sha256(content).hexdigest()==entry['sha256']
        before=allocation(regular[name].size);after=allocation(len(content))
        rows.append({'path':name,'before_bytes':regular[name].size,'after_bytes':len(content),'after_sha256':hashlib.sha256(content).hexdigest(),
                     'logical_growth_bytes':len(content)-regular[name].size,
                     'before_ext2_file':before,'after_ext2_file':after,
                     'ext2_file_growth_bytes':after['allocated_bytes']-before['allocated_bytes']})
    stock_size=sum(member.size for member in regular.values())
    stock_file_alloc=sum(allocation(member.size)['allocated_bytes'] for member in regular.values())
    registration=None
    if 'etc/AppList.conf' in originals:
        original=originals['etc/AppList.conf'];fragment=(area/'review/AppList.fragment.NOT_INSTALLED').read_bytes()
        proposed=original+(b'' if original.endswith(b'\n') else b'\n')+fragment
        merged=any(row['path']=='etc/AppList.conf' for row in rows)
        registration={'path':'etc/AppList.conf','actually_merged':merged,'logical_growth_if_appended':len(proposed)-len(original),'ext2_file_growth_if_appended':allocation(len(proposed))['allocated_bytes']-allocation(len(original))['allocated_bytes'],'included_in_overlay_totals':merged}
report={'version':version,'scope':__doc__,'installer_sha256':hashlib.sha256(installer).hexdigest(),
        'root_partition':'/dev/mtdblock/1','filesystem':'ext2','block_bytes':BLOCK,
        'installation_reformats_root_first':True,'update_file_checked_after_format':True,
        'stock_regular_file_bytes':stock_size,'stock_regular_file_allocation_model_bytes':stock_file_alloc,
        'changes':rows,'logical_growth_bytes':sum(row['logical_growth_bytes'] for row in rows),
        'ext2_regular_file_growth_bytes':sum(row['ext2_file_growth_bytes'] for row in rows),
        'registration_append_scenario':registration,'external_launcher_bytes':manifest['external_program_bytes'],
        'new_system_paths':0,'system_partition_capacity_bytes':None,'capacity_qualified':False,
        'limits':['Regular-file block model only; not an actual mkfs/extraction measurement.',
                  'All overlay paths replace original regular files; no new inode/directory count is assumed.',
                  'Pending AppList merge shown separately; not included in staged overlay totals.',
                  'Partition size/default reserved space/inode tables/directory allocation and bad blocks are not proved.',
                  'Fresh formatting is destructive before extraction; small growth alone does not prove recovery/flash safety.',
                  'Original installer/kernel/initrd are not modified, no UPG generated or physical device accessed.']}
definition_path=ROOT/'sources/native-root-partition-definition.json'
if definition_path.exists():
    definition_bytes=definition_path.read_bytes();definition=json.loads(definition_bytes)
    assert definition['module_sha256']=='3263ab460d48160549dba1c67d96a9a76ee47ff93281d061a6c663b1c191cdd9'
    report['stock_root_partition_definition_bytes']=definition['definition_bytes']
    report['stock_definition_report_sha256']=hashlib.sha256(definition_bytes).hexdigest()
    report['model_remaining_before_filesystem_metadata_bytes']=definition['definition_bytes']-stock_file_alloc-report['ext2_regular_file_growth_bytes']
    report['limits'].append('Stock module defines148MiB, but system_partition_capacity_bytes stays unknown until matching actual-device evidence; modeled remainder excludes filesystem metadata/reservation.')
population_path=ROOT/'sources/native-stock-ext2-population.json'
if population_path.exists():
    content=population_path.read_bytes();population=json.loads(content)
    measured=(ROOT/population['experiment_directory']/'tree').resolve()
    assert measured.is_relative_to((ROOT/'work').resolve())
    matches=all(hashlib.sha256((measured/row['path']).read_bytes()).hexdigest()==row['after_sha256'] for row in rows)
    report['dense_measurement_overlay_equivalence']={'matches':matches,'report_sha256':hashlib.sha256(content).hexdigest(),'measurement_version':population['version'],'overlay_paths_checked':len(rows),'candidate_available_nonreserved_bytes':population['candidate_available_nonreserved_bytes'] if matches else None,'capacity_qualified':False}
(ROOT/'sources/native-installation-footprint.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({key:report[key] for key in ('version','logical_growth_bytes','ext2_regular_file_growth_bytes','registration_append_scenario','system_partition_capacity_bytes','capacity_qualified')},indent=2))
