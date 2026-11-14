"""Real owner-observer IPC after slow startup, with no RF/device operations."""
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

from player_arm_guest import stock_libraries

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'work/owner-startup-recheck' / str(time.time_ns())
out.mkdir(parents=True)
sources = ['tools/test_owner_startup_recheck.c', 'runtime/apps/wireless-remote/owner_admission.c',
           'runtime/platform/wireless/mode_client.c', 'runtime/platform/wireless/mode_channel.c',
           'runtime/platform/wireless/mode_policy.c', 'runtime/store/stock_fs_bridge.c',
           'runtime/store/stock_stat64.c']
owner_path = ROOT / 'runtime/apps/wireless-remote/rf_owner.c'
owner = owner_path.read_text()
preflight_line, = re.findall(r' if\(owner_mode_\w+\([^;\n]*?\)\)return owner_startup_failed\(writer,cookie,105\);',owner)
def function(name):
    begin = owner.index('static int ' + name + '(')
    brace = owner.index('{', begin)
    depth = 1
    end = brace + 1
    while depth:
        depth += (owner[end] == '{') - (owner[end] == '}')
        end += 1
    return owner[begin:end]
actual = r'''
#define XNOW_REMOTE_MODE_VIEW
#define mode_admission gate
#include "runtime/platform/espnow/xnow_full_control.h"
#include "runtime/platform/espnow/xnow_owner_stream.h"
#include "runtime/platform/espnow/native_environment.h"
#include "runtime/platform/player/wireless_host.h"
#include "runtime/apps/wireless-remote/startup_result.h"
#include <string.h>
static struct xnow_full_control owner_control;
static unsigned pairing_listener=1;
static volatile int stop_requested;
static unsigned long long fixture_now;
static int shared_wake_attempted;
static struct xnow_owner_stream owner_stream;
static const uint8_t pairing_broadcast[6]={255,255,255,255,255,255};
static uint8_t peer_address[6]={2,1,2,3,4,5};
static struct xnow_native_security native_security;
static uint32_t pairing_queue_head,pairing_queue_drops;
static unsigned long long pairing_queue_sample_at;
static unsigned security_delay_ms,endpoint_delay_ms;
static int security_result,endpoint_result,stop_in_prepare,fail_policy_in_prepare,replies_enabled;
static int stop_in_endpoint,fail_policy_in_endpoint,endpoint_calls,local_ready_events;
int hb_monotonic_millis(unsigned long long *out){*out=fixture_now;return 0;}
int usleep(useconds_t wait){
 fixture_now+=(wait+999)/1000;
 if(replies_enabled)for(unsigned i=0;i<2;i++){int rc=xw_mode_channel_step(&server);assert(!rc||rc==XW_MODE_PENDING);}
 return 0;
}
static int pairing_queue_snapshot(uint32_t *head,uint32_t *drops){(void)head;(void)drops;return -1;}
static int prepare_security(void *p,struct xnow_full_control *c){
 (void)p;(void)c;fixture_now+=security_delay_ms;
 if(stop_in_prepare)stop_requested=1;
 if(fail_policy_in_prepare)assert(xw_mode_policy_release(&policy,&lease,0)==XW_MODE_FAULT);
 return security_result;
}
int xnow_endpoint_add(struct xnow_endpoint *e,const struct xnow_peer *p){
 (void)e;(void)p;fixture_now+=endpoint_delay_ms;endpoint_calls++;
 if(stop_in_endpoint)stop_requested=1;
 if(fail_policy_in_endpoint)assert(xw_mode_policy_release(&policy,&lease,0)==XW_MODE_FAULT);
 return endpoint_result;
}
int xnow_owner_stream_receive(struct xnow_owner_stream *s,const void *p,size_t n,const struct xnow_full_received *r){(void)s;(void)p;(void)n;(void)r;local_ready_events++;return 0;}
int xnow_full_control_step(struct xnow_full_control *c){fixture_now+=3149;c->session.phase=XNOW_SESSION_READY;return c->session.phase;}
void xnow_full_control_stop(struct xnow_full_control *c){c->stop_requested=1;}
static int power_off_admission(void *p){(void)p;return 0;}
static int wr_radio_stop_step(struct xnow_full_control *c,void *p,int (*guard)(void *)){
 (void)c;(void)p;(void)guard;return 0;
}
static int candidate_guard(void *p,enum xnow_session_action action){(void)p;(void)action;fixture_now+=3149;return 0;}
int xnow_owner_gate_radio_valid(void *p){(void)p;return 1;}
int xnow_sd8686_deep_sleep_get(int *sleeping){*sleeping=0;return 0;}
int xnow_sd8686_deep_sleep_set(int sleeping){(void)sleeping;return 0;}
int cnmgr_get_state(void){return 3;}
static int fixture_channel(struct xnow_sd8686_full *r,unsigned *out){(void)r;*out=1;return 0;}
static int owner_startup_failed(int fd,const uint8_t cookie[16],unsigned stage){(void)fd;(void)cookie;return (int)stage;}
FUNCTIONS
static int exercise_preflight_boundary(void){
 int writer=7;const uint8_t cookie[16]={1};
 PREFLIGHT
 return 0;
}
static void exercise_actual_owner_startup(void){
 replies_enabled=1;
 open_gate();fixture_now=4150;stop_requested=0;
 assert(!exercise_preflight_boundary());
 assert(wr_owner_admission_allowed(&gate));close_gate();
 open_gate();fixture_now=1001;stop_requested=0;
 owner_control=(struct xnow_full_control){0};
 owner_control.manager.held=1;owner_control.session.lease=1;
 owner_control.shared_channel=fixture_channel;
 assert(!remote_radio_guard(NULL,XNOW_SESSION_VERIFY_CANDIDATE));
 assert(wr_owner_admission_allowed(&gate));close_gate();
 open_gate();fixture_now=1001;stop_requested=0;
 owner_control=(struct xnow_full_control){0};owner_control.session.phase=XNOW_SESSION_STARTING;
 assert(remote_controller_step(NULL,&owner_control)==XNOW_SESSION_READY);
 assert(!stop_requested&&!owner_control.stop_requested&&wr_owner_admission_allowed(&gate));
 assert(gate.observed_at>=4150&&gate.client.serial>=2);
 assert(!wr_owner_admission_poll(&gate,fixture_now));close_gate();
}
static void open_shared_gate(void){
 policy=(struct xw_wireless_mode_policy){0};server=(struct xw_mode_channel){0};gate=(struct wr_owner_admission){0};
 assert(!xw_mode_policy_init(&policy,901));
 assert(!xw_mode_policy_adopt_wifi(&policy,XW_NATIVE_WIFI_CONSUMER,1,&lease));
 assert(!xw_mode_policy_pin_wifi(&policy,&lease,1));
 int fds[2];assert(!socketpair(AF_UNIX,SOCK_DGRAM,0,fds));
 assert(!xw_mode_channel_open(&server,&policy,fds[0],lease.consumer,XW_MODE_GRANT_READ));
 assert(!xw_mode_channel_observe(&server,&lease));
 assert(!wr_owner_admission_open_shared(&gate,fds[1],&lease));close(fds[0]);close(fds[1]);
 fixture_now=1000;stop_requested=0;pairing_listener=0;
 security_delay_ms=endpoint_delay_ms=0;
 security_result=endpoint_result=stop_in_prepare=fail_policy_in_prepare=0;replies_enabled=1;
 stop_in_endpoint=fail_policy_in_endpoint=endpoint_calls=local_ready_events=0;
 owner_control=(struct xnow_full_control){0};owner_control.session.phase=XNOW_SESSION_READY;
 memcpy(owner_control.local_mac,peer_address,6);
 assert(wr_owner_admission_poll(&gate,fixture_now)==XW_MODE_PENDING);reply();
 assert(!wr_owner_admission_poll(&gate,++fixture_now));
}
static void prepare_case(const char *name,int expected,uint64_t serial,int ready){
 printf("REMOTE_PREPARE_CASE_BEGIN %s\n",name);fflush(stdout);
 int rc=owner_prepare(NULL,&owner_control.endpoint,owner_control.local_mac);
 assert(rc==expected&&gate.client.serial==serial);
 if(ready)assert(!stop_requested&&!owner_control.stop_requested&&!wr_owner_admission_poll(&gate,fixture_now)&&wr_owner_admission_allowed(&gate));
 else if(!rc)assert(stop_requested&&owner_control.stop_requested);
 assert(local_ready_events==(ready&&pairing_listener?1:0));
 if(stop_in_prepare)assert(!endpoint_calls);
 /* The observer reports parent state; local STOP remains an independent
  * gate. A parent grant may stay cached when the local stop short-circuits. */
 printf("REMOTE_PREPARE_CASE_END %s result=%d\n",name,rc);fflush(stdout);close_gate();
}
static void exercise_actual_remote_prepare(void){
 open_shared_gate();prepare_case("quick-prepare",0,2,1);
 open_shared_gate();security_delay_ms=3149;prepare_case("slow-security",0,2,1);
 open_shared_gate();endpoint_delay_ms=3149;prepare_case("slow-peer-admission",0,2,1);
 open_shared_gate();security_result=-71;prepare_case("security-failure",-71,1,0);
 open_shared_gate();endpoint_result=-72;prepare_case("peer-failure",-72,1,0);
 open_shared_gate();stop_in_prepare=1;prepare_case("stop-during-prepare",0,1,0);
 open_shared_gate();security_delay_ms=3149;fail_policy_in_prepare=1;
 prepare_case("policy-failed-during-prepare",0,2,0);
 open_shared_gate();fixture_now+=201;
 assert(wr_owner_admission_poll(&gate,fixture_now)==XW_MODE_PENDING);reply();
 security_delay_ms=3149;fail_policy_in_prepare=1;
 prepare_case("queued-old-reply-cannot-grant-ready",0,3,0);
 open_shared_gate();fixture_now+=201;
 assert(wr_owner_admission_poll(&gate,fixture_now)==XW_MODE_PENDING);reply();
 security_delay_ms=3149;prepare_case("queued-old-reply-needs-fresh-serial",0,3,1);
 open_shared_gate();replies_enabled=0;
 unsigned long long query_began=fixture_now;
 prepare_case("parent-query-timeout",0,2,0);
 assert(fixture_now-query_began==1000);
 open_shared_gate();fixture_now+=1000;
 assert(wr_owner_admission_poll(&gate,fixture_now)==XW_MODE_FAULT);
 prepare_case("revoked-observer-not-revived",0,1,0);
 open_shared_gate();stop_in_endpoint=1;prepare_case("stop-during-peer-admission",0,1,0);
 open_shared_gate();pairing_listener=1;endpoint_delay_ms=3149;
 prepare_case("pairing-slow-peer-admission",0,2,1);
 open_shared_gate();pairing_listener=1;stop_in_endpoint=1;
 prepare_case("pairing-stop-during-peer",0,1,0);
 open_shared_gate();pairing_listener=1;fail_policy_in_endpoint=1;
 prepare_case("pairing-policy-failed",0,2,0);
 puts("REMOTE_PREPARE_OBSERVATION_PASS");
}
#undef mode_admission
'''.replace('PREFLIGHT',preflight_line).replace('FUNCTIONS', '\n'.join(function(n) for n in
    ('owner_mode_await', 'owner_mode_recheck', 'remote_radio_guard', 'remote_controller_step', 'owner_prepare_cancel', 'owner_prepare')))
fixture = (ROOT / sources[0]).read_text().replace('int main(void){', actual + '\nint main(void){')
fixture = fixture.replace(' puts("OWNER_STARTUP_RECHECK_PASS");',
                          ' exercise_actual_owner_startup();\n exercise_actual_remote_prepare();\n puts("OWNER_STARTUP_RECHECK_PASS");')
fixture = fixture.replace('"../runtime/', '"' + str(ROOT / 'runtime') + '/')
generated = out / 'actual-owner-startup.c'
generated.write_text(fixture)
original_sources = sources[:]
sources[0] = str(generated.relative_to(ROOT))
flags = ['-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation']
flags += ['-I', str(ROOT)]
host = out / 'test.host'
subprocess.run(['gcc', *flags, '-fsanitize=address,undefined', '-pthread', *sources,
                '-o', str(host)], cwd=ROOT, check=True)
run = subprocess.run([str(host)], capture_output=True, text=True, timeout=10)
assert run.returncode == 0 and 'OWNER_STARTUP_RECHECK_PASS' in run.stdout, run.stdout + run.stderr
host_output=run.stdout
libs = stock_libraries()
arm = out / 'test.arm'
subprocess.run(['arm-linux-gnueabi-gcc', *flags, '-Os', '-DHB_STORE_SONY_LIBC',
                '-D_DEFAULT_SOURCE=', '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0',
                '-march=armv5te', '-marm', '-mfloat-abi=soft', '-fno-builtin',
                '-fno-pie', '-fno-stack-protector', '-no-pie', '-nostdlib',
                '-Wl,--hash-style=sysv,--build-id=none', *sources,
                'runtime/store/start.c', 'runtime/store/start.S',
                str(libs['libpthread.so.0']), str(libs['libc.so.6']),
                str(libs['ld-linux.so.3']), '-lgcc', '-o', str(arm)], cwd=ROOT, check=True)
search = ':'.join(dict.fromkeys(str(p.parent) for p in libs.values()))
run = subprocess.run(['qemu-arm', '-cpu', 'arm926', str(libs['ld-linux.so.3']),
                      '--library-path', search, str(arm)], capture_output=True, text=True, timeout=10)
assert run.returncode == 0 and 'OWNER_STARTUP_RECHECK_PASS' in run.stdout, run.stdout + run.stderr
arm_output=run.stdout
prepare_cases=['quick-prepare','slow-security','slow-peer-admission','security-failure','peer-failure',
               'stop-during-prepare','policy-failed-during-prepare','queued-old-reply-cannot-grant-ready',
               'queued-old-reply-needs-fresh-serial','parent-query-timeout','revoked-observer-not-revived',
               'stop-during-peer-admission','pairing-slow-peer-admission','pairing-stop-during-peer','pairing-policy-failed']
successful={'quick-prepare','slow-security','slow-peer-admission','queued-old-reply-needs-fresh-serial'}
for output in (host_output,arm_output):
 assert 'REMOTE_PREPARE_OBSERVATION_PASS' in output
 groups=re.findall(r'REMOTE_PREPARE_CASE_BEGIN ([^\n]+)\n(.*?)REMOTE_PREPARE_CASE_END \1 result=(-?\d+)',output,re.S)
 assert [name for name,_,_ in groups]==prepare_cases
 for name,body,result in groups:
  assert ('REMOTE_RF_ENDPOINT_READY' in body)==(name in successful)
  assert ('REMOTE_PAIRING_LISTEN' in body)==(name=='pairing-slow-peer-admission')
  assert int(result)=={'security-failure':-71,'peer-failure':-72}.get(name,0)
report = dict(passed=True, real_datagram_ipc=True, original_libc_arm926=True,
              actual_remote_prepare_executed=True, modeled_security_delay_ms=3149,
              remote_prepare_cases=prepare_cases, fresh_ready_only_after_parent_confirmation=True,
              pairing_prepare_stop_checked=True,
              native_security_and_endpoint_effects_modeled=True,
              actual_owner_controller_and_recheck_executed=True, modeled_startup_delay_ms=3149,
              actual_preflight_and_live_verify_boundaries=True,
              host_sanitizers=True, stale_reply_does_not_grant_data=True,
              revoked_lease_and_clock_regression_rejected=True, timeout_unchanged=True,
              device_accessed=False, source_hashes={s: hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in [*sources,*original_sources,str(owner_path.relative_to(ROOT)),
                  'tools/test_owner_startup_recheck.py','runtime/apps/wireless-remote/startup_result.h',
                  'runtime/apps/wireless-remote/owner_admission.h','runtime/platform/player/wireless_host.h',
                  'runtime/platform/wireless/mode_client.h','runtime/platform/wireless/mode_channel.h',
                  'runtime/platform/wireless/mode_policy.h','runtime/platform/wireless/mode.h']})
(out / 'report.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
