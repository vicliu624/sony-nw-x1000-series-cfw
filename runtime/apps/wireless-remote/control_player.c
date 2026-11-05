#include "control.h"
#include <string.h>
int wr_control_dispatch(struct wr_control_ledger *l,struct xw_player *p,uint64_t session,const struct wr_control *c,struct wr_control_receipt *out){
 if(!l||!p||!out||!c||!session||c->session!=session||!c->request||c->operation>XW_OP_STEP_VOLUME)return -1;
 if(c->operation==XW_OP_STEP_VOLUME?(c->value!=1&&c->value!=-1):c->operation==XW_OP_SET_VOLUME?(c->value<0||c->value>255):c->value!=0)return -1;
 if(l->have){if(c->session!=l->last.session||c->request<l->last.request)return -1;
  if(c->request==l->last.request){if(c->operation!=l->last.operation||c->value!=l->last.value)return -1;
   *out=(struct wr_control_receipt){session,c->request,l->result};return 0;}}
 struct xw_player_command cmd;memset(&cmd,0,sizeof cmd);cmd.operation=(enum xw_player_operation)c->operation;cmd.value=c->value;
 l->last=*c;l->have=1;l->result=XW_PLAYER_UNCERTAIN;
 l->result=xw_player_command(p,&cmd);*out=(struct wr_control_receipt){session,c->request,l->result};return 0;
}
