"""Complete empty STX records without changing IDs or existing strings."""
import re,struct
from resources import parse_stx

def complete_missing(base,japanese,translations):
 before=parse_stx(base);jp=parse_stx(japanese)
 if len(before)<len(jp):raise ValueError('Target resource is shorter than Japanese reference')
 expected={i for i,s in enumerate(jp) if s and not before[i]}
 if set(translations)!=expected:raise ValueError('Translation IDs must exactly match missing records')
 mapped=struct.unpack_from('<I',base,52)[0]
 if mapped!=len(base) or len(base)%2:raise ValueError('Unexpected mapped length or UTF16 alignment')
 result=bytearray(base)
 for i in sorted(expected):
  s=translations[i]
  if not isinstance(s,str) or not s or '\0' in s:raise ValueError('Invalid translation at '+str(i))
  source_tokens=re.findall('[\ue000-\uf8ff]',jp[i]);target_tokens=re.findall('[\ue000-\uf8ff]',s)
  if source_tokens!=target_tokens:raise ValueError('Dynamic placeholders changed at '+str(i))
  struct.pack_into('<I',result,56+i*4,len(result));result+=s.encode('utf-16-le')+b'\0\0'
 struct.pack_into('<I',result,52,len(result))
 after=parse_stx(result)
 if after!=[translations.get(i,s) for i,s in enumerate(before)]:raise ValueError('Original strings or indices changed')
 return bytes(result)


def replace_verified_texts(base,expected,replacements):
 """Replace a reviewed whitelist of nonempty fallback texts, with source checks."""
 before=parse_stx(base)
 if set(expected)!=set(replacements):raise ValueError('Expected/replacement IDs differ')
 if len(base)%2 or struct.unpack_from('<I',base,52)[0]!=len(base):raise ValueError('Bad mapped resource length')
 result=bytearray(base)
 for i in sorted(replacements):
  if not isinstance(i,int) or not 0<=i<len(before) or before[i]!=expected[i]:raise ValueError('Fallback source mismatch')
  text=replacements[i]
  if not text or '\0' in text:raise ValueError('Invalid replacement')
  if re.findall('[\ue000-\uf8ff]',before[i])!=re.findall('[\ue000-\uf8ff]',text):raise ValueError('Changed dynamic placeholders')
  struct.pack_into('<I',result,56+i*4,len(result));result+=text.encode('utf-16-le')+b'\0\0'
 struct.pack_into('<I',result,52,len(result))
 if parse_stx(result)!=[replacements.get(i,text)for i,text in enumerate(before)]:raise ValueError('Unlisted record changed')
 return bytes(result)
