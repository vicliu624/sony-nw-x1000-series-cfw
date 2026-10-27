"""Run bounded X1000 lifecycle regressions. Never execute device mode or build firmware."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
COMMON=['--native-resume-slot','--consume-battery-event','--ordered-activation','--activation-callback','--root-reactivation','--native-gui-resume','--consume-gui-resume','--complete-gui-resume','--dispatch-gui-resume','--finish-gui-transition','--native-resume-worker','--ack-activation']
UI=['--native-config','--native-destroy','--upper-delete','--native-base','--native-pool','--stop-operation','--slot-lifecycle','--exit-gui-state']
CASES=[
 ('proxy-frontend-contract',['tools/check_proxy_frontend_contract.py'],'native-entry-exit-contract.json','Fresh original manager/proxy argv -> ARM frontend -> frontend exit status -> original proxy reap/quit; virtual boundaries, no Sony return qualification'),
 ('proxy-noargs-launch',['tools/check_manager_change_notification.py','--no-launch-arguments'],'native-manager-proxy-noargs-exec.json','Original manager/proxy instructions capture argv for zero-argument registration; exec/IPC/device remain virtual'),
 ('external-real-process',['tools/test_native_process.py'],'native-process-tests.json','Unmodified launcher C function with real host fork/exec/wait/signals; syscall boundary translated, not Sony or ARM integration'),
 ('coordinator-baseline',['tools/check_command7_coordinator.py'],'native-command7-coordinator.json','Original coordinator fixtures, services virtual'),
 ('activation-accepted',['tools/check_command7_coordinator.py',*COMMON],'native-resume-slot-integrated.json','Native callback/root/GUI/completion/APF with accepted virtual IPC reply'),
 ('activation-rejected',['tools/check_command7_coordinator.py',*COMMON,'--reject-activation'],'native-resume-slot-integrated.json','Same bounded chain; virtual IPC rejects activation'),
 ('worker-service-error',['tools/check_command7_coordinator.py',*COMMON,'--worker-error','7'],'native-resume-slot-integrated.json','Worker-service failure fixture must not be confused with successful restoration'),
 ('control-state-exit',['tools/check_gui_operation5.py',*UI],'native-gui-state4-exit-lifecycle.json','Native UI create/state-exit/delete; event20620 and pool backing supplied'),
 ('page-coordinator',['tools/check_command7_coordinator.py',*COMMON,'--native-page-coordinator'],'native-resume-page-coordinator.json','Native page recovery orchestration and callback registration; backend/services virtual'),
 ('frame-factory',['tools/check_command7_coordinator.py',*COMMON,'--native-page-coordinator','--native-frame-factory'],'native-resume-frame-factory.json','Native page-frame factory and slot selection; frame initializer virtual'),
 ('frame-failure-joint',['tools/check_command7_coordinator.py',*COMMON,'--native-page-coordinator','--native-frame-factory','--frame-child-failure'],'native-resume-frame-child-failure.json','Native frame failure continues original lifecycle; not UI success'),
 ('frame-initializer',['tools/check_command7_coordinator.py',*COMMON,'--native-page-coordinator','--native-frame-factory','--native-frame-initializer','--native-frame-base','--native-frame-pixels','--native-resource-register','--release-frames','--home-state-transition','--native-home-preparation','--complete-registry-initialization','--native-page-request','--native-page-manager','--native-home-template','--native-template-transition'],'native-resume-template-transition.json','Native page/template initialization and transition packets; interface/GUI dispatch virtual'),
 ('template-dispatch',['tools/check_command7_coordinator.py',*COMMON,'--native-page-coordinator','--native-frame-factory','--native-frame-initializer','--native-frame-base','--native-frame-pixels','--native-resource-register','--release-frames','--home-state-transition','--native-home-preparation','--complete-registry-initialization','--native-page-request','--native-page-manager','--native-home-template','--native-template-transition','--native-template-dispatch'],'native-resume-template-dispatch.json','Original template GUI dispatcher; active view supplied, graphics service virtual'),
 ('native-view-pool',['tools/check_command7_coordinator.py',*COMMON,'--native-page-coordinator','--native-frame-factory','--native-frame-initializer','--native-frame-base','--native-frame-pixels','--native-resource-register','--release-frames','--home-state-transition','--native-home-preparation','--complete-registry-initialization','--native-page-request','--native-page-manager','--native-home-template','--native-template-transition','--native-template-dispatch','--native-view-pool'],'native-resume-view-pool.json','Native three-slot view init/allocation/exhaustion/select/release, followed by template dispatch; full manager startup excluded'),
 ('registry-callback-cycle',['tools/check_gui_registry_callback_cycle.py'],'native-gui-registry-callback-cycle.json','Original callback registration/start/stop; module handlers and bridges virtual'),
 ('registry-stock-descriptors',['tools/check_gui_registry_callback_cycle.py','--stock-descriptors'],'native-gui-registry-stock-cycle.json','Original descriptor registration/getters/converters; module handler bodies intercepted'),
 ('registry-inactive-handlers',['tools/check_gui_registry_callback_cycle.py','--stock-descriptors','--inactive-handlers'],'native-gui-registry-inactive-cycle.json','Actual handler bodies in inactive state'),
 ('registry-active-parent',['tools/check_gui_registry_callback_cycle.py','--stock-descriptors','--inactive-handlers','--active-parent0'],'native-gui-registry-active-parent-cycle.json','One active module executes actual parent insert/remove; rendering services virtual'),
 ('frame-child-failure',['tools/check_frame_factory_failure.py'],'native-frame-factory-child-failure.json','Native frame initializer failure; child allocator returns null, caller cleanup excluded'),
 ('pixel-buffer',['tools/check_frame_pixel_buffer.py'],'native-frame-pixel-buffer.json','Native format2 buffer create/release; OS memory mapping virtual'),
 ('complete-page-registry',['tools/check_complete_page_registry.py'],'native-complete-page-registry.json','Complete original registry setup and config tables; memory services virtual'),
 ('resource-pool',['tools/check_gui_resource_pool.py'],'native-gui-resource-pool.json','Empty resource pool only, no loaded textures'),
]
VIEW_PREFIX=next(case for case in CASES if case[0]=='native-view-pool')
CASES.insert(CASES.index(VIEW_PREFIX)+1,('native-view-startup-prefix', [*VIEW_PREFIX[1],'--native-view-startup-prefix'],'native-resume-view-startup-prefix.json','Original e8800 initialization prefix creates two views; stops before remaining manager init, graphics prelude virtual'))

MANAGER_BASE=next(case for case in CASES if case[0]=='native-view-startup-prefix')
CASES.insert(CASES.index(MANAGER_BASE)+1,('native-manager-init',[*MANAGER_BASE[1],'--native-manager-init'],'native-resume-manager-init.json','Original outer GUI manager init returns and registers dispatch callbacks; module init and receiver services virtual'))

RECEIVER_BASE=next(case for case in CASES if case[0]=='native-manager-init')
CASES.insert(CASES.index(RECEIVER_BASE)+1,('native-receiver-init',[*RECEIVER_BASE[1],'--native-receiver-init'],'native-resume-receiver-init.json','Original receiver and queue memory initialization; not queue pumping or OS thread execution'))

CASES.append(('receiver-envelope',['tools/check_gui_receiver_envelope.py'],'native-gui-receiver-envelope.json','Original receiver envelope conversion and indirect callback; queue bookkeeping/callback body virtual'))

CASES.append(('receiver-bookkeeping',['tools/check_gui_receiver_envelope.py','--native-bookkeeping'],'native-gui-receiver-bookkeeping.json','Native queue match/removal/count accounting with supplied class1 record; no enqueue or callback body'))

CASES.append(('receiver-insertion',['tools/check_gui_receiver_envelope.py','--native-bookkeeping','--native-insertion'],'native-gui-receiver-insertion.json','Native insertion and matching removal for supplied type1 payload; no OS pump or callback body'))

CASES.append(('receiver-control',['tools/check_gui_receiver_envelope.py','--native-bookkeeping','--native-insertion','--native-gui-callback'],'native-gui-receiver-control.json','Original receiver to dispatcher to target-control wrapper; supplied null-handler control, no rendering'))

CASES.append(('receiver-default-handler',['tools/check_gui_receiver_envelope.py','--native-bookkeeping','--native-insertion','--native-gui-callback','--native-default-handler'],'native-gui-receiver-default-handler.json','Original default control handler and empty delegate; no painting or populated widget handler'))

CASES.append(('receiver-child-delegate',['tools/check_gui_receiver_envelope.py','--native-bookkeeping','--native-insertion','--native-gui-callback','--native-default-handler','--native-child-delegate'],'native-gui-receiver-child-delegate.json','Original child attach/delegation/detach with default handlers; empty leaf, no rendering'))

FRAME_RECEIVER_BASE=next(case for case in CASES if case[0]=='native-receiver-init')
CASES.append(('frame-receiver',[*FRAME_RECEIVER_BASE[1],'--native-frame-receiver'],'native-resume-frame-receiver.json','Native constructed frame control activated by original prefix, receiver/default handler and release; rendering excluded'))

FRAME_ACTIVATION_BASE=next(case for case in CASES if case[0]=='frame-receiver')
CASES.append(('frame-activation',[*FRAME_ACTIVATION_BASE[1],'--native-frame-activation'],'native-resume-frame-activation.json','Outer activation returns, two actual frame handlers take empty-control-list branch; three refresh services virtual'))

FRAME_CHILD_BASE=next(case for case in CASES if case[0]=='frame-activation')
CASES.append(('frame-child',[*FRAME_CHILD_BASE[1],'--native-frame-child'],'native-resume-frame-child.json','Native insertion/removal of constructed control; nonempty frame handler branch, supplied topology and virtual attach bridges'))

GRAPHICS_BASE=next(case for case in CASES if case[0]=='frame-child')
CASES.append(('graphics-context',[*GRAPHICS_BASE[1],'--native-attach-dispatch','--native-graphics-context'],'native-resume-graphics-context.json','Original embedded graphics context initialization and attach notification, qsort<=1 virtual; no physical graphics'))

ACTIVATION_QUEUE_BASE=next(case for case in CASES if case[0]=='graphics-context')
CASES.append(('activation-queues',[*ACTIVATION_QUEUE_BASE[1],'--native-activation-queues'],'native-resume-activation-queues.json','Native empty queue maintenance and pump state0 return7; no running receiver or real consumption'))

RECEIVER_START_BASE=next(case for case in CASES if case[0]=='activation-queues')
CASES.append(('receiver-start',[*RECEIVER_START_BASE[1],'--native-receiver-start'],'native-resume-receiver-start.json','Original receiver start0->1 and empty upstream pump return0; no actual message consumed'))

CASES.append(('upstream-queue',['tools/check_gui_upstream_queue.py'],'native-gui-upstream-queue.json','Original upstream init/enqueue/peek/pop; enabled flag supplied, one payload, no receiver pump'))

UPSTREAM_INIT_BASE=next(case for case in CASES if case[0]=='receiver-start')
CASES.append(('upstream-init',[*UPSTREAM_INIT_BASE[1],'--native-upstream-init'],'native-resume-upstream-init.json','Original upstream queue init and receiver pointer registration; receiver startup/empty pump, no actual consumption'))

PROCESSOR_BASE=next(case for case in CASES if case[0]=='upstream-init')
CASES.append(('processor-registration',[*PROCESSOR_BASE[1],'--native-processor-registration'],'native-resume-processor-registration.json','Original slot0 processing descriptor registration, receiver startup/empty pump; no real operation completion'))

UPSTREAM_REJECT_BASE=next(case for case in CASES if case[0]=='processor-registration')
CASES.append(('upstream-reject',[*UPSTREAM_REJECT_BASE[1],'--native-upstream-message','--native-upstream-reject'],'native-resume-upstream-reject.json','Native image-task validation error10, completion boundary and queue removal; no successful image load'))

UPSTREAM_COMPLETION_BASE=next(case for case in CASES if case[0]=='upstream-reject')
CASES.append(('upstream-completion',[*UPSTREAM_COMPLETION_BASE[1],'--native-upstream-completion'],'native-resume-upstream-completion.json','Native rejected image request completion body, queue removal and recovery; successful loading excluded'))

CASES.extend([
 ('home-entry',['tools/check_home_parent.py'],'native-home-parent.json','Candidate Home construction, native simulated touch and switch request; real APF transport/rendering excluded'),
 ('home-outside',['tools/check_home_parent.py','--touch-outside'],'native-home-parent-outside.json','Touch outside candidate entry must not select or switch'),
 ('home-close-ack',['tools/check_home_parent.py','--ack-manager-close'],'native-home-parent-ack-manager-close.json','Constructed Home close through completion/APF ack with virtual transport and display services'),
])

CASES.append(('home-page-reopen',['tools/check_home_parent.py','--reopen-home'],'native-home-parent-reopen-close.json','Same-emulator GUI-page close/rebuild and repeat touch selection; full UI manager reopen/APF return excluded'))

CASES.append(('manager-open-pool',['tools/check_manager_open_pool.py'],'native-manager-open-pool.json','Original mode0 pool prefix and allocation failure; reserved root and display backend excluded'))

CASES.append(('manager-open-root',['tools/check_manager_open_pool.py','--reserved-root'],'native-manager-open-root.json','Original mode0 reserved-root construction; stops before module startup, display/allocator virtual'))

CASES.extend([
 ('home-open-root',['tools/check_home_parent.py','--native-open-root'],'native-home-parent-open-root.json','Mode0 reserved root plus constructed Home and touch; module startup/rendering excluded'),
 ('home-open-root-close',['tools/check_home_parent.py','--native-open-root','--ack-manager-close'],'native-home-parent-open-root-ack-manager-close.json','Reserved root plus Home selection and native close/APF ack; virtual OS/transport'),
])

CASES.append(('home-manager-reopen-ack',['tools/check_home_parent.py','--reopen-manager','--ack-manager-close'],'native-home-parent-manager-reopen-open-complete-ack-manager-close.json','Same-memory two mode0/Home/command6/APF-ack cycles with original input-mode restore; OS/IPC virtual, command7 dispatch excluded'))

CASES.append(('home-command7-reopen',['tools/check_home_parent.py','--command7-reopen'],'native-home-parent-command7-manager-reopen-open-complete-ack-manager-close.json','Original command7 input restore plus deferred native mode0/Home rebuild; activation async worker/completion excluded'))

CASES.append(('home-command7-worker',['tools/check_home_parent.py','--command7-worker'],'native-home-parent-worker-command7-manager-reopen-open-complete-ack-manager-close.json','Same-memory Home restore plus original async worker/GUI completion; services and thread scheduling virtual, activation APF ack excluded'))

CASES.append(('home-command7-ack',['tools/check_home_parent.py','--command7-ack'],'native-home-parent-activation-ack-worker-command7-manager-reopen-open-complete-ack-manager-close.json','Same-memory close/GUI command7 worker/coordinator/APF activation/reclose; reconstruction boundary and OS/IPC virtual'))

CASES.append(('home-native-page-rebuild',['tools/check_home_parent.py','--native-page-rebuild'],'native-home-parent-native-rebuild-activation-ack-worker-command7-manager-reopen-open-complete-ack-manager-close.json','Original12ef8 mode0 recovery plus same-memory Home/input/worker/APF; frame factory and auxiliary services virtual'))

CASES.append(('native-tgp-reader',['tools/check_native_tgp.py'],'native-tgp00-reader.json','Original TGP/TXD parser on139 stock records; virtual file mapping, no registration/rendering'))

CASES.append(('native-tgp-registration',['tools/check_native_tgp.py','--register-images'],'native-tgp00-registration.json','Stock139 images parsed/registered/grouped/released by native code; file/mmap/libc virtual, no catalog/Home integration'))

CASES.append(('native-tgp-catalog',['tools/check_native_tgp.py','--catalog-map'],'native-tgp00-catalog.json','Native packed DAT load/catalog mapping/lookup/release; virtual file/OS, no Home integration'))

CASES.append(('home-native-assets',['tools/check_home_parent.py','--native-home-assets'],'native-home-parent-assets-catalog-frames-native-rebuild-activation-ack-worker-command7-manager-reopen-open-complete-ack-manager-close.json','Same-memory native group0 assets, real recovery frames, Home/input/activation/reclose and resource release; OS/IPC virtual'))

CASES.append(('home-asset-handoff',['tools/check_home_parent.py','--native-asset-handoff'],'native-home-parent-handoff-assets-catalog-frames-native-rebuild-activation-ack-worker-command7-manager-reopen-open-complete-ack-manager-close.json','Original command6 asset release then native reload/lookup before return; same-memory Home/activation, OS/IPC virtual'))

CASES.append(('home-asset-handoff-outside',['tools/check_home_parent.py','--native-asset-handoff','--touch-outside'],'native-home-parent-handoff-assets-catalog-frames-native-rebuild-activation-ack-worker-command7-manager-reopen-open-complete-outside-ack-manager-close.json','Asset handoff/reload negative touch control; no outside selection or switch, OS/IPC virtual'))

CASES.append(('worker-resource-requests',['tools/check_worker_resource_requests.py'],'native-worker-resource-requests.json','Original worker resource-group selection for11 supplied modes; loading/status UI virtual, stock files counted separately'))

CASES.append(('home-stock-resource-pools',['tools/check_home_parent.py','--stock-resource-pools'],'native-home-parent-stock-pools-handoff-assets-catalog-frames-native-rebuild-activation-ack-worker-command7-manager-reopen-open-complete-ack-manager-close.json','Original16-group/1024-image initializer plus group0 handoff/Home return; full worker8-group loading excluded'))

CASES.append(('worker-asset-loading',['tools/check_worker_asset_loading.py'],'native-worker-asset-loading.json','Original mode0 recovery worker loads/maps550 images in8 real DATs and releases all; OS/cancel/status UI/display virtual'))

CASES.append(('home-worker-assets',['tools/check_home_parent.py','--native-worker-assets'],'native-home-parent-worker-assets.json','Original recovery worker8-group loading before reconstructed Home/activation/reclose; mode0 and OS/cancel/status/display boundaries virtual'))

CASES.extend([
 ('worker-cancel-ticket',['tools/check_worker_asset_loading.py','--native-cancel-ticket'],'native-worker-cancel-ticket.json','Native ticket init/cancel/query/clear; packed load stops after first group and cleans, mutex/OS virtual'),
 ('home-native-cancel-predicate',['tools/check_home_parent.py','--native-cancel-predicate'],'native-home-parent-native-ticket-worker-assets.json','Same-memory worker/Home/return with native cancellation query, initialized ticket, no cancel requested'),
])

def main():
 area=ROOT/'work/lifecycle-regression';area.mkdir(parents=True,exist_ok=True)
 rows=[]
 for name,args,report,scope in CASES:
  start=time.monotonic();command=[sys.executable,*args]
  result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
  (area/(name+'.log')).write_text(result.stdout+result.stderr)
  row={'name':name,'command':command,'scope':scope,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,3)}
  if result.returncode==0:
   # Snapshot immediately: exploratory scripts may share output filenames across modes.
   evidence=json.loads((ROOT/'sources'/report).read_text())
   snapshot=area/(name+'.json');snapshot.write_text(json.dumps(evidence,indent=2)+'\n')
   row['report_snapshot']=snapshot.relative_to(ROOT).as_posix()
   row['report_sha256']=hashlib.sha256(snapshot.read_bytes()).hexdigest()
  rows.append(row);print(name, 'PASS' if result.returncode==0 else 'FAIL',flush=True)
  if result.returncode:break
 report={'scope':'Bounded original ARM lifecycle regression; not whole-firmware emulation or hardware qualification','cases':rows,'all_passed':len(rows)==len(CASES) and all(r['exit_code']==0 for r in rows),'limits':['Fixture state, virtual IPC/services/memory and manually delivered events remain; see each evidence snapshot.', 'No actual UI rendering, full Sony process startup, networking/app store or physical hardware qualification.', 'No updater, firmware generation or device writes.']}
 (ROOT/'sources/native-lifecycle-regression.json').write_text(json.dumps(report,indent=2)+'\n')
 return 0 if report['all_passed'] else 1
if __name__=='__main__':raise SystemExit(main())
