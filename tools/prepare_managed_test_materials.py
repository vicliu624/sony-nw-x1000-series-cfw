"""Assemble private review materials, not an installation or public release."""
import argparse,hashlib,json,shutil,time
from app_registry import ROOT
from review_managed_remote_profile import private,receipt,digest

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--firmware-review',required=True)
 parser.add_argument('--first-use-plan',required=True)
 parser.add_argument('--core2-review',required=True)
 parser.add_argument('--pairing-review',required=True)
 args=parser.parse_args()
 fp,firmware=receipt(args.firmware_review);mp=private(args.first_use_plan);plan=json.loads(mp.read_text())
 kp,core=receipt(args.core2_review);pp=private(args.pairing_review);pair=json.loads(pp.read_text())
 if not firmware['prepared'] or firmware['ready_to_flash'] or not core['built'] or plan['schema']!='x1000-remote-first-use-v1':raise ValueError('Expected private diagnostic inputs')
 if plan['pairing_review_sha256']!=digest(pp) or (mp.parent/'installation-attempt.private.json').exists():raise ValueError('First-use input already attempted or mismatched')
 component_path=private(plan['component_review']);component=json.loads(component_path.read_text())
 if digest(component_path)!=plan['component_sha256'] or component['configuration_kind']!='unqualified-private':raise ValueError('External component review changed')
 # Tie the UPG's reviewed system layout to the external supervisor inputs.
 layout_paths=[name for name,sha in firmware['inputs'].items() if sha==firmware['layout_review_sha256']]
 if len(layout_paths)!=1:raise ValueError('Firmware layout provenance is ambiguous')
 layout_path,layout=receipt(layout_paths[0])
 if digest(layout_path)!=firmware['layout_review_sha256']:raise ValueError('Firmware layout review changed')
 factory=layout['host_build']['remote_factory_profile']
 if factory['sha256']!=component['components']['supervisor']['sha256']:raise ValueError('Firmware/external supervisor mismatch')
 supervisor_path,supervisor=receipt(factory['review'])
 if digest(supervisor_path)!=component['receipts']['supervisor']['sha256']:raise ValueError('Supervisor receipt mismatch')
 byname={row['relative']:row for row in plan['files']}
 for name,leaf in [('service','service.arm'),('owner','owner.arm'),('config','config.bin')]:
  if byname['runtime/'+leaf]['sha256']!=supervisor['inputs'][name]['sha256']:raise ValueError('Firmware/external runtime mismatch: '+name)
 if byname['session.keys']['sha256']!=pair['files']['session.keys']['sha256']:raise ValueError('External transport pairing mismatch')
 upg=private(firmware['artifact'])
 if digest(upg)!=firmware['sha256']:raise ValueError('Firmware identity mismatch')
 out=ROOT/'work/managed-test-materials'/str(time.time_ns());out.mkdir(parents=True)
 updater=ROOT/'work/candidate6-first-device-inputs/sony-updater'
 independent=ROOT/'work/updater-static-review-1/extracted'
 for name in ('FWUpdater.exe','FWUpdaterCom.dll','FWUpdaterRes.dll','NW-X10X0.ini'):
  if digest(updater/name)!=digest(independent/name):raise ValueError('Original updater copies differ')
 if digest(updater/'NW_WM_FW.UPG')!='002b6720b59f093a84440f554ffabe29f5879646839a5a28d43487b5cb41914b':raise ValueError('Updater template lacks pinned stock package')
 shutil.copytree(updater,out/'01_PC_UPDATE');shutil.copy2(upg,out/'01_PC_UPDATE/NW_WM_FW.UPG')
 external=out/'02_FIRST_USE';external.mkdir()
 shutil.copy2(mp,external/'plan.private.json')
 for row in plan['files']:
  source=private(mp.parent/'files'/row['relative'])
  if source.stat().st_size!=row['bytes'] or digest(source)!=row['sha256']:raise ValueError('External file differs')
  target=external/'files'/row['relative'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
 for name in ('Install-RemoteFirstUse.ps1','RemoteFirstUse.psm1'):shutil.copy2(ROOT/'tools'/name,external/name)
 controller=out/'03_CORE2';controller.mkdir()
 for name,row in core['artifacts'].items():
  source=private(row['local'])
  if digest(source)!=row['sha256']:raise ValueError('Controller file differs')
  shutil.copy2(source,controller/name)
 command=private(pp.parent/'controller-usb.private.txt')
 if digest(command)!=pair['files']['controller-usb.private.txt']['sha256']:raise ValueError('Controller pairing differs')
 shutil.copy2(command,controller/command.name)
 (out/'READ_BEFORE_TESTING.md').write_text('''# Private diagnostic materials

Not approved or qualified for installation. No device has been changed by preparation.
The firmware retains Sony's formatting/updater behavior. A failed installation may
leave the player unable to boot or reconnect; reflashing is not guaranteed recovery.

## Contents

- 01_PC_UPDATE: unchanged original updater/INI/DLL/licenses with the reviewed diagnostic UPG.
- 02_FIRST_USE: eight private external inputs and a separate manual installer. Never drag-copy PN seeds over existing state.
- 03_CORE2: retained controller images and a secret RAM-only USB pairing command. Do not publish this folder.

## Proposed acceptance order

1. Review capacity, original-component identity and current device conditions before deciding on installation.
2. Verify the intended Sony USB disk identity. External first-use installation must refuse an existing wireless-remote directory. An uncertain attempt requires review.
3. If installation is explicitly chosen, use Sony's unchanged updater normally; do not modify INI/version checks. Do not disconnect or reset during update.
4. First verify stock player boot, local controls and playback with remote OFF. Stop on a boot/storage fault.
5. Enable ESP-NOW through wireless settings, then enable the separate player remote function. Provision Core2 with the private command only through its local USB interface.
6. Verify title/artist/state/volume, play/pause, previous/next and each of five stock play modes. Core2 alpha.6 and later also have a read-only library page; verify actual supported views, pagination and unsupported/stale/empty responses without assuming native playlist semantics.
7. Verify local touch responsiveness, remote OFF retirement, native Wi-Fi mutual exclusion, Homebrew handoff, repeated sleep/wake and USB ownership. Software OFF evidence alone does not measure standby current.

No script here automatically flashes X1060 or Core2. These materials do not prove
hardware acceptance. Record observations before extending scope or repeating any
failed first-use initialization. Never restore initial counters after radio use.
''',encoding='utf-8')
 files={p.relative_to(out).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in out.rglob('*') if p.is_file()}
 report=dict(prepared=True,ready_to_flash=False,device_accessed=False,published=False,contains_secrets=True,
  files=files,input_reviews={str(path.relative_to(ROOT)):digest(path) for path in (fp,mp,kp,pp)},
  firmware_external_pairing_consistency_checked=True,
  limits=['Private review materials only; no hardware qualification.','Do not distribute pairing/PN material.','Review manual first-test decision before installation.'])
 (out/'review.private.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(prepared=True,directory=out.relative_to(ROOT).as_posix(),ready_to_flash=False,contains_secrets=True,device_accessed=False),indent=2))
if __name__=='__main__':main()
