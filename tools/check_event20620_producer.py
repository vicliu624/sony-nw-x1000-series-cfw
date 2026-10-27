"""Execute stock event20620 producer basic block; stop before its following work."""
import runpy,json,argparse
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC,UC_ARM_REG_R0,UC_ARM_REG_LR
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--entry-prefix',action='store_true');parser.add_argument('--native-query',action='store_true');args=parser.parse_args();assert not args.native_query or args.entry_prefix
n=runpy.run_path(str(Path(__file__).with_name('check_spider_restore_dispatch.py')));u=n['u'];n['queued'].clear()
if args.native_query:
 u.mem_map(0xe60000,0x2000);u.mem_write(0xe60188,(0x6a).to_bytes(4,'little'))
 n['hook'].__globals__['deactivate_probe']=False
 client=n['call'](0xe5f4,(0,0,0,0));u.mem_write(client+0x20,(1).to_bytes(4,'little'))
def stop(uc,pc,size,data):
 if args.native_query and pc==0x74634:return
 if args.entry_prefix and pc in (0x20688,0x21830,0x74634):
  uc.reg_write(UC_ARM_REG_R0,0x820012 if pc==0x74634 else 0);uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR));return
 if pc==0x76228:uc.reg_write(UC_ARM_REG_PC,0x50000000)
u.hook_add(UC_HOOK_CODE,stop)
n['call'](0x76078 if args.entry_prefix else 0x76208,(0,0,2 if args.native_query else 0,0));assert n['queued'][-1]==[0x20620,0,0,0],n['queued']
if not args.entry_prefix:assert len(n['queued'])==1
r={'SpiderApp_sha256':n['digest'],'scope':'Stock basic block76208..76224, original instructions produce event; queue transport intercepted','generated_event':n['queued'][-1],'stop':'0x76228','limits':['Start is an interior branch, not proven function entry or reached condition.','Enclosing function/state/meaning and additional events not yet executed.','Not proof that normal app return takes this branch.']}
if args.entry_prefix:
 r['scope']='Original76078 entry to76228; query helpers20688/21830/74634 virtual'
 r['events_before_stop']=n['queued'];r['command_query_fixture']='0x820012'
 r['limits']=['Initial helper/query responses supplied, command query820012 drives stock jump table to event20620.', 'Stops before following20615 and49020c events/PCS work; not full function execution.', 'Producer event/action identity and connection to normal APF restoration not established.']
if args.native_query:
 r.pop('command_query_fixture',None)
 r['scope']='Native76078 branch with native74634/751ec table lookup; status helpers20688/21830 mocked'
 r['lookup_fixture']={'selector':'0x6a','variant':1,'index':2,'selected_command':'0x820012'}
 r['limits']=['Selector/variant/index supplied; their actual UI origin and business identity remain unverified.', 'Native lookup returns command820012 and producer queues20620; status helpers and queue transport virtual.', 'Stops before remaining producer events; no actual APF return path qualification.']
Path(n['ROOT'],'sources/native-event20620-native-query.json' if args.native_query else 'sources/native-event20620-producer-entry.json' if args.entry_prefix else 'sources/native-event20620-producer-prefix.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

