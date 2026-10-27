"""Trace actual recovery-worker resource requests for supplied operation-mode fixtures."""
import runpy,struct,json,sys,hashlib
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_SP
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];rows=[];requests=[];mode=0;trace=[]
sys.path.insert(0,str(n['ROOT']/'scripts'));from resources import parse_tgp
virtual=(0x3ce08,0x3d6dc,0x33c528,0xb4a54,0xb52dc,0xf6a58,0xf5714)
def hook(uc,pc,size,data):
 trace.append(hex(pc));del trace[:-16]
 if pc not in virtual:return
 a=[uc.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
 if pc==0xf6a58:
  requests.append({'group':a[2],'variant':a[3],'callback':hex(a[1]),'packed_flag':n['word'](uc.reg_read(UC_ARM_REG_SP))})
 value=mode if pc==0x3d6dc else 0
 uc.reg_write(UC_ARM_REG_R0,value);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
for mode in range(11):
 requests.clear()
 try:assert n['call'](0x11a04,(0,0,0,0))==0
 except Exception as exc:raise AssertionError((mode,trace,hex(u.reg_read(UC_ARM_REG_PC)),hex(u.reg_read(UC_ARM_REG_LR)))) from exc
 assert requests and all(q['callback']=='0x117fc' and q['packed_flag']==1 for q in requests)
 groups=[q['group'] for q in requests]
 assert groups[:4]==[0,1,2,3] and groups[-3:]==[15,16,17] and len(groups)==8
 counts=[]
 for group in groups:
  data=(n['ROOT']/f'work/resource-analysis/TEXGRP{group:02d}.DAT').read_bytes()
  counts.append({'group':group,'records':len(parse_tgp(data)),'file_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 rows.append({'operation_mode_fixture':mode,'resource_requests':[q.copy() for q in requests],'stock_group_files':counts,'total_records':sum(x['records'] for x in counts),'total_file_bytes':sum(x['file_bytes'] for x in counts)})
r={'SpiderApp_sha256':n['digest'],'scope':'Original11a04/118a0/b4964/b4868/ea6fc resource-group selection; loading intercepted','cases':rows,'limits':['Operation modes0..10 supplied through3d6dc; actual device current mode not established.', 'f6a58 loading returns virtual success; no file/image/asset availability or worker-service success proved.', 'Display refresh, subsystem getters, status-UI setter f5714 and diagnostics virtual; no device operations.']}
Path(n['ROOT'],'sources/native-worker-resource-requests.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([{'mode':x['operation_mode_fixture'],'groups':[q['group'] for q in x['resource_requests']]} for x in rows]))
