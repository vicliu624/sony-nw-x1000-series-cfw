"""Replay exact Sony loader with fake module tools on the PC. No device IO.

Uses only the hash-bound original rootfs, never a generated candidate root tree.
This characterizes shell control flow, not kernel/SDIO timing or restoration.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT / 'work/upg-jp/verified-3.bin'
EXPECTED = 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
OUT = ROOT / 'work/espnow-stock-loader-tests'


def original_loader(name='wlan_load_driver.sh'):
    if hashlib.sha256(IMAGE.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError('unqualified rootfs')
    with tarfile.open(IMAGE, 'r:gz') as archive:
        matches = [m for m in archive.getmembers()
                   if m.name.lstrip('./') == 'usr/local/bin/'+name]
        if len(matches) != 1 or not matches[0].isfile():
            raise ValueError('ambiguous original loader')
        return archive.extractfile(matches[0]).read()


def replay(script, mode):
    with tempfile.TemporaryDirectory(prefix='loader-', dir=OUT) as temp:
        folder = Path(temp)
        (folder / 'loader.sh').write_bytes(script)
        # No real module utility can be reached: all three commands are private
        # shell functions. grep is the only external executable used by Sony.
        harness = r'''
insmod() {
    printf 'insmod %s\n' "$*" >> "$LAB_TRACE"
    case "$1" in
    */sd8686.ko)
        radio_attempts=$((radio_attempts+1))
        case "$LAB_MODE" in
        existing|radio-fail) return 1;;
        radio-retry) [ "$radio_attempts" -ge 3 ]; return $?;;
        esac;;
    */mp200_sdio.ko)
        [ "$LAB_MODE" != sdio-fail ] || return 1;;
    esac
    return 0
}
rmmod() { printf 'rmmod %s\n' "$*" >> "$LAB_TRACE"; return 0; }
lsmod() {
    printf 'lsmod\n' >> "$LAB_TRACE"
    if [ "$LAB_MODE" = existing ]; then
        printf 'sd8xxx\nmp200_sdio\nwlan_pm_register\nwlan_pwr_ctrl\n'
    fi
    return 0
}
radio_attempts=0
. "$LAB_SCRIPT"
'''
        trace = folder / 'trace'
        env = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C',
               'LAB_MODE': mode, 'LAB_TRACE': str(trace),
               'LAB_SCRIPT': str(folder / 'loader.sh'),
               'fw_dir': '/contents/HOMEBREW/data/espnow/candidate'}
        run = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-c', harness],
                             env=env, cwd=folder, capture_output=True,
                             text=True, timeout=10)
        lines = trace.read_text().splitlines()
        radio = [s for s in lines if s.startswith('insmod /lib/modules/sd8686.ko ')]
        sdio = [s for s in lines if s == 'insmod /lib/modules/mp200_sdio.ko']
        expected_args = ('helper_name=/contents/HOMEBREW/data/espnow/candidate/helper_sd.bin '
                         'fw_name=/contents/HOMEBREW/data/espnow/candidate/sd8686.bin')
        assert all(s.endswith(expected_args) for s in radio)
        assert not run.stderr, run.stderr
        expected = {'success': (0, 1, 1), 'existing': (0, 1, 1),
                    'radio-retry': (0, 3, 3), 'radio-fail': (1, 10, 10),
                    'sdio-fail': (1, 0, 10)}[mode]
        assert (run.returncode, len(radio), len(sdio)) == expected
        return {'mode': mode, 'exit': run.returncode, 'radio_attempts': len(radio),
                'sdio_attempts': len(sdio), 'trace': lines}


def replay_unload(script,mode):
    with tempfile.TemporaryDirectory(prefix='unload-',dir=OUT) as temp:
        folder=Path(temp);(folder/'wlanapi.sh').write_bytes(script)
        harness=r'''
iwconfig() { printf 'iwconfig\n' >> "$LAB_TRACE"; printf 'eth0 IEEE 802.11\n'; }
ifconfig() {
    printf 'ifconfig %s\n' "$*" >> "$LAB_TRACE"
    if [ "$#" = 1 ]; then
        if [ "$LAB_MODE" = down ]; then printf 'eth0\n DOWN\n'; else printf 'eth0\n UP BROADCAST RUNNING\n'; fi
    fi
    return 0
}
rmmod() {
    printf 'rmmod %s\n' "$*" >> "$LAB_TRACE"
    [ "$LAB_MODE" != missing ] && [ "$LAB_MODE" != "$1" ]
}
forbid() { printf 'FORBIDDEN %s\n' "$*" >> "$LAB_TRACE"; return 99; }
killall() { forbid killall "$@"; }
nvp() { forbid nvp "$@"; }
insmod() { forbid insmod "$@"; }
mknod() { forbid mknod "$@"; }
rm() { forbid rm "$@"; }
iwpriv() { forbid iwpriv "$@"; }
pidof_in() { forbid pidof_in "$@"; }
. "$LAB_SCRIPT" unload
'''
        trace=folder/'trace'
        run=subprocess.run(['/bin/bash','--noprofile','--norc','-c',harness,str(folder/'runner')],
                           env={'PATH':'/usr/bin:/bin','LC_ALL':'C','LAB_MODE':mode,
                                'LAB_SCRIPT':str(folder/'wlanapi.sh'),'LAB_TRACE':str(trace)},
                           cwd=folder,capture_output=True,text=True,timeout=10)
        lines=trace.read_text().splitlines()
        assert not run.stderr,run.stderr
        assert all(line=='iwconfig' or line.startswith(('ifconfig ','rmmod ')) for line in lines),lines
        modules=['sd8xxx','mp200_sdio','wlan_pm_register','wlan_pwr_ctrl']
        assert [s for s in lines if s.startswith('rmmod ')]==['rmmod '+m for m in modules]
        assert ('ifconfig eth0 down' in lines)==(mode!='down')
        # The stock err bookkeeping loses later rmmod failures; a zero exit is
        # not proof of complete unload. The native runner checks /proc/modules.
        assert run.returncode==(1 if mode in ('sd8xxx','missing') else 0)
        return {'mode':mode,'exit':run.returncode,'trace':lines}


def replay_initializer(script,region='00',failure='none'):
    with tempfile.TemporaryDirectory(prefix='init-',dir=OUT) as temp:
        folder=Path(temp);(folder/'wlanapi.sh').write_bytes(script);trace=folder/'trace'
        harness=r'''
iwpriv() { printf 'iwpriv %s\n' "$*" >> "$LAB_TRACE"; [ "$LAB_FAIL" != "$2" ]; }
nvp() { printf 'nvp %s\n' "$*" >> "$LAB_TRACE"; printf 'nvp read byte %s\n' "$LAB_REGION"; }
wlanconfig() { printf 'wlanconfig %s\n' "$*" >> "$LAB_TRACE"; [ "$LAB_FAIL" != "$4" ]; }
iwconfig() { printf 'iwconfig %s\n' "$*" >> "$LAB_TRACE"; [ "$LAB_FAIL" != "$2" ]; }
. "$LAB_SCRIPT" load
'''
        env={'PATH':'/usr/bin:/bin','LC_ALL':'C','LAB_REGION':region,'LAB_FAIL':failure,
             'LAB_TRACE':str(trace),'LAB_SCRIPT':str(folder/'wlanapi.sh'),
             'proc_load':'w8_proc_init','WIF':'eth0'}
        run=subprocess.run(['/bin/bash','--noprofile','--norc','-c',harness,str(folder/'runner')],
                           env=env,cwd=folder,capture_output=True,text=True,timeout=10)
        expected_region='0x41' if region=='FF' else ['0x41','0x10','0x30','0x30','0x30','0x30','0x30','0x10'][int(region)]
        lines=trace.read_text().splitlines()
        assert lines==['iwpriv eth0 deepsleep 0','nvp zr 11 1',
                       'iwpriv eth0 setregioncode '+expected_region,'iwpriv eth0 tpccfg 0',
                       'wlanconfig eth0 hostcmd /etc/hostcmd.conf pa_cfg_ext_set','iwconfig eth0 txpower 15'],lines
        assert not run.stderr,run.stderr
        assert run.returncode==(1 if failure=='deepsleep' else 0)
        return {'nvp_region':region,'failed_command':failure,'exit':run.returncode,'trace':lines}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    script = original_loader()
    unload=original_loader('wlanapi.sh')
    report = {'passed': True, 'rootfs_sha256': EXPECTED,
              'loader_sha256': hashlib.sha256(script).hexdigest(),
              'shell': 'host bash sourcing original script',
              'module_commands_substituted': True, 'device_accessed': False,
              'hardware_restoration_qualified': False,
              'cases': [replay(script, mode) for mode in
                        ('success', 'existing', 'radio-retry', 'radio-fail', 'sdio-fail')],
              'unload_script_sha256':hashlib.sha256(unload).hexdigest(),
              'unload_cases':[replay_unload(unload,mode) for mode in
                              ('up','down','sd8xxx','mp200_sdio','wlan_pm_register','wlan_pwr_ctrl','missing')],
              'initialization_cases':[replay_initializer(unload,region) for region in
                                      ('00','01','02','03','04','05','06','07','FF')]+
                                     [replay_initializer(unload,failure=failure) for failure in
                                      ('deepsleep','setregioncode','tpccfg','pa_cfg_ext_set','txpower')]}
    (OUT / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in ('cases','unload_cases','initialization_cases')}, indent=2))
    for case in report['cases']:
        print(case['mode'], 'exit', case['exit'], 'radio attempts', case['radio_attempts'])
    for case in report['unload_cases']:print('unload',case['mode'],'exit',case['exit'])
    print('initialization cases',len(report['initialization_cases']))


if __name__ == '__main__':
    main()
