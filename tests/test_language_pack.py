import sys,struct,unittest,io,tarfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from resources import STX_MAGIC
from language_pack import manifest,parse_manifest,validate_id,REQUIRED_IDS,PARAMETERS
from language_profile import audit_minimal_overlay

def stx():
 b=bytearray(56+7310*4);b[:len(STX_MAGIC)]=STX_MAGIC;offsets={}
 for count in range(4):offsets[count]=len(b);b+=('A'+'\ue42a'*count+'\0').encode('utf-16le')
 for i in REQUIRED_IDS:struct.pack_into('<I',b,56+i*4,offsets[PARAMETERS.get(str(i),{'en':0})['en']])
 struct.pack_into('<III',b,44,56,7310,len(b));return bytes(b)

def archive(files):
 out=io.BytesIO()
 with tarfile.open(fileobj=out,mode='w:gz')as tar:
  for name,data in files:
   info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;tar.addfile(info,io.BytesIO(data))
 return out.getvalue()
class PackTests(unittest.TestCase):
 def test_external_and_stock_manifest(self):
  data=stx();self.assertEqual(parse_manifest(manifest('en','English','en',data),data)['wording'],'wording.stx');self.assertEqual(parse_manifest(manifest('jp','Japanese','jp'))['wording'],'stock')
 def test_bad_ids_and_path_injection(self):
  for s in ['../en','/en','en/x','en\\x','stock','Stock','']:
   with self.assertRaises(ValueError):validate_id(s)
  raw=manifest('en','English','en',stx()).replace(b'wording=wording.stx',b'wording=/etc/passwd')
  with self.assertRaises(ValueError):parse_manifest(raw,stx())
 def test_wrong_resource_identity_and_duplicate_fields(self):
  raw=manifest('en','English','en',stx())
  with self.assertRaises(ValueError):parse_manifest(raw+b'api=1\n',stx())
  with self.assertRaises(ValueError):parse_manifest(raw,stx()+b'\0\0')
 def test_bad_base_name_and_target(self):
  for name,base in [('English\nwording=/etc/passwd','en'),('English','unverified')]:
   with self.assertRaises(ValueError):manifest('en',name,base,stx())
  with self.assertRaises(ValueError):parse_manifest(manifest('en','English','en',stx()).replace(b'stx7310',b'stx7308'),stx())
 def test_only_same_size_elf_overlay_allowed(self):
  files=[('./usr/local/bin/SpiderApp',b'AAAA'),('./usr/local/share/gemini/res/stx/ucs2-dev-en.stx',b'STX')]
  changed=[(files[0][0],b'BBBB'),files[1]];self.assertEqual(audit_minimal_overlay(archive(files),archive(changed))['system_logical_growth_from_baseline_bytes'],0)
 def test_embedded_wording_and_new_entries_rejected(self):
  files=[('./usr/local/bin/SpiderApp',b'AAAA'),('./usr/local/share/gemini/res/stx/ucs2-dev-en.stx',b'STX')]
  for bad in [[files[0],(files[1][0],b'NEW')],files+[('./new-language.stx',b'text')],[(files[0][0],b'BIGGER'),files[1]]]:
   with self.assertRaises(ValueError):audit_minimal_overlay(archive(files),archive(bad))
if __name__=='__main__':unittest.main()
