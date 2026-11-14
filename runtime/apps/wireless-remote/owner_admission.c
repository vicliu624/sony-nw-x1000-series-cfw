#include "owner_admission.h"
#include "../../platform/player/wireless_host.h"
#include <string.h>
#include <unistd.h>
extern unsigned long pthread_self(void);
static int owner(const struct wr_owner_admission *gate){
 return gate&&gate->client.pid==(int)getpid()&&gate->client.thread==pthread_self();
}
static int revoked(struct wr_owner_admission *gate,int result){
 gate->authorized=0;gate->revoked=1;return result;
}
static int admission_open(struct wr_owner_admission *gate,int fd,const struct xw_wireless_lease *expected,int mode){
 if(!gate||!expected||gate->client.bound||gate->revoked||gate->closed||
    !expected->generation||!expected->serial||!expected->consumer||expected->mode!=mode)return XW_MODE_INVALID;
 struct xw_mode_client client={0};
 int rc=xw_mode_client_open(&client,fd,expected->generation);if(rc)return rc;
 gate->client=client;gate->expected=*expected;gate->authorized=0;return 0;
}
int wr_owner_admission_open(struct wr_owner_admission *gate,int fd,const struct xw_wireless_lease *expected){
 return admission_open(gate,fd,expected,XW_WIRELESS_MODE_ESPNOW);
}
int wr_owner_admission_open_shared(struct wr_owner_admission *gate,int fd,const struct xw_wireless_lease *expected){
 if(!expected||expected->consumer!=XW_NATIVE_WIFI_CONSUMER)return XW_MODE_INVALID;
 return admission_open(gate,fd,expected,XW_WIRELESS_MODE_WIFI);
}
int wr_owner_admission_refresh(struct wr_owner_admission *gate){
 if(!owner(gate))return XW_MODE_WRONG_OWNER;
 if(gate->closed||gate->revoked)return XW_MODE_DENIED;
 int rc=xw_mode_client_begin(&gate->client,XW_MODE_QUERY,0); /* Reserved query field, not a mode selection. */
 if(rc&&rc!=XW_MODE_BUSY)return revoked(gate,rc);
 return rc;
}
int wr_owner_admission_step(struct wr_owner_admission *gate){
 if(!owner(gate))return XW_MODE_WRONG_OWNER;
 if(gate->closed||gate->revoked)return XW_MODE_DENIED;
 struct xw_mode_reply reply;
 int rc=xw_mode_client_step(&gate->client,&reply);
 if(rc==XW_MODE_PENDING)return rc;
 if(rc)return revoked(gate,rc);
 if(reply.lease.generation!=gate->expected.generation||reply.lease.serial!=gate->expected.serial||
    reply.lease.consumer!=gate->expected.consumer||reply.lease.mode!=gate->expected.mode||
    xw_mode_reply_data_allowed(&reply))return revoked(gate,XW_MODE_DENIED);
 gate->authorized=1;gate->had_data_permission=1;return 0;
}
int wr_owner_admission_allowed(const struct wr_owner_admission *gate){
 return owner(gate)&&gate->client.bound&&!gate->client.fault&&!gate->closed&&!gate->revoked&&gate->authorized;
}
static int retirement_failed(struct wr_owner_admission *gate, int result)
{
    gate->retirement = WR_OWNER_RETIREMENT_FAILED;
    return revoked(gate, result);
}

int wr_owner_admission_retirement_begin(struct wr_owner_admission *gate, uint64_t now)
{
    if (!owner(gate)) return XW_MODE_WRONG_OWNER;
    if (gate->closed || gate->client.fault || !gate->client.bound ||
        !gate->had_data_permission)
        return XW_MODE_DENIED;
    if (!gate->timed || gate->retirement != WR_OWNER_RETIREMENT_NONE)
        return XW_MODE_INVALID;
    if (now < gate->last_poll) return retirement_failed(gate, XW_MODE_FAULT);

    gate->authorized = 0;
    gate->revoked = 1;
    gate->retirement = WR_OWNER_RETIREMENT_QUERYING;
    gate->rechecking = gate->client.pending ? 1u : 2u;
    gate->last_poll = gate->query_started = now;
    return XW_MODE_PENDING;
}

int wr_owner_admission_retirement_poll(struct wr_owner_admission *gate, uint64_t now)
{
    if (!owner(gate)) return XW_MODE_WRONG_OWNER;
    if (gate->closed || gate->client.fault || !gate->client.bound ||
        !gate->had_data_permission)
        return XW_MODE_DENIED;
    if (gate->retirement != WR_OWNER_RETIREMENT_QUERYING) return XW_MODE_STALE;
    if (now < gate->last_poll || now - gate->query_started >= WR_OWNER_OBSERVATION_STALE_MS)
        return retirement_failed(gate, XW_MODE_FAULT);
    gate->last_poll = now;

    if (!gate->client.pending) {
        int rc = xw_mode_client_begin(&gate->client, XW_MODE_QUERY, 0);
        if (rc) return retirement_failed(gate, rc);
    }
    struct xw_mode_reply reply;
    int rc = xw_mode_client_step(&gate->client, &reply);
    if (rc == XW_MODE_PENDING) return rc;
    if (rc) return retirement_failed(gate, rc);
    if (reply.operation != XW_MODE_QUERY || reply.result || !reply.active ||
        !reply.owned || reply.off_verified || reply.phase == XW_MODE_UNVERIFIED ||
        reply.lease.generation != gate->expected.generation ||
        reply.lease.serial != gate->expected.serial ||
        reply.lease.consumer != gate->expected.consumer ||
        reply.lease.mode != gate->expected.mode)
        return retirement_failed(gate, XW_MODE_DENIED);

    if (gate->rechecking == 1) {
        /* A queued pre-stop reply cannot prove current ownership. The next
         * serial must complete within this same, unextended query deadline. */
        gate->rechecking = 2;
        return XW_MODE_PENDING;
    }
    gate->rechecking = 0;
    gate->retirement = WR_OWNER_RETIREMENT_VERIFIED;
    return 0;
}

int wr_owner_admission_recheck_begin(struct wr_owner_admission *gate,uint64_t now){
 if(!owner(gate))return XW_MODE_WRONG_OWNER;
 if(gate->closed||gate->revoked)return XW_MODE_DENIED;
 if(!gate->timed||gate->rechecking)return XW_MODE_INVALID;
 if(now<gate->last_poll)return revoked(gate,XW_MODE_FAULT);
 gate->authorized=gate->observed=0;
 gate->last_poll=gate->query_started=now;
 gate->rechecking=gate->client.pending?1u:2u;
 return XW_MODE_PENDING;
}
int wr_owner_admission_poll(struct wr_owner_admission *gate,uint64_t now){
 if(!owner(gate))return XW_MODE_WRONG_OWNER;
 if(gate->closed||gate->revoked)return XW_MODE_DENIED;
 if(!gate->timed){
  if(gate->client.serial||gate->client.pending)return revoked(gate,XW_MODE_INVALID);
  gate->timed=1;gate->last_poll=now;
 }
 if(now<gate->last_poll)return revoked(gate,XW_MODE_FAULT);
 gate->last_poll=now;
 if(gate->rechecking){
  if(now-gate->query_started>=WR_OWNER_OBSERVATION_STALE_MS)return revoked(gate,XW_MODE_FAULT);
  if(!gate->client.pending){
   int rc=wr_owner_admission_refresh(gate);if(rc)return rc;
  }
  int rc=wr_owner_admission_step(gate);
  if(rc)return rc;
  if(gate->rechecking==1){
   /* The earlier reply may have been generated before the blocking call.
    * Its validity permits draining only; a new serial must be acknowledged. */
   gate->authorized=0;gate->rechecking=2;gate->query_started=now;
   rc=wr_owner_admission_refresh(gate);
   return rc?rc:XW_MODE_PENDING;
  }
  gate->rechecking=0;gate->observed=1;gate->observed_at=now;return 0;
 }
 if(gate->observed&&now-gate->observed_at>=WR_OWNER_OBSERVATION_STALE_MS)return revoked(gate,XW_MODE_FAULT);
 if(!gate->client.pending){
  if(gate->observed&&now-gate->observed_at<WR_OWNER_OBSERVATION_REFRESH_MS)return 0;
  int rc=wr_owner_admission_refresh(gate);if(rc)return rc;
  gate->query_started=now;
 }
 if(now-gate->query_started>=WR_OWNER_OBSERVATION_STALE_MS)return revoked(gate,XW_MODE_FAULT);
 int rc=wr_owner_admission_step(gate);
 if(!rc){gate->observed=1;gate->observed_at=now;}
 return rc;
}
int wr_owner_admission_close(struct wr_owner_admission *gate){
 if(!owner(gate))return XW_MODE_WRONG_OWNER;
 if(gate->closed)return 0;
 int rc=xw_mode_client_close(&gate->client);
 gate->authorized=0;gate->revoked=1;
 if(!gate->client.bound)gate->closed=1;
 return rc;
}
