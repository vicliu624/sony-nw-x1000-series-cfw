"""Bounded live research: metadata/standard status only, no raw device opens."""
from pathlib import Path
import argparse,datetime,hashlib,json
from terminal_client import connect,execute
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('host');p.add_argument('--code-file',required=True)
p.add_argument('--detail',action='store_true',help='second phase: bindings, mapped files and verified standard attributes')
p.add_argument('--identity',action='store_true',help='final narrow identity and standard runtime observations')
a=p.parse_args();code=Path(a.code_file).read_text(encoding='ascii').strip()
out=ROOT/'work/terminal-live'/datetime.datetime.now(datetime.timezone.utc).strftime('research-%Y%m%dT%H%M%SZ')
out.mkdir(parents=True,exist_ok=False)
queries={
 'baseline':'id; uname -a; cat /proc/cpuinfo; cat /proc/meminfo; cat /proc/mtd; cat /proc/mounts; df; cat /proc/cmdline',
 'device_inventory':'ls -l /dev; ls -l /dev/sound /dev/v4l /dev/fb /dev/input; ls -l /sys/class; ls -l /sys/bus; ls -l /proc/driver',
 'driver_status':'cat /proc/modules; cat /proc/devices; cat /proc/interrupts; cat /proc/ioports; cat /proc/iomem; ls -l /sys/module',
 'process_permissions':'''for d in /proc/[0-9]*; do if [ -r "$d/status" ]; then echo "PROCESS $d"; grep -E '^(Name|Pid|PPid|Uid|Gid|Groups|CapInh|CapPrm|CapEff):' "$d/status"; fi; done''',
 'usb_metadata':'''for f in /sys/module/g_nwm/parameters/mode /sys/module/g_nwm/parameters/product /sys/module/g_nwm/parameters/iserial_len /sys/module/g_nwm_msc/parameters/file /sys/module/g_nwm_msc/parameters/removable; do if [ -r "$f" ]; then echo "FILE $f"; cat "$f"; fi; done; ls -l /sys/devices/platform; ls -l /sys/class/usb_gadget''',
 'network_metadata':'''cat /proc/net/dev; cat /proc/net/route; cat /proc/net/wireless; for d in /sys/class/net/*; do echo "INTERFACE $d"; for n in type mtu flags operstate carrier; do if [ -r "$d/$n" ]; then echo "$n"; cat "$d/$n"; fi; done; done; /sbin/iptables -L INPUT -n''',
 'filesystem_metadata':'''cat /etc/fstab; cat /proc/filesystems; cat /proc/partitions; for d in /sys/block/*; do echo "BLOCK $d"; for n in size removable ro queue/logical_block_size queue/hw_sector_size; do if [ -r "$d/$n" ]; then echo "$n"; cat "$d/$n"; fi; done; done''',
 'kernel_driver_messages':"dmesg | grep -i -E 'si470|radio|codec|cs42|r2a|s1r72|nand|memory|mp200|lcd|touch|sd8'",
}
if a.detail:
 queries={
  'i2c_bindings':'''ls -l /sys/bus/i2c/devices; for d in /sys/bus/i2c/devices/*; do echo "I2C $d"; ls -l "$d"; if [ -r "$d/name" ]; then cat "$d/name"; fi; done''',
  'display_audio':'''for d in /sys/class/graphics/* /sys/class/video4linux/* /sys/class/input/*; do echo "DEVICE $d"; ls -l "$d"; for n in name bits_per_pixel virtual_size stride; do if [ -r "$d/$n" ]; then echo "$n"; cat "$d/$n"; fi; done; done; ls -l /proc/asound; for f in /proc/asound/cards /proc/asound/pcm /proc/asound/devices /proc/asound/version; do if [ -r "$f" ]; then echo "FILE $f"; cat "$f"; fi; done''',
  'application_chain':'''for d in /proc/[0-9]*; do if [ -r "$d/status" ]; then n=$(sed -n 's/^Name:[[:space:]]*//p' "$d/status"); case "$n" in app|appproxy|sysmgrd) echo "PROCESS $d"; grep -E '^(Name|Tgid|Pid|PPid|Uid|Gid|Groups|CapPrm|CapEff):' "$d/status"; ls -l "$d/exe" "$d/cwd"; ls -l "$d/fd"; cat "$d/maps";; esac; fi; done''',
  'stock_binary_identity':'md5sum /usr/local/bin/sysmgrd /usr/local/bin/appproxy /lib/libc.so.6 /lib/ld-linux.so.3; ls -l /usr/local/bin/sysmgrd /usr/local/bin/appproxy /lib/libc.so.6 /lib/ld-linux.so.3',
  'mtd_sysfs':'''for d in /sys/class/mtd/mtd[0-9]; do echo "MTD $d"; for n in name size erasesize writesize oobsize type flags; do if [ -r "$d/$n" ]; then echo "$n"; cat "$d/$n"; fi; done; done''',
 }
if a.identity:
 queries={
  'module_identity':'md5sum /lib/modules/icx_si470x_radio_tuner.ko /lib/modules/r2A15602LG_d.ko /lib/modules/icx_touch_screen.ko /lib/modules/s1r72v17_usbc_icx1087.ko /lib/modules/g_nwm.ko /lib/modules/g_nwm_msc.ko',
  'runtime_clock':'date; cat /proc/uptime; cat /proc/loadavg; cat /proc/sys/kernel/osrelease; cat /proc/sys/kernel/version',
  'legacy_class_layout':'ls -l /sys/class/mtd/mtd1; ls -l /sys/devices/platform/i2c-0/0-0010; ls -l /sys/devices/platform/i2c-0/0-001e; ls -l /sys/devices/platform/i2c-0/0-0020; ls -l /sys/devices/platform/s1r72v17',
 }
report={'scope':'Read-only live standard proc/sysfs attributes, directory metadata, process credentials and filtered kernel messages. No ioctl, raw device reads, device scripts, network reconfiguration or device file writes.','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'queries':{}}
for name,cmd in queries.items():
 try:
  with connect(a.host,2323,ROOT/'work/terminal-review/computer/server-cert.sha256',code) as s:data,status=execute(s,cmd,45)
  (out/(name+'.txt')).write_bytes(data)
  report['queries'][name]={'command':cmd,'status':status,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
  print(name,'status='+str(status),'bytes='+str(len(data)),flush=True)
 except Exception as e:
  report['queries'][name]={'command':cmd,'error':str(e)}
  print(name,'ERROR',str(e),flush=True)
 (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('Saved:',out)
