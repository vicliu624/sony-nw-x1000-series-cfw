"""Build candidate12: process-owned language cache, external translations; manual installation only."""
from pathlib import Path
import argparse,copy,gzip,hashlib,io,json,shutil,struct,subprocess,sys,tarfile,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from upg import unpack
from language_pack import parse_manifest
from language_profile import audit_minimal_overlay
from review_process_language_cache import review as cache_review

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def report(path):
 r=json.loads(path.read_text());assert r['passed']is True,path
 for name,digest in r.get('source_hashes',{}).items():assert sha(ROOT/name)==digest,(path,name)
 return r

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare-local-review',required=True,action='store_true');p.parse_args();assert __debug__,'Do not run with Python optimization'
 preflight=cache_review()
 version=(ROOT/'VERSION').read_text().strip();d=ROOT/'dist'/version;base=ROOT/'dist/0.1.0-dev.16/diagnostic-review-9';out=d/'diagnostic-review-12';work=ROOT/'work/candidate12-language-cache-build';kit=d/'first-device-test-candidate12-language-cache'
 assert not any(p.exists()for p in (out,work,kit)),'Preserve existing outputs'
 source=base/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG';assert sha(source)=='947acd961e019b79a07e006f21ce3751e2a555a23768f5ec21b769aa8bf093b4'
 bridge=ROOT/'work/external-language-bridge-10-process-cache-final';build=report(bridge/'report.json');elf=ROOT/build['artifact'];assert sha(elf)==preflight['elf_sha256']==build['sha256']and build['elf_size_growth_bytes']==0
 pipeline=json.loads((bridge/'native-cache-tests.json').read_text());assert pipeline['passed']and pipeline['candidate_sha256']==sha(elf)and len(pipeline['cases'])==13
 shared=report(ROOT/'work/external-language-pack-tests/report.json')
 # The already-tested external UI is intentionally unchanged; no new app feature.
 previous=ROOT/'dist/0.1.0-dev.16/first-device-test-candidate11-external-languages/02_PLAYER_FILES/HOMEBREW/apps/language'
 app=previous/'app';assert sha(app)=='b77e79a179c87df027a1a5f8fdded6dc77633366d9d162bc7ab4806616042070'
 app_build={'version':'0.2.0-dev.1','sha256':sha(app)}
 capacity=report(ROOT/'work/language-cache-capacity-review-1/report.json');assert capacity['extra_allocated_bytes']==0 and capacity['new_inodes']==0 and capacity['available_nonreserved_bytes']==29003776 and capacity['readback_files'][0]['sha256']==sha(elf)
 packs={};resource_bytes=0
 for ident in ['en','jp','zh-CN','zh-TW']:
  area=ROOT/'dist/0.1.0-dev.16/language-packs-v1'/ident;pack_report=report(area/'report.json');folder=area/'HOMEBREW/languages'/ident;data=(folder/'wording.stx').read_bytes()if(folder/'wording.stx').exists()else None;metadata=(folder/'language.ini').read_bytes();parsed=parse_manifest(metadata,data);observed=pipeline['pack_inputs'][ident]
  assert sha(folder/'language.ini')==observed['language.ini'];assert data is None or sha(folder/'wording.stx')==observed['wording.stx']
  assert parsed['id']==ident and pack_report['system_partition_bytes']==0;resource_bytes+=len(data)if data else 0;packs[ident]={'folder':folder,'bytes':len(data)if data else 0,'metadata_sha256':sha(folder/'language.ini'),'resource_sha256':None if data is None else sha(folder/'wording.stx')}
 # Check the new Chinese text glyph repertoire remains a subset of actual LCF render tests.
 coverage=json.loads((ROOT/'work/chinese-font-glyph-check-1/glyph-report.json').read_text());assert coverage['passed']
 for label in ['zh-CN','zh-TW']:
  translations=json.loads((ROOT/('translations/x1000-'+label+'.json')).read_text())['translations'];chars={c for s in translations.values()for c in s if not c.isspace()and not 0xe000<=ord(c)<=0xf8ff};seen={g['character']for row in coverage['languages']if row['language']==label for g in row['rendered']};assert chars<=seen
 _,parts=unpack(source.read_bytes(),require_stock=False)
 for i in range(3):assert parts[i]==(ROOT/f'work/upg-jp/verified-{i}.bin').read_bytes()
 work.mkdir();(out/'firmware').mkdir(parents=True)
 # Root construction has no language-pack or translation input.
 with tarfile.open(fileobj=io.BytesIO(parts[3]),mode='r:gz')as a,tarfile.open(work/'rootfs.tar','w',format=tarfile.GNU_FORMAT)as b:
  assert len(a.getmembers())==1433
  for member in a:
   item=copy.copy(member)
   if not member.isfile():b.addfile(item);continue
   original=a.extractfile(member).read();data=elf.read_bytes()if member.name.removeprefix('./')=='usr/local/bin/SpiderApp'else original
   assert len(data)==len(original);b.addfile(item,io.BytesIO(data))
 rootfs=gzip.compress((work/'rootfs.tar').read_bytes(),compresslevel=9,mtime=0);audit=audit_minimal_overlay(parts[3],rootfs);assert audit['modified_system_files']==['usr/local/bin/SpiderApp']and audit['system_logical_growth_from_baseline_bytes']==0
 (work/'root-audit.json').write_text(json.dumps(audit,indent=2)+'\n');inputs=[]
 for i,data in enumerate(parts[:3]+[rootfs]):p=work/f'component-{i}.bin';p.write_bytes(data);inputs.append(p)
 tool=ROOT/'third_party/rockbox-upgtools/upgtool';upg=out/'firmware/DIAGNOSTIC-REVIEW-ONLY.UPG'
 for cmd in [[str(tool),'--no-color','--create','-k','466c8cd0','-s','daefe603',str(upg),*[str(p)for p in inputs]],[str(tool),'--no-color','--extract','-k','466c8cd0','-s','daefe603','-o',str(work/'independent-'),str(upg)]]:
  r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode==0,r.stdout+r.stderr
 _,decoded=unpack(upg.read_bytes(),require_stock=False)
 for i,data in enumerate(decoded):assert data==inputs[i].read_bytes()==(work/f'independent-{i}.bin').read_bytes()
 audit_minimal_overlay(parts[3],decoded[3])
 external=out/'external/HOMEBREW';(external/'apps').mkdir(parents=True);shutil.copytree(app.parent,external/'apps/language')
 for ident,pack in packs.items():shutil.copytree(pack['folder'],external/'languages'/ident)
 pref=external/'data/language/ui-language';pref.parent.mkdir(parents=True);pref.write_bytes(b'en\n')
 review=out/'review';review.mkdir();evidence=[bridge/'report.json',bridge/'native-cache-tests.json',ROOT/'work/external-language-app-build/build.json',ROOT/'work/external-language-app-tests/report.json',ROOT/'work/external-language-pack-tests/report.json',ROOT/'work/language-storage-current-tests/report.json',ROOT/'work/language-cache-capacity-review-1/report.json',work/'root-audit.json',ROOT/'work/chinese-wording-review-2/report.json',ROOT/'work/chinese-font-glyph-check-1/glyph-report.json']
 for p in evidence:shutil.copyfile(p,review/(p.parent.name+'-'+p.name))
 summary={'passed':True,'profile':'process-owned-language-cache-manual-test','revision':12,'version':version,'base_candidate9_upg_sha256':sha(source),'upg_sha256':sha(upg),'upg_bytes':upg.stat().st_size,'compressed_upg_delta_vs_candidate9_bytes':upg.stat().st_size-source.stat().st_size,'rootfs_entries':1433,'modified_system_files':audit['modified_system_files'],'all_system_resources_unchanged':True,'language_translation_bytes_in_system_delta':0,'system_logical_growth_vs_candidate9_bytes':0,'extra_allocated_system_bytes':0,'system_logical_growth_vs_original_bytes':50556,'capacity_model_available_nonreserved_bytes':29003776,'bridge_bytes_in_existing_padding':build['payload_bytes'],'original_installer_kernel_initrd_unchanged':True,'pcm_session_mode1_preserved':True,'language_app_version':app_build['version'],'language_app_bytes':app.stat().st_size,'language_app_sha256':sha(app),'external_wording_bytes':resource_bytes,'language_packs':{i:{k:v for k,v in r.items()if k!='folder'}for i,r in packs.items()},'dynamic_catalog':True,'existing_launcher_and_other_apps_in_bundle':False,'default_external_choice':'en','native_pipeline_cases':len(pipeline['cases']),'rebuild_cleanup_cycles':384,'language_pack_opens_per_process':1,'recovery_language_file_io':False,'process_owned_cache':True,'external_app_reused_unchanged_from_candidate11':True,'hardware_tested':False,'device_written':False,'ready_to_flash':False}
 (review/'verification.json').write_text(json.dumps(summary,indent=2)+'\n');(out/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(out).as_posix()+'\n'for p in sorted(out.rglob('*'))if p.is_file()))
 kit.mkdir();shutil.copytree(ROOT/'work/candidate6-first-device-inputs/sony-updater',kit/'01_PC_UPDATE');shutil.copyfile(upg,kit/'01_PC_UPDATE/NW_WM_FW.UPG');shutil.copytree(out/'external',kit/'02_PLAYER_FILES');shutil.copytree(review,kit/'03_RECORDS')
 instructions="""# NW-X1060 候选12：外部语言包

本地实验候选，尚未实机验证。无需先安装候选10或11。本版包含新的进程内语言缓存，旧候选11不包含此优化。原Sony版本仍为1.11；更新器/INI/内核/initrd/升级脚本保持原行为。没有自动执行更新器或写播放器。

## 首次手动安装（只需一次配套固件）

本包要求已有可运行的Homebrew启动器，不覆盖现有启动器、其他APP或数据。

1. 电量充足，用可靠USB数据线连接日版NW-X1060。
2. 将02_PLAYER_FILES内HOMEBREW合并复制到播放器根目录。必须同时复制新Language应用及languages目录。data/language/ui-language是初始en选择；设备已有该文件时请保留，切勿覆盖已有选择。现有Language和四种语言包若已安装，可直接保留；本版兼容原来的外部文件。
3. 在01_PC_UPDATE中手动运行FWUpdater.exe，保持INI/DLL/许可证/NW_WM_FW.UPG同目录，按Sony原流程更新，不改版本或INI。更新期间不要断线或RESET。
4. 更新完成后安全弹出并拔线，打开Homebrew → Language。列表应发现English、Japanese、Simplified Chinese、Traditional Chinese及Original setting。
5. 选择语言，看到SAVED RETURN TO WALKMAN后，BACK TO APPS，再选择WALKMAN。继承候选9模式1交接，按设计重启Sony后读取语言；真实效果需实测。不要只用应用选中框判断原厂界面已切换。

## 本轮缓存优化

首次启动读取并校验所选语言后，关闭外部文件。休眠/唤醒后的界面重建复用同一份进程缓存，不再重复读取语言包。缺包/坏包/读取错误在本进程内保持原厂回退，需重新启动Walkman才重新尝试。翻译仍在用户存储，系统文件逻辑占用不增加。

384轮离线重建/清理通过，不能保证实机黑屏已解决。首次加载仍需读取用户存储；原厂电源和内核没有改动。Language应用本身与候选11一致（0.2.0-dev.1），优化位于新固件内。勿使用候选11旧更新器目录代替本目录。

## 以后增加或更新语言，不刷机

兼容语言包只放HOMEBREW/languages/<id>，包含language.ini及wording.stx（引用原厂资源的包没有STX）。Language动态读取目录；点击标题刷新，上下滑动翻页，最多显示32个有效包。选择后退出整个自制会话返回WALKMAN再加载。

翻译、字体回退和索尼设置映射不混用编号。包限定本固件的7310项资源ABI，校验SHA、大小/偏移/UTF16、必需文字与动态参数数量；损坏/缺失包回退原厂资源。Language只在验证过的用户VFAT保存ID，不直接修改原厂DB/NVP，也不自动重启或刷机。不要把PC测试preload库/Python脚本复制到播放器。

## 范围和容量

英文新增/修订589项；简体补空234项、合计修订599项；繁体补空232项、合计修订597项。统一1seg，不使用翻译API。原有有效中文尽量保留，图片按用户要求全部保留原样。

全部翻译STX只在用户存储，合计341,536字节；中文字体复用原厂文件，不重复安装。系统相对候选9只变同长度SpiderApp中的缓存桥接，文字/字体/图片/其他文件和元数据原样，逻辑大小和密集分配占用均增加0。系统相对原版仍有早期入口/图标的50,556字节增量，并非声称比原版增加0。

容量模型扣保留块后余29,003,776字节（约27.66MiB），模型不能保证实机刷写安全。压缩UPG仍可能略变，不能用其压缩大小推断root分区占用。原厂根文件系统/软件行为仍需实机验证。

离线通过：原ARM一次加载/逐项查询/失败回退及384轮缓存复用/清理、实际ARM语言APP动态发现/保存/翻页/返回、主机短写/中断/失败/错盘拒绝、中文新字符原LCF渲染、49项Python测试、root完整对比与Rockbox独立解包。OS/显示/挂载/驱动有夹具，不能称为全机运行或音频硬件验证。

候选8/9及历史10保留。回退仍依赖设备能被原更新器识别；不要为取得成功报告反复刷机。03_RECORDS只供PC审阅。
"""
 (kit/'START_HERE.md').write_text(instructions,encoding='utf-8');(kit/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(kit).as_posix()+'\n'for p in sorted(kit.rglob('*'))if p.is_file()))
 z=d/('NW-X1060-'+version+'-candidate12-language-cache-manual-test.zip');assert not z.exists()
 with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,6)as archive:
  for p in sorted(kit.rglob('*')):
   if p.is_file():archive.write(p,p.relative_to(kit).as_posix())
 with zipfile.ZipFile(z)as archive:
  assert archive.testzip()is None
  for p in kit.rglob('*'):
   if p.is_file():assert archive.read(p.relative_to(kit).as_posix())==p.read_bytes()
 (work/'package-audit.json').write_text(json.dumps({**summary,'zip_sha256':sha(z),'zip_bytes':z.stat().st_size,'zip_readback_passed':True,'builder_sha256':sha(Path(__file__))},indent=2)+'\n');print(json.dumps({k:summary[k]for k in ['passed','profile','revision','upg_sha256','upg_bytes','extra_allocated_system_bytes','capacity_model_available_nonreserved_bytes']}|{'zip':str(z),'zip_sha256':sha(z)},indent=2))
if __name__=='__main__':main()
