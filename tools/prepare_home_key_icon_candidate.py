"""Prepare a local JP1.11 HOME-key/shadow-icon candidate; never access a player."""
from pathlib import Path
import argparse,copy,gzip,hashlib,io,json,shutil,subprocess,sys,tarfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack
from resources import parse_tgp

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-local-review',action='store_true',required=True)
    args=parser.parse_args()
    version=(ROOT/'VERSION').read_text().strip()
    base=ROOT/'dist'/version/'diagnostic-review-6'
    out=ROOT/'dist'/version/'diagnostic-review-7'
    work=ROOT/'work/candidate7-build'
    if out.exists() or work.exists():raise FileExistsError('Preserve previous output')
    old=base/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG'
    assert sha(old)=='11f466c94d091c2a7bfb905beb3d94f81ab540dcc0bc33c38597c2ae34daa8cd'
    icon_area=ROOT/'work/homebrew-icon-overlay-2'
    icon=json.loads((icon_area/'report.json').read_text())
    elf=icon_area/'SpiderApp.icon.analysis-only.elf';dat=icon_area/'TEXGRP00.DAT'
    assert sha(elf)==icon['new_elf_sha256'] and sha(dat)==icon['new_dat_sha256']
    assert icon['original_settings_texture_63_unchanged'] and icon['new_texture_id']==139
    loader=json.loads((icon_area/'native-resource-lifecycle.json').read_text())
    assert loader['candidate_sha256']==sha(elf) and len(loader['cases'])==4
    capacity=ROOT/'work/homebrew-icon-capacity-review-1/report.json'
    cap=json.loads(capacity.read_text());assert cap['passed'] and cap['available_nonreserved_bytes']==29003776
    build_path=ROOT/'work/launcher-home-key-review/build.json'
    build=json.loads(build_path.read_text());launcher=ROOT/build['artifact']
    assert build['passed'] and sha(launcher)==build['sha256']
    for name,digest in build['source_hashes'].items():assert sha(ROOT/name)==digest,name
    evidence=[ROOT/'work/home-key-ui-test/report.json',ROOT/'work/home-key-child-test/report.json']
    for path in evidence:
        report=json.loads(path.read_text())
        assert report['passed'] and report['actual_launcher_sha256']==sha(launcher)
    subprocess.run([sys.executable,'tools/verify_external_stop_review.py',str(base.relative_to(ROOT))],cwd=ROOT,check=True)
    work.mkdir();(out/'firmware').mkdir(parents=True)
    _,parts=unpack(old.read_bytes(),require_stock=False)
    replacements={'usr/local/bin/SpiderApp':elf,'usr/local/share/GUI/skinRom/TEXGRP00.DAT':dat}
    tar_path=work/'rootfs.tar';changes=[]
    with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as source,tarfile.open(tar_path,'w',format=tarfile.GNU_FORMAT) as target:
        assert len(source.getmembers())==1433
        for member in source:
            item=copy.copy(member);name=member.name.removeprefix('./')
            if not member.isfile():target.addfile(item);continue
            before=source.extractfile(member).read()
            after=replacements[name].read_bytes() if name in replacements else before
            if name in replacements:
                changes.append({'path':name,'before_bytes':len(before),'after_bytes':len(after),
                                'before_sha256':hashlib.sha256(before).hexdigest(),
                                'after_sha256':hashlib.sha256(after).hexdigest()})
            item.size=len(after);target.addfile(item,io.BytesIO(after))
    assert len(changes)==2
    rootfs=work/'rootfs.tar.gz';rootfs.write_bytes(gzip.compress(tar_path.read_bytes(),compresslevel=9,mtime=0))
    inputs=[]
    for i in range(3):
        p=work/f'component-{i}.bin';p.write_bytes(parts[i]);inputs.append(p)
    tool=ROOT/'third_party/rockbox-upgtools/upgtool'
    upg=out/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG'
    result=subprocess.run([str(tool),'--no-color','--create','-k','466c8cd0','-s','daefe603',str(upg),*[str(p) for p in inputs],str(rootfs)],capture_output=True,text=True)
    (work/'create.log').write_text(result.stdout+result.stderr);assert result.returncode==0
    _,decoded=unpack(upg.read_bytes(),require_stock=False)
    assert decoded[:3]==parts[:3] and decoded[3]==rootfs.read_bytes()
    prefix=work/'independent-'
    result=subprocess.run([str(tool),'--no-color','--extract','-k','466c8cd0','-s','daefe603','-o',str(prefix),str(upg)],capture_output=True,text=True)
    (work/'extract.log').write_text(result.stdout+result.stderr);assert result.returncode==0
    for i,data in enumerate(decoded):assert (work/f'independent-{i}.bin').read_bytes()==data
    shutil.copytree(base/'external',out/'external')
    shutil.copyfile(launcher,out/'external/HOMEBREW/launcher/app')
    review=out/'review';review.mkdir()
    for i,path in enumerate([build_path,*evidence,icon_area/'report.json',icon_area/'native-resource-lifecycle.json',capacity]):
        shutil.copyfile(path,review/f'{i}-{path.parent.name}.json')
    report={'profile':'home-key-shadow-icon-local-review','version':version,'revision':7,
            'base_candidate':str(base.relative_to(ROOT)),'base_upg_sha256':sha(old),
            'upg_sha256':sha(upg),'upg_bytes':upg.stat().st_size,
            'original_installer_kernel_initrd_unchanged':True,'rootfs_entries':1433,
            'system_changes_from_candidate6':changes,'logical_system_growth_from_original_bytes':50556,
            'new_system_paths_from_candidate6':[],
            'model_available_nonreserved_bytes':cap['available_nonreserved_bytes'],
            'icon_texture_id':139,'original_settings_texture_63_unchanged':True,
            'launcher_sha256':sha(launcher),'launcher_bytes':launcher.stat().st_size,
            'home_binding':{'source':'user physical observation','node':0,'type':1,'code':18,'trigger':'release after press'},
            'other_keys_remapped':False,'prev_next_buttons_removed':True,'list_paging':'vertical swipe',
            'ready_to_flash':False,'hardware_tested':False,'device_written':False,
            'source_hashes':{str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),old,elf,dat,launcher,build_path,*evidence,capacity]}}
    (review/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    (out/'REVIEW.md').write_text((ROOT/'docs/STATUS.md').read_text(encoding='utf-8'))
    (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in sorted(out.rglob('*')) if p.is_file()))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
