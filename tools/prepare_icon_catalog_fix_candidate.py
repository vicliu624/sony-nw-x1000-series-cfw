"""Prepare candidate8/manual kit locally. No player access or updater execution."""
from pathlib import Path
import argparse,copy,gzip,hashlib,io,json,shutil,struct,subprocess,sys,tarfile,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-local-review',required=True,action='store_true');parser.parse_args()
 version=(ROOT/'VERSION').read_text().strip();d=ROOT/'dist'/version;base=d/'diagnostic-review-7';out=d/'diagnostic-review-8';w=ROOT/'work/candidate8-build';kit=d/'first-device-test-candidate8'
 assert not any(p.exists() for p in (out,w,kit)),'Preserve existing output'
 old=base/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG';assert sha(old)=='dc0a52eb347f770ae3823a19576580fa9a5b5a2f6a52c7f1395dbf15616c4b29'
 fixed=ROOT/'work/homebrew-icon-overlay-3/SpiderApp.icon.analysis-only.elf';launcher=ROOT/'work/launcher-home-first-press-review/launcher.elf'
 build=json.loads((launcher.parent/'build.json').read_text());assert build['passed'] and sha(launcher)==build['sha256']
 for name,digest in build['source_hashes'].items():assert sha(ROOT/name)==digest,name
 icon_reports=[]
 for name,handle in [('broken',0),('fixed',139)]:
  p=ROOT/('work/homebrew-icon-overlay-3/'+name+'-catalog.json');r=json.loads(p.read_text());assert r['appended_icon_catalog_handle']==handle
  icon_reports.append(p)
 assert json.loads(icon_reports[1].read_text())['actual_elf_sha256']==sha(fixed)
 ui=ROOT/'work/home-first-press-ui-test/report.json';r=json.loads(ui.read_text());assert r['passed'] and r['actual_launcher_sha256']==sha(launcher)
 _,parts=unpack(old.read_bytes(),require_stock=False);w.mkdir();(out/'firmware').mkdir(parents=True)
 with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as src,tarfile.open(w/'rootfs.tar','w',format=tarfile.GNU_FORMAT) as dst:
  members=src.getmembers();assert len(members)==1433
  for member in members:
   item=copy.copy(member)
   if not member.isfile():dst.addfile(item);continue
   before=src.extractfile(member).read();after=fixed.read_bytes() if member.name.removeprefix('./')=='usr/local/bin/SpiderApp' else before
   if after!=before:
    assert len(after)==len(before) and sum(a!=b for a,b in zip(before,after))==1
    assert before[0x4ef930:0x4ef934]==struct.pack('<I',139) and after[0x4ef930:0x4ef934]==struct.pack('<I',140)
   item.size=len(after);dst.addfile(item,io.BytesIO(after))
 rootfs=gzip.compress((w/'rootfs.tar').read_bytes(),compresslevel=9,mtime=0);inputs=[]
 for i,data in enumerate(parts[:3]+[rootfs]):
  p=w/f'component-{i}.bin';p.write_bytes(data);inputs.append(p)
 tool=ROOT/'third_party/rockbox-upgtools/upgtool';upg=out/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG'
 for command in [[str(tool),'--no-color','--create','-k','466c8cd0','-s','daefe603',str(upg),*[str(p) for p in inputs]],[str(tool),'--no-color','--extract','-k','466c8cd0','-s','daefe603','-o',str(w/'independent-'),str(upg)]]:
  result=subprocess.run(command,capture_output=True,text=True);assert result.returncode==0,result.stdout+result.stderr
 _,decoded=unpack(upg.read_bytes(),require_stock=False)
 for i,data in enumerate(decoded):assert data==inputs[i].read_bytes()==(w/f'independent-{i}.bin').read_bytes()
 # Independent complete tar comparison against candidate7.
 with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz') as a,tarfile.open(fileobj=io.BytesIO(decoded[3]),mode='r:gz') as b:
  ma=a.getmembers();mb=b.getmembers();assert len(ma)==len(mb)==1433;changed=[]
  for x,y in zip(ma,mb):
   assert x.name==y.name
   for field in ('mode','uid','gid','mtime','type','linkname','uname','gname','size'):assert getattr(x,field)==getattr(y,field),(x.name,field)
   if x.isfile() and a.extractfile(x).read()!=b.extractfile(y).read():changed.append(x.name.removeprefix('./'))
  assert changed==['usr/local/bin/SpiderApp']
 shutil.copytree(base/'external',out/'external');shutil.copyfile(launcher,out/'external/HOMEBREW/launcher/app')
 review=out/'review';review.mkdir()
 for p in [*icon_reports,ui,launcher.parent/'build.json',ROOT/'work/posix-full-loop-home-first-press/report.json',ROOT/'work/homebrew-icon-overlay-3/report.json']:
  shutil.copyfile(p,review/(p.parent.name+'-'+p.name))
 report={'profile':'home-first-press-icon-catalog-fix','version':version,'revision':8,'upg_sha256':sha(upg),'upg_bytes':upg.stat().st_size,'base_candidate7_upg_sha256':sha(old),'rootfs_entries':1433,'rootfs_metadata_and_sizes_preserved':True,'system_changed_from_candidate7':changed,'system_bytes_changed_from_candidate7':1,'original_installer_kernel_initrd_unchanged':decoded[:3]==parts[:3],'logical_system_growth_from_original_bytes':50556,'capacity_model_nonreserved_bytes':29003776,'capacity_model_reused_reason':'same tar paths, metadata and file sizes as candidate7','launcher_bytes':launcher.stat().st_size,'launcher_sha256':sha(launcher),'home_trigger':'EV_KEY code18 value1 immediately; release/repeat ignored','icon_catalog_table_va':'0x4f7930','icon_catalog_count_before':139,'icon_catalog_count_after':140,'new_icon_lookup_before':0,'new_icon_lookup_after':139,'hardware_tested':False,'device_written':False,'ready_to_flash':False}
 (review/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
 (out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n' for p in sorted(out.rglob('*')) if p.is_file()))
 kit.mkdir();shutil.copytree(ROOT/'work/candidate6-first-device-inputs/sony-updater',kit/'01_PC_UPDATE');shutil.copyfile(upg,kit/'01_PC_UPDATE/NW_WM_FW.UPG');shutil.copytree(out/'external',kit/'02_PLAYER_FILES');shutil.copytree(review,kit/'03_RECORDS')
 instructions="""# NW-X1060 候选8：HOME与图标修复

适用日版NW-X1060，Sony版本仍为1.11。本地诊断候选，尚未实机验证。不要把离线测试当成刷写安全保证。

## 修改

HOME改为收到event0/type1/code18/value1立即请求退出，不再等待1→0的顺序配对；重复值2、释放值0忽略，其他按键不重映射。移除PREV/NEXT，超过六项上下滑动。

图标保留候选7的阴影素材。修正SpiderApp的资源数量表0x4f7930，从139改140；旧包已读入140张，但只映射139张，新增索引139错误查到句柄0。原ARM代码回归对照已复现旧错误，修复后查到139及正确64×64像素。原Settings不变。

## 手动安装

1. 电量充足，用可靠数据线连接播放器。
2. 将02_PLAYER_FILES/HOMEBREW/launcher/app覆盖到播放器HOMEBREW/launcher/app，保留现有apps、ROM和存档。若首次安装，可合并复制整个HOMEBREW目录。仅更新这个文件可先测试HOME，不改变系统图标。
3. 为修复Sony菜单黑方块，手动运行01_PC_UPDATE/FWUpdater.exe。保持同目录的INI、DLL、许可证和NW_WM_FW.UPG齐全，按Sony原更新流程操作，不改版本或INI。
4. 更新中不要RESET或断线，等待原程序完成。安全弹出并拔线。
5. 进入Homebrew检查图标；完整按一次HOME检查返回；再运行自制应用检查HOME退出与正常触摸返回；检查Sony播放和USB连接。

## 风险和范围

没有自动执行更新器或刷机。原升级脚本、内核、initrd保持不变。相对候选7只有SpiderApp一个数量值改变，文件大小、元数据和其他系统文件完全一致；外部只更换启动器。

系统逻辑体积相对原版增加50,556字节，与候选7相同。148MiB离线容量模型扣除保留块后余29,003,776字节，不能代替实机测量。

图标查找错误已有确切复现和修复验证；HOME变更已通过ARM/QEMU的正常、反序事件及非HOME对照，真实事件时序与Sony恢复后的页面仍需实测。候选6/7完整保留；回退需设备仍能被原更新器识别。

03_RECORDS是PC审阅报告，不要复制到设备。设备新增程序仅为C/C++和必要汇编，无Python运行时。
"""
 (kit/'START_HERE.md').write_text(instructions)
 (kit/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(kit).as_posix()+'\n' for p in sorted(kit.rglob('*')) if p.is_file()))
 z=d/('NW-X1060-'+version+'-candidate8-manual-test.zip');assert not z.exists()
 with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,6) as archive:
  for p in sorted(kit.rglob('*')):
   if p.is_file():archive.write(p,p.relative_to(kit).as_posix())
 with zipfile.ZipFile(z) as archive:
  assert archive.testzip() is None
  for p in kit.rglob('*'):
   if p.is_file():assert archive.read(p.relative_to(kit).as_posix())==p.read_bytes()
 (w/'package-audit.json').write_text(json.dumps({**report,'zip_sha256':sha(z),'zip_bytes':z.stat().st_size,'zip_readback_passed':True,'builder_sha256':sha(Path(__file__))},indent=2)+'\n')
 print(json.dumps({**report,'zip':str(z),'zip_sha256':sha(z)},indent=2))
if __name__=='__main__':main()
