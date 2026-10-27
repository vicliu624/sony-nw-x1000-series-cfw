import sys,struct,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from resources import STX_MAGIC,parse_stx
from wording import complete_missing,replace_verified_texts

def resource(items):
 b=bytearray(56+len(items)*4);b[:len(STX_MAGIC)]=STX_MAGIC;struct.pack_into('<II',b,44,56,len(items))
 for i,s in enumerate(items):
  if s:struct.pack_into('<I',b,56+i*4,len(b));b+=s.encode('utf-16-le')+b'\0\0'
 struct.pack_into('<I',b,52,len(b));return bytes(b)
class WordingTests(unittest.TestCase):
 def test_preserves_original_ids_tail_and_dynamic_tokens(self):
  base=resource(['Yes','','','Homebrew']);jp=resource(['はい','曲\ue42a','']);new=complete_missing(base,jp,{1:'Tracks \ue42a'});self.assertEqual(parse_stx(new),['Yes','Tracks \ue42a','','Homebrew']);self.assertEqual(base[56:60],new[56:60]);self.assertEqual(base[64:],new[64:len(base)])
 def test_rejects_existing_or_incomplete_translation(self):
  for rows in ({},{0:'Changed',1:'Missing'}):
   with self.assertRaises(ValueError):complete_missing(resource(['Original','']),resource(['原文','未訳']),rows)
 def test_rejects_placeholder_loss_or_order_change(self):
  for text in ['Missing','\ue42b \ue42a']:
   with self.assertRaises(ValueError):complete_missing(resource(['']),resource(['\ue42a \ue42b']),{0:text})
 def test_rejects_embedded_nul_and_bad_mapping(self):
  with self.assertRaises(ValueError):complete_missing(resource(['']),resource(['文']),{0:'A\0B'})
  base=bytearray(resource(['']));struct.pack_into('<I',base,52,0)
  with self.assertRaises(ValueError):complete_missing(base,resource(['文']),{0:'Text'})
class FallbackTests(unittest.TestCase):
 def test_only_verified_fallback_can_change(self):
  base=resource(['Original','録音','Homebrew']);new=replace_verified_texts(base,{1:'録音'},{1:'Recording'});self.assertEqual(parse_stx(new),['Original','Recording','Homebrew'])
  with self.assertRaises(ValueError):replace_verified_texts(base,{1:'Different source'},{1:'Recording'})
 def test_rejects_undeclared_id(self):
  with self.assertRaises(ValueError):replace_verified_texts(resource(['録音']),{0:'録音'},{1:'Recording'})
if __name__=='__main__':unittest.main()
