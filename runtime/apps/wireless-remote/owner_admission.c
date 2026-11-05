#include "owner_admission.h"
#include <string.h>
#include <unistd.h>
extern unsigned long pthread_self(void);
static int owner(const struct wr_owner_admission *gate){
 return gate&&gate->client.pid==(int)getpid()&&gate->client.thread==pthread_self();
}
static int revoked(struct wr_owner_admission *gate,int result){
 gate->authorized=0;gate->revoked=1;return result;
}
int wr_owner_admission_open(struct wr_owner_admission *gate,int fd,const struct xw_wireless_lease *expected){
 if(!gate||!expected||gate->client.bound||gate->revoked||gate->closed||
    !expected->generation||!expected->serial||!expected->consumer||expected->mode!=XW_WIRELESS_MODE_ESPNOW)return XW_MODE_INVALID;
 struct xw_mode_client client={0};
 int rc=xw_mode_client_open(&client,fd,expected->generation);if(rc)return rc;
 gate->client=client;gate->expected=*expected;gate->authorized=0;return 0;
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
 gate->authorized=1;return 0;
}
int wr_owner_admission_allowed(const struct wr_owner_admission *gate){
 return owner(gate)&&gate->client.bound&&!gate->client.fault&&!gate->closed&&!gate->revoked&&gate->authorized;
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
 if(gate->observed&&now-gate->observed_at>=1000u)return revoked(gate,XW_MODE_FAULT);
 if(!gate->client.pending){
  if(gate->observed&&now-gate->observed_at<200u)return 0;
  int rc=wr_owner_admission_refresh(gate);if(rc)return rc;
  gate->query_started=now;
 }
 if(now-gate->query_started>=1000u)return revoked(gate,XW_MODE_FAULT);
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
