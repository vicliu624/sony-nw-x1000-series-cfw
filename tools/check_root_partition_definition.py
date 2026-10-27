"""Read JP1.11 NAND module partition definition; no module/kernel/device execution."""
from pathlib import Path
import hashlib,io,json,struct,subprocess,tarfile
from elftools.elf.elffile import ELFFile
ROOT=Path(__file__).resolve().parents[1]
archive=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(archive).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
    raw=tar.extractfile('./lib/modules/icx1087-nand-p.ko').read()
digest=hashlib.sha256(raw).hexdigest()
assert digest=='3263ab460d48160549dba1c67d96a9a76ee47ff93281d061a6c663b1c191cdd9'
elf=ELFFile(io.BytesIO(raw));symbols=elf.get_section_by_name('.symtab')
table=next(s for s in symbols.iter_symbols() if s.name=='icx1087_nand_fixed_size_partitions')
assert table['st_size']==32
section=elf.get_section(table['st_shndx']);data=section.data();offset=table['st_value']
entry=data[offset:offset+32];size,partition_offset=struct.unpack_from('<QQ',entry,4)
relocations=elf.get_section_by_name('.rel.data')
name_relocation=next(r for r in relocations.iter_relocations() if r['r_offset']==offset)
name_symbol=symbols.get_symbol(name_relocation['r_info_sym'])
name_data=elf.get_section(name_symbol['st_shndx']).data()
name_offset=name_symbol['st_value']+struct.unpack_from('<I',entry)[0]
name=name_data[name_offset:].split(b'\0')[0].decode()
assert name=='ICX1087 NAND RootFS' and size==0x09400000 and partition_offset==0
init=elf.get_section_by_name('.init.text').data()
word=lambda address:struct.unpack_from('<I',init,address)[0]
assert word(0x9c0)==0xe59f4500 and word(0xec8)==offset
assert word(0xa28)==0xe9940300 # root size read as two 32-bit words
assert word(0xa38)==0xe584500c and word(0xa3c)==0xe5846010 # computed offset, not size
assert word(0x12a4)==0xe51f13e4 and word(0x12a8)==0xe3a02001
relocations=elf.get_section_by_name('.rel.init.text')
call=next(r for r in relocations.iter_relocations() if r['r_offset']==0x12ac)
assert symbols.get_symbol(call['r_info_sym']).name=='icx1087_nand_register'
literal=next(r for r in relocations.iter_relocations() if r['r_offset']==0xec8)
assert symbols.get_symbol(literal['r_info_sym'])['st_shndx']==table['st_shndx']
area=ROOT/'work/partition-source';area.mkdir(exist_ok=True)
copy=area/'initrd-nand-p.ko'
subprocess.run(['debugfs','-R','dump /lib/modules/icx1087-nand-p.ko '+str(copy),str(ROOT/'work/upg-jp/verified-2.bin')],check=True,capture_output=True)
assert hashlib.sha256(copy.read_bytes()).hexdigest()==digest
linuxrc=subprocess.run(['debugfs','-R','cat /linuxrc',str(ROOT/'work/upg-jp/verified-2.bin')],check=True,capture_output=True).stdout
assert linuxrc.index(b'icx1087-nand-i.ko')<linuxrc.index(b'icx1087-nand-p.ko')
report={'scope':__doc__,'module_sha256':digest,'initrd_module_identical':True,
        'partition_name':name,'definition_bytes':size,'definition_MiB':size//1048576,
        'fixed_table_section':section.name,'fixed_table_offset':hex(offset),
        'registration_call':'.init.text+0x12ac','registered_fixed_entries':1,
        'root_size_read':'.init.text+0xa28','computed_offset_stores':['.init.text+0xa38','.init.text+0xa3c'],
        'actual_device_capacity_verified':False,'capacity_qualified':False,
        'limits':['Fixed table and bounded instruction/relocation inspection, not full module initialization execution.',
                  'Does not prove actual hardware geometry, every alternate initialization path, MTD registration order or device partition listing.',
                  '148MiB is this stock module definition, not measured usable ext2 space or a flash-safety guarantee.',
                  'Rootfs/initrd read offline; no kernel modules loaded, no NVP or raw storage accessed.']}
(ROOT/'sources/native-root-partition-definition.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
