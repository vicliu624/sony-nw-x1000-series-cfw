"""Read-only stock firmware/source audit for USB terminal feasibility; PC only."""
from pathlib import Path
import hashlib, io, json, re, tarfile
from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'work/usb-terminal-audit'
OUT.mkdir(parents=True, exist_ok=True)
def sha(b): return hashlib.sha256(b).hexdigest()
raw = (ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert sha(raw) == 'c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
report = {'physical_device_access': False, 'stock_rootfs_sha256': sha(raw)}
with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as tf:
    members = tf.getmembers()
    report['usb_modules'] = [m.name for m in members if '/lib/modules/' in m.name and any(x in m.name.lower() for x in ('usb','g_nwm','serial','gadget'))]
    report['stock_files'] = {}
    for name in ('./usr/local/bin/load_usb_epson','./etc/AppList.conf','./etc/passwd','./etc/init.d/gemini'):
        b=tf.extractfile(name).read()
        (OUT/Path(name).name).write_bytes(b)
        report['stock_files'][name]={'sha256':sha(b),'text':b.decode('utf-8',errors='replace')}
    report['module_symbols']={}
    for name in report['usb_modules']:
        b=tf.extractfile(name).read(); elf=ELFFile(io.BytesIO(b)); tab=elf.get_section_by_name('.symtab')
        syms=[s.name for s in tab.iter_symbols()]
        modinfo=elf.get_section_by_name('.modinfo')
        report['module_symbols'][name]={'sha256':sha(b),'elf_flags':hex(elf['e_flags']),'modinfo':modinfo.data().decode('ascii',errors='replace').split('\0') if modinfo else [],'exports':[s.removeprefix('__ksymtab_') for s in syms if s.startswith('__ksymtab_')],'relevant_symbols':[s for s in syms if re.search(r'gadget|register|unregister|serial|acm|tty|function|nwm|ioctl|open|read|write',s,re.I)]}
        (OUT/Path(name).name).write_bytes(b)
    report['shell_entries']=[{'name':m.name,'link':m.linkname,'mode':oct(m.mode)} for m in members if m.name in ('./bin/sh','./bin/busybox','./dev/ptmx','./dev/pts')]
kernel=(ROOT/'work/upg-jp/verified-1.bin').read_bytes()
assert sha(kernel)=='6877f0e38a9d0c1aa08baefbf9f20a4ad9f755ca30300135309c2c5b9a64d645'
elf=ELFFile(io.BytesIO((ROOT/'work/isolation-audit/x1000-kernel-analysis.elf').read_bytes()))
assert elf.get_section_by_name('.kernel').data()[:len(kernel)]==kernel
syms={s.name:s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
report['kernel_sha256']=sha(kernel)
report['kernel_relevant_symbols']={s:hex(v) for s,v in syms.items() if re.search(r'gadget|^gs_|gserial|g_serial|gadgetfs|usb_gadget|^pty_|^ptmx_|^devpts_|^init_devpts|^sys_init_module$|^sys_delete_module$',s,re.I)}
apis=['alloc_tty_driver','tty_register_driver','tty_unregister_driver','tty_set_operations','tty_std_termios']
report['kernel_tty_exports']={s:hex(syms['__ksymtab_'+s]) for s in apis if '__ksymtab_'+s in syms}
controller=report['module_symbols']['./lib/modules/s1r72v17_usbc_icx1087.ko']
assert {'usb_gadget_register_driver','usb_gadget_unregister_driver'} <= set(controller['exports'])
assert all(s in syms for s in ('sys_init_module','sys_delete_module','ptmx_open','pty_init','init_devpts_fs'))
assert not any('/g_serial.' in n or '/gadgetfs.' in n for n in report['usb_modules'])
assert not any(s in syms for s in ('gs_bind','gs_init','gadgetfs_init','init_gadgetfs'))
config=ROOT/'work/integration-0.1.0-dev.16/system-overlay/etc/AppList.conf'
report['candidate_applist']={'sha256':sha(config.read_bytes()),'homebrew_line':next(l for l in config.read_text().splitlines() if l.startswith('0x00030001'))}
parsed=json.loads((ROOT/'sources/native-applist-full-config.json').read_text())
report['candidate_parsed_homebrew']=next(r for c in parsed['cases'] if c['case']=='full-merged' for r in c['records'] if r['id']=='0x30001')
assert report['candidate_parsed_homebrew']['uid']==report['candidate_parsed_homebrew']['gid']==0
report['permission_limit']='Parser getuid/getgid and child syscall effects were simulated. Candidate requests manager/root credentials; actual device process UID/GID/capabilities were not read.'
source=ROOT/'work/downloads/linux-kernel-2.6.10.local.tgz'
report['gpl_source_sha256']=sha(source.read_bytes())
report['source_files']={}
with tarfile.open(source, 'r:gz') as tf:
    for m in tf:
        n=m.name
        if not m.isfile(): continue
        if (re.search(r'drivers/usb/(gadget|.*s1r72|.*nwm)',n) and n.endswith(('.c','.h','Kconfig','Makefile'))) or n.endswith('icx1087_fu_defconfig'):
            b=tf.extractfile(m).read()
            dest=OUT/'gpl'/n.lstrip('./'); dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(b)
            text=b.decode('utf-8',errors='replace')
            matches=[{'line':i,'text':line} for i,line in enumerate(text.splitlines(),1) if re.search(r'CONFIG_USB|CONFIG_UNIX98|CONFIG_DEVPTS|CONFIG_MODULE|EXPORT_SYMBOL|usb_gadget_register_driver|usb_gadget_unregister_driver|register_chrdev|misc_register|EBUSY|g_serial|G_SERIAL|GADGETFS|gs_bind|gs_init|nwm_register',line)]
            report['source_files'][n]={'sha256':sha(b),'matches':matches}
(OUT/'audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ('stock_files','source_files','module_symbols')},indent=2))
print('Extracted relevant GPL files:',len(report['source_files']))
