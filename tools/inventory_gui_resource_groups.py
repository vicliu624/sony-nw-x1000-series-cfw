import runpy,struct,json
from pathlib import Path
n=runpy.run_path('tools/check_spider_restore_dispatch.py');u=n['u'];w=n['word'];rows=[]
def string(p):
 b=bytearray()
 for i in range(256):
  v=u.mem_read(p+i,1)[0]
  if not v:break
  b.append(v)
 return b.decode('utf-8',errors='replace')
for group in range(21):
 entries=[]
 for i in range(32):
  at=0x41c050+group*256+i*8;kind=w(at);p=w(at+4)
  if kind==0:break
  assert 0x8000<=p<0x908000
  entries.append({'declared_value':kind,'suffix':string(p)})
 roots=[]
 for jump_table in (0xf6500,0xf6578):
  target=w(jump_table+group*4);instruction=w(target)
  assert instruction & 0xfffff000==0xe59f5000,hex(instruction)
  literal=target+8+(instruction&0xfff)
  roots.append(string(w(literal)))
 rows.append({'group_id':group,'directory_roots':roots,'entries':entries})
r={'SpiderApp_sha256':n['digest'],'table':'0x41c050','scope':'Static native file-suffix table and initialization directory roots; no directory enumeration or file loading','groups':rows}
Path(n['ROOT'],'sources/native-gui-resource-groups.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,ensure_ascii=False))

