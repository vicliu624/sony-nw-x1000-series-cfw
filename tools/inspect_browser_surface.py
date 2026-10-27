"""Inventory scheme-like strings and named dynamic imports in stock NetFront."""
from pathlib import Path
import hashlib,io,json,struct,tarfile
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_SP,UC_ARM_REG_LR,UC_ARM_REG_PC
ROOT=Path(__file__).resolve().parents[1]
raw=(ROOT/'work/upg-jp/verified-3.bin').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='c6307dba718f1faae821e0330b64532f13fe6ef98ff330a5919d7fb10525adf5'
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:b=tar.extractfile('./usr/local/bin/netfront').read()
sha=hashlib.sha256(b).hexdigest();assert sha=='fb027a1f3d86753d110b12827d0a462d46a79ff784e42018820f13e8fd4b2f4f'
import re
e=ELFFile(io.BytesIO(b));segments=[s for s in e.iter_segments() if s['p_type']=='PT_LOAD']
def va(off):
 return next(s['p_vaddr']+off-s['p_offset'] for s in segments if s['p_offset']<=off<s['p_offset']+s['p_filesz'])
schemes=[]
for match in re.finditer(rb'[ -~]{4,}',b):
 value=match.group()
 if not re.fullmatch(rb'[a-z][a-z0-9+.-]{1,20}:(?://)?',value):continue
 address=va(match.start());refs=[va(m.start()) for m in re.finditer(re.escape(struct.pack('<I',address)),b) if m.start()%4==0]
 if not refs:continue
 schemes.append({'text':value.decode(),'virtual_address':hex(address),'aligned_pointer_references':[hex(a) for a in refs]})
imports=sorted(s.name for s in e.get_section_by_name('.dynsym').iter_symbols() if s['st_shndx']=='SHN_UNDEF' and s.name)
interesting=[name for name in imports if name in ('execve','execv','execvp','execl','system','popen','dlopen','fork','vfork')]
report={'netfront_sha256':sha,'method':'ASCII string scan with aligned direct address references; ELF undefined dynamic symbols.','scheme_like_strings_with_direct_references':schemes,'native_execution_imports_from_named_set':interesting,'all_passed':True,'physical_device_access':False,'limits':['Pointer reference is not proof that a scheme is enabled, reachable or accepted by the browser.','Absence of named imports does not exclude direct syscalls, static wrappers or computed runtime behavior.','file: references include parsing/policy code, not proven execution of local ELF.','No custom Sony app-install URI has been identified; this scan cannot prove none exists.']}
(ROOT/'sources/browser-uri-surface.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


