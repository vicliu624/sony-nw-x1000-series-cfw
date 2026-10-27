"""Compare user-reported model/version against pinned Sony installer configuration."""
from pathlib import Path
import configparser,hashlib,io,json,subprocess,tarfile
ROOT=Path(__file__).resolve().parents[1]
device=json.loads((ROOT/'sources/device-under-test.json').read_text())
installer=ROOT/'firmware/original/NW-X1000_V1_11.exe'
digest=hashlib.sha256(installer.read_bytes()).hexdigest()
assert digest=='25c8290dbac1065809f39332614491958ef7c93ce6e2e67e8cb5f815009a5a81'
config_bytes=subprocess.run(['7z','x','-so',str(installer),'/NW-X10X0.ini'],capture_output=True,check=True).stdout
assert len(config_bytes)==592
config=configparser.ConfigParser(interpolation=None);config.read_string(config_bytes.decode('ascii'))
matches=[name for name in config.sections() if config[name].get('DeviceName')==device['model']]
assert len(matches)==1;section=config[matches[0]]
assert section['Version00']==device['firmware_version']=='1.11'
assert section['FWPackage00']=='NW_WM_FW.UPG'
upg=ROOT/'work/updater-jp/NW_WM_FW.UPG'
assert hashlib.sha256(upg.read_bytes()).hexdigest()=='002b6720b59f093a84440f554ffabe29f5879646839a5a28d43487b5cb41914b'
archive=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(archive).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
    rc=tar.extractfile('./etc/init.d/rc.sysinfo').read()
    models=tar.extractfile('./etc/models').read()
assert b'nvpflag -x mid' in rc and b'sysinfo bdrev' in rc and b'sysinfo lcd' in rc
report={'scope':__doc__,'reported_device':device,'installer_sha256':digest,
        'installer_configuration_sha256':hashlib.sha256(config_bytes).hexdigest(),
        'matching_section':matches[0],'model_version_configuration_match':True,
        'vendor_id':section['VID'],'product_id':section['PID'],'device_product':section['DevicePropertyProductInfo'],
        'firmware_package':section['FWPackage00'],'startup_sysinfo_sha256':hashlib.sha256(rc).hexdigest(),
        'models_database_sha256':hashlib.sha256(models).hexdigest(),
        'device_access':False,'hardware_qualified':False,
        'limits':['Model/version are user-reported, not USB or device observations.',
                  'Installer lists the model; no updater is executed and no device model ID/NVP is read.',
                  'Startup derives model/board/LCD and other hardware fields dynamically; actual values remain unknown.',
                  'Does not establish actual partition capacity, UI/USB recovery or flash safety.']}
(ROOT/'sources/native-device-target-match.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
